import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    // Mirrors the "@/*" path alias in tsconfig.json - the route handlers and
    // their tests import lib/auth through it.
    alias: {
      "@": fileURLToPath(new URL("./", import.meta.url)),
    },
  },
  test: {
    environment: "node",
    // Set before any test module's top-level `process.env.X ?? default` runs -
    // those constants are evaluated at import time, so this can't be done
    // per-test via vi.stubEnv() for modules imported statically.
    env: {
      ADMIN_API_KEY: "test-admin-key",
      API_URL: "http://backend.test",
      NEXT_PUBLIC_DYNAMIC_ENVIRONMENT_ID: "test-environment-id",
    },
  },
});
