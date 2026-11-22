import { useSession } from "./session";

/** Structured API error: the backend returns {"error": {code, message, details, request_id}}. */
export class ApiError extends Error {
  status: number;
  code: string;
  details: Record<string, any>;
  requestId?: string;
  constructor(status: number, code: string, message: string, details: Record<string, any> = {}, requestId?: string) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

type Init = RequestInit & { json?: unknown; idempotencyKey?: string };

export async function api<T = any>(path: string, init?: Init): Promise<T> {
  const { json, idempotencyKey, ...rest } = init ?? {};
  const headers = new Headers(rest.headers);
  headers.set("X-LedgerBot-User", useSession.getState().userId);
  if (json !== undefined) headers.set("Content-Type", "application/json");
  if (idempotencyKey) headers.set("Idempotency-Key", idempotencyKey);
  let r: Response;
  try {
    r = await fetch(`/api${path}`, {
      ...rest,
      headers,
      method: rest.method ?? (json !== undefined ? "POST" : "GET"),
      body: json !== undefined ? JSON.stringify(json) : rest.body,
    });
  } catch {
    throw new ApiError(0, "network", "The LedgerBot API is not reachable. Check that the backend is running.");
  }
  if (!r.ok) {
    let body: any = null;
    try {
      body = await r.json();
    } catch {
      /* non-JSON error */
    }
    const e = body?.error;
    if (e) throw new ApiError(r.status, e.code, e.message, e.details, e.request_id);
    throw new ApiError(r.status, "http_error", body?.detail ?? `Request failed (${r.status})`);
  }
  const ct = r.headers.get("content-type") ?? "";
  return (ct.includes("application/json") ? r.json() : (r.text() as any)) as Promise<T>;
}

export const post = <T = any>(path: string, json: unknown = {}, init?: Init) => api<T>(path, { ...init, json });
export const put = <T = any>(path: string, json: unknown) => api<T>(path, { method: "PUT", json });
export const patch = <T = any>(path: string, json: unknown) => api<T>(path, { method: "PATCH", json });

export function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") u.set(k, String(v));
  const s = u.toString();
  return s ? `?${s}` : "";
}

export const newIdempotencyKey = () =>
  (globalThis.crypto && "randomUUID" in globalThis.crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`);
