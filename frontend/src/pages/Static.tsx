import type { ReactNode } from "react";
import { Link as RouterLink } from "react-router";
import { buttonClass, useTitle } from "../components";

function Doc({ title, updated, children }: { title: string; updated: string; children: ReactNode }) {
  useTitle(title);
  return (
    <article className="mx-auto max-w-2xl space-y-6 text-sm leading-relaxed [&_h2]:mt-8 [&_h2]:text-base [&_h2]:font-semibold [&_li]:ml-5 [&_li]:list-disc [&_p]:text-ink/90">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">{title}</h1>
        <p className="text-muted">Last updated {updated}</p>
      </header>
      {children}
    </article>
  );
}

const report = (
  <RouterLink to="/report" className="text-signal underline">
    report form
  </RouterLink>
);

export function Privacy() {
  return (
    <Doc title="Privacy notice" updated="November 11, 2026">
      <p>
        SafeLinks lets you create short links that stop working after a set time or number of visits. This notice
        explains what we store and for how long.
      </p>
      <h2>What we store</h2>
      <ul>
        <li>Your account: email address and a password hash, managed by our authentication provider.</li>
        <li>
          Your links: the destination URL, its host, expiry time, visit limit, visit count, and whether a passcode
          is set. Passcodes are stored only as a one-way hash.
        </li>
        <li>
          Link activity: when a link was created, each successful visit time, and when it was revoked. We do not
          record recipients&apos; names, emails, or full IP addresses.
        </li>
        <li>
          Abuse protection: rate-limit counters keyed by a salted hash of the requester&apos;s IP address, kept for
          about one day.
        </li>
        <li>Abuse reports: the reported link, reason, details, and an optional contact email.</li>
      </ul>
      <h2>What we do not do</h2>
      <ul>
        <li>We do not read, copy, or host the content at your destination URL.</li>
        <li>We do not sell personal data or use it for advertising.</li>
        <li>
          We do not offer end-to-end encryption. Links are transmitted over HTTPS, and the destination URL is stored
          on our servers so the redirect can work.
        </li>
      </ul>
      <h2>Retention and deletion</h2>
      <ul>
        <li>Expired, exhausted, and revoked links are deleted 30 days after they stop working.</li>
        <li>Link activity records are deleted after 90 days.</li>
        <li>
          Deleting your account removes your account, all of your links, and their activity immediately. Links stop
          working at once.
        </li>
      </ul>
      <h2>Contact</h2>
      <p>For privacy questions or to report misuse, use the {report}.</p>
    </Doc>
  );
}

export function Terms() {
  return (
    <Doc title="Terms of service" updated="November 11, 2026">
      <h2>What SafeLinks does</h2>
      <p>
        SafeLinks controls access to the short redirect link, not access to the destination itself. When a visit is
        allowed, the recipient is redirected to your destination URL. A SafeLinks link is a redirect with limits, not
        a secure document delivery system.
      </p>
      <p>
        After a recipient reaches the destination they may copy, screenshot, download, bookmark, or redistribute what
        they see, including the destination URL. If the destination itself must stay private, protect it with its own
        access controls.
      </p>
      <h2>Prohibited uses</h2>
      <p>You may not use SafeLinks to:</p>
      <ul>
        <li>Phish, steal credentials, or impersonate another person or organization.</li>
        <li>Distribute malware or link to exploit pages.</li>
        <li>Send spam or bulk unsolicited messages.</li>
        <li>Share illegal content, including child sexual abuse material.</li>
        <li>Harass, threaten, or dox anyone.</li>
        <li>Hide the destination of a link to evade another service&apos;s safety filters.</li>
      </ul>
      <h2>Reporting abuse</h2>
      <p>Anyone can report a SafeLinks link using the {report}. We review reports and may revoke links.</p>
      <h2>Suspension and appeal</h2>
      <p>
        We may revoke links or suspend accounts that break these terms. While an account is suspended, its links stop
        working and it cannot create new ones. To appeal, reply to the suspension notice or contact us through the{" "}
        {report} with the subject &ldquo;Appeal&rdquo; and your account email. A person reviews every appeal.
      </p>
      <h2>Data retention and deletion</h2>
      <p>
        Inactive links are deleted 30 days after they stop working and activity records after 90 days. You can delete
        your account and all of its data at any time from the account page. See the{" "}
        <RouterLink to="/privacy" className="text-signal underline">
          privacy notice
        </RouterLink>{" "}
        for details.
      </p>
      <h2>No warranty</h2>
      <p>
        SafeLinks is provided as is. We aim to enforce expiry and visit limits exactly, but we are not liable for what
        happens at the destination or after a recipient has opened it.
      </p>
    </Doc>
  );
}

export function NotFound() {
  useTitle("Page not found");
  return (
    <section className="space-y-4 py-12 text-center">
      <h1 className="text-2xl font-semibold">Page not found.</h1>
      <p className="text-sm text-muted">The page you are looking for does not exist.</p>
      <RouterLink to="/" className={buttonClass("secondary")}>
        Go to SafeLinks
      </RouterLink>
    </section>
  );
}
