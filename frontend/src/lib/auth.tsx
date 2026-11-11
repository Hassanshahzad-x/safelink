// Supabase Auth (GoTrue). Locally the web server proxies /auth/v1 to the auth container;
// against hosted Supabase set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY (both public).
import { AuthClient, type Session } from "@supabase/auth-js";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

const base = (import.meta.env.VITE_SUPABASE_URL as string | undefined)?.replace(/\/$/, "");
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

export const authClient = new AuthClient({
  url: `${base ?? window.location.origin}/auth/v1`,
  headers: anonKey ? { apikey: anonKey } : {},
  storageKey: "safelinks-auth",
  persistSession: true,
  autoRefreshToken: true,
  detectSessionInUrl: true, // email confirmation and password recovery links
  flowType: "implicit",
});

interface AuthState {
  session: Session | null;
  loading: boolean;
}

const AuthContext = createContext<AuthState>({ session: null, loading: true });

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ session: null, loading: true });
  useEffect(() => {
    let active = true;
    authClient.getSession().then(({ data }) => {
      if (active) setState({ session: data.session, loading: false });
    });
    const { data } = authClient.onAuthStateChange((_event, session) => {
      if (active) setState({ session, loading: false });
    });
    return () => {
      active = false;
      data.subscription.unsubscribe();
    };
  }, []);
  return <AuthContext.Provider value={state}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
