import type { Config } from "tailwindcss";

const v = (name: string) => `var(--${name})`;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: v("paper"), surface: v("surface"), "surface-2": v("surface-2"), line: v("line"),
        ink: v("ink"), "ink-2": v("ink-2"), "ink-3": v("ink-3"),
        lagoon: v("lagoon"), "lagoon-soft": v("lagoon-soft"), saffron: v("saffron"), "saffron-soft": v("saffron-soft"),
        sage: v("sage"), "sage-soft": v("sage-soft"), clay: v("clay"), "clay-soft": v("clay-soft"),
        amber: v("amber"), "amber-soft": v("amber-soft"), iris: v("iris"), "iris-soft": v("iris-soft"),
        s1: "#0E5E6F", s2: "#8A6D3B", s3: "#9C4F6B", s4: "#3F5F8F", s5: "#6E7B4E", s6: "#B4683A",
      },
      fontFamily: {
        serif: ['"Instrument Serif"', "Georgia", "serif"],
        sans: ['"Geist Variable"', "system-ui", "sans-serif"],
        mono: ['"Geist Mono Variable"', "ui-monospace", "monospace"],
      },
      borderRadius: { card: "16px" },
      boxShadow: { card: "0 1px 2px rgba(21,23,28,.04), 0 8px 24px rgba(21,23,28,.06)" },
    },
  },
  plugins: [],
} satisfies Config;
