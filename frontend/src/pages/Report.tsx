import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router";
import { Button, Field, Notice, inputClass, useTitle } from "../components";
import { api, errorMessage } from "../lib/api";

const REASONS = [
  ["phishing", "Phishing or credential theft"],
  ["malware", "Malware"],
  ["spam", "Spam"],
  ["illegal", "Illegal content"],
  ["other", "Something else"],
] as const;

export default function Report() {
  useTitle("Report abuse");
  const [params] = useSearchParams();
  const [link, setLink] = useState(params.get("link") ?? "");
  const [reason, setReason] = useState("phishing");
  const [details, setDetails] = useState("");
  const [email, setEmail] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (pending) return;
    if (!link.trim()) return setError("Enter the SafeLinks short link or link ID.");
    setPending(true);
    setError(null);
    try {
      await api.report({ link: link.trim(), reason, details: details.trim() || null, email: email.trim() || null });
      setDone(true);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPending(false);
    }
  }

  return (
    <section aria-labelledby="report-title" className="mx-auto max-w-xl space-y-6">
      <div className="space-y-2">
        <h1 id="report-title" className="text-2xl font-semibold">
          Report abuse
        </h1>
        <p className="text-sm text-muted">
          Tell us about a SafeLinks short link used for phishing, malware, spam or other abuse. We review every report.
        </p>
      </div>
      {done ? (
        <Notice tone="success">Thanks. We received your report.</Notice>
      ) : (
        <form noValidate onSubmit={submit} className="space-y-4 rounded-lg border border-line bg-surface p-5">
          {error && <Notice>{error}</Notice>}
          <Field label="Short link or link ID">
            {(p) => (
              <input
                {...p}
                maxLength={2048}
                value={link}
                onChange={(e) => setLink(e.target.value)}
                className={`${inputClass} font-mono`}
              />
            )}
          </Field>
          <Field label="Reason">
            {(p) => (
              <select {...p} value={reason} onChange={(e) => setReason(e.target.value)} className={inputClass}>
                {REASONS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label="Details (optional)">
            {(p) => (
              <textarea
                {...p}
                rows={4}
                maxLength={2000}
                value={details}
                onChange={(e) => setDetails(e.target.value)}
                className={`${inputClass} h-auto py-2`}
              />
            )}
          </Field>
          <Field label="Your email (optional)" hint="Only used if we need to follow up.">
            {(p) => (
              <input
                {...p}
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={inputClass}
              />
            )}
          </Field>
          <Button type="submit" loading={pending}>
            Send report
          </Button>
        </form>
      )}
    </section>
  );
}
