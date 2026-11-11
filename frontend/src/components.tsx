import { AlertTriangle, Check, CheckCircle2, Copy, LoaderCircle } from "lucide-react";
import { useEffect, useId, useRef, useState, type ComponentProps, type ReactNode } from "react";
import { errorMessage, type Link, type LinkStatus } from "./lib/api";
import { expiresSoon, formatDateTime, fromNow, lifecycleText, visits } from "./lib/format";

export function useTitle(title: string) {
  useEffect(() => {
    document.title = `${title} · SafeLinks`;
  }, [title]);
}

export function Logo({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 text-base font-semibold tracking-tight ${className}`}>
      <svg viewBox="0 0 32 32" aria-hidden="true" className="size-6">
        <path
          d="M22.43 8.34A10 10 0 1 1 9.57 8.34"
          fill="none"
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
        />
        <circle cx="22.43" cy="8.34" r="3" fill="var(--color-signal)" />
      </svg>
      SafeLinks
    </span>
  );
}

const variants = {
  primary: "border-transparent bg-signal text-white hover:bg-signal-dark",
  secondary: "border-line bg-surface text-ink hover:border-muted",
  danger: "border-transparent bg-danger text-white hover:brightness-95",
  ghost: "border-transparent bg-transparent text-ink hover:bg-ink/5",
};

export const buttonClass = (variant: keyof typeof variants = "primary") =>
  `inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-md border px-4 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${variants[variant]}`;

export function Button({
  variant = "primary",
  loading = false,
  className = "",
  disabled,
  children,
  ...rest
}: ComponentProps<"button"> & { variant?: keyof typeof variants; loading?: boolean }) {
  return (
    <button
      type="button"
      className={`${buttonClass(variant)} ${className}`}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading && <LoaderCircle aria-hidden className="size-4 motion-safe:animate-spin" />}
      {children}
    </button>
  );
}

export const inputClass =
  "h-10 w-full min-w-0 rounded-md border border-line bg-surface px-3 text-sm placeholder:text-muted/70 aria-[invalid=true]:border-danger";

type ControlProps = { id: string; "aria-invalid"?: true; "aria-describedby"?: string };

/** Label + control + hint + inline error, wired together for assistive tech. */
export function Field({
  label,
  hint,
  error,
  children,
}: {
  label: ReactNode;
  hint?: ReactNode;
  error?: string;
  children: (props: ControlProps) => ReactNode;
}) {
  const id = useId();
  const describedBy = [hint && `${id}-hint`, error && `${id}-error`].filter(Boolean).join(" ");
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium">
        {label}
      </label>
      {children({
        id,
        "aria-invalid": error ? true : undefined,
        "aria-describedby": describedBy || undefined,
      })}
      {error && (
        <p id={`${id}-error`} className="flex items-start gap-1.5 text-sm text-danger">
          <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0" />
          {error}
        </p>
      )}
      {hint && (
        <p id={`${id}-hint`} className="text-xs text-muted">
          {hint}
        </p>
      )}
    </div>
  );
}

export function Notice({ tone = "error", children }: { tone?: "error" | "success"; children: ReactNode }) {
  const error = tone === "error";
  return (
    <div
      role={error ? "alert" : "status"}
      className={`flex items-start gap-2 rounded-md border px-3 py-2.5 text-sm ${
        error ? "border-danger/30 bg-danger-soft text-danger" : "border-signal/30 bg-signal-soft text-signal-dark"
      }`}
    >
      {error ? (
        <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0" />
      ) : (
        <CheckCircle2 aria-hidden className="mt-0.5 size-4 shrink-0" />
      )}
      <div>{children}</div>
    </div>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <p role="status" className="flex items-center gap-2 py-8 text-sm text-muted">
      <LoaderCircle aria-hidden className="size-4 motion-safe:animate-spin" />
      {label}…
    </p>
  );
}

const STATUS: Record<LinkStatus, [label: string, className: string]> = {
  active: ["Active", "bg-signal-soft text-signal-dark"],
  expired: ["Expired", "bg-ink/5 text-muted"],
  exhausted: ["Visit limit reached", "bg-ink/5 text-muted"],
  revoked: ["Revoked", "bg-danger-soft text-danger"],
};

export function StatusBadge({ status }: { status: LinkStatus }) {
  const [label, className] = STATUS[status];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${className}`}>
      <span aria-hidden className="size-1.5 rounded-full bg-current" />
      {label}
    </span>
  );
}

