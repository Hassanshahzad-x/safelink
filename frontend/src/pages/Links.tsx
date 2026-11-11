import { Lock, Plus, Search } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link as RouterLink, useSearchParams } from "react-router";
import {
  Button,
  ConfirmAction,
  CopyButton,
  Notice,
  Spinner,
  StatusBadge,
  buttonClass,
  inputClass,
  useTitle,
} from "../components";
import { api, errorMessage, type Link, type Sort } from "../lib/api";
import { expiresSoon, formatDateTime, lifecycleText } from "../lib/format";

const STATUSES = [
  ["", "All statuses"],
  ["active", "Active"],
  ["expired", "Expired"],
  ["exhausted", "Visit limit reached"],
  ["revoked", "Revoked"],
] as const;

const SORTS: [Sort, string][] = [
  ["created_desc", "Newest first"],
  ["created_asc", "Oldest first"],
  ["expires_asc", "Expires soonest"],
  ["expires_desc", "Expires latest"],
];

export function LinkRow({ link, onRevoked }: { link: Link; onRevoked: (l: Link) => void }) {
  const active = link.status === "active";
  return (
    <li
      className={`grid gap-3 px-4 py-4 transition-opacity sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center ${
        link.status === "revoked" ? "opacity-75" : ""
      }`}
    >
      <div className="min-w-0 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <RouterLink to={`/links/${link.id}`} className="font-mono text-sm font-medium hover:underline">
            {link.id}
          </RouterLink>
          <StatusBadge status={link.status} />
          {link.passcode_protected && (
            <span className="inline-flex items-center gap-1 text-xs text-muted">
              <Lock aria-hidden className="size-3" />
              Passcode
            </span>
          )}
        </div>
        <p className="truncate text-sm">{link.destination_host}</p>
        <p className="text-xs text-muted">
          {link.clicks} of {link.max_clicks} visits used
          {active && ` · ${link.remaining_clicks} left`}
          {" · "}
          <span className={expiresSoon(link) ? "text-amber" : undefined}>{lifecycleText(link)}</span>
          {" · Created "}
          {formatDateTime(link.created_at)}
        </p>
      </div>
      {active && (
        <div className="flex flex-wrap items-center gap-2">
          <CopyButton text={link.short_url} label={`Copy link ${link.id}`} />
          <ConfirmAction
            label="Revoke"
            prompt="Revoke this link? Recipients will no longer be able to open it."
            confirmLabel="Revoke link"
            onConfirm={async () => onRevoked(await api.revokeLink(link.id))}
          />
        </div>
      )}
    </li>
  );
}

export default function Links() {
  useTitle("Your links");
  const [params, setParams] = useSearchParams();
  const status = params.get("status") ?? "";
  const sort = (params.get("sort") as Sort | null) ?? "created_desc";
  const q = params.get("q") ?? "";
  const [search, setSearch] = useState(q);
  const [items, setItems] = useState<Link[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const requestId = useRef(0);

  const update = useCallback(
    (key: string, value: string) =>
      setParams(
        (p) => {
          if (value) p.set(key, value);
          else p.delete(key);
          return p;
        },
        { replace: true },
      ),
    [setParams],
  );

  // Debounce search typing into the URL.
  useEffect(() => {
    if (search === q) return;
    const t = window.setTimeout(() => update("q", search.trim()), 300);
    return () => window.clearTimeout(t);
  }, [search, q, update]);

  const load = useCallback(async () => {
    const id = ++requestId.current;
    setLoading(true);
    setError(null);
    try {
      const page = await api.listLinks({ status, search: q, sort });
      if (id !== requestId.current) return;
      setItems(page.items);
      setCursor(page.next_cursor);
    } catch (err) {
      if (id === requestId.current) setError(errorMessage(err));
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, [status, q, sort]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetching on filter change is the point
    void load();
  }, [load]);

  async function loadMore() {
    if (!cursor) return;
    const id = requestId.current;
    setLoadingMore(true);
    try {
      const page = await api.listLinks({ status, search: q, sort, cursor });
      if (id !== requestId.current) return;
      setItems((prev) => [...prev, ...page.items]);
      setCursor(page.next_cursor);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoadingMore(false);
    }
  }

  const filtered = Boolean(status || q);

  return (
    <section aria-labelledby="links-title" className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 id="links-title" className="text-2xl font-semibold">
          Your links
        </h1>
        <RouterLink to="/" className={buttonClass()}>
          <Plus aria-hidden className="size-4" />
          Create link
        </RouterLink>
      </div>

      <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_12rem_12rem]" role="search">
        <div className="relative">
          <Search aria-hidden className="pointer-events-none absolute top-3 left-3 size-4 text-muted" />
          <label htmlFor="link-search" className="sr-only">
            Search by destination or link ID
          </label>
          <input
            id="link-search"
            type="search"
            maxLength={200}
            placeholder="Search by destination or link ID"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className={`${inputClass} pl-9`}
          />
        </div>
        <label className="sr-only" htmlFor="status-filter">
          Status
        </label>
        <select
          id="status-filter"
          value={status}
          onChange={(e) => update("status", e.target.value)}
          className={inputClass}
        >
          {STATUSES.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <label className="sr-only" htmlFor="sort">
          Sort
        </label>
        <select id="sort" value={sort} onChange={(e) => update("sort", e.target.value)} className={inputClass}>
          {SORTS.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>

      {notice && <Notice tone="success">{notice}</Notice>}

      {loading ? (
        <Spinner label="Loading links" />
      ) : error && items.length === 0 ? (
        <div className="space-y-3">
          <Notice>{error}</Notice>
          <Button variant="secondary" onClick={() => void load()}>
            Try again
          </Button>
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-lg border border-dashed border-line bg-surface px-6 py-12 text-center">
          {filtered ? (
            <>
              <p className="font-medium">No links match these filters.</p>
              <Button
                variant="ghost"
                className="mt-3"
                onClick={() => {
                  setSearch("");
                  setParams({}, { replace: true });
                }}
              >
                Clear filters
              </Button>
            </>
          ) : (
            <>
              <p className="font-medium">No links yet.</p>
              <p className="mt-1 text-sm text-muted">Create a link with an expiry and a visit limit.</p>
              <RouterLink to="/" className={`${buttonClass()} mt-4`}>
                Create link
              </RouterLink>
            </>
          )}
        </div>
      ) : (
        <>
          <ul className="divide-y divide-line rounded-lg border border-line bg-surface">
            {items.map((link) => (
              <LinkRow
                key={link.id}
                link={link}
                onRevoked={(updated) => {
                  setItems((prev) => prev.map((l) => (l.id === updated.id ? updated : l)));
                  setNotice("Link revoked.");
                }}
              />
            ))}
          </ul>
          {error && <Notice>{error}</Notice>}
          {cursor && (
            <div className="flex justify-center">
              <Button variant="secondary" loading={loadingMore} onClick={loadMore}>
                Load more
              </Button>
            </div>
          )}
        </>
      )}
    </section>
  );
}
