# SafeLinks

## Product Requirements Document (PRD)

**Version:** 1.0\
**Status:** Proposed\
**Date:** November 11, 2026\
**Product type:** Secure, policy-controlled link sharing\
**Primary goal:** Turn the existing self-destructing URL shortener into
a dependable, differentiated product that demonstrates strong product
thinking, backend engineering, security, and operational maturity.

------------------------------------------------------------------------

## 1. Executive summary

SafeLinks lets someone share a URL with explicit access limits. A link
can expire after a defined time, after a maximum number of successful
visits, or when its owner revokes it. The recipient gets a simple
redirect experience; the creator gets clear control over the link's
lifecycle.

The existing project already has the essential foundation:

-   A React frontend.
-   A Python creator service.
-   A Python resolver service.
-   A Python cleanup function.
-   Google Cloud Datastore shared by the backend services.
-   Time-based and click-based expiration.

The next version should not become a generic URL shortener with dozens
of features. It should become a focused **controlled-sharing tool** that
makes temporary access predictable, secure, and easy to understand.

The product should be differentiated by doing a small number of
important things exceptionally well:

1.  **Reliable access enforcement:** expiry and click limits must remain
    correct under concurrent traffic.
2.  **Immediate control:** owners can revoke a link at any time and see
    its current state.
3.  **Safer sharing:** optional passcode protection, abuse controls, and
    clear destination information.
4.  **Useful lifecycle visibility:** owners can see whether a link is
    active, expired, exhausted, or revoked, and understand its usage
    without invasive tracking.
5.  **Operational trust:** automated cleanup, observability, tested
    deployment, and clear failure handling.

The product should feel like a polished security utility, not a
feature-heavy SaaS dashboard.

------------------------------------------------------------------------

## 2. Product vision

### Vision statement

**Make temporary access to any URL simple to create, safe to share, and
reliable to control.**

### Positioning

SafeLinks is a controlled link-sharing service for people who need to
share a destination temporarily without leaving access open
indefinitely.

It is not trying to compete as a high-volume marketing URL shortener.
Its value is the access policy attached to each link.

### Product promise

A link should behave exactly as its owner configured it:

-   It works only while active.
-   It never exceeds its successful-use limit.
-   It can be revoked before its natural expiry.
-   Optional protection is enforced before the destination is revealed.
-   Its owner can understand its status without guessing.

### Product principles

1.  **Correctness before features.** A click limit that can be bypassed
    is worse than having no click limit.
2.  **Privacy by default.** Collect only the data needed to operate the
    product and explain link usage.
3.  **Simple recipient experience.** Opening a link should not require
    an account.
4.  **Owner control.** Creation, visibility, and revocation should be
    straightforward.
5.  **Honest product behavior.** The interface must never promise
    protection that the backend does not enforce.
6.  **Small, coherent scope.** Every feature must strengthen controlled
    sharing.

------------------------------------------------------------------------

## 3. Problem statement

Ordinary URL shorteners primarily make URLs shorter and easier to share.
They generally do not make access lifecycle guarantees the central
product experience.

People sharing temporary resources face several problems:

-   A shared URL may remain accessible long after it is useful.
-   A one-time link may be opened by multiple people if requests arrive
    together.
-   A creator may have no simple way to revoke an already-shared link.
-   Passwords and access limits are often separate or awkward to manage.
-   The owner may not know whether a link is still active, expired,
    exhausted, or revoked.
-   Public link creation endpoints can be abused if they lack rate
    limits and abuse controls.
-   Cleanup jobs may fail silently, leaving unnecessary records behind.

SafeLinks should solve these problems without requiring recipients to
register or install anything.

------------------------------------------------------------------------

## 4. Goals and non-goals

### 4.1 Product goals

  -----------------------------------------------------------------------
  ID                      Goal                    Success condition
  ----------------------- ----------------------- -----------------------
  G1                      Enforce access policies No successful redirect
                          reliably                beyond the configured
                                                  time or usage limit

  G2                      Give owners lifecycle   Owners can inspect and
                          control                 revoke their links

  G3                      Improve sharing         Optional passcode
                          security                protection and abuse
                                                  controls are enforced
                                                  server-side

  G4                      Make link behavior      Clear status, expiry,
                          understandable          remaining-use
                                                  information, and
                                                  recipient error states

  G5                      Operate reliably in     Automated tests,
                          production              structured logs,
                                                  monitoring, and
                                                  scheduled cleanup

  G6                      Keep the product        The primary workflow
                          focused                 remains quick and
                                                  uncluttered
  -----------------------------------------------------------------------

### 4.2 Non-goals for the initial release

The first production-grade release will not include:

-   A general-purpose marketing campaign platform.
-   UTM builder or advanced attribution.
-   QR-code campaigns.
-   Team workspaces and complex role hierarchies.
-   Enterprise SSO or SCIM.
-   Browser extensions.
-   Native mobile applications.
-   AI-generated summaries or AI-based link recommendations.
-   A public API marketplace.
-   Arbitrary file hosting or file uploads.
-   Link previews that fetch arbitrary destination pages.
-   Guaranteed prevention of screenshots, copying, or redistribution
    after a recipient has accessed the destination.

These may be considered later only if user evidence supports them.

------------------------------------------------------------------------

## 5. Target users and primary use cases

### 5.1 Target users

**Individuals sharing temporary resources**\
People who need to share a document, private resource, or destination
for a limited period.

**Freelancers and consultants**\
People sharing client resources, previews, proposals, or temporary
deliverables.

**Small teams**\
Teams that need lightweight, controlled sharing without adopting a
complex document-management platform.

**Developers and technical users**\
Users who want predictable link policies and a simple API for temporary
access workflows.

### 5.2 Core use cases

1.  Create a link that works for one successful visit.
2.  Create a link that works for a fixed number of successful visits.
3.  Create a link that expires after a selected duration.
4.  Protect a link with a passcode.
5.  Revoke a link immediately after sharing it.
6.  Review active and inactive links.
7.  Understand why a recipient cannot access a link.
8.  Integrate link creation into another workflow through a documented
    API.

### 5.3 Primary user journey

