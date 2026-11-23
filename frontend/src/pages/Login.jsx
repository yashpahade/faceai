import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "../api/client";
import LivenessFlow from "../components/LivenessFlow";
import { Aurora, ease, spring, toast } from "../components/motion";
import { ErrorBox } from "../components/ui";
import { useAuth } from "../store/auth";

const FEATURES = [
  ["Face login in 3 seconds", "No passwords, no queues"],
  ["Liveness check", "Photos and screens can't fool it"],
  ["Encrypted face data", "Templates, never photos"],
];

export function AuthShell({ children, title, subtitle }) {
  return (
    <div className="relative min-h-screen">
      <Aurora />
      <div className="mx-auto grid min-h-screen max-w-6xl items-center gap-10 px-4 py-8 lg:grid-cols-[1.1fr_1fr] lg:px-8">
        <motion.div initial={{ opacity: 0, x: -24 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.7, ease }} className="hidden lg:block">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-brand-200/70 bg-white/60 px-3 py-1 text-xs font-semibold text-brand-700 backdrop-blur dark:border-white/10 dark:bg-white/5 dark:text-brand-200">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" /> Biometric attendance
          </div>
          <h1 className="text-5xl font-bold leading-[1.05] tracking-tight xl:text-6xl">
            Attendance that <span className="text-gradient">recognizes</span> you.
          </h1>
          <p className="mt-5 max-w-md text-lg text-slate-600 dark:text-slate-400">
            Look at the camera, turn your head, done. Built for classrooms, coaching centres and offices.
          </p>
          <ul className="mt-10 space-y-4">
            {FEATURES.map(([t, d], i) => (
              <motion.li key={t} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 + i * 0.1, duration: 0.5, ease }} className="flex items-start gap-3">
                <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-accent-500 text-white shadow-glow">
                  <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" aria-hidden="true">
                    <path d="M5 13l4 4L19 7" />
                  </svg>
                </span>
                <span>
                  <span className="block font-semibold">{t}</span>
                  <span className="block text-sm text-slate-500">{d}</span>
                </span>
              </motion.li>
            ))}
          </ul>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 24, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.6, ease, delay: 0.05 }} className="mx-auto w-full max-w-md">
          <div className="mb-6 text-center lg:hidden">
            <img src="/icon.svg" alt="" className="mx-auto h-14 w-14 drop-shadow-lg" />
          </div>
          <div className="glass p-5 sm:p-7">
            <h2 className="text-2xl font-bold tracking-tight">{title}</h2>
            {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
            <div className="mt-5">{children}</div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}

export default function Login() {
  const [mode, setMode] = useState("face");
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const setSession = useAuth((s) => s.setSession);
  const nav = useNavigate();

  const done = (r) => {
    setSession(r.access_token, r.user);
    toast(`Welcome back, ${r.user.full_name.split(" ")[0]}`, "success");
    nav(r.user.role === "admin" ? "/admin" : "/dashboard", { replace: true });
  };

  async function passwordLogin(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      done(await api("/v1/auth/login", { method: "POST", json: form, auth: false }));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function faceLogin(token) {
    try {
      const r = await api("/v1/auth/face-login", { method: "POST", json: { liveness_token: token }, auth: false });
      await new Promise((res) => setTimeout(res, 700)); // success animation ko dikhne do
      done(r);
    } catch (err) {
      throw new Error(err.status === 401 ? "Face not recognized. Use email & password, or enroll your face first." : err.message);
    }
  }

  return (
    <AuthShell title="Welcome back" subtitle="Sign in to mark your attendance">
      <div className="mb-5 grid grid-cols-2 rounded-2xl bg-slate-100/80 p-1 dark:bg-white/5" role="tablist">
        {[
          ["face", "Face login"],
          ["password", "Email & password"],
        ].map(([k, label]) => (
          <button key={k} role="tab" aria-selected={mode === k} onClick={() => setMode(k)} className={`relative min-h-[42px] rounded-xl text-sm font-semibold transition-colors ${mode === k ? "text-slate-900 dark:text-white" : "text-slate-500"}`}>
            {mode === k && <motion.span layoutId="login-tab" transition={spring} className="absolute inset-0 rounded-xl bg-white shadow-soft dark:bg-white/10" />}
            <span className="relative">{label}</span>
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait" initial={false}>
        {mode === "face" ? (
          <motion.div key="face" initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 16 }} transition={{ duration: 0.25 }}>
            <LivenessFlow onToken={faceLogin} actionLabel="Sign in with my face" successTitle="Face verified" />
          </motion.div>
        ) : (
          <motion.form key="pwd" onSubmit={passwordLogin} className="space-y-4" initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }} transition={{ duration: 0.25 }}>
            <div>
              <label className="label" htmlFor="email">Email</label>
              <input id="email" className="input" type="email" autoComplete="username" placeholder="you@school.in" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            </div>
            <div>
              <label className="label" htmlFor="password">Password</label>
              <input id="password" className="input" type="password" autoComplete="current-password" placeholder="••••••••" required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
            </div>
            <ErrorBox error={error} />
            <button className="btn-primary w-full" disabled={busy}>
              {busy && <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />}
              {busy ? "Signing in…" : "Sign in"}
            </button>
          </motion.form>
        )}
      </AnimatePresence>

      <p className="mt-6 text-center text-sm text-slate-500">
        New student?{" "}
        <Link to="/signup" className="font-semibold text-brand-600 hover:underline dark:text-brand-300">
          Create an account
        </Link>
      </p>
    </AuthShell>
  );
}
