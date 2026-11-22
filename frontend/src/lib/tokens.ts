/** Resolve a design token (CSS custom property on :root) to its concrete value.
 *  SVG presentation attributes (used by Recharts) do not resolve var(), so charts read tokens through this. */
const cache = new Map<string, string>();

export function tok(name: string): string {
  if (!cache.has(name)) {
    const v = typeof document !== "undefined" ? getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim() : "";
    cache.set(name, v || "#808285");
  }
  return cache.get(name)!;
}
