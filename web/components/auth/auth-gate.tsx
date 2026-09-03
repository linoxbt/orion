"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useDynamicContext, useIsLoggedIn } from "@dynamic-labs/sdk-react-core";

/** Client-side gate for the signed-in application shell.
 *
 * This is the courtesy half of the gate - it keeps a signed-out visitor from
 * staring at an empty dashboard. The half that matters is server-side: the
 * proxy routes in app/api/negotiations/* verify the Dynamic JWT before they
 * touch the admin key, so nothing here can be bypassed into real data by
 * disabling JavaScript or editing state in a console.
 */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const isLoggedIn = useIsLoggedIn();
  const { sdkHasLoaded } = useDynamicContext();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    // Waiting for the SDK matters: before it loads, isLoggedIn is false for a
    // signed-in user too, and redirecting on that bounces people to /login on
    // every refresh.
    if (!sdkHasLoaded) return;
    if (!isLoggedIn) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [sdkHasLoaded, isLoggedIn, router, pathname]);

  if (!sdkHasLoaded || !isLoggedIn) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-muted">
          {sdkHasLoaded ? "Redirecting…" : "Loading…"}
        </p>
      </div>
    );
  }

  return <>{children}</>;
}
