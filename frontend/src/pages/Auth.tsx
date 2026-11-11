import { useState, type FormEvent, type ReactNode } from "react";
import { Link as RouterLink, Navigate, useLocation, useNavigate } from "react-router";
import { Button, Field, Notice, Spinner, inputClass, useTitle } from "../components";
import { authClient, useAuth } from "../lib/auth";
import type { Draft } from "./Create";

type From = { from?: string; draft?: Draft } | null;

function friendly(message: string) {
  if (/email not confirmed/i.test(message)) return "Confirm your email address first. Check your inbox for the link.";
  if (/invalid login credentials/i.test(message)) return "Email or password is incorrect.";
  if (/already registered/i.test(message)) return "An account with this email already exists. Sign in instead.";
  if (/rate limit|too many/i.test(message)) return "Too many attempts. Wait a moment and try again.";
  if (/fetch|network/i.test(message)) return "Could not reach SafeLinks. Check your connection and try again.";
  return message || "Something went wrong. Try again.";
}

function AuthCard({ title, children, footer }: { title: string; children: ReactNode; footer?: ReactNode }) {
  useTitle(title);
  return (
    <section aria-labelledby="auth-title" className="mx-auto max-w-sm space-y-6">
      <h1 id="auth-title" className="text-2xl font-semibold">
        {title}
      </h1>
      <div className="rounded-lg border border-line bg-surface p-5">{children}</div>
      {footer && <div className="text-center text-sm text-muted">{footer}</div>}
    </section>
  );
}

/** Shared submit plumbing: one request at a time, error text on failure. */
function useSubmit() {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function run(fn: () => Promise<{ error: { message: string } | null }>) {
    if (pending) return false;
    setPending(true);
    setError(null);
    try {
      const { error } = await fn();
      if (error) setError(friendly(error.message));
      return !error;
    } catch (err) {
      setError(friendly(err instanceof Error ? err.message : ""));
      return false;
    } finally {
      setPending(false);
    }
  }
  return { pending, error, setError, run };
}

function EmailField({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <Field label="Email">
      {(p) => (
        <input
          {...p}
          type="email"
          autoComplete="email"
          required
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={inputClass}
        />
      )}
    </Field>
  );
}

function PasswordField({
  label = "Password",
  value,
  onChange,
  autoComplete,
  hint,
}: {
  label?: string;
  value: string;
  onChange: (v: string) => void;
  autoComplete: string;
  hint?: string;
}) {
  return (
    <Field label={label} hint={hint}>
      {(p) => (
        <input
          {...p}
          type="password"
          autoComplete={autoComplete}
          required
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={inputClass}
        />
      )}
    </Field>
  );
}

export function SignIn() {
  const { session, loading } = useAuth();
  const state = useLocation().state as From;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const { pending, error, run } = useSubmit();

  if (loading) return <Spinner />;
  // Redirect once the session lands, so we never race onAuthStateChange.
  if (session) return <Navigate to={state?.from ?? "/links"} replace state={state?.draft ? { draft: state.draft } : undefined} />;

  return (
    <AuthCard
      title="Sign in"
      footer={
        <>
          No account?{" "}
          <RouterLink to="/signup" state={state} className="text-signal hover:underline">
            Sign up
          </RouterLink>
        </>
      }
    >
      <form
        className="space-y-4"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          void run(() => authClient.signInWithPassword({ email: email.trim(), password }));
        }}
      >
        {error && <Notice>{error}</Notice>}
        <EmailField value={email} onChange={setEmail} />
        <PasswordField value={password} onChange={setPassword} autoComplete="current-password" />
        <Button type="submit" loading={pending} className="w-full">
          Sign in
        </Button>
        <RouterLink to="/forgot-password" className="block text-center text-sm text-signal hover:underline">
          Forgot password?
        </RouterLink>
      </form>
    </AuthCard>
  );
}

