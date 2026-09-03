import { afterEach, describe, expect, it, vi } from "vitest";

import { GET, POST } from "./route";

// This route carries the most sensitive data in the product, so it is tested
// both ways: the forwarding path with verification stubbed, and the rejection
// path with the real verifier.
vi.mock("@/lib/auth", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/auth")>();
  return {
    ...actual,
    requireUser: vi.fn().mockResolvedValue({ id: "user-1", email: "a@b.co" }),
  };
});

const params = { params: Promise.resolve({ taskId: "abc-123" }) };

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("POST /api/negotiations/[taskId]/account-details", () => {
  it("forwards the details with the admin key attached", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      status: 200,
      json: async () => ({ task_id: "abc-123", provider: "Comcast" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(
      new Request("http://localhost:3002/api/negotiations/abc-123/account-details", {
        method: "POST",
        body: JSON.stringify({ security_pin: "4821" }),
      }),
      params
    );

    expect(response.status).toBe(200);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://backend.test/api/negotiations/abc-123/account-details");
    expect(init.headers["X-Orion-Admin-Key"]).toBe("test-admin-key");
    expect(JSON.parse(init.body)).toEqual({ security_pin: "4821" });
  });

  it("passes through the backend's refusal when the vault has no key", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      status: 503,
      json: async () => ({ detail: "account_vault_not_configured" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(
      new Request("http://localhost:3002/api/negotiations/abc-123/account-details", {
        method: "POST",
        body: JSON.stringify({ security_pin: "4821" }),
      }),
      params
    );

    expect(response.status).toBe(503);
    expect((await response.json()).detail).toBe("account_vault_not_configured");
  });
});

describe("GET /api/negotiations/[taskId]/account-details", () => {
  it("returns field names, which is all the backend exposes", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      status: 200,
      json: async () => ({ fields: ["account_number", "security_pin"] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(
      new Request("http://localhost:3002/api/negotiations/abc-123/account-details"),
      params
    );

    expect(await response.json()).toEqual({ fields: ["account_number", "security_pin"] });
  });
});
