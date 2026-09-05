/**
 * @vitest-environment jsdom
 *
 * The gate in front of every signed-in page, and the two ways it used to leave
 * somebody looking at a loader that would never resolve: an SDK that never
 * started, and a session the server had stopped accepting.
 */

import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const dynamicState = {
  isLoggedIn: false,
  sdkHasLoaded: false,
  handleLogOut: vi.fn(),
};

const router = { replace: vi.fn() };

vi.mock("@dynamic-labs/sdk-react-core", () => ({
  useIsLoggedIn: () => dynamicState.isLoggedIn,
  useDynamicContext: () => dynamicState,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => router,
  usePathname: () => "/dashboard",
}));

import { AuthGate } from "./auth-gate";

afterEach(() => {
  router.replace.mockClear();
  vi.useRealTimers();
});

describe("AuthGate", () => {
  it("shows the signed-in app once the session is established", () => {
    dynamicState.sdkHasLoaded = true;
    dynamicState.isLoggedIn = true;

    render(
      <AuthGate>
        <p>the dashboard</p>
      </AuthGate>
    );
    expect(screen.getByText("the dashboard")).toBeTruthy();
  });

  it("sends a signed-out visitor to sign in, with somewhere to come back to", async () => {
    dynamicState.sdkHasLoaded = true;
    dynamicState.isLoggedIn = false;

    render(
      <AuthGate>
        <p>the dashboard</p>
      </AuthGate>
    );

    await waitFor(() =>
      expect(router.replace).toHaveBeenCalledWith("/login?next=%2Fdashboard")
    );
    expect(screen.queryByText("the dashboard")).toBeNull();
  });

  it("waits before redirecting, because isLoggedIn is false until the SDK loads", () => {
    dynamicState.sdkHasLoaded = false;
    dynamicState.isLoggedIn = false;

    render(
      <AuthGate>
        <p>the dashboard</p>
      </AuthGate>
    );

    expect(router.replace).not.toHaveBeenCalled();
    expect(screen.getByRole("status")).toBeTruthy();
  });

  it("stops waiting on an SDK that never starts, and says so", async () => {
    vi.useFakeTimers();
    dynamicState.sdkHasLoaded = false;
    dynamicState.isLoggedIn = false;

    render(
      <AuthGate>
        <p>the dashboard</p>
      </AuthGate>
    );

    // Inside act, so the state change the timer causes is flushed before the
    // assertion looks for what it rendered.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(screen.getByText("Sign-in did not start.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Reload" })).toBeTruthy();
  });
});
