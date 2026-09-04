"use client";

import { DynamicContextProvider } from "@dynamic-labs/sdk-react-core";

const ENVIRONMENT_ID = process.env.NEXT_PUBLIC_DYNAMIC_ENVIRONMENT_ID ?? "";

/** Dynamic is configured for email and social only.
 *
 * Orion is a consumer product about lowering household bills - the people it
 * serves are not crypto users, and no wallet connectors are installed, so no
 * wallet UI can appear. Adding one later means installing the connector package
 * and listing it here; it is not a runtime toggle.
 *
 * The environment ID is public by design (it identifies the project to
 * Dynamic's hosted widget, it does not authorize anything). Authorization
 * happens server-side, where lib/auth.ts verifies the signed JWT against
 * Dynamic's JWKS before any privileged route runs. */
export function DynamicProvider({ children }: { children: React.ReactNode }) {
  // Not guarded on a missing ENVIRONMENT_ID. Skipping the provider only moves
  // the failure: every signed-in page calls Dynamic's hooks, which throw
  // "Store not initialized" without it. An unconfigured deployment cannot
  // render an authenticated app at all, so failing the build is the honest
  // outcome. The environment id is public, so CI supplies it directly
  // (.github/workflows/ci.yml) rather than treating it as a secret.
  return (
    <DynamicContextProvider
      settings={{
        environmentId: ENVIRONMENT_ID,
        walletConnectors: [],
        initialAuthenticationMode: "connect-and-sign",
        appName: "Orion",
        // Sessions persist to localStorage by default in this SDK, so signing
        // in survives closing the browser and ends only on an explicit sign
        // out or when the person clears their site data. There is deliberately
        // no storage or expiry option set here: the SDK exposes neither, and
        // how long the issued JWT stays valid is a setting on the Dynamic
        // environment itself rather than something this app can choose.
        //
        // A suffix scopes the stored keys to this app, so a session cannot be
        // confused with another Dynamic app on the same origin.
        localStorageSuffix: "orion",
      }}
    >
      {children}
    </DynamicContextProvider>
  );
}