1.  User opens SafeLinks.
2.  User pastes a valid HTTP or HTTPS URL.
3.  User configures expiry and maximum successful visits.
4.  User optionally enables passcode protection.
5.  User creates the link.
6.  SafeLinks displays the short URL and its policy summary.
7.  User copies and shares the URL.
8.  Recipient opens the URL.
9.  Resolver checks the link's state and policy.
10. If permitted, the visit is atomically recorded and the recipient is
    redirected.
11. If access is not permitted, the recipient sees a clear, branded
    status page.
12. Owner can inspect or revoke the link from the dashboard.

------------------------------------------------------------------------

## 6. Product scope and prioritization

Use the following priority definitions:

-   **P0:** Required for the first production-grade release.
-   **P1:** Important follow-up after P0 is stable.
-   **P2:** Optional future enhancement.

  -----------------------------------------------------------------------
  Capability              Priority                Rationale
  ----------------------- ----------------------- -----------------------
  Atomic click-limit      P0                      Core product guarantee
  enforcement                                     

  Link lifecycle state    P0                      Prevent ambiguous
  model                                           behavior

  Owner accounts and      P0                      Required for private
  authentication                                  link management

  Link dashboard and      P0                      Gives owners control
  status visibility                               

  Manual revocation       P0                      Essential lifecycle
                                                  control

  Rate limiting and abuse P0                      Protects public
  protection                                      services

  Passcode-protected      P1                      Meaningful security
  links                                           enhancement

  Scheduled cleanup and   P0                      Operational hygiene
  retention                                       

  Production WSGI server  P0                      Deployment readiness

  Automated tests and CI  P0                      Prevent regressions

  Structured logs and     P0                      Operational visibility
  monitoring                                      

  Custom aliases          P2                      Convenience, not core
                                                  differentiation

  Advanced analytics      P2                      Avoid invasive tracking

  Team workspaces         P2                      Adds authorization
                                                  complexity

  Billing and paid plans  P2                      Validate usage before
                                                  monetization
  -----------------------------------------------------------------------

**Scope rule:** Do not add a feature simply because competing URL
shorteners offer it. Add it only when it strengthens controlled sharing
or addresses a validated user problem.

------------------------------------------------------------------------

## 7. Functional requirements

### 7.1 Link creation

**Description:** A user creates a short link with explicit access
limits.

**Requirements**

-   Accept only absolute `http` and `https` URLs.
-   Reject missing hosts, malformed URLs, unsupported schemes, and
    invalid ports.
-   Normalize and validate input without silently changing the intended
    destination.
-   Require a positive integer expiry duration.
-   Require a positive integer maximum successful-visit count.
-   Enforce configurable maximum values to prevent unreasonable
    retention or usage.
-   Generate IDs using a cryptographically secure random generator.
-   Persist the link and its owner association.
-   Return the generated short URL and a policy summary.
-   Never expose internal database keys or secrets.
-   Apply per-user and per-IP creation limits.
-   Return consistent JSON errors with stable machine-readable error
    codes.

**Acceptance criteria**

-   Valid requests create one unique link.
-   Invalid URLs and invalid policy values return HTTP 400.
-   A duplicate ID collision is safely retried.
-   The returned URL resolves through the configured resolver domain.
-   A failed database write never returns a successful short URL.
-   The user sees the configured expiry and usage limit after creation.

### 7.2 Link policy and lifecycle

Each link must have an explicit lifecycle state.

Recommended states:

  State         Meaning
  ------------- ----------------------------------------------------------
  `active`      Link can be accessed if all policy checks pass
  `expired`     Current time is at or beyond `expires_at`
  `exhausted`   Successful visits have reached `max_clicks`
  `revoked`     Owner or authorized system action explicitly disabled it

The effective state may be derived from timestamps and counters, but
revocation must be persisted.

**Rules**

-   A link is not valid at or after its expiry timestamp.
-   A link is not valid when successful visits are equal to or greater
    than the configured maximum.
-   A revoked link is never valid, regardless of remaining time or
    visits.
-   The resolver must be the authority for access decisions.
-   Frontend state is informational and must never determine access.
-   State transitions must be deterministic and testable.
-   Expired and exhausted links may be retained for a configurable
    period before deletion.

**Acceptance criteria**

-   Every invalid state produces a predictable recipient response.
-   The resolver never redirects an invalid link.
-   Revocation takes effect on the next access attempt after the
    revocation write succeeds.
-   Dashboard state agrees with resolver behavior.

### 7.3 Atomic successful-visit enforcement

**Description:** Ensure the maximum-use policy cannot be exceeded under
concurrent requests.

This is the most important backend requirement.

The current read-then-write implementation is unsafe. Replace it with a
transaction or another datastore-supported atomic conditional update.

**Required behavior**

Within one atomic operation:

1.  Read the link.
2.  Verify it exists.
3.  Verify it is not revoked.
4.  Verify current time is before expiry.
5.  Verify successful visits are below the maximum.
6.  Increment the successful-visit counter.
7.  Commit the update.
8.  Redirect only after the commit succeeds.

If the transaction cannot commit because another request changed the
record, retry safely according to the datastore client's transaction
behavior. After retries, re-read and return the correct unavailable
response.

**Important details**

-   A visit counts only when the resolver has successfully
    reserved/recorded access.
-   Failed, malformed, missing, expired, exhausted, and revoked requests
    do not increment the counter.
-   The system must define the counter as an accepted redirect
    authorization, not proof that the destination fully loaded.
-   A transaction failure must never be treated as permission to
    redirect.
-   Do not perform external network calls inside a datastore
    transaction.

**Acceptance criteria**

-   With `max_clicks = 1`, many concurrent requests produce exactly one
    successful redirect.
-   With `max_clicks = N`, no more than N requests receive redirect
    authorization.
-   Counter values never exceed `max_clicks`.
-   Tests cover transaction retries and contention.

### 7.4 Link dashboard

**Description:** Authenticated users can view and manage their own
links.

**Requirements**

-   Show links created by the authenticated user only.
-   Display destination hostname, creation date, expiry date, click
    count, maximum visits, and lifecycle state.
