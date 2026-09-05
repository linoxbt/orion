/**
 * The transcript that grew a fresh copy of itself every minute.
 *
 * The backend replays what it has already sent to every new subscriber, so a
 * browser that lands mid-call sees the whole conversation. The platform cuts
 * the streaming function about once a minute, so during a normal call the
 * client reconnects several times - and each replay was appended again, until
 * the transcript showed every turn four or five times.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("./auth-client", () => ({
  authHeaders: (extra: HeadersInit = {}) => ({ ...extra, authorization: "Bearer test-token" }),
}));

import { subscribeToNegotiationEvents, type LiveEvent } from "./api";

/** A stream that delivers `frames`, ends, and on the next connection delivers
 * them again - which is exactly what a reconnect looks like. */
function streamingFetch(frames: string[], connections: { n: number }) {
  return vi.fn().mockImplementation(async () => {
    connections.n += 1;
    const encoder = new TextEncoder();
    const queue = [...frames];
    return {
      ok: true,
      status: 200,
      body: {
        getReader() {
          return {
            async read() {
              const next = queue.shift();
              if (next === undefined) return { done: true, value: undefined };
              return { done: false, value: encoder.encode(next) };
            },
          };
        },
      },
    };
  });
}

const TURN = (seq: number, text: string) =>
  `data: ${JSON.stringify({ type: "turn", speaker: "rep", text, seq })}\n\n`;

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("subscribeToNegotiationEvents", () => {
  it("delivers each turn once", async () => {
    const connections = { n: 0 };
    vi.stubGlobal("fetch", streamingFetch([TURN(1, "hello"), TURN(2, "one moment")], connections));

    const seen: LiveEvent[] = [];
    const stop = subscribeToNegotiationEvents("t1", (event) => seen.push(event));
    await vi.waitFor(() => expect(seen.length).toBe(2));
    stop();

    expect(seen.map((e) => (e as { text: string }).text)).toEqual(["hello", "one moment"]);
  });

  it("does not deliver the replay again after a reconnect", async () => {
    const connections = { n: 0 };
    // Every connection replays the same two turns, as the backend does.
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async () => {
        connections.n += 1;
        const encoder = new TextEncoder();
        const queue = [TURN(1, "hello"), TURN(2, "one moment")];
        return {
          ok: true,
          status: 200,
          body: {
            getReader: () => ({
              async read() {
                const next = queue.shift();
                if (next === undefined) return { done: true, value: undefined };
                return { done: false, value: encoder.encode(next) };
              },
            }),
          },
        };
      })
    );

    const seen: LiveEvent[] = [];
    const stop = subscribeToNegotiationEvents("t1", (event) => seen.push(event));
    await vi.waitFor(() => expect(seen.length).toBe(2));
    // Wait long enough for at least one reconnect and its replay.
    await vi.waitFor(() => expect(connections.n).toBeGreaterThan(1), { timeout: 4000 });
    await new Promise((resolve) => setTimeout(resolve, 50));
    stop();

    expect(seen.length).toBe(2);
  }, 10000);

  it("splits frames that arrive across chunk boundaries", async () => {
    const connections = { n: 0 };
    const whole = TURN(1, "hello");
    vi.stubGlobal(
      "fetch",
      streamingFetch([whole.slice(0, 12), whole.slice(12)], connections)
    );

    const seen: LiveEvent[] = [];
    const stop = subscribeToNegotiationEvents("t1", (event) => seen.push(event));
    await vi.waitFor(() => expect(seen.length).toBe(1));
    stop();
    expect((seen[0] as { text: string }).text).toBe("hello");
  });

  it("stops for good on a 401 rather than reconnecting into a dead session", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 401, body: null });
    vi.stubGlobal("fetch", fetchMock);

    const stop = subscribeToNegotiationEvents("t1", () => {});
    await new Promise((resolve) => setTimeout(resolve, 100));
    stop();

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
