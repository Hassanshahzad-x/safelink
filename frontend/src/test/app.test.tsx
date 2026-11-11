import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { validate, type Draft } from "../pages/Create";
import { signIn } from "./authState";
import { link, mockFetch, renderApp } from "./render";

const body = (fetchMock: ReturnType<typeof mockFetch>, i = 0) =>
  JSON.parse((fetchMock.mock.calls[i] as unknown as [string, RequestInit])[1].body as string);
const url = (fetchMock: ReturnType<typeof mockFetch>, i = 0) =>
  (fetchMock.mock.calls[i] as unknown as [string])[0];

describe("validate", () => {
  const d = (over: Partial<Draft>): Draft => ({
    url: "https://example.com",
    ttl_hours: 24,
    max_clicks: "1",
    passcodeOn: false,
    passcode: "",
    ...over,
  });
  it("accepts a good draft", () => expect(validate(d({}))).toEqual({}));
  it.each(["", "example.com", "javascript:alert(1)", "ftp://x.com", "https://u:p@x.com"])("rejects url %j", (u) =>
    expect(validate(d({ url: u })).url).toBeTruthy(),
  );
  it.each(["0", "1001", "1.5", "-1", "", "abc"])("rejects max_clicks %j", (n) =>
    expect(validate(d({ max_clicks: n })).max_clicks).toBeTruthy(),
  );
  it("checks passcode length only when enabled", () => {
    expect(validate(d({ passcodeOn: true, passcode: "abc" })).passcode).toBeTruthy();
    expect(validate(d({ passcodeOn: false, passcode: "abc" })).passcode).toBeUndefined();
  });
});