-   Display remaining visits for active links.
-   Support search by destination hostname or short-link ID.
-   Support filtering by active, expired, exhausted, and revoked.
-   Support sorting by creation date and expiry date.
-   Provide a copy action.
-   Provide a revoke action with confirmation.
-   Provide an empty state that explains how to create the first link.
-   Provide pagination or cursor-based loading.
-   Do not reveal another user's links through API parameters or guessed
    IDs.

**Acceptance criteria**

-   A user cannot view, revoke, or modify another user's link.
-   Dashboard values come from the backend.
-   Revoked links are clearly distinguishable from naturally expired
    links.
-   Copying a link does not change its policy.

### 7.5 Manual revocation

**Description:** Owners can invalidate a link immediately.

**Requirements**

-   Provide an authenticated revoke endpoint.
-   Verify ownership before revocation.
-   Persist the revoked state and timestamp.
-   Make repeated revocation requests idempotent.
-   Return a consistent response if the link is already revoked.
-   Do not physically delete the record during revocation.
-   Record the revocation event for auditability.

**Acceptance criteria**

-   A revoked link returns the unavailable response on its next request.
-   Repeated requests do not create duplicate state transitions.
-   Unauthorized users cannot revoke the link.
-   Revocation remains effective even if the link has unused visits and
    time remaining.

### 7.6 Passcode protection

**Priority:** P1, after authentication and lifecycle correctness.

**Description:** A creator can require a passcode before redirecting a
recipient.

**Requirements**

-   Passcode is optional at creation.
-   Store only a secure password hash, never plaintext.
-   Use a password-hashing algorithm designed for secrets, such as
    Argon2id, with appropriate parameters.
-   Never return the hash through an API.
-   Require the recipient to submit the passcode through a branded
    interstitial page.
-   Do not consume a successful visit for an incorrect passcode.
-   Apply per-link and per-IP attempt throttling.
-   Avoid revealing whether a passcode is correct through materially
    different error behavior or timing.
-   Do not put passcodes in query parameters or URLs.
-   The resolver must validate the passcode server-side before reserving
    a successful visit.

**Acceptance criteria**

-   A protected link cannot redirect without a valid passcode.
-   Incorrect passcodes do not increment the successful-visit count.
-   Passcodes are not present in logs, analytics, URLs, or API
    responses.
-   Brute-force attempts are throttled.

### 7.7 Recipient experience

**Description:** Make the destination and link status understandable
without exposing unnecessary information.

**Requirements**

-   Valid unprotected links redirect using HTTP 302.
-   Protected links show a passcode screen before redirecting.
-   Unknown, expired, exhausted, and revoked links display a branded
    unavailable page.
-   Do not reveal the original destination for invalid links.
-   Do not expose database details, stack traces, or internal service
    names.
-   Include a clear message and a way to return to the SafeLinks
    homepage.
-   Avoid misleading wording such as "one-time secure" unless the actual
    policy supports it.

**Acceptance criteria**

-   Every resolver outcome has a deliberate response.
-   Recipient pages work on mobile and desktop.
-   The experience does not depend on JavaScript for basic server-side
    access enforcement.

### 7.8 Cleanup and retention

**Description:** Remove records that are no longer needed without making
cleanup part of the redirect path.

**Requirements**

-   Configure a scheduled invocation of the remover.
-   Cleanup must delete only records that meet the retention policy.
-   Use paginated/batched queries rather than loading the entire
    collection into memory.
-   Make cleanup idempotent.
-   Log processed, deleted, skipped, and failed record counts.
-   Handle partial failures without losing track of remaining work.
-   Define retention separately for expired, exhausted, and revoked
    links.
-   Never rely on cleanup to enforce link expiration; the resolver
    enforces expiration on every request.

**Acceptance criteria**

-   A scheduled job runs automatically in the deployed environment.
-   Cleanup can be run manually by an authorized operator.
-   Large collections are processed in bounded batches.
-   Re-running cleanup is safe.
-   Failures are visible through logs and monitoring.

### 7.9 API behavior and errors

All API responses must use consistent status codes and error structures.

Recommended error shape:

``` json
{
  "error": {
    "code": "LINK_EXPIRED",
    "message": "This link is no longer available."
  }
}
```

Do not expose exception text or internal infrastructure details.

Suggested response mapping:

  Situation                                                                    HTTP status
  ------------------------------------- --------------------------------------------------
  Successful link creation                                                             201
  Successful dashboard query                                                           200
  Successful revocation                                                                200
  Invalid request body                                                                 400
  Missing authentication                                                               401
  Authenticated but not authorized                                                     403
  Unknown link                            404 or a privacy-preserving unavailable response
  Expired, exhausted, or revoked link                                                  410
  Rate limit exceeded                                                                  429
  Unexpected server failure                                                            500
  Temporary dependency failure                                                         503

The public resolver may intentionally use the same recipient-facing
unavailable page for unknown, expired, exhausted, and revoked links to
avoid disclosing link state.

------------------------------------------------------------------------

## 8. Security and abuse prevention

Security is a core product requirement, not a later polish task.

### 8.1 Authentication and authorization

-   Add a proven authentication solution rather than implementing
    password authentication from scratch.
-   Verify authentication on every private API request.
-   Enforce ownership in backend queries and mutations.
-   Never trust a user ID supplied by the client.
-   Keep resolver access public; recipients should not need accounts.
-   Keep creator, dashboard, and revoke permissions separate.
-   Use secure, HttpOnly, SameSite cookies if cookie-based sessions are
    used.
-   Protect cookie-authenticated mutations against CSRF.
-   Apply strict session expiry and revocation behavior.

The implementation should choose an authentication provider compatible
with the existing stack and deployment constraints. Do not commit
provider secrets.

### 8.2 Rate limiting

Apply limits at multiple levels:

-   IP-based limits for anonymous resolver traffic.
-   IP-based limits for sign-up and authentication attempts.
-   User-based limits for link creation.
-   Per-link limits for passcode attempts.
-   Global service limits to protect infrastructure.

Use a shared rate-limit store or a suitable managed edge/service
capability. In-memory counters are not sufficient across multiple Cloud
Run instances.

Return HTTP 429 with a retry hint where appropriate.

### 8.3 URL safety and redirect abuse

