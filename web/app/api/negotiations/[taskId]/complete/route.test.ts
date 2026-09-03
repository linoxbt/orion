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

describe("POST /api/negotiations/[taskId]/complete proxy", () => {
  it("forwards to the backend with the admin key, taskId, and body", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      status: 200,
      json: async () => ({ task_id: "abc-123", status: "completed", verified: true }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const request = new Request("http://localhost:3002/api/negotiations/abc-123/complete", {
      method: "POST",
      body: JSON.stringify({ outcome: "reduced rate", previous_rate: 89.99, new_rate: 69.99 }),
    });
    const response = await POST(request, { params: Promise.resolve({ taskId: "abc-123" }) });
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.verified).toBe(true);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://backend.test/api/negotiations/abc-123/complete");
    expect(init.method).toBe("POST");
    expect(init.headers["X-Orion-Admin-Key"]).toBe("test-admin-key");
    expect(JSON.parse(init.body)).toEqual({ outcome: "reduced rate", previous_rate: 89.99, new_rate: 69.99 });
  });
});
