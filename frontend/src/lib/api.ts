// Thin client for the SafeLinks API. Same-origin: nginx (docker) and Vite (dev) proxy /api.
import { authClient } from "./auth";

export type LinkStatus = "active" | "expired" | "exhausted" | "revoked";

export interface Link {
  id: string;
  short_url: string;
  url: string;
  destination_host: string;
  created_at: string;
  expires_at: string;
  max_clicks: number;
  clicks: number;
  remaining_clicks: number;
  status: LinkStatus;
  revoked_at: string | null;
  passcode_protected: boolean;
}

export interface LinkEvent {
  type: string;
  at: string;
  metadata: Record<string, unknown>;
}

export interface LinkPage {
  items: Link[];
  next_cursor: string | null;
}

export interface Me {
  id: string;
  email: string | null;
  status: string;
  limits: { max_ttl_hours: number; max_clicks: number };
}

export type Sort = "created_desc" | "created_asc" | "expires_asc" | "expires_desc";

export class ApiError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const headers: Record<string, string> = { accept: "application/json" };
  if (body !== undefined) headers["content-type"] = "application/json";
  const { data } = await authClient.getSession();
  if (data.session) headers.authorization = `Bearer ${data.session.access_token}`;

  let res: Response;
  try {
    res = await fetch(`/api/v1${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "Could not reach SafeLinks. Check your connection and try again.");
  }
  if (res.status === 204) return undefined as T;
  const json = await res.json().catch(() => null);
  if (!res.ok) {
    throw new ApiError(
      res.status,
      json?.error?.code ?? "HTTP_ERROR",
      json?.error?.message ?? "Something went wrong. Try again.",
    );
  }
  return json as T;
}

export const api = {
  me: () => request<Me>("/me"),
  createLink: (body: { url: string; ttl_hours: number; max_clicks: number; passcode: string | null }) =>
    request<Link>("/links", "POST", body),
  listLinks: (q: { status?: string; search?: string; sort?: Sort; cursor?: string | null }) => {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(q)) if (v) params.set(k, v);
    return request<LinkPage>(`/links?${params}`);
  },
  getLink: (id: string) => request<Link & { events: LinkEvent[] }>(`/links/${encodeURIComponent(id)}`),
  revokeLink: (id: string) => request<Link>(`/links/${encodeURIComponent(id)}/revoke`, "POST"),
  deleteAccount: () => request<void>("/account", "DELETE"),
  report: (body: { link: string; reason: string; details: string | null; email: string | null }) =>
    request<{ status: string }>("/reports", "POST", body),
};

export const errorMessage = (err: unknown) =>
  err instanceof ApiError ? err.message : "Something went wrong. Try again.";
