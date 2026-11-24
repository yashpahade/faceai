import { create } from "zustand";
import { persist } from "zustand/middleware";

export const ACCENTS = [
  ["maroon", "Maroon", "#701a27"],
  ["forest", "Forest", "#1d4c30"],
  ["navy", "Navy", "#1f345c"],
];

// Browser address bar ka rang (Android Chrome / PWA)
const BAR = { light: "#701a27", dark: "#141110" };

const media = () => window.matchMedia?.("(prefers-color-scheme: dark)");

export function applyTheme({ mode, accent }) {
  const dark = mode === "dark" || (mode === "system" && media()?.matches);
  const root = document.documentElement;
  root.classList.toggle("dark", !!dark);
  root.dataset.accent = accent;
  root.style.colorScheme = dark ? "dark" : "light";
  const hex = ACCENTS.find((a) => a[0] === accent)?.[2] || BAR.light;
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", dark ? BAR.dark : hex);
}

// Per-device preference (localStorage). public/theme-init.js isi key ko page load se PEHLE padhta
// hai, taaki galat theme ka "flash" na dikhe.
// Key v2: naye design (light + maroon) pe sab devices fresh shuru hon; purani "indigo/system"
// setting carry over na ho.
export const THEME_KEY = "faceai-theme-v2";

export const useTheme = create(
  persist(
    (set, get) => ({
      mode: "light", // light | dark | system
      accent: "maroon",
      setMode: (mode) => {
        set({ mode });
        applyTheme(get());
      },
      setAccent: (accent) => {
        set({ accent });
        applyTheme(get());
      },
      cycleMode: () => {
        const next = { light: "dark", dark: "system", system: "light" }[get().mode];
        get().setMode(next);
      },
    }),
    { name: THEME_KEY },
  ),
);

// OS theme badle aur mode "system" ho to turant follow karo
media()?.addEventListener?.("change", () => applyTheme(useTheme.getState()));
