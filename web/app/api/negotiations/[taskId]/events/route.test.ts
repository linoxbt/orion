import { afterEach, describe, expect, it, vi } from "vitest";
import { GET } from "./route";

// The proxy routes verify a Dynamic JWT before touching the admin key. These
// tests cover the forwarding behaviour, so the verification is stubbed to a
// signed-in user; test_route_auth.test.ts covers the rejection path for real.
vi.mock("@/lib/auth", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/auth")>();
  return { ...actual, requireUser: vi.fn().mockResolvedValue({ id: "user-1", email: "a@b.co" }) };
});


afterEach(() => {
  vi.unstubAllGlobals();
});

function sseStream(payload: string): ReadableStream<Uint8Array> {
  return new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(payload));
      controller.close();
    },
  });
}

describe("GET /api/negotiations/[taskId]/events proxy", () => {
  it("streams the backend's events through with the admin key attached", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: sseStream('data: {"type":"turn","speaker":"rep","text":"Thanks for calling."}\n\n'),
    });
    vi.stubGlobal("fetch", fetchMock);

    const request = new Request("http://localhost:3002/api/negotiations/abc-123/events");
    const response = await GET(request, { params: Promise.resolve({ taskId: "abc-123" }) });

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("text/event-stream");
    // Buffering a live transcript would defeat the point of streaming it.
    expect(response.headers.get("cache-control")).toContain("no-cache");
    expect(response.headers.get("x-accel-buffering")).toBe("no");
    expect(await response.text()).toContain("Thanks for calling.");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://backend.test/api/negotiations/abc-123/events");
    expect(init.headers["X-Orion-Admin-Key"]).toBe("test-admin-key");
    // The browser closing the EventSource must reach the backend so it drops
    // its subscriber rather than holding a queue open for a tab that's gone.
    expect(init.signal).toBe(request.signal);
  });

  it("passes through a failure from the backend as JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      body: null,
      text: async () => JSON.stringify({ detail: "not_found" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const request = new Request("http://localhost:3002/api/negotiations/nope/events");
    const response = await GET(request, { params: Promise.resolve({ taskId: "nope" }) });

    expect(response.status).toBe(404);
    expect(response.headers.get("content-type")).toBe("application/json");
    expect(JSON.parse(await response.text())).toEqual({ detail: "not_found" });
  });
});
