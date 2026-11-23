import { create } from "zustand";
import { persist } from "zustand/middleware";

export const ACCENTS = [
  ["indigo", "Indigo", "#6366f1"],
  ["ocean", "Ocean", "#0ea5e9"],
  ["emerald", "Emerald", "#10b981"],
  ["sunset", "Sunset", "#f97316"],
  ["rose", "Rose", "#f43f5e"],
];

const media = () => window.matchMedia?.("(prefers-color-scheme: dark)");

export function applyTheme({ mode, accent }) {
  const dark = mode === "dark" || (mode === "system" && media()?.matches);
  const root = document.documentElement;
  root.classList.toggle("dark", !!dark);
  root.dataset.accent = accent;
  root.style.colorScheme = dark ? "dark" : "light";
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", dark ? "#070a13" : ACCENTS.find((a) => a[0] === accent)?.[2] || "#6366f1");
}

// Per-device preference (localStorage). public/theme-init.js isi key ko page load se PEHLE padhta
// hai, taaki galat theme ka "flash" na dikhe.
export const useTheme = create(
  persist(
    (set, get) => ({
      mode: "system", // system | light | dark
      accent: "indigo",
      setMode: (mode) => {
        set({ mode });
        applyTheme(get());
      },
      setAccent: (accent) => {
        set({ accent });
        applyTheme(get());
      },
      cycleMode: () => {
        const next = { system: "light", light: "dark", dark: "system" }[get().mode];
        get().setMode(next);
      },
    }),
    { name: "faceai-theme" },
  ),
);

// OS theme badle aur mode "system" ho to turant follow karo
media()?.addEventListener?.("change", () => applyTheme(useTheme.getState()));
