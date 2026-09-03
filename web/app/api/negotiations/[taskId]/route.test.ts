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

describe("GET /api/negotiations/[taskId] proxy", () => {
  it("forwards to the backend with the admin key and taskId", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      status: 200,
      json: async () => ({ task_id: "abc-123", provider: "Comcast" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const request = new Request("http://localhost:3002/api/negotiations/abc-123");
    const response = await GET(request, { params: Promise.resolve({ taskId: "abc-123" }) });
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.task_id).toBe("abc-123");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://backend.test/api/negotiations/abc-123");
    expect(init.headers["X-Orion-Admin-Key"]).toBe("test-admin-key");
  });

  it("passes through a 404 from the backend", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      status: 404,
      json: async () => ({ detail: "not_found" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const request = new Request("http://localhost:3002/api/negotiations/does-not-exist");
    const response = await GET(request, { params: Promise.resolve({ taskId: "does-not-exist" }) });
    const body = await response.json();

    expect(response.status).toBe(404);
    expect(body).toEqual({ detail: "not_found" });
  });
});
