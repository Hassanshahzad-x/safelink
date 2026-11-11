import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Dev server proxies the same paths nginx serves in docker, so the app always talks to
// its own origin: /api -> FastAPI, /auth/v1 -> Supabase Auth.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/auth/v1": { target: "http://localhost:9999", rewrite: (p) => p.replace(/^\/auth\/v1/, "") },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["src/test/setup.ts"],
    css: false,
  },
});
