/**
 * @vitest-environment jsdom
 *
 * The page that loaded forever.
 *
 * A 401 used to be swallowed - "the AuthGate's problem" - which left the data
 * at null and the loading state on screen permanently. The AuthGate only
 * redirects when Dynamic's own isLoggedIn flips, and that does not happen when
 * the browser still holds a token the server has stopped accepting.
 */

import { renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const handleLogOut = vi.fn();
const router = { replace: vi.fn() };

vi.mock("@dynamic-labs/sdk-react-core", () => ({
  useDynamicContext: () => ({ handleLogOut }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => router,
  usePathname: () => "/account",
}));

import { ApiError } from "@/lib/api";
import { useSessionExpiry } from "./use-session-expiry";

afterEach(() => {
  router.replace.mockClear();
  handleLogOut.mockClear();
});

describe("useSessionExpiry", () => {
  it("takes responsibility for a 401 and sends the person to sign in", () => {
    const { result } = renderHook(() => useSessionExpiry());

    const handled = result.current(new ApiError(401, "not_authenticated"));

    expect(handled).toBe(true);
    expect(router.replace).toHaveBeenCalledWith("/login?next=%2Faccount");
  });

  it("clears the dead session, so signing in again does not bounce straight back", () => {
    const { result } = renderHook(() => useSessionExpiry());
    result.current(new ApiError(401, "not_authenticated"));
    expect(handleLogOut).toHaveBeenCalled();
  });

  it("leaves a real error to the caller to show", () => {
    const { result } = renderHook(() => useSessionExpiry());

    const handled = result.current(new ApiError(503, "supabase_not_configured"));

    expect(handled).toBe(false);
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("leaves an ordinary failure alone", () => {
    const { result } = renderHook(() => useSessionExpiry());
    expect(result.current(new Error("network down"))).toBe(false);
    expect(router.replace).not.toHaveBeenCalled();
  });
});
