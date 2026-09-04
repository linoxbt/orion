import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  darkMode: ["selector", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        paper: "var(--paper)",
        surface: "var(--surface)",
        surface2: "var(--surface-2)",
        ink: "var(--ink)",
        "ink-soft": "var(--ink-soft)",
        muted: "var(--muted)",
        line: "var(--line)",
        "line-strong": "var(--line-strong)",
        accent: "var(--accent)",
        "accent-hover": "var(--accent-hover)",
        "accent-soft": "var(--accent-soft)",
        "accent-ink": "var(--accent-ink)",
        pass: "var(--pass)",
        partial: "var(--partial)",
        fail: "var(--fail)",
      },
      fontFamily: {
        // One face across the product: the landing page's. `display` and
        // `sans` both resolve to it so the ~18 files already using
        // font-display keep working without a sweep, and nothing can
        // drift back to a second typeface.
        display: ["var(--font-grotesk)", "ui-sans-serif", "system-ui", "sans-serif"],
        sans: ["var(--font-grotesk)", "ui-sans-serif", "system-ui", "sans-serif"],
        grotesk: ["var(--font-grotesk)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      fontSize: {
        // A display scale distinct from the body scale - editorial layouts live
        // or die on the jump between the two.
        "display-sm": ["2rem", { lineHeight: "1.12", letterSpacing: "-0.015em" }],
        "display-md": ["2.75rem", { lineHeight: "1.06", letterSpacing: "-0.02em" }],
        "display-lg": ["4rem", { lineHeight: "1.02", letterSpacing: "-0.025em" }],
        "display-xl": ["5.25rem", { lineHeight: "0.98", letterSpacing: "-0.03em" }],
      },
      boxShadow: {
        sm: "var(--shadow-sm)",
        md: "var(--shadow-md)",
        lg: "var(--shadow-lg)",
      },
      borderRadius: {
        sm: "4px",
        DEFAULT: "8px",
        lg: "12px",
        xl: "18px",
      },
      maxWidth: {
        prose: "62ch",
      },
    },
  },
  plugins: [],
} satisfies Config;