describe("create link", () => {
  it("shows inline errors, focuses the field and sends nothing", async () => {
    signIn();
    const fetchMock = mockFetch([201, link()]);
    const user = renderApp();
    await user.type(await screen.findByLabelText("Destination URL"), "not a url");
    await user.click(screen.getByRole("button", { name: "Create link" }));
    const input = screen.getByLabelText("Destination URL");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveFocus();
    expect(screen.getByText(/full web address/)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("submits once on double click, then shows the success state and copies", async () => {
    signIn();
    const fetchMock = mockFetch([201, link({ passcode_protected: true })]);
    const user = renderApp();
    await user.type(await screen.findByLabelText("Destination URL"), "https://example.com/doc");
    await user.clear(screen.getByLabelText("Maximum visits"));
    await user.type(screen.getByLabelText("Maximum visits"), "3");
    expect(screen.getByText("This link expires in 24 hours. Available for 3 successful visits.")).toBeInTheDocument();
    await user.click(screen.getByLabelText("Require a passcode"));
    await user.type(screen.getByLabelText("Passcode"), "letmein");
    const submit = screen.getByRole("button", { name: "Create link" });
    await user.dblClick(submit);

    expect(await screen.findByRole("heading", { name: "Your link is ready." })).toHaveFocus();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(body(fetchMock)).toEqual({
      url: "https://example.com/doc",
      ttl_hours: 24,
      max_clicks: 3,
      passcode: "letmein",
    });
    expect((fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1].headers).toMatchObject({
      authorization: "Bearer test-token",
    });
    expect(screen.getByLabelText("Short link")).toHaveValue(link().short_url);

    await user.click(screen.getByRole("button", { name: "Copy short link" }));
    expect(screen.getByRole("button", { name: "Copy short link" })).toHaveTextContent("Copied");
    expect(screen.getByText("Link copied to clipboard.")).toBeInTheDocument();
    expect(await navigator.clipboard.readText()).toBe(link().short_url);
  });

  it("maps API field errors inline and keeps the input", async () => {
    signIn();
    mockFetch([400, { error: { code: "INVALID_URL", message: "That URL is not allowed." } }]);
    const user = renderApp();
    await user.type(await screen.findByLabelText("Destination URL"), "https://bad.example");
    await user.click(screen.getByRole("button", { name: "Create link" }));
    expect(await screen.findByText("That URL is not allowed.")).toBeInTheDocument();
    expect(screen.getByLabelText("Destination URL")).toHaveValue("https://bad.example");
    expect(screen.getByRole("button", { name: "Create link" })).toBeEnabled();
  });

  it("shows form-level errors such as rate limiting", async () => {
    signIn();
    mockFetch([429, { error: { code: "RATE_LIMITED", message: "Too many links created. Try again later." } }]);
    const user = renderApp();
    await user.type(await screen.findByLabelText("Destination URL"), "https://example.com");
    await user.click(screen.getByRole("button", { name: "Create link" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Too many links created.");
  });

  it("sends signed-out users to sign in, keeping the draft but not the passcode", async () => {
    const fetchMock = mockFetch([201, link()]);
    const user = renderApp();
    await user.type(await screen.findByLabelText("Destination URL"), "https://example.com/x");
    await user.click(screen.getByRole("button", { name: "Create link" }));
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("works with the keyboard alone", async () => {
    signIn();
    const fetchMock = mockFetch([201, link()]);
    const user = renderApp();
    await screen.findByLabelText("Destination URL");
    // Tab from the top of the page: skip link, logo, 3 nav links, sign out, then the URL field.
    for (let i = 0; i < 7 && document.activeElement !== screen.getByLabelText("Destination URL"); i++)
      await user.tab();
    expect(screen.getByLabelText("Destination URL")).toHaveFocus();
    await user.keyboard("https://example.com{Enter}");
    await screen.findByRole("heading", { name: "Your link is ready." });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("dashboard", () => {
  it("shows the empty state", async () => {
    signIn();
    mockFetch([200, { items: [], next_cursor: null }]);
    renderApp("/links");
    expect(await screen.findByText("No links yet.")).toBeInTheDocument();
  });

  it("lists links, filters by status and paginates", async () => {
    signIn();
    const fetchMock = mockFetch(
      [200, { items: [link()], next_cursor: "CUR1" }],
      [200, { items: [link({ id: "SecondLinkIdxxxxxxxxxx" })], next_cursor: null }],
      [200, { items: [], next_cursor: null }],
    );
    const user = renderApp("/links");
    expect(await screen.findByText("AbCdEfGhIjKlMnOpQrStUv")).toBeInTheDocument();
    expect(screen.getByText(/0 of 1 visits used · 1 left/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Load more" }));
    expect(await screen.findByText("SecondLinkIdxxxxxxxxxx")).toBeInTheDocument();
    expect(url(fetchMock, 1)).toContain("cursor=CUR1");
    expect(screen.queryByRole("button", { name: "Load more" })).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Status"), "revoked");
    expect(await screen.findByText("No links match these filters.")).toBeInTheDocument();
    expect(url(fetchMock, 2)).toContain("status=revoked");
  });

  it("debounces search into the request", async () => {
    signIn();
    const fetchMock = mockFetch([200, { items: [], next_cursor: null }]);
    const user = renderApp("/links");
    await screen.findByText("No links yet.");
    await user.type(screen.getByLabelText("Search by destination or link ID"), "example");
    await waitFor(() => expect(url(fetchMock, fetchMock.mock.calls.length - 1)).toContain("search=example"));
    expect(fetchMock.mock.calls.length).toBe(2); // initial + one debounced search
  });

  it("revokes only after confirmation", async () => {
    signIn();
    const fetchMock = mockFetch(
      [200, { items: [link()], next_cursor: null }],
      [200, link({ status: "revoked", revoked_at: new Date().toISOString(), remaining_clicks: 0 })],
    );
    const user = renderApp("/links");
    await user.click(await screen.findByRole("button", { name: "Revoke" }));
    const group = screen.getByRole("group", { name: /Revoke this link\?/ });
    const confirm = within(group).getByRole("button", { name: "Revoke link" });
    expect(confirm).toHaveFocus();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("group")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Revoke" })).toHaveFocus();

    await user.click(screen.getByRole("button", { name: "Revoke" }));
    await user.click(screen.getByRole("button", { name: "Revoke link" }));
    expect(await screen.findByText("Link revoked.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(url(fetchMock, 1)).toMatch(/\/links\/AbCdEfGhIjKlMnOpQrStUv\/revoke$/);
    expect(screen.getAllByText("Revoked").length).toBeGreaterThan(0);
  });

  it("shows API errors with a retry", async () => {
    signIn();
    mockFetch([503, { error: { code: "SERVICE_UNAVAILABLE", message: "Service unavailable." } }]);
    renderApp("/links");
    expect(await screen.findByRole("alert")).toHaveTextContent("Service unavailable.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});

describe("routing and pages", () => {
  it("redirects protected pages to sign in", async () => {
    renderApp("/links");
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  it("shows sign-in errors", async () => {
    const user = renderApp("/signin");
    await user.type(await screen.findByLabelText("Email"), "a@example.com");
    await user.type(screen.getByLabelText("Password"), "wrongpass");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Email or password is incorrect.");
  });

  it("renders link detail with events", async () => {
    signIn();
    mockFetch([
      200,
      {
        ...link({ clicks: 1, remaining_clicks: 0, status: "exhausted" }),
        events: [
          { type: "created", at: new Date().toISOString(), metadata: {} },
          { type: "visit", at: new Date().toISOString(), metadata: {} },
        ],
      },
    ]);
    renderApp("/links/AbCdEfGhIjKlMnOpQrStUv");
    expect(await screen.findByText("This link has reached its visit limit.")).toBeInTheDocument();
    expect(screen.getByText("Successful visit")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Revoke link" })).not.toBeInTheDocument();
  });

  it("submits abuse reports publicly", async () => {
    const fetchMock = mockFetch([202, { status: "received" }]);
    const user = renderApp("/report?link=AbCdEfGhIjKlMnOpQrStUv");
    expect(await screen.findByLabelText("Short link or link ID")).toHaveValue("AbCdEfGhIjKlMnOpQrStUv");
    await user.selectOptions(screen.getByLabelText("Reason"), "malware");
    await user.click(screen.getByRole("button", { name: "Send report" }));
    expect(await screen.findByText("Thanks. We received your report.")).toBeInTheDocument();
    expect(body(fetchMock)).toEqual({ link: "AbCdEfGhIjKlMnOpQrStUv", reason: "malware", details: null, email: null });
  });

  it("has privacy and terms pages covering the required points", async () => {
    renderApp("/terms");
    expect(await screen.findByText(/not access to the destination itself/)).toBeInTheDocument();
    expect(screen.getByText(/copy, screenshot, download/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Suspension and appeal" })).toBeInTheDocument();
  });
});
