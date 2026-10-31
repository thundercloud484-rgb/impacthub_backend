import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans:    ["var(--font-sans)",    "system-ui", "sans-serif"],
        display: ["var(--font-display)", "Georgia",   "serif"],
      },
      colors: {
        /* === Civic brand palette === */
        civic: {
          50:  "#DDF3EE",   // soft tint (active state bg)
          100: "#B8E6DD",
          200: "#8DD4CA",
          300: "#60C2B6",
          400: "#35B1A2",
          500: "#0F9E8F",   // mid teal
          600: "#0F766E",   // primary teal  ← main brand colour
          700: "#0B5A54",   // primary-dark  ← hover
          800: "#0A3B38",   // brand-deep    ← login panel
          900: "#062422",
          950: "#031614",
        },
        /* === Semantic aliases (map to CSS vars) === */
        "civic-bg":     "#F5F8F7",
        "civic-border": "#E3EBE9",
        "civic-text":   "#0E2A2B",
        "civic-muted":  "#4A6061",
        "civic-tint":   "#DDF3EE",
      },
      backgroundImage: {
        "gradient-radial":   "radial-gradient(var(--tw-gradient-stops))",
        "gradient-primary":  "linear-gradient(135deg, #0F766E 0%, #0A3B38 100%)",
        "gradient-tint":     "linear-gradient(135deg, #DDF3EE 0%, #B8E6DD 100%)",
      },
      boxShadow: {
        soft:      "0 1px 3px rgba(14,42,43,0.06), 0 1px 2px rgba(14,42,43,0.04)",
        medium:    "0 4px 16px rgba(14,42,43,0.10), 0 1px 4px rgba(14,42,43,0.06)",
        large:     "0 8px 32px rgba(14,42,43,0.12), 0 2px 8px rgba(14,42,43,0.06)",
        green:     "0 1px 4px rgba(15,118,110,0.35)",
        "green-lg":"0 2px 10px rgba(15,118,110,0.40)",
        inner:     "inset 0 1px 3px rgba(14,42,43,0.06)",
      },
      borderRadius: {
        "card": "20px",
      },
      animation: {
        "fade-in":  "fadeIn 0.3s ease-out",
        "slide-up": "slideUp 0.3s ease-out",
        "scale-in": "scaleIn 0.2s ease-out",
        "float":    "float 4s ease-in-out infinite",
      },
      keyframes: {
        fadeIn:  { "0%": { opacity: "0" },                               "100%": { opacity: "1" } },
        slideUp: { "0%": { transform: "translateY(16px)", opacity: "0" }, "100%": { transform: "translateY(0)", opacity: "1" } },
        scaleIn: { "0%": { transform: "scale(0.95)", opacity: "0" },     "100%": { transform: "scale(1)",    opacity: "1" } },
        float:   { "0%, 100%": { transform: "translateY(0)" }, "50%": { transform: "translateY(-6px)" } },
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
export default config;
