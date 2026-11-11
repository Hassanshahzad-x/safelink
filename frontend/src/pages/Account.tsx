import { useNavigate } from "react-router";
import { Button, ConfirmAction, useTitle } from "../components";
import { api } from "../lib/api";
import { authClient, useAuth } from "../lib/auth";

export default function Account() {
  useTitle("Account");
  const { session } = useAuth();
  const navigate = useNavigate();

  return (
    <section aria-labelledby="account-title" className="max-w-2xl space-y-6">
      <h1 id="account-title" className="text-2xl font-semibold">
        Account
      </h1>
      <dl className="rounded-lg border border-line bg-surface px-4 py-3 text-sm">
        <dt className="text-muted">Email</dt>
        <dd className="break-all">{session?.user.email}</dd>
      </dl>
      <Button
        variant="secondary"
        onClick={async () => {
          await authClient.signOut();
          navigate("/signin", { state: { notice: "You are signed out." } });
        }}
      >
        Sign out
      </Button>
      <section aria-labelledby="delete-title" className="space-y-3 rounded-lg border border-danger/30 bg-surface p-4">
        <h2 id="delete-title" className="font-medium">
          Delete account
        </h2>
        <p className="text-sm text-muted">
          This deletes your account, all of your links and their activity. Your links stop working immediately. This
          cannot be undone.
        </p>
        <ConfirmAction
          label="Delete account"
          prompt="Delete your account and all links?"
          confirmLabel="Delete permanently"
          onConfirm={async () => {
            await api.deleteAccount();
            await authClient.signOut({ scope: "local" });
            navigate("/", { replace: true, state: { notice: "Your account was deleted." } });
          }}
        />
      </section>
    </section>
  );
}
