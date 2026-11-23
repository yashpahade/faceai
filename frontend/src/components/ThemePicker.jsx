import { motion } from "framer-motion";

import { ACCENTS, useTheme } from "../store/theme";
import { spring } from "./motion";

const MODES = [
  ["light", "Light", "M12 4V2m0 20v-2m8-8h2M2 12h2m13.66-5.66 1.41-1.41M4.93 19.07l1.41-1.41m0-11.32L4.93 4.93m14.14 14.14-1.41-1.41M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10z"],
  ["dark", "Dark", "M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"],
  ["system", "System", "M4 5h16v11H4zM8 20h8M12 16v4"],
];

function Icon({ d, className = "h-4 w-4" }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={d} />
    </svg>
  );
}

// Full picker: Profile page "Appearance" card
export default function ThemePicker() {
  const { mode, accent, setMode, setAccent } = useTheme();
  return (
    <div className="space-y-5">
      <div>
        <p className="label">Mode</p>
        <div className="grid grid-cols-3 gap-1 rounded-2xl bg-slate-100/80 p-1 dark:bg-white/5" role="radiogroup" aria-label="Color mode">
          {MODES.map(([k, label, d]) => (
            <button key={k} role="radio" aria-checked={mode === k} onClick={() => setMode(k)} className={`relative flex min-h-[44px] items-center justify-center gap-2 rounded-xl text-sm font-semibold ${mode === k ? "text-slate-900 dark:text-white" : "text-slate-500"}`}>
              {mode === k && <motion.span layoutId="mode-pill" transition={spring} className="absolute inset-0 rounded-xl bg-white shadow-soft dark:bg-white/10" />}
              <span className="relative flex items-center gap-2">
                <Icon d={d} /> {label}
              </span>
            </button>
          ))}
        </div>
      </div>
      <div>
        <p className="label">Accent color</p>
        <div className="flex flex-wrap gap-3" role="radiogroup" aria-label="Accent color">
          {ACCENTS.map(([k, label, hex]) => (
            <button key={k} role="radio" aria-checked={accent === k} onClick={() => setAccent(k)} className="group flex flex-col items-center gap-1.5" title={label}>
              <span className="relative flex h-11 w-11 items-center justify-center rounded-full ring-2 ring-offset-2 ring-offset-white transition dark:ring-offset-ink-850" style={{ background: hex, "--tw-ring-color": accent === k ? hex : "transparent" }}>
                {accent === k && (
                  <motion.svg initial={{ scale: 0 }} animate={{ scale: 1 }} transition={spring} viewBox="0 0 24 24" className="h-5 w-5 text-white" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" aria-hidden="true">
                    <path d="M5 13l4 4L19 7" />
                  </motion.svg>
                )}
              </span>
              <span className={`text-xs font-medium ${accent === k ? "text-slate-900 dark:text-white" : "text-slate-500"}`}>{label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// Compact: header/sidebar quick toggle (cycles light -> dark -> system)
export function ThemeToggle({ className = "" }) {
  const { mode, cycleMode } = useTheme();
  const [, label, d] = MODES.find((m) => m[0] === mode);
  return (
    <button onClick={cycleMode} className={`flex h-9 w-9 items-center justify-center rounded-xl text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 dark:hover:bg-white/10 dark:hover:text-white ${className}`} aria-label={`Theme: ${label} (change)`} title={`Theme: ${label}`}>
      <motion.span key={mode} initial={{ rotate: -90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} transition={spring}>
        <Icon d={d} className="h-5 w-5" />
      </motion.span>
    </button>
  );
}
