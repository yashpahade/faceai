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
  teacher: "M4 19V6l8-3 8 3v13M9 21v-6h6v6M8 9h8",
  sun: "M12 3v2m0 14v2m9-9h-2M5 12H3m14.36-6.36-1.42 1.42M7.06 16.94l-1.42 1.42m12.72 0-1.42-1.42M7.06 7.06 5.64 5.64M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z",
  leave: "M8 7V3m8 4V3M4 11h16M5 5h14v15H5zM9 15l2 2 4-4",
  user: "M16 8a4 4 0 1 1-8 0 4 4 0 0 1 8 0M4 21c1-4 4-6 8-6s7 2 8 6",
  more: "M5 12h.01M12 12h.01M19 12h.01",
};
const TEACHER = [
  ["/admin", "Overview", I.home],
  ["/admin/live", "Live", I.live],
  ["/admin/students", "Students", I.users],
  ["/admin/attendance", "Attendance", I.cal],
  ["/admin/leaves", "Leaves", I.leave],
  ["/admin/reports", "Reports", I.chart],
];
const ADMIN = [
  ...TEACHER,
  ["/admin/batches", "Batches", I.layers],
  ["/admin/teachers", "Teachers", I.teacher],
  ["/admin/holidays", "Holidays", I.sun],
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
  const [moreOpen, setMoreOpen] = useState(false);
  useEffect(() => setMoreOpen(false), [pathname]); // page badla -> menu band
  const items = user.role === "admin" ? [...ADMIN, ["/profile", "Profile", I.user]] : user.role === "teacher" ? [...TEACHER, ["/profile", "Profile", I.user]] : STUDENT;
  const primary = items.length > 5 ? items.slice(0, 4) : items;
  const extra = items.length > 5 ? items.slice(4) : [];
  const moreActive = extra.some(([to]) => isActive(pathname, to));
  const initials = user.full_name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  const signOut = () => {
    logout();
    nav("/login");
  };

  return (
    <div className="min-h-screen md:flex">
      {/* ---------- desktop sidebar ---------- */}
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-stone-200 bg-white dark:border-white/[0.08] dark:bg-ink-900 md:flex">
        <div className="flex items-center gap-2.5 border-b border-stone-200 px-5 py-4 dark:border-white/[0.08]">
          <img src="/icon.svg" alt="" className="h-8 w-8" />
          <div>
            <p className="font-display text-[17px] font-semibold leading-tight text-brand-800 dark:text-brand-200">FaceAI Pro</p>
            <p className="text-[11px] text-stone-500">Attendance register</p>
          </div>
        </div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-4" aria-label="Main">
          {items.map(([to, label, d]) => {
            const active = isActive(pathname, to);
            return (
              <NavLink key={to} to={to} end={to === "/admin"} className={`relative flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${active ? "bg-brand-50 font-semibold text-brand-800 dark:bg-brand-500/15 dark:text-brand-100" : "font-medium text-stone-600 hover:bg-stone-100 hover:text-stone-900 dark:text-stone-400 dark:hover:bg-white/5 dark:hover:text-white"}`}>
                {active && <span className="absolute inset-y-1.5 left-0 w-[3px] rounded-r bg-brand-700 dark:bg-brand-300" />}
                <span className="relative flex items-center gap-3">
                  <Icon d={d} /> {label}
                </span>
              </NavLink>
            );
          })}
        </nav>
        <div className="flex items-center gap-3 border-t border-stone-200 p-3 dark:border-white/[0.08]">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-700 text-sm font-semibold text-white">{initials}</div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold">{user.full_name}</p>
            <p className="truncate text-xs capitalize text-slate-500">{user.role}</p>
          </div>
          <ThemeToggle />
          <button onClick={signOut} className="rounded-md p-2 text-stone-500 hover:bg-stone-100 hover:text-stone-900 dark:hover:bg-white/10 dark:hover:text-white" aria-label="Log out" title="Log out">
            <Icon d="M15 12H4m0 0l4-4m-4 4l4 4M14 4h5a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-5" />
          </button>
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        {/* ---------- mobile header ---------- */}
        <header className="sticky top-0 z-20 flex items-center justify-between bg-brand-700 px-4 py-2.5 text-white dark:bg-ink-900 md:hidden">
          <span className="flex items-center gap-2 font-display text-lg font-semibold">
            <img src="/icon.svg" alt="" className="h-7 w-7 rounded" /> FaceAI Pro
          </span>
          <span className="flex items-center gap-1">
            <button onClick={signOut} className="flex h-9 w-9 items-center justify-center rounded-full border border-white/40 text-xs font-semibold text-white" aria-label="Log out">
              {initials}
            </button>
          </span>
        </header>
        <AnimatePresence>
          {!online && (
            <motion.div initial={{ height: 0 }} animate={{ height: "auto" }} exit={{ height: 0 }} className="overflow-hidden border-b border-amber-200 bg-amber-50 text-center text-sm text-amber-900 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-200">
              <p className="px-4 py-2">You're offline · showing saved data · attendance can't be marked offline</p>
            </motion.div>
          )}
        </AnimatePresence>
        <main className="mx-auto max-w-6xl px-4 pb-24 pt-5 md:px-8 md:pb-10 md:pt-8">{children}</main>
      </div>

      {/* ---------- mobile bottom tab bar (thumb zone) ----------
          Admin ke 10 pages ek row mein fit nahi hote (pehle side-scroll mein chhup jaate the).
          4 main tabs + "More" -> baaki pages ek list mein. */}
      {moreOpen && <button className="fixed inset-0 z-20 bg-stone-900/20 md:hidden" aria-label="Close menu" onClick={() => setMoreOpen(false)} />}
      <AnimatePresence>
        {moreOpen && (
          <motion.div
            id="more-menu"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            transition={{ duration: 0.15 }}
            className="safe-bottom fixed inset-x-0 bottom-[57px] z-30 border-t border-stone-200 bg-white shadow-lift dark:border-white/10 dark:bg-ink-900 md:hidden"
          >
            <ul className="divide-y divide-stone-100 dark:divide-white/5">
              {extra.map(([to, label, d]) => (
                <li key={to}>
                  <NavLink to={to} className={`flex min-h-[52px] items-center gap-3 px-5 text-[15px] ${isActive(pathname, to) ? "font-semibold text-brand-800 dark:text-brand-100" : "text-stone-700 dark:text-stone-300"}`}>
                    <Icon d={d} /> {label}
                  </NavLink>
                </li>
              ))}
              <li>
                <button onClick={signOut} className="flex min-h-[52px] w-full items-center gap-3 px-5 text-[15px] text-stone-700 dark:text-stone-300">
                  <Icon d="M15 12H4m0 0l4-4m-4 4l4 4M14 4h5a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-5" /> Log out
                </button>
              </li>
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
      <nav className="safe-bottom fixed inset-x-0 bottom-0 z-30 border-t border-stone-200 bg-white dark:border-white/10 dark:bg-ink-900 md:hidden" aria-label="Main">
        <div className="flex">
          {primary.map(([to, label, d]) => {
            const active = isActive(pathname, to);
            return (
              <NavLink key={to} to={to} end={to === "/admin"} className={`relative flex min-h-[56px] min-w-[64px] flex-1 flex-col items-center justify-center gap-0.5 text-[11px] transition-colors ${active ? "font-semibold text-brand-700 dark:text-brand-200" : "font-medium text-stone-500 dark:text-stone-400"}`}>
                {active && <motion.span layoutId="tab-line" transition={spring} className="absolute inset-x-3 top-0 h-[3px] rounded-b bg-brand-700 dark:bg-brand-300" />}
                <span className="relative flex flex-col items-center gap-0.5">
                  <Icon d={d} className="h-[22px] w-[22px]" />
                  {label}
                </span>
              </NavLink>
            );
          })}
          {extra.length > 0 && (
            <button
              onClick={() => setMoreOpen((o) => !o)}
              aria-expanded={moreOpen}
              aria-controls="more-menu"
              className={`relative flex min-h-[56px] min-w-[64px] flex-1 flex-col items-center justify-center gap-0.5 text-[11px] transition-colors ${moreOpen || moreActive ? "font-semibold text-brand-700 dark:text-brand-200" : "font-medium text-stone-500 dark:text-stone-400"}`}
            >
              {moreActive && !moreOpen && <span className="absolute inset-x-3 top-0 h-[3px] rounded-b bg-brand-700 dark:bg-brand-300" />}
              <Icon d={I.more} className="h-[22px] w-[22px]" />
              More
            </button>
          )}
        </div>
      </nav>
    </div>
  );
}
