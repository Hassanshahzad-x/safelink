import type { ReactNode } from "react";
import { Link as RouterLink, Navigate, NavLink, Route, Routes, useLocation, useNavigate } from "react-router";
import { Logo, Notice, Spinner } from "./components";
import { authClient, useAuth } from "./lib/auth";
import Account from "./pages/Account";
import { ForgotPassword, ResetPassword, SignIn, SignUp } from "./pages/Auth";
import Create from "./pages/Create";
import LinkDetail from "./pages/LinkDetail";
import Links from "./pages/Links";
import Report from "./pages/Report";
import { NotFound, Privacy, Terms } from "./pages/Static";

const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-2.5 py-1.5 text-sm transition-colors hover:bg-ink/5 ${isActive ? "font-medium text-ink" : "text-muted"}`;

function Shell({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const notice = (location.state as { notice?: string } | null)?.notice;

  async function signOut() {
    await authClient.signOut();
    navigate("/signin", { state: { notice: "You are signed out." } });
  }

  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-surface px-3 py-2 focus:not-sr-only focus:absolute focus:top-2 focus:left-2"
      >
        Skip to content
      </a>
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-3">
          <RouterLink to="/" aria-label="SafeLinks home" className="rounded-md">
            <Logo />
          </RouterLink>
          <nav aria-label="Main" className="flex flex-wrap items-center gap-1">
            {session ? (
              <>
                <NavLink to="/" end className={navClass}>
                  Create
                </NavLink>
                <NavLink to="/links" className={navClass}>
                  Links
                </NavLink>
                <NavLink to="/account" className={navClass}>
                  Account
                </NavLink>
                <button type="button" onClick={signOut} className={navClass({ isActive: false })}>
                  Sign out
                </button>
              </>
            ) : (
              <>
                <NavLink to="/signin" className={navClass}>
                  Sign in
                </NavLink>
                <NavLink to="/signup" className={navClass}>
                  Sign up
                </NavLink>
              </>
            )}
          </nav>
        </div>
      </header>
      <main id="main" tabIndex={-1} className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 outline-none sm:py-12">
        {notice && (
          <div className="mb-6">
            <Notice tone="success">{notice}</Notice>
          </div>
        )}
        {children}
      </main>
      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-5xl flex-col gap-2 px-4 py-6 text-xs text-muted sm:flex-row sm:items-center sm:justify-between">
          <p>SafeLinks controls access to the short link, not the destination.</p>
          <nav aria-label="Legal" className="flex gap-4">
            <RouterLink to="/privacy" className="hover:text-ink">
              Privacy
            </RouterLink>
            <RouterLink to="/terms" className="hover:text-ink">
              Terms
            </RouterLink>
            <RouterLink to="/report" className="hover:text-ink">
              Report abuse
            </RouterLink>
          </nav>
        </div>
      </footer>
    </div>
  );
}

function RequireAuth({ children }: { children: ReactNode }) {
  const { session, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Spinner />;
  if (!session) return <Navigate to="/signin" replace state={{ from: location.pathname + location.search }} />;
  return children;
}

export default function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Create />} />
        <Route
          path="/links"
          element={
            <RequireAuth>
              <Links />
            </RequireAuth>
          }
        />
        <Route
          path="/links/:id"
          element={
            <RequireAuth>
              <LinkDetail />
            </RequireAuth>
          }
        />
        <Route
          path="/account"
          element={
            <RequireAuth>
              <Account />
            </RequireAuth>
          }
        />
        <Route path="/signin" element={<SignIn />} />
        <Route path="/signup" element={<SignUp />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/report" element={<Report />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/terms" element={<Terms />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Shell>
  );
}
