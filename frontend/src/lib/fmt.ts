/** Formatting helpers for the enterprise app. Indian digit grouping for rupees; explicit units everywhere. */

export function groupIN(n: number): string {
  const neg = n < 0;
  const s = Math.round(Math.abs(n)).toString();
  if (s.length <= 3) return (neg ? "-" : "") + s;
  return (neg ? "-" : "") + s.slice(0, -3).replace(/\B(?=(\d{2})+(?!\d))/g, ",") + "," + s.slice(-3);
}

export const inr = (n: number | null | undefined, compact = false): string => {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  if (compact) {
    const a = Math.abs(n);
    if (a >= 1e7) return `₹${(n / 1e7).toFixed(2)} Cr`;
    if (a >= 1e5) return `₹${(n / 1e5).toFixed(1)} L`;
  }
  return `₹${groupIN(n)}`;
};

export const num = (n: number | null | undefined, d = 0): string =>
  n === null || n === undefined || Number.isNaN(n) ? "—" : d === 0 ? Math.round(n).toLocaleString("en-IN") : n.toFixed(d);

export const pct = (x: number | null | undefined, d = 1): string =>
  x === null || x === undefined || Number.isNaN(x) ? "—" : `${(x * 100).toFixed(d)}%`;

export const prob = (p: number | null | undefined): string => (p === null || p === undefined ? "—" : p.toFixed(3));

export function dateTime(ts: number | null | undefined): string {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleString("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function date(ts: number | null | undefined): string {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

export function ago(ts: number | null | undefined): string {
  if (!ts) return "—";
  const s = Date.now() / 1000 - ts;
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  if (s < 86400 * 14) return `${Math.round(s / 86400)} d ago`;
  return date(ts);
}

export const duration = (min: number | null | undefined): string => {
  if (!min) return "—";
  const h = Math.floor(min / 60);
  const m = min % 60;
  return h ? `${h} h${m ? ` ${m} min` : ""}` : `${m} min`;
};

export const BOARD: Record<string, string> = { RO: "Room only", BB: "Breakfast", HB: "Half board", FB: "Full board", AI: "All inclusive" };

export const SUPPLIER_COLOR: Record<string, string> = {
  S1: "#307FE2", S2: "#8A6D3B", S3: "#A23B72", S4: "#2F7F86", S5: "#6B7A2E", S6: "#F36B21",
};
export const SUPPLIER_NAME: Record<string, string> = {
  S1: "DirectConnect", S2: "GlobalBeds", S3: "IberiaBeds", S4: "LuxeCollection", S5: "RapidStay", S6: "NovaBeds",
};

export const plural = (n: number, one: string, many = `${one}s`) => `${num(n)} ${n === 1 ? one : many}`;
