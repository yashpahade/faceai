/** @type {import('tailwindcss').Config} */
import colors from "tailwindcss/colors";

export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: "class", // ThemePicker: light (default) / dark / system (src/store/theme.js)
  theme: {
    extend: {
      fontFamily: {
        // Body: OS ka apna font (Windows: Segoe UI, Android: Roboto, iOS: SF). Tez, familiar, koi download nahi.
        sans: ["system-ui", "-apple-system", '"Segoe UI"', "Roboto", '"Helvetica Neue"', "Arial", "sans-serif"],
        // Headings: serif -> register / certificate jaisa institutional feel (maroon ke saath jachta hai)
        display: ['"Iowan Old Style"', '"Palatino Linotype"', "Palatino", '"Book Antiqua"', "Georgia", "serif"],
      },
      colors: {
        // Cool slate -> warm stone: poori app ek saath garam kaagaz jaisi tone mein (har file edit kiye bina)
        slate: colors.stone,
        // Accent themes: colors CSS variables se (index.css), runtime pe badalte hain
        brand: Object.fromEntries(
          [50, 100, 200, 300, 400, 500, 600, 700, 800, 900].map((k) => [k, `rgb(var(--brand-${k}) / <alpha-value>)`]),
        ),
        accent: Object.fromEntries([400, 500, 600].map((k) => [k, `rgb(var(--accent-${k}) / <alpha-value>)`])),
        paper: { DEFAULT: "#f7f4ef", deep: "#efe9e1" },
        // Dark mode: neela-kaala nahi, garam kaala
        ink: { 950: "#141110", 900: "#1b1714", 850: "#221d19", 800: "#2b2520" },
      },
      boxShadow: {
        // Halki, asli kaagaz jaisi parchhai. Koi rangeen "glow" nahi.
        soft: "0 1px 2px rgba(41,37,36,.06)",
        lift: "0 1px 2px rgba(41,37,36,.06), 0 4px 12px -6px rgba(41,37,36,.12)",
        glow: "0 1px 2px rgba(41,37,36,.08)",
      },
      // Bahut gol kone = "template" look. Sab thode kam gol (avatars/chips ke liye rounded-full waisa hi).
      borderRadius: { xl: "0.5rem", "2xl": "0.625rem", "2.5xl": "0.75rem", "3xl": "0.75rem" },
      keyframes: {
        shimmer: { "100%": { transform: "translateX(100%)" } },
        scan: { "0%": { top: "8%" }, "50%": { top: "88%" }, "100%": { top: "8%" } },
        ring: { "0%": { transform: "scale(1)", opacity: ".7" }, "100%": { transform: "scale(1.12)", opacity: "0" } },
      },
      animation: {
        shimmer: "shimmer 1.6s infinite",
        scan: "scan 2.6s ease-in-out infinite",
        ring: "ring 1.8s ease-out infinite",
      },
    },
  },
  plugins: [],
};
