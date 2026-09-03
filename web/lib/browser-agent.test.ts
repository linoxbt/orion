import { describe, expect, it, vi } from "vitest";

import { BrowserAgentCall } from "./browser-agent";

vi.mock("./api", () => ({
  createBrowserSession: vi.fn(),
  recordAgentTranscript: vi.fn(),
  runAgentTool: vi.fn(),
}));

/** Ending a call.
 *
 * This is the second bug in this path, so it gets tests. The first version
 * announced "ended" as the *last* line of stop(), after every teardown step -
 * so anything that threw part-way (closing an already-closed AudioContext
 * does) skipped it. The call screen closed but the button stayed on "Call in
 * progress", and worse, the microphone and websocket were never released.
 */
function callWith(parts: Partial<Record<string, unknown>>) {
  const call = new BrowserAgentCall("task-1", {});
  Object.assign(call, parts);
  return call;
}

describe("ending a call", () => {
  it("announces the end before touching anything that can throw", async () => {
    const seen: string[] = [];
    const call = new BrowserAgentCall("task-1", { onStatus: (s) => seen.push(s) });
    Object.assign(call, {
      node: {
        disconnect() {
          throw new Error("context already closed");
        },
      },
    });

    await call.stop();

    expect(seen).toContain("ended");
  });

  it("releases the microphone even when an earlier step throws", async () => {
    // The mic matters most: leaving it live keeps the browser's recording
    // indicator on after the user has hung up.
    const stopTrack = vi.fn();
    const call = callWith({
      node: {
        disconnect() {
          throw new Error("boom");
        },
      },
      stream: { getTracks: () => [{ stop: stopTrack }] },
    });

    await call.stop();

    expect(stopTrack).toHaveBeenCalled();
  });

  it("closes the socket even when the microphone step throws", async () => {
    // An open socket is a billable session nobody is watching.
    const close = vi.fn();
    const call = callWith({
      stream: {
        getTracks() {
          throw new Error("boom");
        },
      },
      ws: { readyState: 1, close },
    });

    await call.stop();

    expect(close).toHaveBeenCalled();
  });

  it("only runs once, however many things call it", async () => {
    // The End button, the socket closing and the silence timer can all arrive
    // together.
    const close = vi.fn();
    const call = callWith({ ws: { readyState: 1, close } });

    await call.stop();
    await call.stop();
    await call.stop();

    expect(close).toHaveBeenCalledTimes(1);
  });

  it("keeps an error visible instead of replacing it with a bland ending", async () => {
    const seen: string[] = [];
    const call = new BrowserAgentCall("task-1", { onStatus: (s) => seen.push(s) });

    await call.stop("error");

    expect(seen).toEqual(["error"]);
  });

  it("does not try to close an AudioContext that is already closed", async () => {
    const close = vi.fn();
    const call = callWith({ audio: { state: "closed", close } });

    await call.stop();

    expect(close).not.toHaveBeenCalled();
  });
});
