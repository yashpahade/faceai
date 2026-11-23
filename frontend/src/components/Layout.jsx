import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../store/auth";
import { spring } from "./motion";
import { ThemeToggle } from "./ThemePicker";

const I = {
  home: "M3 11.5L12 4l9 7.5M5.5 10v10h13V10",
  live: "M15 10l4.5-2.5v9L15 14M3.5 7h11.5v10H3.5z",
  users: "M16 11a4 4 0 1 0-8 0M3 21c1-4 5-6 9-6s8 2 9 6",
  cal: "M8 3v4m8-4v4M4 10h16M5 5h14v15H5z",
  chart: "M4 20V10m6 10V4m6 16v-7m4 7H2",
  layers: "M12 3l9 5-9 5-9-5 9-5zM3 13l9 5 9-5",
  user: "M16 8a4 4 0 1 1-8 0 4 4 0 0 1 8 0M4 21c1-4 4-6 8-6s7 2 8 6",
};
const ADMIN = [
  ["/admin", "Overview", I.home],
  ["/admin/live", "Live", I.live],
  ["/admin/students", "Students", I.users],
  ["/admin/attendance", "Attendance", I.cal],
  ["/admin/reports", "Reports", I.chart],
  ["/admin/batches", "Batches", I.layers],
];
const STUDENT = [
  ["/dashboard", "Home", I.home],
  ["/profile", "Profile", I.user],
];

function Icon({ d, className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={d} />
    </svg>
  );
}

function useOnline() {
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);
  return online;
}

const isActive = (pathname, to) => (to === "/admin" ? pathname === "/admin" : pathname === to || pathname.startsWith(`${to}/`));

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const { pathname } = useLocation();
  const online = useOnline();
  const items = user.role === "admin" ? [...ADMIN, ["/profile", "Profile", I.user]] : STUDENT;
  const initials = user.full_name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  const signOut = () => {
    logout();
    nav("/login");
  };

  return (
    <div className="min-h-screen md:flex">
      {/* ---------- desktop sidebar ---------- */}
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-slate-200/70 bg-white/70 p-4 backdrop-blur-xl dark:border-white/[0.06] dark:bg-ink-900/70 md:flex">
        <div className="mb-8 flex items-center gap-2.5 px-2 pt-1">
          <img src="/icon.svg" alt="" className="h-9 w-9 drop-shadow" />
          <div>
            <p className="text-[15px] font-bold leading-tight">FaceAI Pro</p>
            <p className="text-[11px] font-medium text-slate-500">Attendance, simplified</p>
          </div>
        </div>
        <nav className="flex-1 space-y-1" aria-label="Main">
          {items.map(([to, label, d]) => {
            const active = isActive(pathname, to);
            return (
              <NavLink key={to} to={to} end={to === "/admin"} className={`relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors ${active ? "text-brand-700 dark:text-white" : "text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"}`}>
                {active && <motion.span layoutId="side-pill" transition={spring} className="absolute inset-0 rounded-xl bg-gradient-to-r from-brand-100 to-brand-50 shadow-sm ring-1 ring-brand-200/60 dark:from-brand-500/25 dark:to-accent-500/10 dark:ring-white/10" />}
                <span className="relative flex items-center gap-3">
                  <Icon d={d} /> {label}
                </span>
              </NavLink>
            );
          })}
        </nav>
        <div className="mt-4 flex items-center gap-3 rounded-2xl border border-slate-200/70 p-2.5 dark:border-white/[0.06]">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-accent-500 text-sm font-bold text-white">{initials}</div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold">{user.full_name}</p>
            <p className="truncate text-xs capitalize text-slate-500">{user.role}</p>
          </div>
          <ThemeToggle />
          <button onClick={signOut} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-900 dark:hover:bg-white/10 dark:hover:text-white" aria-label="Log out" title="Log out">
            <Icon d="M15 12H4m0 0l4-4m-4 4l4 4M14 4h5a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-5" />
          </button>
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        {/* ---------- mobile header ---------- */}
        <header className="sticky top-0 z-20 flex items-center justify-between border-b border-slate-200/70 bg-white/75 px-4 py-3 backdrop-blur-xl dark:border-white/[0.06] dark:bg-ink-950/75 md:hidden">
          <span className="flex items-center gap-2 font-bold">
            <img src="/icon.svg" alt="" className="h-7 w-7" /> FaceAI Pro
          </span>
          <span className="flex items-center gap-1">
            <ThemeToggle />
            <button onClick={signOut} className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-accent-500 text-xs font-bold text-white" aria-label="Log out">
              {initials}
            </button>
          </span>
        </header>
        <AnimatePresence>
          {!online && (
            <motion.div initial={{ height: 0 }} animate={{ height: "auto" }} exit={{ height: 0 }} className="overflow-hidden bg-amber-100 text-center text-sm text-amber-900 dark:bg-amber-500/15 dark:text-amber-200">
              <p className="px-4 py-2">You're offline · showing saved data · attendance can't be marked offline</p>
            </motion.div>
          )}
        </AnimatePresence>
        <main className="mx-auto max-w-6xl px-4 pb-28 pt-5 md:px-8 md:pb-10 md:pt-8">{children}</main>
      </div>

      {/* ---------- mobile bottom tab bar (thumb zone) ---------- */}
      <nav className="safe-bottom fixed inset-x-3 bottom-3 z-20 md:hidden" aria-label="Main">
        <div className="glass flex overflow-x-auto p-1.5">
          {items.map(([to, label, d]) => {
            const active = isActive(pathname, to);
            return (
              <NavLink key={to} to={to} end={to === "/admin"} className={`relative flex min-h-[52px] min-w-[60px] flex-1 flex-col items-center justify-center gap-0.5 rounded-2xl text-[10.5px] font-semibold transition-colors ${active ? "text-white" : "text-slate-500 dark:text-slate-400"}`}>
                {active && <motion.span layoutId="tab-pill" transition={spring} className="absolute inset-0 rounded-2xl bg-gradient-to-br from-brand-600 to-accent-500 shadow-glow" />}
                <span className="relative flex flex-col items-center gap-0.5">
                  <Icon d={d} className="h-[22px] w-[22px]" />
                  {label}
                </span>
              </NavLink>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
