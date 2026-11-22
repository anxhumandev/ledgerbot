import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, qs } from "./api";
import { duration, groupIN, inr, pct, prob } from "./fmt";
import { useSession } from "./session";

describe("formatting", () => {
  it("uses Indian digit grouping for rupees", () => {
    expect(groupIN(12345678)).toBe("1,23,45,678");
    expect(inr(164100)).toBe("₹1,64,100");
    expect(inr(31_500 * 1e7, true)).toBe("₹31500.00 Cr");
    expect(inr(null)).toBe("—");
  });
  it("formats percentages, probabilities and durations", () => {
    expect(pct(0.9996, 2)).toBe("99.96%");
    expect(prob(0.48312)).toBe("0.483");
    expect(duration(90)).toBe("1 h 30 min");
    expect(duration(45)).toBe("45 min");
  });
  it("builds query strings without empty values", () => {
    expect(qs({ a: "x", b: "", c: undefined, d: 0, e: null })).toBe("?a=x&d=0");
    expect(qs({})).toBe("");
  });
});

describe("api client", () => {
  afterEach(() => vi.restoreAllMocks());

  it("sends the workspace identity and parses JSON", async () => {
    useSession.getState().setUser("u-sara");
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ ok: true }), { headers: { "content-type": "application/json" } }));
    await expect(api("/health")).resolves.toEqual({ ok: true });
    const headers = spy.mock.calls[0][1]!.headers as Headers;
    expect(headers.get("X-LedgerBot-User")).toBe("u-sara");
  });

  it("turns structured errors into ApiError", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ error: { code: "stale_version", message: "changed", details: { version: 3 }, request_id: "req_1" } }),
      { status: 409, headers: { "content-type": "application/json" } }));
    const err = await api("/review/cases/x/decision", { json: {} }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(409);
    expect(err.code).toBe("stale_version");
    expect(err.details.version).toBe(3);
    expect(err.requestId).toBe("req_1");
  });

  it("reports an unreachable backend as a network error", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    const err = await api("/overview").catch((e) => e);
    expect(err.code).toBe("network");
  });

  it("sends an Idempotency-Key when given", async () => {
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { headers: { "content-type": "application/json" } }));
    await api("/x", { json: { a: 1 }, idempotencyKey: "k1" });
    expect((spy.mock.calls[0][1]!.headers as Headers).get("Idempotency-Key")).toBe("k1");
    expect(spy.mock.calls[0][1]!.method).toBe("POST");
  });
});
