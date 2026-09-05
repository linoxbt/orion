/**
 * @vitest-environment jsdom
 *
 * Every call made, playable and downloadable.
 *
 * The failure this guards against is quiet: a negotiation that was dialled
 * three times showing one recording, or none at all, with nothing saying a
 * call had happened.
 */

import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/auth-client", () => ({
  authHeaders: (extra: HeadersInit = {}) => ({ ...extra, authorization: "Bearer test-token" }),
}));

import { CallHistory } from "./call-history";

function mockCalls(calls: unknown[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => calls })
  );
}

const A_CALL = {
  call_sid: "CA1",
  started_at: "2026-09-05T10:00:00+00:00",
  answered: true,
  ended_at: null,
  end_reason: "completed",
  duration_seconds: 184,
  outcome: "Agreed 69.99 for 12 months.",
  url: "https://storage.example/one.mp3",
  download_name: "orion-comcast.mp3",
};

describe("CallHistory", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("lists every attempt, not just the last", async () => {
    mockCalls([A_CALL, { ...A_CALL, call_sid: "CA2", url: null, answered: false, outcome: null }]);
    render(<CallHistory taskId="t1" />);

    await waitFor(() => expect(screen.getByText("Attempt 2")).toBeTruthy());
    expect(screen.getByText("Attempt 1")).toBeTruthy();
  });

  it("offers a download for a call that has a recording", async () => {
    mockCalls([A_CALL]);
    render(<CallHistory taskId="t1" />);

    const link = await screen.findByLabelText("Download this recording");
    expect(link.getAttribute("href")).toBe("https://storage.example/one.mp3");
    expect(link.getAttribute("download")).toBe("orion-comcast.mp3");
  });

  it("disables play on an attempt with no recording", async () => {
    mockCalls([{ ...A_CALL, url: null }]);
    render(<CallHistory taskId="t1" />);

    const play = await screen.findByLabelText("Play this call");
    expect((play as HTMLButtonElement).disabled).toBe(true);
  });

  it("says plainly when no call has been made", async () => {
    mockCalls([]);
    render(<CallHistory taskId="t1" />);
    await waitFor(() => expect(screen.getByText(/No calls yet/)).toBeTruthy());
  });

  it("shows the outcome the agent recorded", async () => {
    mockCalls([A_CALL]);
    render(<CallHistory taskId="t1" />);
    expect(await screen.findByText("Agreed 69.99 for 12 months.")).toBeTruthy();
  });
});
