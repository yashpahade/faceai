import { AnimatePresence, motion } from "framer-motion";
import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, fd } from "../api/client";
import FaceCamera from "../components/FaceCamera";
import { SuccessBurst, toast } from "../components/motion";
import { ErrorBox } from "../components/ui";
import { useAuth } from "../store/auth";
import { AuthShell } from "./Login";

// Step 1: account + explicit biometric consent. Step 2: face enroll (quality-checked by the API).
function Steps({ step }) {
  return (
    <ol className="mb-6 flex items-center gap-3 text-xs font-semibold" aria-label="Progress">
      {["Your details", "Face ID"].map((label, i) => {
        const n = i + 1;
        const state = step > n ? "done" : step === n ? "now" : "next";
        return (
          <li key={label} className="flex flex-1 items-center gap-2">
            <motion.span
              animate={{ scale: state === "now" ? 1.08 : 1 }}
              className={`flex h-7 w-7 items-center justify-center rounded-full ${state === "next" ? "bg-slate-200 text-slate-500 dark:bg-white/10" : "bg-gradient-to-br from-brand-500 to-accent-500 text-white shadow-glow"}`}
            >
              {state === "done" ? "✓" : n}
            </motion.span>
            <span className={state === "next" ? "text-slate-400" : ""}>{label}</span>
            {i === 0 && (
              <span className="relative h-0.5 flex-1 overflow-hidden rounded bg-slate-200 dark:bg-white/10">
                <motion.span className="absolute inset-y-0 left-0 bg-gradient-to-r from-brand-500 to-accent-500" animate={{ width: step > 1 ? "100%" : "0%" }} transition={{ duration: 0.6 }} />
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}

export default function Signup() {
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({ full_name: "", email: "", phone: "", password: "", consent: false });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const cam = useRef(null);
  const { setSession, setUser } = useAuth();
  const nav = useNavigate();

  async function register(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api("/v1/auth/signup", { method: "POST", auth: false, json: { ...form, phone: form.phone || null } });
      setSession(r.access_token, r.user);
      setStep(2);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function enroll() {
    setBusy(true);
    setError(null);
    try {
      const blob = await cam.current.capture({ maxSide: 1280, quality: 0.9 }); // enroll: thodi zyada quality
      await api("/v1/me/face", { method: "POST", form: fd([["file", new File([blob], "face.jpg", { type: "image/jpeg" })]]) });
      setUser(await api("/v1/me"));
      setDone(true);
      toast("Face ID ready", "success", "You can now sign in with your face");
      setTimeout(() => nav("/dashboard", { replace: true }), 1400);
    } catch (err) {
      setError(err.detail?.message ? `${err.detail.message}. Move closer, face the camera, good light.` : err.message);
    } finally {
      setBusy(false);
    }
  }

  const pwStrength = Math.min(4, [/.{8,}/, /[A-Z]/, /[0-9]/, /[^A-Za-z0-9]/].filter((r) => r.test(form.password)).length);

  return (
    <AuthShell title="Create your account" subtitle="Two quick steps, under a minute">
      <Steps step={step} />
      <AnimatePresence mode="wait">
        {step === 1 ? (
          <motion.form key="s1" onSubmit={register} className="space-y-4" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
            {[
              ["full_name", "Full name", "text", "name", "Asha Rao"],
              ["email", "Email", "email", "email", "asha@school.in"],
              ["phone", "Phone (optional)", "tel", "tel", "+91 98xxxxxx"],
            ].map(([k, label, type, ac, ph]) => (
              <div key={k}>
                <label className="label" htmlFor={k}>{label}</label>
                <input id={k} className="input" type={type} autoComplete={ac} placeholder={ph} required={k !== "phone"} value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
              </div>
            ))}
            <div>
              <label className="label" htmlFor="password">Password</label>
              <input id="password" className="input" type="password" autoComplete="new-password" minLength={8} required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
              <div className="mt-2 grid grid-cols-4 gap-1" aria-hidden="true">
                {[0, 1, 2, 3].map((i) => (
                  <motion.span key={i} className="h-1 rounded-full" animate={{ backgroundColor: i < pwStrength ? ["#ef4444", "#f59e0b", "#6366f1", "#10b981"][pwStrength - 1] : "#e2e8f0" }} />
                ))}
              </div>
            </div>
            <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-slate-200 bg-white/60 p-3.5 text-sm dark:border-white/10 dark:bg-white/5">
              <input type="checkbox" className="mt-0.5 h-5 w-5 accent-brand-600" required checked={form.consent} onChange={(e) => setForm({ ...form, consent: e.target.checked })} />
              <span className="text-slate-600 dark:text-slate-300">
                I agree that my <b>face template</b> (not my photo) is stored encrypted and used only for attendance and login. I can delete it anytime.
              </span>
            </label>
            <ErrorBox error={error} />
            <button className="btn-primary w-full" disabled={busy || !form.consent}>
              {busy ? "Creating…" : "Continue"}
            </button>
          </motion.form>
        ) : done ? (
          <SuccessBurst key="done" title="You're all set!" subtitle="Taking you to your dashboard…" />
        ) : (
          <motion.div key="s2" className="space-y-4" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
            <FaceCamera ref={cam} state={busy ? "scanning" : error ? "error" : "idle"} hint={busy ? "Hold still…" : "Face inside the oval, look straight"} />
            <ErrorBox error={error} />
            <button className="btn-primary w-full" onClick={enroll} disabled={busy}>
              {busy ? "Enrolling…" : "Capture & enroll"}
            </button>
            <button className="btn-secondary w-full" onClick={() => nav("/dashboard")}>
              Skip for now
            </button>
          </motion.div>
        )}
      </AnimatePresence>
      <p className="mt-6 text-center text-sm text-slate-500">
        Already registered?{" "}
        <Link to="/login" className="font-semibold text-brand-600 hover:underline dark:text-brand-300">
          Sign in
        </Link>
      </p>
    </AuthShell>
  );
}
