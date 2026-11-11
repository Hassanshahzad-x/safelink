import type { Link } from "./api";

const dateTime = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });
const relative = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

export const formatDateTime = (iso: string) => dateTime.format(new Date(iso));

export function fromNow(iso: string, now = Date.now()) {
  const seconds = (new Date(iso).getTime() - now) / 1000;
  const abs = Math.abs(seconds);
  const [value, unit]: [number, Intl.RelativeTimeFormatUnit] =
    abs < 3600
      ? [Math.round(seconds / 60), "minute"]
      : abs < 86400
        ? [Math.round(seconds / 3600), "hour"]
        : [Math.round(seconds / 86400), "day"];
  return relative.format(value, unit);
}

export const visits = (n: number) => `${n} successful visit${n === 1 ? "" : "s"}`;

export const TTL_OPTIONS: [hours: number, label: string][] = [
  [1, "1 hour"],
  [6, "6 hours"],
  [24, "24 hours"],
  [72, "3 days"],
  [168, "7 days"],
  [720, "30 days"],
];

export const ttlLabel = (hours: number) =>
  TTL_OPTIONS.find(([h]) => h === hours)?.[1] ?? `${hours} hours`;

/** One line describing where a link is in its lifecycle. */
export function lifecycleText(link: Link, now = Date.now()) {
  switch (link.status) {
    case "revoked":
      return `Revoked ${formatDateTime(link.revoked_at ?? link.expires_at)}`;
    case "expired":
      return `Expired ${fromNow(link.expires_at, now)}`;
    case "exhausted":
      return "Visit limit reached";
    default:
      return `Expires ${fromNow(link.expires_at, now)}`;
  }
}

export const expiresSoon = (link: Link, now = Date.now()) =>
  link.status === "active" && new Date(link.expires_at).getTime() - now < 3600_000;