SafeLinks is an open redirect service by design: it redirects to
user-provided destinations. That creates abuse risk.

Requirements:

-   Accept only HTTP and HTTPS.
-   Reject `javascript:`, `data:`, `file:`, and other non-web schemes.
-   Reject malformed and hostless URLs.
-   Normalize hostnames consistently.
-   Do not fetch the destination URL during link creation.
-   Do not generate previews by requesting arbitrary destinations.
-   Do not follow destination redirects on the server.
-   Display the destination hostname to the creator before sharing.
-   Provide an abuse-reporting path.
-   Add controls to suspend abusive accounts and links.
-   Consider domain reputation or blocklists only as a later,
    evidence-driven enhancement.

### 8.4 CORS and HTTP security

-   Replace wildcard CORS with the production frontend origin and
    explicit local development origins.
-   Do not treat CORS as authentication.
-   Use HTTPS in production.
-   Configure appropriate security headers on the frontend.
-   Avoid exposing detailed errors in production.
-   Set request size limits.
-   Validate content types and JSON structure.
-   Keep secrets in the deployment platform's secret manager or
    equivalent.

### 8.5 Data protection and privacy

-   Store only data required to operate the service.
-   Do not store recipient IP addresses indefinitely.
-   If IPs are needed for rate limiting or abuse investigation, apply a
    short retention period and document the purpose.
-   Do not add invasive recipient fingerprinting.
-   Do not log full destination URLs if they may contain tokens or
    private query parameters.
-   Redact secrets and passcodes from logs.
-   Define account deletion and data-retention behavior.
-   Provide a clear privacy policy before public launch.

------------------------------------------------------------------------

## 9. Data model

The implementation should inspect the current repository and migration
constraints before changing the schema. The following is the target
logical model, not a mandate to adopt a particular database product.

### 9.1 Link entity

  -----------------------------------------------------------------------
  Field                   Type                    Description
  ----------------------- ----------------------- -----------------------
  `id`                    string                  Cryptographically
                                                  random public
                                                  identifier

  `owner_id`              string                  Authenticated owner

  `original_url`          string                  Destination URL

  `destination_host`      string                  Normalized hostname for
                                                  safe display and search

  `created_at`            datetime UTC            Creation timestamp

  `expires_at`            datetime UTC            Expiry timestamp

  `max_clicks`            integer                 Maximum successful
                                                  visits

  `clicks`                integer                 Successfully reserved
                                                  visits

  `status`                string                  Active, revoked,
                                                  expired, or exhausted

  `revoked_at`            datetime nullable       Revocation timestamp

  `passcode_hash`         string nullable         Secure hash when
                                                  passcode protection is
                                                  enabled

  `updated_at`            datetime UTC            Last mutation timestamp

  `deleted_at`            datetime nullable       Optional soft-delete
                                                  timestamp, if required
                                                  by retention policy
  -----------------------------------------------------------------------

### 9.2 Account entity

Use the authentication provider's canonical user identifier.

  Field          Type           Description
  -------------- -------------- ------------------------------------------
  `id`           string         Provider user ID
  `created_at`   datetime UTC   Account creation timestamp
  `status`       string         Active or suspended
  `plan`         string         Internal plan identifier, initially free

Avoid duplicating credentials managed by the authentication provider.

### 9.3 Audit event entity

Keep audit events focused and privacy-conscious.

  Field          Type              Description
  -------------- ----------------- ------------------------------------------
  `id`           string            Event identifier
  `link_id`      string            Related link
  `owner_id`     string nullable   Actor, when applicable
  `event_type`   string            Created, revoked, passcode enabled, etc.
  `created_at`   datetime UTC      Event timestamp
  `metadata`     object            Minimal non-sensitive event details

Do not store passcodes, authentication tokens, or full sensitive
destination URLs in event metadata.

### 9.4 Data access and indexing

-   Add indexes required for owner-scoped listing and cleanup.
-   Verify all required composite indexes in deployment.
-   Use cursor pagination.
-   Avoid unbounded collection scans.
-   Keep datastore access in a shared repository/data-access layer.
-   Keep business rules out of route handlers.
-   Ensure all mutations that enforce a policy use transactions or
    atomic conditional operations.

------------------------------------------------------------------------

## 10. API specification

The existing API should be evolved without breaking the basic short-link
resolution contract unnecessarily.

Base URLs should come from environment configuration.

### 10.1 Create a link

`POST /api/v1/links`

Authentication: required.

Request:

``` json
{
  "url": "https://example.com/report.pdf",
  "ttl_hours": 24,
  "max_clicks": 1,
  "passcode": null
}
```

Success: `201 Created`

``` json
{
  "id": "opaque-public-id",
  "short_url": "https://safe.example/r/opaque-public-id",
  "expires_at": "2026-11-12T00:00:00Z",
  "max_clicks": 1,
  "clicks": 0,
  "status": "active"
}
```

### 10.2 List owned links

`GET /api/v1/links`

Authentication: required.

Supported query parameters:

-   `status`
-   `search`
-   `limit`
-   `cursor`
-   `sort`

Success: `200 OK`.

Return only links belonging to the authenticated user.

### 10.3 Get link details

`GET /api/v1/links/{id}`

Authentication: required.

Return the policy and lifecycle information for an owned link.

### 10.4 Revoke a link

`POST /api/v1/links/{id}/revoke`

Authentication: required.

Success: `200 OK`.

``` json
{
  "id": "opaque-public-id",
  "status": "revoked",
  "revoked_at": "2026-11-11T12:00:00Z"
}
```

### 10.5 Resolve a link

`GET /r/{short_id}`

Authentication: not required.

Behavior:

-   Validate link state.
-   Atomically reserve a successful visit.
-   Redirect with HTTP 302 if permitted.
-   Show a passcode interstitial when protection is enabled.
-   Return a branded unavailable response when access is denied.

### 10.6 Verify passcode

`POST /r/{short_id}/verify`

Authentication: not required.

Only needed if passcode protection is included in the release.

The endpoint must not expose whether a link exists through unnecessarily
distinct responses.

### 10.7 Health checks

Provide appropriate health endpoints for deployed services.

