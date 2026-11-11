"""Public resolver: GET /r/{id} and POST /r/{id}/verify. Server-rendered, no JavaScript.

The resolver is the only authority for access decisions. A redirect is issued only after
the visit reservation statement has committed.

Run: uvicorn safelinks.resolver:app
"""

from __future__ import annotations

import asyncio
import logging
from html import escape
from urllib.parse import parse_qs

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from . import repository as repo
from .config import settings
from .domain import LinkStatus, derive_status, looks_like_link_id, verify_passcode
from .http import client_ip, create_app, enforce_limit, ip_hash
from .logs import event

log = logging.getLogger("safelinks.resolver")

# No scripts at all; inline styles only. No form-action directive: browsers apply it to the
# redirect that follows a successful passcode POST, which would block the destination.
PAGE_CSP = (
    "default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
    "frame-ancestors 'none'; base-uri 'none'"
)

MARK = (
    '<svg width="28" height="28" viewBox="0 0 32 32" aria-hidden="true">'
    '<path d="M22.43 8.34A10 10 0 1 1 9.57 8.34" fill="none" stroke="#17211F" '
    'stroke-width="3" stroke-linecap="round"/>'
    '<circle cx="22.43" cy="8.34" r="3" fill="#247A58"/></svg>'
)

STYLE = """
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:flex;flex-direction:column;align-items:center;
background:#F7F8F5;color:#17211F;font:15px/1.5 Inter,system-ui,-apple-system,"Segoe UI",
Roboto,sans-serif;padding:48px 16px}
header{display:flex;align-items:center;gap:8px;font-weight:600;font-size:16px;margin-bottom:32px}
header a{color:inherit;text-decoration:none;display:flex;align-items:center;gap:8px}
main{width:100%;max-width:420px;background:#fff;border:1px solid #DCE3DE;border-radius:8px;
padding:28px}
h1{font-size:20px;line-height:1.3;margin:0 0 8px}
p{margin:0 0 16px;color:#66736E}
code{font-family:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px;
background:#F7F8F5;border:1px solid #DCE3DE;border-radius:4px;padding:2px 6px;color:#17211F;
word-break:break-all}
label{display:block;font-weight:500;margin:20px 0 6px}
input{width:100%;height:40px;border:1px solid #DCE3DE;border-radius:6px;padding:0 12px;
font:inherit;background:#fff;color:#17211F}
input[aria-invalid=true]{border-color:#B54242}
.err{color:#B54242;font-size:14px;margin:6px 0 0}
button,.btn{display:inline-flex;align-items:center;justify-content:center;height:40px;
padding:0 16px;border-radius:6px;border:1px solid #247A58;background:#247A58;color:#fff;
font:inherit;font-weight:500;text-decoration:none;cursor:pointer;margin-top:16px;width:100%}
.btn.secondary{background:#fff;color:#17211F;border-color:#DCE3DE}
:focus-visible{outline:2px solid #247A58;outline-offset:2px}
footer{margin-top:24px;font-size:13px;color:#66736E}
footer a{color:#66736E}
"""

MESSAGES = {
    LinkStatus.EXPIRED: ("This link has expired.", 410),
    LinkStatus.EXHAUSTED: ("This link has reached its visit limit.", 410),
    LinkStatus.REVOKED: ("This link is no longer available.", 410),
}


