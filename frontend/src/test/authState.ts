// Mutable fake auth state shared by the @supabase/auth-js mock and the tests.
export const authState: { session: { access_token: string; user: { email: string } } | null } = {
  session: null,
};

export const signIn = () => {
  authState.session = { access_token: "test-token", user: { email: "owner@example.com" } };
};
