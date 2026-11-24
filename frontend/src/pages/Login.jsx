import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "../api/client";
import LivenessFlow from "../components/LivenessFlow";
import { ease, toast } from "../components/motion";
import { ErrorBox } from "../components/ui";
import { useAuth } from "../store/auth";

const FEATURES = [
  ["Face login in about three seconds", "No passwords to forget, no queue at the door."],
  ["Checks that a real person is present", "A printed photo or a phone screen is rejected."],
  ["Face data stays encrypted", "Only a numeric template is kept. Photos are never stored."],
];

export function AuthShell({ children, title, subtitle }) {
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      {/* Left: maroon panel, institution letterhead jaisa (sirf bade screens pe) */}
      <aside className="relative hidden flex-col justify-between bg-brand-800 px-12 py-10 text-[#f7f4ef] lg:flex">
        <div className="flex items-center gap-3">
          <img src="/icon.svg" alt="" className="h-10 w-10 rounded" />
          <span className="font-display text-xl font-semibold">FaceAI Pro</span>
        </div>
        <div className="max-w-md">
          <p className="mb-4 text-xs font-semibold uppercase tracking-[0.2em] text-accent-400">Attendance register</p>
          <h1 className="text-[2.6rem] font-semibold leading-[1.15]">Attendance, marked by a glance at the camera.</h1>
          <p className="mt-5 text-[15px] leading-relaxed text-[#f7f4ef]/75">
            For classrooms, coaching centres and offices. Students look at the camera, turn their head once, and they are marked present.
          </p>
          <ul className="mt-10 divide-y divide-white/15 border-y border-white/15">
            {FEATURES.map(([t, d]) => (
              <li key={t} className="py-4">
                <p className="font-semibold">{t}</p>
                <p className="mt-0.5 text-sm text-[#f7f4ef]/65">{d}</p>
              </li>
            ))}
          </ul>
        </div>
        <p className="text-xs text-[#f7f4ef]/50">Biometric data is used only for attendance, with consent.</p>
      </aside>

      {/* Right: form */}
      <main className="flex min-h-screen flex-col px-4 py-8 sm:px-8 lg:min-h-0 lg:justify-center lg:px-16">
        <div className="flex items-center justify-between lg:hidden">
          <span className="flex items-center gap-2">
            <img src="/icon.svg" alt="" className="h-9 w-9 rounded" />
            <span className="font-display text-xl font-semibold text-brand-800">FaceAI Pro</span>
          </span>
        </div>
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, ease }} className="mx-auto mt-10 w-full max-w-md lg:mt-0">
          <h2 className="text-[1.9rem] font-semibold text-stone-900 dark:text-stone-50">{title}</h2>
          {subtitle && <p className="mt-1.5 text-[15px] text-stone-600 dark:text-stone-400">{subtitle}</p>}
          <div className="mt-7">{children}</div>
        </motion.div>
      </main>
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
    nav(r.user.role === "student" ? "/dashboard" : "/admin", { replace: true });
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
      <div className="mb-6 grid grid-cols-2 border-b border-stone-200 dark:border-white/10" role="tablist">
        {[
          ["face", "Face login"],
          ["password", "Email & password"],
        ].map(([k, label]) => (
          <button key={k} role="tab" aria-selected={mode === k} onClick={() => setMode(k)} className={`relative -mb-px min-h-[44px] border-b-2 text-sm transition-colors ${mode === k ? "border-brand-700 font-semibold text-brand-800 dark:border-brand-300 dark:text-brand-100" : "border-transparent font-medium text-stone-500 hover:text-stone-800"}`}>
            {label}
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait" initial={false}>
        {mode === "face" ? (
          <motion.div key="face" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
            <LivenessFlow onToken={faceLogin} actionLabel="Sign in with my face" successTitle="Face verified" />
          </motion.div>
        ) : (
          <motion.form key="pwd" onSubmit={passwordLogin} className="space-y-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
            <div>
              <label className="label" htmlFor="email">Email</label>
              <input id="email" className="input" type="email" autoComplete="username" placeholder="you@school.in" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            </div>
            <div>
              <div className="flex items-baseline justify-between">
                <label className="label" htmlFor="password">Password</label>
                <Link to="/forgot-password" className="text-[13px] font-medium text-brand-700 hover:underline dark:text-brand-300">
                  Forgot password?
                </Link>
              </div>
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

      <p className="mt-8 border-t border-stone-200 pt-5 text-sm text-stone-600 dark:border-white/10 dark:text-stone-400">
        New student?{" "}
        <Link to="/signup" className="font-semibold text-brand-700 underline decoration-brand-300 underline-offset-2 hover:decoration-brand-700 dark:text-brand-300">
          Create an account
        </Link>
      </p>
    </AuthShell>
  );
}
