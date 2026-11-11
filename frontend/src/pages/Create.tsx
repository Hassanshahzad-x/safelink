import { Ban, Clock, MousePointerClick } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { flushSync } from "react-dom";
import { Link as RouterLink, useLocation, useNavigate } from "react-router";
import { Button, CopyButton, Field, Notice, PolicySummary, StatusBadge, inputClass, useTitle } from "../components";
import { api, ApiError, errorMessage, type Link } from "../lib/api";
import { useAuth } from "../lib/auth";
import { TTL_OPTIONS, ttlLabel, visits } from "../lib/format";

export interface Draft {
  url: string;
  ttl_hours: number;
  max_clicks: string;
  passcodeOn: boolean;
  passcode: string;
}

type FieldName = "url" | "ttl" | "max_clicks" | "passcode";
type Errors = Partial<Record<FieldName | "form", string>>;

const EMPTY: Draft = { url: "", ttl_hours: 24, max_clicks: "1", passcodeOn: false, passcode: "" };
const MAX_CLICKS = 1000;

const FIELD_FOR_CODE: Record<string, FieldName> = {
  INVALID_URL: "url",
  INVALID_TTL: "ttl",
  INVALID_MAX_CLICKS: "max_clicks",
  INVALID_PASSCODE: "passcode",
};

export function validate(d: Draft): Errors {
  const errors: Errors = {};
  const url = d.url.trim();
  if (!url) errors.url = "Enter the URL you want to share.";
  else {
    let parsed: URL | null = null;
    try {
      parsed = new URL(url);
    } catch {
      /* handled below */
    }
    if (!parsed || !["http:", "https:"].includes(parsed.protocol) || !parsed.hostname)
      errors.url = "Enter a full web address starting with https:// or http://.";
    else if (parsed.username || parsed.password) errors.url = "Remove the username or password from the URL.";
  }
  const n = Number(d.max_clicks);
  if (!/^\d+$/.test(d.max_clicks.trim()) || n < 1 || n > MAX_CLICKS)
    errors.max_clicks = `Enter a whole number from 1 to ${MAX_CLICKS}.`;
  if (d.passcodeOn && (d.passcode.length < 4 || d.passcode.length > 128))
    errors.passcode = "Use 4 to 128 characters.";
  return errors;
}

const policySentence = (d: Draft) => {
  const n = Number(d.max_clicks);
  const uses = Number.isInteger(n) && n >= 1 ? ` Available for ${visits(n)}.` : "";
  return `This link expires in ${ttlLabel(d.ttl_hours)}.${uses}`;
};

