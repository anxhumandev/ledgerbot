import type { Config } from "tailwindcss";

const v = (name: string) => `var(--${name})`;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Enterprise design tokens (TBO brand, see src/index.css). Components use only these.
        brand: { DEFAULT: v("brand"), hover: v("brand-hover"), soft: v("brand-soft"), ink: v("brand-ink") },
        accent: { DEFAULT: v("accent"), hover: v("accent-hover"), soft: v("accent-soft"), ink: v("accent-ink") },
        canvas: v("canvas"),
        panel: { DEFAULT: v("panel"), 2: v("panel-2"), 3: v("panel-3") },
        edge: { DEFAULT: v("edge"), strong: v("edge-strong") },
        fg: { DEFAULT: v("fg"), 2: v("fg-2"), 3: v("fg-3") },
        ok: { DEFAULT: v("ok"), soft: v("ok-soft") },
        warn: { DEFAULT: v("warn"), soft: v("warn-soft") },
        bad: { DEFAULT: v("bad"), soft: v("bad-soft") },
        info: { DEFAULT: v("info"), soft: v("info-soft") },
        sim: { DEFAULT: v("sim"), soft: v("sim-soft") },
      },
      fontFamily: {
        sans: ['"Montserrat Variable"', "Montserrat", "system-ui", "sans-serif"],
        mono: ['"Geist Mono Variable"', "ui-monospace", "monospace"],
      },
      fontSize: { "2xs": ["11px", "16px"] },
      borderRadius: { card: "10px" },
      boxShadow: {
        card: "0 1px 2px rgba(16,24,40,.05)",
        pop: "0 8px 24px rgba(16,24,40,.12), 0 2px 6px rgba(16,24,40,.06)",
      },
    },
  },
  plugins: [],
} satisfies Config;
