import { afterEach, describe, expect, it, vi } from "vitest";

// Deliberately NOT mocking @/lib/auth: this file exists to prove the gate is
// real. The sibling route tests stub verification to cover forwarding, so
// without this, a regression that removed the gate entirely would still leave
// a fully green suite.
import { GET as listNegotiations } from "./route";
import { POST as startNegotiation } from "./start/route";
import { POST as placeCall } from "./[taskId]/call/route";
import { POST as chargeNegotiation } from "./[taskId]/charge/route";
import { GET as negotiationEvents } from "./[taskId]/events/route";
import { POST as saveAccountDetails } from "./[taskId]/account-details/route";

const params = { params: Promise.resolve({ taskId: "abc-123" }) };

afterEach(() => {
  vi.unstubAllGlobals();
});

function noFetchAllowed() {
  // If a handler reaches the backend without a verified session, that's the
  // bug - fail loudly rather than letting a stubbed 200 hide it.
  const fetchMock = vi.fn(() => {
    throw new Error("handler called the backend without authenticating");
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("proxy routes reject unauthenticated callers", () => {
  it("refuses to list negotiations", async () => {
    const fetchMock = noFetchAllowed();
    const res = await listNegotiations(new Request("http://localhost:3002/api/negotiations"));
    expect(res.status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("refuses to start a negotiation", async () => {
    const fetchMock = noFetchAllowed();
    const res = await startNegotiation(
      new Request("http://localhost:3002/api/negotiations/start", {
        method: "POST",
        body: JSON.stringify({ provider: "Comcast" }),
      })
    );
    expect(res.status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("refuses to place a call - the expensive one", async () => {
    const fetchMock = noFetchAllowed();
    const res = await placeCall(
      new Request("http://localhost:3002/api/negotiations/abc-123/call", { method: "POST" }),
      params
    );
    expect(res.status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("refuses to charge a card", async () => {
    const fetchMock = noFetchAllowed();
    const res = await chargeNegotiation(
      new Request("http://localhost:3002/api/negotiations/abc-123/charge", { method: "POST" }),
      params
    );
    expect(res.status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("refuses to open the live call feed", async () => {
    const fetchMock = noFetchAllowed();
    const res = await negotiationEvents(
      new Request("http://localhost:3002/api/negotiations/abc-123/events"),
      params
    );
    expect(res.status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("refuses to accept account verification details - the most sensitive route", async () => {
    const fetchMock = noFetchAllowed();
    const res = await saveAccountDetails(
      new Request("http://localhost:3002/api/negotiations/abc-123/account-details", {
        method: "POST",
        body: JSON.stringify({ security_pin: "4821" }),
      }),
      params
    );
    expect(res.status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects a malformed bearer token rather than trusting it", async () => {
    const fetchMock = noFetchAllowed();
    const res = await listNegotiations(
      new Request("http://localhost:3002/api/negotiations", {
        headers: { authorization: "Bearer not.a.real.jwt" },
      })
    );
    expect(res.status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