export default function Create() {
  useTitle("Create link");
  const { session } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const restored = (location.state as { draft?: Draft } | null)?.draft;
  const [draft, setDraft] = useState<Draft>(restored ?? EMPTY);
  const [errors, setErrors] = useState<Errors>({});
  const [pending, setPending] = useState(false);
  const [created, setCreated] = useState<Link | null>(null);
  const inFlight = useRef(false);
  const formRef = useRef<HTMLFormElement>(null);
  const successRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (created) successRef.current?.focus();
  }, [created]);

  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((d) => ({ ...d, [key]: value }));

  function showErrors(next: Errors) {
    flushSync(() => setErrors(next));
    formRef.current?.querySelector<HTMLElement>("[aria-invalid=true]")?.focus();
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (inFlight.current) return;
    const found = validate(draft);
    if (Object.keys(found).length) return showErrors(found);
    if (!session) {
      // Never put the passcode into history state.
      navigate("/signin", { state: { from: "/", draft: { ...draft, passcode: "" } } });
      return;
    }
    inFlight.current = true;
    setPending(true);
    setErrors({});
    try {
      const link = await api.createLink({
        url: draft.url.trim(),
        ttl_hours: draft.ttl_hours,
        max_clicks: Number(draft.max_clicks),
        passcode: draft.passcodeOn ? draft.passcode : null,
      });
      setCreated(link);
      setDraft(EMPTY);
    } catch (err) {
      const field = err instanceof ApiError ? FIELD_FOR_CODE[err.code] : undefined;
      showErrors(field ? { [field]: errorMessage(err) } : { form: errorMessage(err) });
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  }

  if (created) {
    return (
      <section className="mx-auto max-w-2xl space-y-6" aria-labelledby="success-title">
        <div className="space-y-2">
          <h1 id="success-title" ref={successRef} tabIndex={-1} className="text-2xl font-semibold outline-none">
            Your link is ready.
          </h1>
          <p className="text-sm text-muted">Access limits are enforced when the link is opened.</p>
        </div>
        <div className="space-y-3 rounded-lg border border-line bg-surface p-4">
          <label htmlFor="short-url" className="block text-sm font-medium">
            Short link
          </label>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              id="short-url"
              readOnly
              value={created.short_url}
              onFocus={(e) => e.currentTarget.select()}
              className={`${inputClass} font-mono`}
            />
            <CopyButton text={created.short_url} label="Copy short link" />
          </div>
          <StatusBadge status={created.status} />
        </div>
        <PolicySummary link={created} />
        <div className="flex flex-wrap gap-3">
          <Button onClick={() => setCreated(null)}>Create another link</Button>
          <RouterLink
            to={`/links/${created.id}`}
            className="inline-flex h-10 items-center rounded-md px-3 text-sm font-medium text-signal hover:underline"
          >
            View details
          </RouterLink>
        </div>
      </section>
    );
  }

  return (
    <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_18rem]">
      <section aria-labelledby="create-title" className="space-y-6">
        <div className="space-y-2">
          <h1 id="create-title" className="text-3xl font-semibold tracking-tight">
            Share links with an expiry.
          </h1>
          <p className="text-muted">Set how long a link works and how many times it can be used.</p>
        </div>

        <form ref={formRef} noValidate onSubmit={submit} className="space-y-5 rounded-lg border border-line bg-surface p-5">
          {errors.form && <Notice>{errors.form}</Notice>}
          <Field label="Destination URL" error={errors.url}>
            {(p) => (
              <input
                {...p}
                type="url"
                inputMode="url"
                autoComplete="url"
                placeholder="https://example.com/document"
                value={draft.url}
                onChange={(e) => set("url", e.target.value)}
                className={inputClass}
              />
            )}
          </Field>
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Expires after" error={errors.ttl}>
              {(p) => (
                <select
                  {...p}
                  value={draft.ttl_hours}
                  onChange={(e) => set("ttl_hours", Number(e.target.value))}
                  className={inputClass}
                >
                  {TTL_OPTIONS.map(([hours, label]) => (
                    <option key={hours} value={hours}>
                      {label}
                    </option>
                  ))}
                </select>
              )}
            </Field>
            <Field label="Maximum visits" hint={`1 to ${MAX_CLICKS}`} error={errors.max_clicks}>
              {(p) => (
                <input
                  {...p}
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={MAX_CLICKS}
                  step={1}
                  value={draft.max_clicks}
                  onChange={(e) => set("max_clicks", e.target.value)}
                  className={inputClass}
                />
              )}
            </Field>
          </div>
          <div className="space-y-3">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={draft.passcodeOn}
                onChange={(e) => set("passcodeOn", e.target.checked)}
                className="size-4 accent-signal"
              />
              Require a passcode
            </label>
            {draft.passcodeOn && (
              <Field label="Passcode" hint="Share it separately from the link." error={errors.passcode}>
                {(p) => (
                  <input
                    {...p}
                    type="password"
                    autoComplete="new-password"
                    value={draft.passcode}
                    onChange={(e) => set("passcode", e.target.value)}
                    className={inputClass}
                  />
                )}
              </Field>
            )}
          </div>
          <p className="rounded-md bg-paper px-3 py-2 text-sm" aria-live="polite">
            {policySentence(draft)}
          </p>
          <Button type="submit" loading={pending} className="w-full sm:w-auto">
            Create link
          </Button>
          {!session && <p className="text-xs text-muted">You will be asked to sign in before the link is created.</p>}
        </form>
      </section>

      <aside aria-labelledby="how-title" className="space-y-4 text-sm">
        <h2 id="how-title" className="font-medium">
          How it works
        </h2>
        <ul className="space-y-3 text-muted">
          <li className="flex gap-3">
            <Clock aria-hidden className="mt-0.5 size-4 shrink-0 text-signal" />
            The link stops working at the expiry time.
          </li>
          <li className="flex gap-3">
            <MousePointerClick aria-hidden className="mt-0.5 size-4 shrink-0 text-signal" />
            Each successful visit counts toward the limit, even under heavy traffic.
          </li>
          <li className="flex gap-3">
            <Ban aria-hidden className="mt-0.5 size-4 shrink-0 text-signal" />
            You can revoke a link at any time.
          </li>
        </ul>
        <p className="border-t border-line pt-4 text-xs text-muted">
          SafeLinks controls access to the short link. It cannot stop recipients from copying or saving what the
          destination shows them.
        </p>
      </aside>
    </div>
  );
}
