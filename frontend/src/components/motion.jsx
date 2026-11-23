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
      initial={{ opacity: 0, y: 14, filter: "blur(4px)" }}
      animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      exit={{ opacity: 0, y: -8, filter: "blur(4px)" }}
      transition={{ duration: 0.45, ease }}
    >
      {children}
    </motion.div>
  );
}

const staggerParent = { hidden: {}, show: { transition: { staggerChildren: 0.06, delayChildren: 0.05 } } };
const staggerChild = {
  hidden: { opacity: 0, y: 16, scale: 0.98 },
  show: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.5, ease } },
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
  const tone = pct >= 75 ? "url(#ring-good)" : pct >= 60 ? "#f59e0b" : "#ef4444";
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden="true">
        <defs>
          <linearGradient id="ring-good" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="rgb(var(--brand-500))" />
            <stop offset="100%" stopColor="rgb(var(--accent-500))" />
          </linearGradient>
        </defs>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} className="stroke-slate-200 dark:stroke-white/10" />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={tone}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: c - (c * pct) / 100 }}
          transition={{ duration: 1.4, ease }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-bold tabular-nums tracking-tight">
          {value == null ? "—" : <AnimatedNumber value={Math.round(pct)} suffix="%" />}
        </span>
        {label && <span className="text-[11px] font-medium uppercase tracking-wider text-slate-500">{label}</span>}
      </div>
    </div>
  );
}

// Success: draw-on checkmark + expanding rings + confetti dots
export function SuccessBurst({ title, subtitle, tone = "green" }) {
  const color = tone === "amber" ? "#f59e0b" : "#10b981";
  const dots = Array.from({ length: 10 }, (_, i) => i);
  return (
    <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={spring} className="flex flex-col items-center py-4 text-center" role="status">
      <div className="relative h-24 w-24">
        {dots.map((i) => {
          const a = (i / dots.length) * Math.PI * 2;
          return (
            <motion.span
              key={i}
              className="absolute left-1/2 top-1/2 h-2 w-2 rounded-full"
              style={{ background: i % 2 ? color : "rgb(var(--brand-500))" }}
              initial={{ x: -4, y: -4, opacity: 1, scale: 1 }}
              animate={{ x: Math.cos(a) * 58 - 4, y: Math.sin(a) * 58 - 4, opacity: 0, scale: 0.4 }}
              transition={{ duration: 0.9, ease, delay: 0.15 }}
            />
          );
        })}
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
  success: "from-emerald-500 to-teal-500",
  error: "from-red-500 to-rose-500",
  info: "from-brand-500 to-accent-500",
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
            className="glass pointer-events-auto flex w-full max-w-sm items-start gap-3 p-3.5 text-left"
          >
            <span className={`mt-0.5 h-8 w-1.5 shrink-0 rounded-full bg-gradient-to-b ${TONE[t.tone]}`} />
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

// Aurora gradient blobs (auth pages hero background)
export function Aurora() {
  return (
    <div className="aurora" aria-hidden="true">
      <span className="-left-24 -top-24 h-[28rem] w-[28rem] animate-aurora bg-brand-400" />
      <span className="-right-32 top-1/4 h-[26rem] w-[26rem] animate-aurora-slow bg-accent-400" />
      <span className="bottom-[-10rem] left-1/4 h-[24rem] w-[24rem] animate-aurora bg-sky-300 dark:bg-sky-700" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_1px_1px,rgba(15,23,42,.07)_1px,transparent_0)] [background-size:22px_22px] dark:bg-[radial-gradient(circle_at_1px_1px,rgba(255,255,255,.05)_1px,transparent_0)]" />
    </div>
  );
}

export { AnimatePresence, motion };
