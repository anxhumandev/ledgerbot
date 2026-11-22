/** Indian digit grouping: 12345678 -> 1,23,45,678 */
export function groupIN(n: number): string {
  const neg = n < 0;
  const s = Math.round(Math.abs(n)).toString();
  if (s.length <= 3) return (neg ? "-" : "") + s;
  const last3 = s.slice(-3);
  const rest = s.slice(0, -3).replace(/\B(?=(\d{2})+(?!\d))/g, ",");
  return (neg ? "-" : "") + rest + "," + last3;
}

export function formatINR(n: number | null | undefined, opts: { compact?: boolean; decimals?: number } = {}): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  const { compact = false, decimals } = opts;
  if (compact) {
    const a = Math.abs(n);
    if (a >= 1e7) return `₹${(n / 1e7).toFixed(decimals ?? 1)} Cr`;
    if (a >= 1e5) return `₹${(n / 1e5).toFixed(decimals ?? 1)} L`;
  }
  if (decimals !== undefined && Math.abs(n) < 1000) return `₹${n.toFixed(decimals)}`;
  return `₹${groupIN(n)}`;
}

export function pct(x: number | null | undefined, d = 1): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "—";
  return `${(x * 100).toFixed(d)}%`;
}

export function num(x: number | null | undefined, d = 0): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "—";
  return d === 0 ? groupIN(x) : x.toFixed(d);
}

export function ms(x: number | null | undefined): string {
  if (x === null || x === undefined) return "—";
  return x < 1 ? `${x.toFixed(2)} ms` : x < 1000 ? `${x.toFixed(x < 10 ? 1 : 0)} ms` : `${(x / 1000).toFixed(1)} s`;
}

export const SUPPLIERS: Record<string, { name: string; color: string }> = {
  S1: { name: "DirectConnect", color: "#014C8E" },
  S2: { name: "GlobalBeds", color: "#8A6D3B" },
  S3: { name: "IberiaBeds", color: "#A23B72" },
  S4: { name: "LuxeCollection", color: "#2F7F86" },
  S5: { name: "RapidStay", color: "#6B7A2E" },
  S6: { name: "NovaBeds", color: "#E8590C" },
};

export const BOARD: Record<string, string> = { RO: "Room only", BB: "Breakfast", HB: "Half board", FB: "Full board", AI: "All inclusive" };

export const qs = new URLSearchParams(window.location.search);
export const REDUCE_MOTION = qs.get("reduceMotion") === "1" || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
export const RECORD_MODE = qs.get("record") === "1";
