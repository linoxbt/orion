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
  return (
    <DynamicContextProvider
      settings={{
        environmentId: ENVIRONMENT_ID,
        walletConnectors: [],
        initialAuthenticationMode: "connect-and-sign",
        appName: "Orion",
      }}
    >
      {children}
    </DynamicContextProvider>
  );
}