-   Liveness should indicate whether the process is alive.
-   Readiness should indicate whether the service can handle requests.
-   Do not expose secrets, configuration values, or infrastructure
    details.

### 10.8 Cleanup trigger

Keep the cleanup trigger private and authorized for the scheduler or
operator. It must not be a publicly callable unauthenticated deletion
endpoint.

------------------------------------------------------------------------

## 11. UX and interface requirements

### 11.1 Overall experience

The interface should feel calm, deliberate, and trustworthy. Avoid the
visual language of generic AI-generated SaaS templates.

The product's main interaction is creating a controlled link. The
interface should make that action obvious without filling the page with
cards, gradients, or decorative dashboards.

### 11.2 Required screens

1.  **Landing / create screen**
    -   URL input.
    -   Expiry selector.
    -   Maximum successful visits.
    -   Optional passcode control when implemented.
    -   Create button.
    -   Short explanation of how the policy works.
2.  **Creation success state**
    -   Generated short URL.
    -   Copy action.
    -   Destination hostname.
    -   Expiry date and time.
    -   Maximum visits.
    -   Clear indication that the link is active.
3.  **Dashboard**
    -   Link list.
    -   Search and status filters.
    -   Usage and expiry information.
    -   Copy and revoke actions.
4.  **Link detail**
    -   Full policy summary.
    -   Current lifecycle state.
    -   Usage count and remaining visits.
    -   Created and expiry timestamps.
    -   Revocation action.
5.  **Recipient passcode screen**
    -   Short-link identity.
    -   Passcode field.
    -   Submit action.
    -   Clear invalid-passcode message.
6.  **Recipient unavailable screen**
    -   Clear explanation that the link is no longer available.
    -   No original destination disclosure.
    -   Return-home action.
7.  **Authentication screens**
    -   Sign in.
    -   Sign up.
    -   Sign out.
    -   Password recovery if supported by the selected provider.

### 11.3 Interaction details

-   Show loading states for all network operations.
-   Disable duplicate submissions while creation is pending.
-   Keep errors next to the relevant control.
-   Preserve valid form input after recoverable failures.
-   Confirm destructive actions such as revocation.
-   Make copy feedback accessible and visible.
-   Ensure keyboard navigation and visible focus states.
-   Use semantic HTML and accessible labels.
-   Support narrow mobile screens without horizontal overflow.
-   Respect reduced-motion preferences.

### 11.4 UX language

Prefer direct, specific language.

Examples:

-   "This link expires in 24 hours."
-   "Available for 1 successful visit."
-   "Link revoked."
-   "This link has expired."
-   "This link has reached its visit limit."

Avoid vague claims such as "military-grade security", "unhackable", or
"complete privacy".

------------------------------------------------------------------------

## 12. Brand kit and visual direction

### 12.1 Brand foundation

**Name:** SafeLinks\
**Category:** Controlled link sharing\
**Brand idea:** Access with an expiration point.\
**Personality:** Precise, calm, discreet, dependable.\
**Voice:** Direct, helpful, technically credible.

SafeLinks should look like a focused security utility. It should not
look like a generic AI startup landing page.

### 12.2 Visual concept

Use a visual language inspired by access-control systems, document
utilities, and well-designed developer tools.

The visual identity should communicate:

-   A link with a defined lifecycle.
-   Control over who can access a destination and for how long.
-   Clear system states.
-   Confidence without fear-based security messaging.

A restrained link/loop/endpoint symbol can serve as the core mark. Avoid
literal padlock clichés unless they are simplified enough to feel
distinctive.

### 12.3 Color palette

  Token               Suggested value   Use
  ------------------- ----------------- --------------------------------------
  Ink                 `#17211F`         Primary text and dark surfaces
  Paper               `#F7F8F5`         Main background
  Surface             `#FFFFFF`         Cards and input surfaces
  Muted               `#66736E`         Secondary text
  Border              `#DCE3DE`         Dividers and outlines
  Signal Green        `#247A58`         Primary action and active state
  Signal Green Soft   `#E7F2EC`         Subtle success surfaces
  Amber               `#A96A18`         Expiring-soon warnings
  Red                 `#B54242`         Revoked, errors, destructive actions
  Deep Surface        `#202B28`         Optional dark theme surface

Use color to communicate state, not as decoration. Maintain accessible
contrast.

### 12.4 Typography

Suggested type system:

-   **Primary UI font:** Inter or a comparable neutral sans-serif.
-   **Monospaced text:** IBM Plex Mono for IDs, short URLs, and
    technical metadata.
-   Use a restrained type scale.
-   Avoid oversized marketing typography inside the application.
-   Keep body text readable and compact.

### 12.5 Layout and components

-   Use a consistent spacing scale based on 4px increments.
-   Prefer clear alignment and generous whitespace over excessive cards.
-   Use subtle borders rather than heavy shadows.
-   Use small, purposeful status indicators.
-   Keep primary actions visually distinct.
-   Use consistent input heights and button sizes.
-   Keep tables readable and responsive.
-   Avoid glassmorphism, neon gradients, floating blobs, excessive blur,
    and decorative 3D objects.

### 12.6 Iconography

Use one consistent line-icon family. Icons must clarify an action or
state.

Suggested concepts:

-   Link
-   Clock
-   Mouse pointer or cursor
-   Shield
-   Copy
-   Ban
-   Check
-   Alert triangle
-   External link

Avoid mixing emoji, filled icons, and unrelated icon styles in the core
UI.

### 12.7 Motion

Motion should communicate state changes:

-   Small confirmation feedback after copying.
-   Subtle loading indicator during creation.
-   Clear transition when a link is revoked.
-   No continuous decorative animations.
-   Respect reduced-motion settings.

### 12.8 Brand voice examples

  -----------------------------------------------------------------------
  Context                             Preferred copy
  ----------------------------------- -----------------------------------
  Main heading                        "Share links with an expiry."

  Supporting copy                     "Set how long a link works and how
                                      many times it can be used."

  Create action                       "Create link"

  Success                             "Your link is ready."

  Expired                             "This link has expired."

  Exhausted                           "This link has reached its visit
                                      limit."

  Revoked                             "This link is no longer available."

  Security note                       "Access limits are enforced when
                                      the link is opened."
  -----------------------------------------------------------------------