def page(title: str, body: str, status: int) -> HTMLResponse:
    home = escape(settings.frontend_url)
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>{escape(title)} · SafeLinks</title><style>{STYLE}</style></head>
<body><header><a href="{home}">{MARK}<span>SafeLinks</span></a></header>
<main>{body}</main>
<footer><a href="{home}/report">Report abuse</a></footer></body></html>"""
    return HTMLResponse(
        html,
        status_code=status,
        headers={"content-security-policy": PAGE_CSP, "x-robots-tag": "noindex"},
    )


def unavailable(message: str = "This link is no longer available.", status: int = 410):
    home = escape(settings.frontend_url)
    return page(
        message,
        f"<h1>{escape(message)}</h1>"
        "<p>Ask the person who shared it for a new link.</p>"
        f'<a class="btn secondary" href="{home}">Go to SafeLinks</a>',
        status,
    )


def passcode_form(link_id: str, *, error: bool = False) -> HTMLResponse:
    err = '<p class="err" id="pc-err" role="alert">Incorrect passcode.</p>' if error else ""
    invalid = ' aria-invalid="true" aria-describedby="pc-err"' if error else ""
    lid = escape(link_id)
    return page(
        "Passcode required",
        "<h1>Passcode required</h1>"
        f"<p>Enter the passcode for <code>{lid}</code>. "
        "Access limits are enforced when the link is opened.</p>"
        f'<form method="post" action="/r/{lid}/verify">'
        '<label for="passcode">Passcode</label>'
        '<input id="passcode" name="passcode" type="password" autocomplete="off" '
        f'required maxlength="128" autofocus{invalid}>{err}'
        '<button type="submit">Continue</button></form>',
        403 if error else 200,
    )


def render_error(status: int, code: str, message: str) -> Response:
    if status == 404:
        return unavailable(status=404)
    if status == 429:
        return page(
            "Too many attempts",
            "<h1>Too many attempts.</h1><p>Wait a few minutes, then try again.</p>",
            429,
        )
    if status == 503:
        return page(
            "Temporarily unavailable",
            "<h1>SafeLinks is temporarily unavailable.</h1>"
            "<p>Your link was not opened. Try again in a moment.</p>",
            503,
        )
    return page("Something went wrong", "<h1>Something went wrong.</h1>", status)


app = create_app("resolver", render_error=render_error)


def redirect(url: str, status: int) -> RedirectResponse:
    return RedirectResponse(url, status_code=status, headers={"cache-control": "no-store"})


async def explain_refusal(conn, link_id: str) -> Response:
    """After a refused reservation, decide which deliberate response to show."""
    row = await repo.resolver_lookup(conn, link_id)
    if row is None:
        event("resolve_outcome", outcome="not_found")
        return unavailable(status=404)
    if row["owner_status"] != "active":
        event("resolve_outcome", outcome="owner_suspended")
        return unavailable()
    status = derive_status(
        now=row["db_now"],
        expires_at=row["expires_at"],
        clicks=row["clicks"],
        max_clicks=row["max_clicks"],
        revoked_at=row["revoked_at"],
    )
    if status == LinkStatus.ACTIVE and row["passcode_hash"]:
        event("resolve_outcome", outcome="passcode_required")
        return passcode_form(link_id)
    event("resolve_outcome", outcome=str(status))
    message, code = MESSAGES.get(status, ("This link is no longer available.", 410))
    return unavailable(message, code)


@app.get("/r/{link_id}")
async def resolve(link_id: str, request: Request):
    async with request.app.state.pool.acquire() as conn:
        await enforce_limit(
            conn, f"resolve:ip:{ip_hash(client_ip(request))}", settings.rl_resolve_ip
        )
        if not looks_like_link_id(link_id):
            event("resolve_outcome", outcome="not_found")
            return unavailable(status=404)
        url = await repo.reserve_visit(conn, link_id, allow_protected=False)
        if url is not None:
            event("resolve_outcome", outcome="redirect")
            return redirect(url, 302)
        return await explain_refusal(conn, link_id)


async def _form_passcode(request: Request) -> str:
    body = (await request.body()).decode("utf-8", errors="replace")
    return (parse_qs(body, max_num_fields=5).get("passcode") or [""])[0]


@app.post("/r/{link_id}/verify")
async def verify(link_id: str, request: Request):
    ip = ip_hash(client_ip(request))
    candidate = await _form_passcode(request)
    async with request.app.state.pool.acquire() as conn:
        # Every attempt counts, correct or not, so throttling cannot be used as an oracle.
        await enforce_limit(conn, f"passcode:ip:{ip}", settings.rl_passcode_ip)
        if looks_like_link_id(link_id):
            await enforce_limit(conn, f"passcode:link:{link_id}", settings.rl_passcode_link)
            row = await repo.resolver_lookup(conn, link_id)
        else:
            row = None
        stored = row["passcode_hash"] if row else None
        # Always run one Argon2 verification (against a dummy hash when there is nothing
        # to check) so unknown links and wrong passcodes look identical, timing included.
        ok = await asyncio.to_thread(verify_passcode, stored, candidate[:128])
        if not ok:
            event("passcode_attempt", outcome="rejected")
            return passcode_form(link_id, error=True)
        url = await repo.reserve_visit(conn, link_id, allow_protected=True)
        if url is not None:
            event("passcode_attempt", outcome="accepted")
            event("resolve_outcome", outcome="redirect")
            return redirect(url, 303)
        return await explain_refusal(conn, link_id)
