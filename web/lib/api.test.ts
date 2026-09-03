import { afterEach, describe, expect, it, vi } from "vitest";
import {
  chargeNegotiation,
  completeNegotiation,
  getHealth,
  getNegotiation,
  ingestBill,
  listNegotiations,
  listPlaybooks,
  placeCall,
  startNegotiation,
} from "./api";

// api.ts attaches the Dynamic session token to every proxied call. The SDK it
// comes from is browser-only, and these tests are about request shape, so the
// header is stubbed to a fixed token.
vi.mock("./auth-client", () => ({
  authHeaders: (extra: HeadersInit = {}) => ({ ...extra, authorization: "Bearer test-token" }),
}));

function mockFetchOnce(status: number, body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("read endpoints hit the backend directly", () => {
  it("getHealth", async () => {
    const fetchMock = mockFetchOnce(200, { ok: true, version: "0.1.0" });
    const result = await getHealth();
    expect(result).toEqual({ ok: true, version: "0.1.0" });
    expect(fetchMock.mock.calls[0][0]).toBe("http://localhost:8080/health");
  });

  it("listPlaybooks", async () => {
    const fetchMock = mockFetchOnce(200, []);
    await listPlaybooks();
    expect(fetchMock.mock.calls[0][0]).toBe("http://localhost:8080/api/playbooks");
  });
});

describe("endpoints gated by the admin key go through same-origin proxy routes, not the backend directly", () => {
  it("startNegotiation", async () => {
    const fetchMock = mockFetchOnce(200, { task_id: "abc" });
    await startNegotiation({ provider: "Comcast", phone_number: "+15551234567", vertical: "cable_internet" });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/negotiations/start");
  });

  it("getNegotiation", async () => {
    const fetchMock = mockFetchOnce(200, { task_id: "abc" });
    await getNegotiation("abc");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/negotiations/abc");
  });

  it("listNegotiations", async () => {
    const fetchMock = mockFetchOnce(200, []);
    await listNegotiations();
    expect(fetchMock.mock.calls[0][0]).toBe("/api/negotiations");
  });

  it("completeNegotiation", async () => {
    const fetchMock = mockFetchOnce(200, { task_id: "abc" });
    await completeNegotiation("abc", { outcome: "reduced rate", previous_rate: 89.99, new_rate: 69.99 });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/negotiations/abc/complete");
  });

  it("placeCall", async () => {
    const fetchMock = mockFetchOnce(200, { task_id: "abc" });
    await placeCall("abc");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/negotiations/abc/call");
  });

  it("chargeNegotiation", async () => {
    const fetchMock = mockFetchOnce(200, { task_id: "abc" });
    await chargeNegotiation("abc");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/negotiations/abc/charge");
  });
});

describe("ingestBill", () => {
  it("posts through the same-origin proxy, not straight to the backend", async () => {
    // Calling the backend cross-origin meant a 500 arrived without CORS
    // headers, so the browser could only report "Failed to fetch" and the real
    // cause was invisible. Same-origin removes CORS from the picture.
    const fetchMock = mockFetchOnce(200, { provider: "Comcast" });
    const file = new File(["fake bill"], "bill.pdf", { type: "application/pdf" });

    const result = await ingestBill(file);

    expect(result).toEqual({ provider: "Comcast" });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/bills/ingest");
    expect(url).not.toContain("http");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    // Extraction spends Gemini quota, so it is gated like every other route.
    expect((init.headers as Record<string, string>).authorization).toBe("Bearer test-token");
  });

  it("sends the filename, which the backend uses to pick the MIME type", async () => {
    // Browsers report application/octet-stream for a .PDF often enough that
    // trusting content_type made Gemini reject valid bills with a 400.
    const fetchMock = mockFetchOnce(200, { provider: "Comcast" });
    await ingestBill(new File(["x"], "October bill.pdf", { type: "application/octet-stream" }));

    const body = fetchMock.mock.calls[0][1].body as FormData;
    expect(body.get("filename")).toBe("October bill.pdf");
  });
});

describe("error handling", () => {
  it("throws with the backend's detail on a non-2xx response", async () => {
    mockFetchOnce(503, { detail: "gemini_not_configured" });
    await expect(getHealth()).rejects.toMatchObject({ status: 503, detail: "gemini_not_configured" });
  });

  it("falls back to a generic detail when the error body is empty/unparseable", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => {
        throw new Error("not json");
      },
    });
    vi.stubGlobal("fetch", fetchMock);
    await expect(getHealth()).rejects.toMatchObject({ status: 500, detail: "request_failed_500" });
  });
});
