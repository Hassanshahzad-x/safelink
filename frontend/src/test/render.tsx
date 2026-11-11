import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { vi } from "vitest";
import App from "../App";
import type { Link } from "../lib/api";
import { AuthProvider } from "../lib/auth";

export function renderApp(path = "/") {
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  return user;
}

/** Stub fetch with a queue of [status, body] responses; returns the mock for call assertions. */
export function mockFetch(...responses: [number, unknown][]) {
  const fn = vi.fn(async () => {
    const [status, body] = responses.length > 1 ? responses.shift()! : responses[0]!;
    return new Response(status === 204 ? null : JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

export const link = (over: Partial<Link> = {}): Link => ({
  id: "AbCdEfGhIjKlMnOpQrStUv",
  short_url: "http://localhost:8001/r/AbCdEfGhIjKlMnOpQrStUv",
  url: "https://example.com/doc",
  destination_host: "example.com",
  created_at: new Date().toISOString(),
  expires_at: new Date(Date.now() + 24 * 3600_000).toISOString(),
  max_clicks: 1,
  clicks: 0,
  remaining_clicks: 1,
  status: "active",
  revoked_at: null,
  passcode_protected: false,
  ...over,
});
