import { afterEach, describe, expect, it, vi } from "vitest";
import { GET } from "./route";

// The proxy routes verify a Dynamic JWT before touching the admin key. These
// tests cover the forwarding behaviour, so the verification is stubbed to a
// signed-in user; test_route_auth.test.ts covers the rejection path for real.
vi.mock("@/lib/auth", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/auth")>();
  return {
    ...actual,
    requireUser: vi
      .fn()
      .mockResolvedValue({ id: "user-1", email: "a@b.co", token: "verified.jwt.here" }),
  };
});


afterEach(() => {
  vi.unstubAllGlobals();
});

describe("GET /api/negotiations proxy", () => {
  it("forwards to the backend with the admin key, preserving status and body", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      status: 200,
      json: async () => [{ task_id: "abc-123", provider: "Comcast" }],
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(new Request("http://localhost:3002/api/negotiations"));
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body).toEqual([{ task_id: "abc-123", provider: "Comcast" }]);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://backend.test/api/negotiations");
    expect(init.headers["X-Orion-Admin-Key"]).toBe("test-admin-key");
    expect(init.headers["X-Orion-User"]).toBe("user-1");
    // The backend verifies this token itself rather than trusting the header
    // above - without forwarding it, a configured deployment rejects
    // everything with no_verified_session.
    expect(init.headers.authorization).toBe("Bearer verified.jwt.here");
  });

  it("passes through a non-2xx status from the backend", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      status: 401,
      json: async () => ({ detail: "unauthorized" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(new Request("http://localhost:3002/api/negotiations"));
    const body = await response.json();

    expect(response.status).toBe(401);
    expect(body).toEqual({ detail: "unauthorized" });
  });
});
