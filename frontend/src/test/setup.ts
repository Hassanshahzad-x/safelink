import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";
import { authState } from "./authState";

vi.mock("@supabase/auth-js", () => ({
  AuthClient: class {
    getSession = async () => ({ data: { session: authState.session } });
    onAuthStateChange = () => ({ data: { subscription: { unsubscribe() {} } } });
    signOut = vi.fn(async () => {
      authState.session = null;
      return { error: null };
    });
    signInWithPassword = vi.fn(async () => ({ error: { message: "Invalid login credentials" } }));
    signUp = vi.fn(async () => ({ data: {}, error: null }));
    resetPasswordForEmail = vi.fn(async () => ({ data: {}, error: null }));
    updateUser = vi.fn(async () => ({ data: {}, error: null }));
  },
}));

afterEach(() => {
  cleanup();
  authState.session = null;
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});
