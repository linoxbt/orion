"use client";

import Link from "next/link";
import { useDynamicContext, useIsLoggedIn } from "@dynamic-labs/sdk-react-core";

/** The header's right-hand side, which depends on whether anyone is signed in.
 *
 * Rendered as a fixed-width slot so the header doesn't reflow when the SDK
 * finishes loading and the label changes. */
export function HeaderAuth() {
  const isLoggedIn = useIsLoggedIn();
  const { sdkHasLoaded } = useDynamicContext();

  if (!sdkHasLoaded) {
    return <span className="h-9 w-[7.5rem]" aria-hidden="true" />;
  }

  return (
    <Link
      href={isLoggedIn ? "/dashboard" : "/login"}
      className="rounded border border-line-strong px-4 py-2 text-[13px] font-medium text-ink transition-colors hover:border-accent hover:text-accent"
    >
      {isLoggedIn ? "Dashboard" : "Sign in"}
    </Link>
  );
}