export function SignUp() {
  const { session } = useAuth();
  const state = useLocation().state as From;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [sent, setSent] = useState(false);
  const { pending, error, setError, run } = useSubmit();

  if (session) return <Navigate to={state?.from ?? "/links"} replace state={state?.draft ? { draft: state.draft } : undefined} />;
  if (sent)
    return (
      <AuthCard title="Check your email">
        <p className="text-sm">
          We sent a confirmation link to <strong className="break-all">{email}</strong>. Open it to finish creating
          your account.
        </p>
      </AuthCard>
    );

  return (
    <AuthCard
      title="Create your account"
      footer={
        <>
          Already have an account?{" "}
          <RouterLink to="/signin" state={state} className="text-signal hover:underline">
            Sign in
          </RouterLink>
        </>
      }
    >
      <form
        className="space-y-4"
        onSubmit={async (e: FormEvent) => {
          e.preventDefault();
          if (password.length < 8) return setError("Use at least 8 characters for your password.");
          const ok = await run(async () => {
            const res = await authClient.signUp({
              email: email.trim(),
              password,
              options: { emailRedirectTo: `${window.location.origin}/links` },
            });
            return res;
          });
          // With email confirmation on there is no session yet; onAuthStateChange handles autoconfirm.
          if (ok) setSent(true);
        }}
      >
        {error && <Notice>{error}</Notice>}
        <EmailField value={email} onChange={setEmail} />
        <PasswordField
          value={password}
          onChange={setPassword}
          autoComplete="new-password"
          hint="At least 8 characters."
        />
        <Button type="submit" loading={pending} className="w-full">
          Sign up
        </Button>
        <p className="text-xs text-muted">
          By signing up you agree to the{" "}
          <RouterLink to="/terms" className="underline">
            terms
          </RouterLink>{" "}
          and{" "}
          <RouterLink to="/privacy" className="underline">
            privacy notice
          </RouterLink>
          .
        </p>
      </form>
    </AuthCard>
  );
}

export function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const { pending, error, run } = useSubmit();

  return (
    <AuthCard
      title="Reset your password"
      footer={
        <RouterLink to="/signin" className="text-signal hover:underline">
          Back to sign in
        </RouterLink>
      }
    >
      {sent ? (
        <p role="status" className="text-sm">
          If an account exists for that email, we sent a link to reset the password.
        </p>
      ) : (
        <form
          className="space-y-4"
          onSubmit={async (e: FormEvent) => {
            e.preventDefault();
            const ok = await run(() =>
              authClient.resetPasswordForEmail(email.trim(), {
                redirectTo: `${window.location.origin}/reset-password`,
              }),
            );
            if (ok) setSent(true);
          }}
        >
          {error && <Notice>{error}</Notice>}
          <EmailField value={email} onChange={setEmail} />
          <Button type="submit" loading={pending} className="w-full">
            Send reset link
          </Button>
        </form>
      )}
    </AuthCard>
  );
}

export function ResetPassword() {
  const { session, loading } = useAuth();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const { pending, error, setError, run } = useSubmit();

  if (loading) return <Spinner />;
  if (!session)
    return (
      <AuthCard title="Reset link expired">
        <p className="text-sm">
          This reset link is invalid or has expired.{" "}
          <RouterLink to="/forgot-password" className="text-signal hover:underline">
            Request a new one
          </RouterLink>
          .
        </p>
      </AuthCard>
    );

  return (
    <AuthCard title="Choose a new password">
      <form
        className="space-y-4"
        onSubmit={async (e: FormEvent) => {
          e.preventDefault();
          if (password.length < 8) return setError("Use at least 8 characters for your password.");
          if (await run(() => authClient.updateUser({ password })))
            navigate("/links", { replace: true, state: { notice: "Your password was updated." } });
        }}
      >
        {error && <Notice>{error}</Notice>}
        <PasswordField
          label="New password"
          value={password}
          onChange={setPassword}
          autoComplete="new-password"
          hint="At least 8 characters."
        />
        <Button type="submit" loading={pending} className="w-full">
          Update password
        </Button>
      </form>
    </AuthCard>
  );
}
