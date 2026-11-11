import { ArrowLeft } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link as RouterLink, useParams } from "react-router";
import { ConfirmAction, CopyButton, Notice, Spinner, StatusBadge, inputClass, useTitle } from "../components";
import { api, ApiError, errorMessage, type Link, type LinkEvent } from "../lib/api";
import { formatDateTime, fromNow, visits } from "../lib/format";

type Detail = Link & { events: LinkEvent[] };

const EVENT_LABEL: Record<string, string> = {
  created: "Link created",
  visit: "Successful visit",
  revoked: "Revoked",
};

function statusSentence(link: Link) {
  switch (link.status) {
    case "expired":
      return "This link has expired.";
    case "exhausted":
      return "This link has reached its visit limit.";
    case "revoked":
      return `This link was revoked on ${formatDateTime(link.revoked_at ?? link.expires_at)}.`;
    default:
      return `This link is active. It expires ${fromNow(link.expires_at)}.`;
  }
}

export default function LinkDetail() {
  const { id = "" } = useParams();
  useTitle(`Link ${id}`);
  const [link, setLink] = useState<Detail | null>(null);
  const [error, setError] = useState<{ notFound: boolean; message: string } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLink(await api.getLink(id));
      setError(null);
    } catch (err) {
      setError({ notFound: err instanceof ApiError && err.status === 404, message: errorMessage(err) });
    }
  }, [id]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch on mount / id change
    void load();
  }, [load]);

  const back = (
    <RouterLink to="/links" className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink">
      <ArrowLeft aria-hidden className="size-4" />
      All links
    </RouterLink>
  );

  if (error)
    return (
      <div className="space-y-4">
        {back}
        {error.notFound ? (
          <>
            <h1 className="text-2xl font-semibold">Link not found.</h1>
            <p className="text-sm text-muted">It may have been deleted after its retention period.</p>
          </>
        ) : (
          <Notice>{error.message}</Notice>
        )}
      </div>
    );
  if (!link) return <Spinner label="Loading link" />;

  const pct = Math.min(100, (link.clicks / link.max_clicks) * 100);
  const rows: [string, React.ReactNode][] = [
    ["Destination", <span className="font-mono text-xs break-all">{link.url}</span>],
    ["Host", link.destination_host],
    ["Created", formatDateTime(link.created_at)],
    ["Expires", `${formatDateTime(link.expires_at)} (${fromNow(link.expires_at)})`],
    ["Visit limit", visits(link.max_clicks)],
    ["Passcode", link.passcode_protected ? "Required before redirect" : "Not required"],
  ];

  return (
    <article aria-labelledby="detail-title" className="space-y-6">
      {back}
      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 id="detail-title" className="font-mono text-xl font-medium break-all">
            {link.id}
          </h1>
          <StatusBadge status={link.status} />
        </div>
        <p className="text-sm text-muted">{statusSentence(link)}</p>
      </header>

      {notice && <Notice tone="success">{notice}</Notice>}

      {link.status === "active" && (
        <div className="flex flex-col gap-2 sm:flex-row">
          <label htmlFor="detail-url" className="sr-only">
            Short link
          </label>
          <input id="detail-url" readOnly value={link.short_url} className={`${inputClass} font-mono`} />
          <CopyButton text={link.short_url} label="Copy short link" />
        </div>
      )}

      <section aria-labelledby="usage-title" className="space-y-2 rounded-lg border border-line bg-surface p-4">
        <h2 id="usage-title" className="text-sm font-medium">
          Usage
        </h2>
        <p className="text-sm">
          {link.clicks} of {link.max_clicks} visits used
          {link.status === "active" && ` · ${link.remaining_clicks} remaining`}
        </p>
        <div aria-hidden className="h-2 overflow-hidden rounded-full bg-ink/5">
          <div className="h-full rounded-full bg-signal" style={{ width: `${pct}%` }} />
        </div>
      </section>

      <dl className="divide-y divide-line rounded-lg border border-line bg-surface text-sm">
        {rows.map(([term, value]) => (
          <div key={term} className="grid gap-1 px-4 py-3 sm:grid-cols-[9rem_1fr]">
            <dt className="text-muted">{term}</dt>
            <dd className="min-w-0">{value}</dd>
          </div>
        ))}
      </dl>

      <section aria-labelledby="events-title" className="space-y-3">
        <h2 id="events-title" className="text-sm font-medium">
          Activity
        </h2>
        {link.events.length === 0 ? (
          <p className="text-sm text-muted">No activity recorded.</p>
        ) : (
          <ol className="space-y-2 text-sm">
            {link.events.map((ev, i) => (
              <li key={i} className="flex flex-wrap justify-between gap-2 border-b border-line pb-2">
                <span>{EVENT_LABEL[ev.type] ?? ev.type}</span>
                <time dateTime={ev.at} className="text-muted">
                  {formatDateTime(ev.at)}
                </time>
              </li>
            ))}
          </ol>
        )}
      </section>

      {link.status === "active" && (
        <ConfirmAction
          label="Revoke link"
          prompt="Revoke this link? Recipients will no longer be able to open it."
          confirmLabel="Revoke link"
          onConfirm={async () => {
            await api.revokeLink(link.id);
            await load();
            setNotice("Link revoked.");
          }}
        />
      )}
    </article>
  );
}