export function CopyButton({ text, label }: { text: string; label?: string }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  const timer = useRef<number>(undefined);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setState("copied");
    } catch {
      setState("failed");
    }
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setState("idle"), 2500);
  }

  return (
    <>
      <Button variant="secondary" onClick={copy} aria-label={label}>
        {state === "copied" ? (
          <Check aria-hidden className="size-4 text-signal" />
        ) : (
          <Copy aria-hidden className="size-4" />
        )}
        {state === "copied" ? "Copied" : state === "failed" ? "Copy failed" : "Copy"}
      </Button>
      <span role="status" className="sr-only">
        {state === "copied"
          ? "Link copied to clipboard."
          : state === "failed"
            ? "Could not copy. Select the link and copy it manually."
            : ""}
      </span>
    </>
  );
}

/** Destructive action with an inline confirmation step. Escape cancels. */
export function ConfirmAction({
  label,
  prompt,
  confirmLabel,
  onConfirm,
}: {
  label: string;
  prompt: string;
  confirmLabel: string;
  onConfirm: () => Promise<void>;
}) {
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const wasAsking = useRef(false);

  useEffect(() => {
    if (asking) confirmRef.current?.focus();
    else if (wasAsking.current) triggerRef.current?.focus();
    wasAsking.current = asking;
  }, [asking]);

  if (!asking) {
    return (
      <Button ref={triggerRef} variant="secondary" className="text-danger" onClick={() => setAsking(true)}>
        {label}
      </Button>
    );
  }
  return (
    <div
      role="group"
      aria-label={prompt}
      className="flex flex-wrap items-center gap-2"
      onKeyDown={(e) => e.key === "Escape" && !busy && setAsking(false)}
    >
      <span className="text-sm">{prompt}</span>
      <Button
        ref={confirmRef}
        variant="danger"
        loading={busy}
        onClick={async () => {
          setBusy(true);
          setError(null);
          try {
            await onConfirm();
            setAsking(false);
          } catch (err) {
            setError(errorMessage(err));
          } finally {
            setBusy(false);
          }
        }}
      >
        {confirmLabel}
      </Button>
      <Button variant="ghost" disabled={busy} onClick={() => setAsking(false)}>
        Cancel
      </Button>
      {error && (
        <p role="alert" className="basis-full text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

/** Policy summary shared by the success state and the detail page. */
export function PolicySummary({ link, showUrl = false }: { link: Link; showUrl?: boolean }) {
  const rows: [string, ReactNode][] = [
    ["Destination", showUrl ? <span className="font-mono text-xs break-all">{link.url}</span> : link.destination_host],
    [
      "Expires",
      <>
        {formatDateTime(link.expires_at)}{" "}
        <span className={expiresSoon(link) ? "text-amber" : "text-muted"}>({fromNow(link.expires_at)})</span>
      </>,
    ],
    ["Visit limit", `Available for ${visits(link.max_clicks)}`],
    [
      "Usage",
      link.status === "active"
        ? `${link.clicks} used · ${link.remaining_clicks} remaining`
        : `${link.clicks} used · ${lifecycleText(link)}`,
    ],
    ["Passcode", link.passcode_protected ? "Required before redirect" : "Not required"],
    ["Created", formatDateTime(link.created_at)],
  ];
  return (
    <dl className="divide-y divide-line rounded-lg border border-line bg-surface text-sm">
      {rows.map(([term, value]) => (
        <div key={term} className="grid gap-1 px-4 py-3 sm:grid-cols-[9rem_1fr]">
          <dt className="text-muted">{term}</dt>
          <dd className="min-w-0">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
