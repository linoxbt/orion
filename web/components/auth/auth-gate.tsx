"use client";

import { useEffect, useState } from "react";
import { Loading } from "@/components/loading";
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
  const [stalled, setStalled] = useState(false);

  useEffect(() => {
    if (sdkHasLoaded) return;
    const timer = window.setTimeout(() => setStalled(true), 9000);
    return () => window.clearTimeout(timer);
  }, [sdkHasLoaded]);
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
    // A gate that waits forever looks identical to a broken page. If the SDK
    // has not started after a few seconds it is not going to, and saying so
    // with a way out beats an animation that never resolves.
    if (stalled && !sdkHasLoaded) {
      return (
        <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 px-6 text-center">
          <p className="text-[15px] text-ink">Sign-in did not start.</p>
          <p className="max-w-sm text-[14px] leading-relaxed text-ink-soft">
            This usually clears on a reload. If it keeps happening, a browser
            extension blocking third-party scripts is the usual cause.
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-2 rounded bg-accent px-5 py-2.5 text-[14px] font-medium text-accent-ink transition-colors hover:bg-accent-hover"
          >
            Reload
          </button>
        </div>
      );
    }

    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Loading label={sdkHasLoaded ? "Redirecting" : "Starting"} />
      </div>
    );
  }

  return <>{children}</>;
}
