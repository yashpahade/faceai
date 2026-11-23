/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: "media",
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter Variable"', "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
      },
      colors: {
        brand: {
          50: "#eef2ff",
          100: "#e0e7ff",
          200: "#c7d2fe",
          300: "#a5b4fc",
          400: "#818cf8",
          500: "#6366f1",
          600: "#4f46e5",
          700: "#4338ca",
          800: "#3730a3",
          900: "#312e81",
        },
        accent: { 400: "#c084fc", 500: "#a855f7", 600: "#9333ea" },
        ink: { 950: "#070a13", 900: "#0b1020", 850: "#10162a", 800: "#151c33" },
      },
      boxShadow: {
        soft: "0 1px 2px rgba(15,23,42,.04), 0 8px 24px -8px rgba(15,23,42,.12)",
        lift: "0 2px 4px rgba(15,23,42,.06), 0 20px 40px -16px rgba(79,70,229,.35)",
        glow: "0 0 0 1px rgba(129,140,248,.25), 0 10px 40px -10px rgba(99,102,241,.55)",
      },
      borderRadius: { "2.5xl": "1.25rem" },
      keyframes: {
        shimmer: { "100%": { transform: "translateX(100%)" } },
        scan: { "0%": { top: "8%" }, "50%": { top: "88%" }, "100%": { top: "8%" } },
        aurora: {
          "0%,100%": { transform: "translate(0,0) scale(1)" },
          "33%": { transform: "translate(6%,-4%) scale(1.08)" },
          "66%": { transform: "translate(-5%,5%) scale(.95)" },
        },
        ring: { "0%": { transform: "scale(1)", opacity: ".7" }, "100%": { transform: "scale(1.18)", opacity: "0" } },
      },
      animation: {
        shimmer: "shimmer 1.6s infinite",
        scan: "scan 2.6s ease-in-out infinite",
        aurora: "aurora 18s ease-in-out infinite",
        "aurora-slow": "aurora 26s ease-in-out infinite reverse",
        ring: "ring 1.8s ease-out infinite",
      },
    },
  },
  plugins: [],
};
