import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  // The component tests are .tsx; without this the JSX in them is a parse
  // error at collection time.
  plugins: [react()],
  resolve: {
    // Mirrors the "@/*" path alias in tsconfig.json - the route handlers and
    // their tests import lib/auth through it.
    alias: {
      "@": fileURLToPath(new URL("./", import.meta.url)),
    },
  },
  test: {
    // Node by default - most of these tests are route handlers and pure
    // functions. Anything that renders a component says so in a docblock
    // pragma (`@vitest-environment jsdom`), which keeps the fast majority
    // fast.
    environment: "node",
    // Set before any test module's top-level `process.env.X ?? default` runs -
    // those constants are evaluated at import time, so this can't be done
    // per-test via vi.stubEnv() for modules imported statically.
    env: {
      ADMIN_API_KEY: "test-admin-key",
      API_URL: "http://backend.test",
      NEXT_PUBLIC_DYNAMIC_ENVIRONMENT_ID: "test-environment-id",
    },
    // React 19 renders through act(); without this the warnings are noise and
    // some updates are not flushed.
    globals: true,
  },
});