### 12.9 Brand assets to deliver

-   Primary logo.
-   Compact symbol.
-   Light and dark logo variants.
-   Favicon.
-   App icon.
-   Color and typography tokens.
-   Button, input, status, and table component styles.
-   A small set of product illustrations only if they explain a real
    interaction.

Do not generate decorative assets just to fill empty space.

------------------------------------------------------------------------

## 13. Technical architecture and engineering requirements

### 13.1 Preserve useful existing architecture

The existing three-part backend separation is reasonable for this
product:

-   Creator handles creation and owner-facing link operations.
-   Resolver handles public access decisions and redirects.
-   Remover handles asynchronous cleanup.

Do not rewrite the architecture solely to adopt a fashionable framework.
First inspect the repository, identify the current deployment
constraints, and preserve working components where practical.

The implementation may consolidate services if repository inspection
demonstrates that doing so materially improves reliability or
maintainability. Any consolidation must preserve clear separation
between public resolution, authenticated management, and maintenance
work.

### 13.2 Backend requirements

-   Keep Python 3.11 compatibility unless repository constraints justify
    an upgrade.
-   Use Flask application factories or an equivalent clean application
    structure.
-   Run production services using Gunicorn or another production WSGI
    server.
-   Keep route handlers thin.
-   Put business rules in service modules.
-   Put datastore operations in repositories/data-access modules.
-   Share validation and domain logic where appropriate.
-   Use typed request/response structures where practical.
-   Centralize error handling.
-   Use UTC-aware datetimes.
-   Make configuration environment-driven.
-   Do not commit credentials or service-account keys.

### 13.3 Datastore requirements

-   Preserve the current Google Cloud Datastore-compatible data layer
    unless a documented technical reason supports migration.
-   Use transactions for click reservation and other policy-sensitive
    mutations.
-   Add required indexes.
-   Use bounded pagination for listing and cleanup.
-   Avoid full-collection scans in normal application requests.
-   Define transaction retry behavior.
-   Handle missing entities and transient datastore errors explicitly.

### 13.4 Frontend requirements

-   Retain React and Vite unless repository inspection reveals a
    concrete limitation.
-   Use reusable components for forms, statuses, tables, and feedback.
-   Keep API calls in a dedicated client/service layer.
-   Keep authentication state and route protection predictable.
-   Handle loading, empty, success, and error states.
-   Avoid unnecessary global state libraries.
-   Remove unused dependencies after verifying they are not required.
-   Keep environment variables limited to public configuration. Never
    place secrets in Vite variables.

### 13.5 Deployment requirements

-   Deploy creator and resolver as Cloud Run services.
-   Deploy cleanup as an HTTP-triggered function or an equivalent
    scheduled job.
-   Configure Cloud Scheduler to invoke cleanup using authenticated
    service-to-service access.
-   Build Docker images from the backend context if shared modules
    require it.
-   Ensure container ports and local Docker instructions agree.
-   Use a dedicated runtime service account with least-privilege
    permissions.
-   Separate development and production configuration.
-   Configure custom domains and HTTPS when the product domain is
    available.
-   Document rollback and redeployment steps.

### 13.6 Reliability requirements

-   No unhandled exception should expose a stack trace to a recipient.
-   A datastore outage must fail closed: do not redirect when policy
    cannot be verified.
-   A cleanup failure must not affect resolver correctness.
-   A failed transaction must not produce a redirect.
-   Requests must have sensible timeouts.
-   Services must shut down gracefully.
-   Deployments should support health checks.
-   Use bounded retries with backoff for transient dependencies.

------------------------------------------------------------------------

## 14. Performance and service-level objectives

These are initial engineering targets, to be validated against the
actual deployment and load profile.

  -----------------------------------------------------------------------
  Metric                              Initial target
  ----------------------------------- -----------------------------------
  Resolver latency                    p95 below 300 ms, excluding
                                      recipient destination load

  Creator latency                     p95 below 700 ms

  Dashboard API latency               p95 below 500 ms for normal page
                                      sizes

  Resolver availability               99.9% monthly target after
                                      production launch

  Click-limit correctness             Zero over-limit successful
                                      redirects in concurrency tests

  Cleanup                             Process eligible records in bounded
                                      batches

  Frontend initial load               Keep production bundle lean;
                                      measure real-user performance

  Error visibility                    All unexpected backend failures
                                      produce structured logs
  -----------------------------------------------------------------------

Do not claim these targets are achieved until measured in the deployed
environment.

------------------------------------------------------------------------

## 15. Observability and operations

### 15.1 Structured logging

Include:

-   Timestamp.
-   Service name.
-   Severity.
-   Request or trace ID.
-   Route or operation.
-   Result category.
-   Duration.
-   Relevant non-sensitive entity identifier where appropriate.

Never log passcodes, auth tokens, service-account credentials, or
sensitive query strings.

### 15.2 Metrics

Track:

-   Link creation attempts and successes.
-   Resolver requests.
-   Successful redirect authorizations.
-   Expired, exhausted, revoked, and unknown-link outcomes.
-   Passcode failures, if enabled.
-   Rate-limit rejections.
-   Datastore transaction conflicts and failures.
-   Cleanup records scanned, deleted, and failed.
-   API latency and error rate.

### 15.3 Alerts

At minimum, alert on:

-   Elevated resolver 5xx rate.
-   Sustained datastore failures.
-   Cleanup job failures or missed runs.
-   Unusual creation spikes.
-   Excessive rate-limit events.
-   High transaction contention.

### 15.4 Runbooks

Document:

-   How to deploy each service.
-   How to roll back a deployment.
-   How to verify the cleanup schedule.
-   How to investigate resolver errors.
-   How to handle abusive links or accounts.
-   How to rotate credentials.
-   How to restore service after a datastore outage.

------------------------------------------------------------------------

## 16. Testing strategy

No production release should be considered complete without automated
coverage of the core access rules.

### 16.1 Unit tests

Cover:

-   URL validation.
-   TTL validation and maximum values.
-   Click-limit validation.
-   Expiry calculations.
-   Lifecycle state derivation.
-   Revocation behavior.
-   Error mapping.
-   Passcode hashing and verification, if implemented.

### 16.2 Integration tests

Cover:

-   Link creation and persistence.
-   Resolver lookup.
-   Successful redirect.
-   Expired link rejection.
-   Exhausted link rejection.
-   Unknown link rejection.
-   Revocation.
-   Owner authorization.
-   Dashboard filtering and pagination.
-   Cleanup behavior.
-   Authentication failure.
-   Rate-limit behavior.

### 16.3 Concurrency tests

These are mandatory.

-   Send concurrent requests to a one-use link.
-   Send concurrent requests to a link with a higher usage limit.
-   Assert that successful redirect authorizations never exceed the
    configured limit.
-   Assert that the stored counter never exceeds the limit.
-   Repeat under transaction contention.
-   Verify failed requests do not consume visits.

### 16.4 Security tests

Cover:

-   Unsupported URL schemes.
-   Malformed URLs.
-   Host-header and forwarded-header assumptions.
-   Cross-origin behavior.
-   Missing and invalid authentication.
-   Cross-user access attempts.
-   Passcode brute-force throttling.
-   Oversized request bodies.
-   Secret leakage in logs and responses.
-   Unauthorized cleanup invocation.

### 16.5 Frontend tests

Cover:

-   Form validation.
-   Duplicate-submit prevention.
-   Success and copy states.
-   API error states.
-   Dashboard empty and populated states.
-   Filters and pagination.
-   Revocation confirmation.
-   Mobile layout.
-   Keyboard navigation.

### 16.6 CI requirements

Every pull request should run:

1.  Backend formatting/linting.
2.  Backend unit tests.
3.  Backend integration tests where feasible.
4.  Frontend linting.
5.  Frontend tests.
6.  Production frontend build.
7.  Docker build verification.
8.  Dependency and secret checks.

Do not deploy automatically to production unless the deployment
environment and approval policy explicitly allow it.

------------------------------------------------------------------------

## 17. Privacy, legal, and trust requirements

Before public launch:

-   Publish a privacy policy.
-   Publish terms of service.
-   Explain that SafeLinks controls access to the redirect URL, not
    access to the destination itself.
-   Explain that recipients may copy, screenshot, download, or
    redistribute content after reaching the destination.
-   Provide an abuse-reporting contact or workflow.
-   Define prohibited uses.
-   Define account suspension and appeal handling.
-   Define data retention and deletion.
-   Avoid claims of end-to-end encryption unless the architecture
    genuinely provides it.
-   Avoid describing a normal redirect as secure document delivery.

------------------------------------------------------------------------

## 18. Monetization direction

Do not build billing before validating real usage.

A sensible initial model is:

### Free

-   Basic temporary links.
-   Time and visit limits.
-   Owner dashboard.
-   Manual revocation.
-   Reasonable monthly creation quota.

### Pro (future)

-   Higher creation limits.
-   Passcode protection.
-   Longer retention.
-   API access.
-   Exportable activity history.
-   Custom aliases or branded domains, if demand supports them.

### Team (future)

-   Shared ownership.
-   Team-level quotas.
-   Member roles.
-   Shared activity and audit history.

The exact limits and pricing should be based on infrastructure costs,
abuse exposure, and user interviews. Do not invent pricing as an
implementation requirement.

------------------------------------------------------------------------

## 19. Product analytics and success metrics

Measure product utility without building invasive tracking.

### Activation

-   Percentage of new users who create their first link.
-   Time from landing to first successful link creation.
-   Percentage who copy a generated link.

### Engagement

-   Links created per active user.
-   Percentage of users who return to manage links.
-   Percentage of links manually revoked.
-   Use of optional passcode protection after release.

### Reliability

-   Successful redirect authorization rate.
-   Over-limit redirect count.
-   Resolver 4xx and 5xx rates.
-   Transaction contention rate.
-   Cleanup success rate.

### Trust and safety

-   Abuse reports.
-   Confirmed abusive links.
-   Rate-limit rejections.
-   Unauthorized access attempts.
-   Account suspensions.

**North-star metric:** Number of link access policies successfully
enforced, measured as valid access decisions made within the configured
policy.

Do not optimize for raw clicks alone. A link that correctly refuses
access after its policy is exhausted is a successful product outcome.

------------------------------------------------------------------------

## 20. Delivery plan

Work should be delivered in small, verifiable phases. The coding agent
must inspect the repository before making implementation assumptions.

### Phase 0: Repository audit and baseline

-   Inspect frontend, creator, resolver, remover, shared modules,
    deployment files, and README.
-   Confirm actual routes, schemas, environment variables, and runtime
    behavior.
-   Run existing build and available checks.
-   Identify current datastore mode and transaction support.
-   Identify deployment and credential assumptions.
-   Document discrepancies between this PRD and the repository.
-   Do not rewrite working code before the audit is complete.

**Exit criteria:** A concise implementation plan grounded in the actual
repository, with risks and migration decisions identified.

### Phase 1: Core correctness and production hardening

-   Implement atomic click reservation.
-   Make resolver fail closed on datastore errors.
-   Introduce consistent lifecycle rules.
-   Add validation and stable error responses.
-   Replace Flask development servers with a production WSGI server.
-   Fix Docker ports and local run instructions.
-   Restrict CORS.
-   Add rate limiting.
-   Add unit, integration, and concurrency tests.
-   Add structured logging and health checks.

**Exit criteria:** Core access guarantees are tested, reproducible, and
safe under concurrent requests.

### Phase 2: Identity and owner control

-   Add authentication.
-   Associate links with owners.
-   Add owner-scoped dashboard APIs.
-   Add link listing and details.
-   Add manual revocation.
-   Add frontend dashboard and link details.
-   Add authorization tests.

**Exit criteria:** Users can securely manage only their own links.

### Phase 3: Recipient experience and operational automation

-   Build branded unavailable states.
-   Improve recipient redirect behavior.
-   Configure scheduled cleanup.
-   Add retention policy.
-   Add monitoring and alerts.
-   Add operational runbooks.
-   Complete accessibility and responsive QA.

