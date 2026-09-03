import { afterEach, describe, expect, it, vi } from "vitest";
import { POST } from "./route";

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

describe("POST /api/negotiations/[taskId]/call proxy", () => {
  it("forwards to the backend with the admin key and taskId", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      status: 200,
      json: async () => ({ task_id: "abc-123", status: "calling", call_sid: "CA_test" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const request = new Request("http://localhost:3002/api/negotiations/abc-123/call", { method: "POST" });
    const response = await POST(request, { params: Promise.resolve({ taskId: "abc-123" }) });
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.status).toBe("calling");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://backend.test/api/negotiations/abc-123/call");
    expect(init.method).toBe("POST");
    expect(init.headers["X-Orion-Admin-Key"]).toBe("test-admin-key");
  });

  it("passes through a 409 when the session isn't authorized yet", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      status: 409,
      json: async () => ({ detail: "not_authorized" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const request = new Request("http://localhost:3002/api/negotiations/abc-123/call", { method: "POST" });
    const response = await POST(request, { params: Promise.resolve({ taskId: "abc-123" }) });
    const body = await response.json();

    expect(response.status).toBe(409);
    expect(body).toEqual({ detail: "not_authorized" });
  });
});
