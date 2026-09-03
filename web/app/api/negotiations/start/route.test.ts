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

describe("POST /api/negotiations/start proxy", () => {
  it("forwards to the backend with the admin key injected, preserving status and body", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      status: 503,
      json: async () => ({ detail: "twilio_not_configured" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const request = new Request("http://localhost:3002/api/negotiations/start", {
      method: "POST",
      body: JSON.stringify({ provider: "Comcast", phone_number: "+15551234567", vertical: "cable_internet" }),
    });

    const response = await POST(request);
    const body = await response.json();

    expect(response.status).toBe(503);
    expect(body).toEqual({ detail: "twilio_not_configured" });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://backend.test/api/negotiations/start");
    expect(init.method).toBe("POST");
    expect(init.headers["X-Orion-Admin-Key"]).toBe("test-admin-key");
    expect(JSON.parse(init.body)).toEqual({
      provider: "Comcast",
      phone_number: "+15551234567",
      vertical: "cable_internet",
    });
  });
});
