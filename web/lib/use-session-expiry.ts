"use client";

import { useCallback } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useDynamicContext } from "@dynamic-labs/sdk-react-core";

import { isAuthError } from "@/lib/api";

/**
 * What to do when the server says the session is over.
 *
 * Pages used to swallow a 401 - "the AuthGate's problem" - and return, leaving
 * their data at null and the loading state on screen for good. The AuthGate
 * only redirects when Dynamic's own `isLoggedIn` flips, and that does not
 * happen when the browser still holds a token the server has stopped
 * accepting. So an expired session showed a spinner that never resolved, with
 * nothing anywhere saying why.
 *
 * Returns a handler: pass it an error, and it returns true when it took
 * responsibility for it - which is the caller's signal to stop rather than
 * render an error the person can do nothing about.
 */
export function useSessionExpiry(): (error: unknown) => boolean {
  const { handleLogOut } = useDynamicContext();
  const router = useRouter();
  const pathname = usePathname();

  return useCallback(
    (error: unknown) => {
      if (!isAuthError(error)) return false;
      // Clear the stale session first, so the login page does not bounce
      // straight back here on a token the server has already rejected.
      void Promise.resolve(handleLogOut?.()).catch(() => {});
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
      return true;
    },
    [handleLogOut, router, pathname]
  );
}
