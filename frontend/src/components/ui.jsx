// Small shared UI pieces: StatsCard, StatusBadge, BatchSelector, Spinner, EmptyState, ErrorBox.
import { useEffect, useState } from "react";

import { AnimatedNumber, motion, Skeleton, StaggerItem } from "./motion";

import { api } from "../api/client";

// [icon tile, value text]. Saade, dabe hue rang - number padhna asaan, aankhon pe zor nahi.
const TONES = {
  brand: ["bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300", "text-stone-900 dark:text-stone-100"],
  green: ["bg-green-50 text-green-800 dark:bg-green-500/15 dark:text-green-300", "text-green-800 dark:text-green-300"],
  amber: ["bg-amber-50 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300", "text-amber-800 dark:text-amber-300"],
  red: ["bg-red-50 text-red-800 dark:bg-red-500/15 dark:text-red-300", "text-red-800 dark:text-red-300"],
};
const ICONS = {
  users: "M16 11a4 4 0 1 0-8 0M3 21c1-4 5-6 9-6s8 2 9 6",
  face: "M9 10h.01M15 10h.01M9.5 15a3.5 3.5 0 0 0 5 0M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3",
  check: "M5 13l4 4L19 7",
  clock: "M12 7v5l3 2M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18",
  x: "M6 6l12 12M18 6L6 18",
  chart: "M4 20V10m6 10V4m6 16v-7m4 7H2",
};

export function StatsCard({ label, value, sub, tone = "brand", icon, suffix = "" }) {
  const [tile, text] = TONES[tone];
  return (
    <StaggerItem className="card p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium text-slate-500">{label}</p>
        {icon && (
          <span className={`flex h-7 w-7 items-center justify-center rounded-md ${tile}`}>
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d={ICONS[icon]} />
            </svg>
          </span>
        )}
      </div>
      <p className={`mt-2 font-display text-3xl font-semibold tabular-nums ${text}`}>
        <AnimatedNumber value={value} suffix={suffix} />
      </p>
      {sub && <p className="mt-0.5 text-xs text-slate-500">{sub}</p>}
    </StaggerItem>
  );
}

const STATUS = {
  present: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-200",
  late: "bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-200",
  absent: "bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-200",
  already_marked: "bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  rejected: "bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-200",
  active: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-200",
  inactive: "bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  holiday: "bg-sky-100 text-sky-800 dark:bg-sky-900/50 dark:text-sky-200",
  leave: "bg-brand-50 text-brand-800 dark:bg-brand-500/15 dark:text-brand-200",
  pending: "bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-200",
  approved: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-200",
};

export function StatusBadge({ status }) {
  return (
    <span className={`chip capitalize ${STATUS[status] || STATUS.inactive}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />
      {String(status).replace("_", " ")}
    </span>
  );
}

export function useBatches() {
  const [batches, setBatches] = useState([]);
  const [error, setError] = useState(null);
  const reload = () =>
    api("/v1/admin/batches")
      .then(setBatches)
      .catch((e) => setError(e.message));
  useEffect(() => {
    reload();
  }, []);
  return { batches, error, reload };
}

export function BatchSelector({ value, onChange, allowAll = true, batches: given, className = "" }) {
  const { batches: loaded } = useBatches();
  const batches = given || loaded;
  return (
    <select className={`input ${className}`} value={value || ""} onChange={(e) => onChange(e.target.value || null)} aria-label="Batch">
      {allowAll && <option value="">All batches</option>}
      {batches.map((b) => (
        <option key={b.id} value={b.id}>
          {b.name}
        </option>
      ))}
    </select>
  );
}

export function Spinner({ rows = 4 }) {
  return (
    <div className="space-y-3" role="status" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className={`h-14 ${i % 2 ? "w-11/12" : "w-full"}`} />
      ))}
    </div>
  );
}

export function EmptyState({ title, children }) {
  return (
    <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className="card flex flex-col items-center p-10 text-center">
      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-md bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300">
        <svg viewBox="0 0 24 24" className="h-7 w-7" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M4 7h16M4 12h10M4 17h7" /></svg>
      </div>
      <p className="font-semibold">{title}</p>
      {children && <div className="mt-1 text-sm text-slate-500">{children}</div>}
    </motion.div>
  );
}

export function ErrorBox({ error }) {
  if (!error) return null;
  return (
    <motion.p initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
      {String(error)}
    </motion.p>
  );
}

export function PageHeader({ title, subtitle, children }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-50 sm:text-[1.75rem]">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {children && <div className="flex flex-wrap gap-2">{children}</div>}
    </div>
  );
}

export const today = () => new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD local
export const daysAgo = (n) => new Date(Date.now() - n * 864e5).toLocaleDateString("en-CA");

// Data ko taaza rakho: har `ms` pe (sirf tab dikh raha ho) + tab pe wapas aate hi.
// Kiosk se attendance lagi -> admin overview khud update.
export function usePolling(fn, ms = 15000) {
  useEffect(() => {
    let alive = true;
    const run = () => alive && document.visibilityState === "visible" && fn();
    const id = setInterval(run, ms);
    const onVis = () => document.visibilityState === "visible" && run();
    document.addEventListener("visibilitychange", onVis);
    window.addEventListener("focus", run);
    return () => {
      alive = false;
      clearInterval(id);
      document.removeEventListener("visibilitychange", onVis);
      window.removeEventListener("focus", run);
    };
  }, [fn, ms]);
}
