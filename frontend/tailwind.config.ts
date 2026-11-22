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
        navy: v("navy"),
        s1: "#014C8E", s2: "#8A6D3B", s3: "#A23B72", s4: "#2F7F86", s5: "#6B7A2E", s6: "#E8590C",
      },
      fontFamily: {
        serif: ['"Raleway Variable"', "Arial", "sans-serif"], // display: TBO's brand face
        sans: ['"Inter Variable"', "system-ui", "sans-serif"], // body and data: built for screen legibility
        mono: ['"Geist Mono Variable"', "ui-monospace", "monospace"],
      },
      borderRadius: { card: "16px" },
      boxShadow: { card: "0 1px 2px rgba(1,40,80,.06), 0 6px 18px rgba(1,40,80,.07)" },
    },
  },
  plugins: [],
} satisfies Config;