**Exit criteria:** The service can be deployed and operated without
manual cleanup or undocumented intervention.

### Phase 4: Differentiating protection

-   Add optional passcode protection.
-   Add passcode attempt throttling.
-   Add privacy-conscious activity history.
-   Add abuse reporting and operator controls.
-   Conduct security review.

**Exit criteria:** Additional protection is enforced server-side and
does not weaken core link guarantees.

### Phase 5: Launch readiness

-   Complete end-to-end testing.
-   Verify production environment variables and secrets.
-   Verify least-privilege service accounts.
-   Run load and concurrency tests.
-   Verify backup/recovery expectations for the chosen datastore
    configuration.
-   Publish privacy policy and terms.
-   Prepare a concise product demo and architecture documentation.
-   Validate product claims against actual behavior.

**Exit criteria:** All P0 requirements are complete, tested, documented,
and deployed to a production-like environment.

------------------------------------------------------------------------

## 21. Definition of done

A feature is not done merely because its UI exists.

Every feature must include:

-   Backend enforcement where applicable.
-   Input validation.
-   Authorization checks where applicable.
-   Predictable error handling.
-   Loading, empty, success, and failure UI states where applicable.
-   Automated tests.
-   Logging without sensitive data.
-   Documentation.
-   Responsive and accessible behavior.
-   Verified deployment configuration.

The product is ready for its first production-grade release only when:

-   Click limits are enforced atomically.
-   Expiry and revocation are enforced by the resolver.
-   Datastore failures fail closed.
-   Users can manage only their own links.
-   Manual revocation works.
-   Rate limiting is active.
-   Cleanup runs on a schedule.
-   Services use production servers.
-   Critical paths have automated tests.
-   Logs, metrics, and alerts are available.
-   Deployment and rollback instructions are verified.
-   Privacy and security claims match the implementation.

------------------------------------------------------------------------

## 22. Risks and mitigations

  -----------------------------------------------------------------------
  Risk                    Impact                  Mitigation
  ----------------------- ----------------------- -----------------------
  Concurrent resolver     Breaks core promise     Atomic transaction and
  requests exceed click                           concurrency tests
  limit                                           

  Public link creation    Cost, reputation, and   Authentication, quotas,
  abuse                   availability damage     rate limits, abuse
                                                  controls

  Open redirect abuse     Phishing and domain     URL validation, clear
                          reputation damage       destination display,
                                                  abuse response

  Datastore outage        Incorrect access        Fail closed, timeouts,
                          decisions               monitoring

  Authentication          Account compromise or   Established provider,
  integration errors      lockout                 secure sessions,
                                                  integration tests

  Cleanup scans become    Increased cloud costs   Pagination, bounded
  expensive                                       batches, indexes

  Excessive product scope Slow delivery and weak  P0/P1/P2 prioritization
                          execution               and explicit non-goals

  Privacy-invasive        Loss of trust           Minimal collection and
  analytics                                       retention limits

  Passcode brute force    Unauthorized access     Per-link and per-IP
                                                  throttling

  Misleading security     User harm and           Explicit product
  claims                  reputational damage     limitations and
                                                  accurate copy
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 23. Product decisions that must be made during implementation

The coding agent should inspect the repository and recommend decisions
with evidence before changing architecture.

1.  **Authentication:** Which provider best fits the existing stack,
    budget, and deployment environment?
2.  **Datastore transactions:** What exact transaction API and retry
    behavior are supported by the current client and datastore mode?
3.  **Rate limiting:** Which shared or managed mechanism fits the
    current GCP setup and expected traffic?
4.  **Cleanup retention:** How long should expired, exhausted, and
    revoked records remain?
5.  **Public unavailable behavior:** Should unknown and inactive links
    share one response to reduce information disclosure?
6.  **Passcode delivery:** Should passcode verification use a
    short-lived server-side session or a signed, short-lived token?
7.  **Domain strategy:** What production domain will host the frontend
    and resolver?
8.  **Authentication and privacy policy:** What account deletion and
    data-retention commitments can the implementation actually support?

Do not block core correctness work on decisions that only affect later
P1 features.

------------------------------------------------------------------------

## 24. Instructions for the implementation agent

Treat this PRD as the product and acceptance baseline. The repository is
the source of truth for the current implementation.

Before editing:

1.  Read the complete repository structure and relevant source files.
2.  Inspect all existing API routes, data access code, Dockerfiles,
    deployment configuration, frontend components, and documentation.
3.  Run the current tests and builds, if present.
4.  Verify every claimed existing behavior against code.
5.  Identify migrations and compatibility risks.
6.  Produce a phased implementation plan with affected files and
    dependencies.

During implementation:

-   Preserve existing working behavior unless a requirement explicitly
    changes it.
-   Do not fabricate environment variables, cloud resources,
    credentials, or deployment results.
-   Do not commit secrets.
-   Do not silently introduce paid services.
-   Prefer the smallest architecture that satisfies the requirements.
-   Keep frontend and backend validation consistent, but enforce all
    security rules on the backend.
-   Do not mark a requirement complete without tests or a clearly
    documented reason it cannot be tested.
-   Avoid speculative features outside the agreed scope.
-   Keep the README aligned with actual behavior.
-   Update API documentation and local deployment instructions alongside
    code changes.
-   Use small, reviewable changes rather than one large rewrite.

At the end of each phase, report:

-   What changed.
-   Which requirements were completed.
-   Which files were affected.
-   Tests and builds run, including their actual results.
-   Any migration or deployment steps.
-   Remaining risks and blockers.

Never claim that a cloud deployment, scheduled job, domain,
authentication provider, or production integration is working unless it
has actually been configured and verified.

------------------------------------------------------------------------

## 25. Final product standard

SafeLinks should be judged by the quality of its guarantees, not by the
number of features in its navigation.

A user should be able to create a temporary link in seconds, understand
exactly how access is limited, share it confidently, and revoke it when
needed.

A recipient should encounter a predictable and clear experience.

An engineer should be able to inspect the system and understand how
access decisions are made, how concurrency is handled, how abuse is
controlled, and how the service is operated.

That is the standard for SafeLinks: **simple on the surface, rigorous
underneath.**
