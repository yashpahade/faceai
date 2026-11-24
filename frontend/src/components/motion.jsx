// Motion toolkit. Sab animations `MotionConfig reducedMotion="user"` ke andar chalti hain:
// OS mein "reduce motion" on ho to sirf opacity fades, koi movement nahi (vestibular a11y).
import { animate, AnimatePresence, motion, useInView, useMotionValue, useTransform } from "framer-motion";
import { useEffect, useRef } from "react";
import { create } from "zustand";

export const ease = [0.22, 1, 0.36, 1]; // "easeOutQuint"-like: tez start, makhmali stop
export const spring = { type: "spring", stiffness: 420, damping: 34 };

export function PageTransition({ children }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2, ease }}
    >
      {children}
    </motion.div>
  );
}

const staggerParent = { hidden: {}, show: { transition: { staggerChildren: 0.03 } } };
const staggerChild = {
  hidden: { opacity: 0, y: 4 },
  show: { opacity: 1, y: 0, transition: { duration: 0.25, ease } },
};

export function Stagger({ as = "div", className, children }) {
  const C = motion[as];
  return (
    <C className={className} variants={staggerParent} initial="hidden" animate="show">
      {children}
    </C>
  );
}

export function StaggerItem({ as = "div", className, children, ...rest }) {
  const C = motion[as];
  return (
    <C className={className} variants={staggerChild} {...rest}>
      {children}
    </C>
  );
}

// Number 0 -> value count-up (dikhne pe). Non-number (e.g. "—", "85%") as-is with suffix support.
export function AnimatedNumber({ value, suffix = "", decimals = 0 }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true });
  const mv = useMotionValue(0);
  const text = useTransform(mv, (v) => `${v.toFixed(decimals)}${suffix}`);
  useEffect(() => {
    if (!inView || typeof value !== "number") return;
    const c = animate(mv, value, { duration: 1.1, ease });
    return c.stop;
  }, [inView, value]);
  if (typeof value !== "number") return <span ref={ref}>{value ?? "—"}</span>;
  return <motion.span ref={ref}>{text}</motion.span>;
}

// Radial progress ring (attendance %)
export function ProgressRing({ value = 0, size = 132, stroke = 12, label }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, value ?? 0));
  const tone = pct >= 75 ? "rgb(var(--brand-700))" : pct >= 60 ? "#b45309" : "#b91c1c";
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} className="stroke-slate-200 dark:stroke-white/10" />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={tone}
          strokeWidth={stroke}
          strokeLinecap="butt"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: c - (c * pct) / 100 }}
          transition={{ duration: 1.4, ease }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-display text-3xl font-semibold tabular-nums">
          {value == null ? "—" : <AnimatedNumber value={Math.round(pct)} suffix="%" />}
        </span>
        {label && <span className="text-[11px] font-medium uppercase tracking-wider text-slate-500">{label}</span>}
      </div>
    </div>
  );
}

// Success: draw-on checkmark + expanding rings + confetti dots
export function SuccessBurst({ title, subtitle, tone = "green" }) {
  const color = tone === "amber" ? "#b45309" : "#15803d";
  return (
    <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={spring} className="flex flex-col items-center py-4 text-center" role="status">
      <div className="relative h-24 w-24">
        <motion.div className="absolute inset-0 rounded-full" style={{ background: `${color}22` }} initial={{ scale: 0 }} animate={{ scale: 1 }} transition={spring} />
        <svg viewBox="0 0 96 96" className="absolute inset-0">
          <motion.circle cx="48" cy="48" r="30" fill={color} initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ ...spring, delay: 0.05 }} style={{ originX: "48px", originY: "48px" }} />
          <motion.path d="M35 49 l9 9 l18 -20" fill="none" stroke="white" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.45, delay: 0.25, ease }} />
        </svg>
      </div>
      <p className="mt-3 text-lg font-bold">{title}</p>
      {subtitle && <p className="text-sm text-slate-500">{subtitle}</p>}
    </motion.div>
  );
}

export function Skeleton({ className = "h-4 w-full" }) {
  return <div className={`skeleton ${className}`} aria-hidden="true" />;
}

export function SkeletonCards({ n = 4, className = "h-24" }) {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" role="status" aria-label="Loading">
      {Array.from({ length: n }, (_, i) => (
        <Skeleton key={i} className={className} />
      ))}
    </div>
  );
}

// ---------- Toasts ----------
export const useToasts = create((set) => ({
  items: [],
  push: (t) => {
    const id = Math.random().toString(36).slice(2);
    set((s) => ({ items: [...s.items, { id, tone: "info", ...t }] }));
    setTimeout(() => set((s) => ({ items: s.items.filter((x) => x.id !== id) })), t.ms || 3500);
  },
  dismiss: (id) => set((s) => ({ items: s.items.filter((x) => x.id !== id) })),
}));
export const toast = (title, tone = "success", body) => useToasts.getState().push({ title, tone, body });

const TONE = {
  success: "bg-green-700",
  error: "bg-red-700",
  info: "bg-brand-700",
};

export function Toaster() {
  const { items, dismiss } = useToasts();
  return (
    <div className="pointer-events-none fixed inset-x-0 top-3 z-50 flex flex-col items-center gap-2 px-3 sm:items-end sm:pr-6" aria-live="polite">
      <AnimatePresence>
        {items.map((t) => (
          <motion.button
            key={t.id}
            layout
            onClick={() => dismiss(t.id)}
            initial={{ opacity: 0, y: -16, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, x: 40, scale: 0.96 }}
            transition={spring}
            className="card pointer-events-auto flex w-full max-w-sm items-start gap-3 p-3.5 text-left shadow-lift"
          >
            <span className={`mt-0.5 h-8 w-1 shrink-0 rounded-full ${TONE[t.tone]}`} />
            <span>
              <span className="block text-sm font-semibold">{t.title}</span>
              {t.body && <span className="block text-xs text-slate-500">{t.body}</span>}
            </span>
          </motion.button>
        ))}
      </AnimatePresence>
    </div>
  );
}

// Aurora blobs hata diye (redesign). Purane imports na tootein isliye stub.
export function Aurora() {
  return null;
}

export { AnimatePresence, motion };
