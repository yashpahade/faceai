import { AnimatePresence, motion } from "framer-motion";
import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, fd } from "../api/client";
import FaceCamera from "../components/FaceCamera";
import Field, { PasswordChecklist } from "../components/Field";
import { SuccessBurst, toast } from "../components/motion";
import { ErrorBox } from "../components/ui";
import { nameError, passwordChecks, passwordError, phoneError, sanitizeName, sanitizePhone } from "../lib/validate";
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
            <span
              className={`flex h-7 w-7 items-center justify-center rounded-full text-sm font-semibold ${state === "next" ? "border border-stone-300 text-stone-500 dark:border-white/20" : "bg-brand-700 text-white"}`}
            >
              {state === "done" ? "✓" : n}
            </span>
            <span className={state === "next" ? "text-slate-400" : ""}>{label}</span>
            {i === 0 && (
              <span className="relative h-0.5 flex-1 overflow-hidden rounded bg-slate-200 dark:bg-white/10">
                <motion.span className="absolute inset-y-0 left-0 bg-brand-700" animate={{ width: step > 1 ? "100%" : "0%" }} transition={{ duration: 0.3 }} />
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
    setTouched({ full_name: true, email: true, phone: true, password: true });
    if (!valid) return;
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

  const [touched, setTouched] = useState({});
  const touch = (k) => () => setTouched((t) => ({ ...t, [k]: true }));
  const errs = {
    full_name: nameError(form.full_name),
    email: /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email) ? null : "Enter a valid email",
    phone: phoneError(form.phone),
    password: passwordError(form.password),
  };
  const valid = !Object.values(errs).some(Boolean) && form.consent;

  return (
    <AuthShell title="Create your account" subtitle="Two quick steps, under a minute">
      <Steps step={step} />
      <AnimatePresence mode="wait" initial={false}>
        {step === 1 ? (
          <motion.form key="s1" onSubmit={register} noValidate className="space-y-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
            <Field id="full_name" label="Full name" error={errs.full_name} touched={touched.full_name}>
              <input id="full_name" className="input" autoComplete="name" placeholder="Asha Rao" value={form.full_name} aria-invalid={!!(touched.full_name && errs.full_name)} onBlur={touch("full_name")} onChange={(e) => setForm({ ...form, full_name: sanitizeName(e.target.value) })} />
            </Field>
            <Field id="email" label="Email" error={errs.email} touched={touched.email}>
              <input id="email" className="input" type="email" autoComplete="email" placeholder="asha@school.in" value={form.email} onBlur={touch("email")} onChange={(e) => setForm({ ...form, email: e.target.value.trim() })} />
            </Field>
            <Field id="phone" label="Mobile (optional)" error={errs.phone} touched={touched.phone} hint="10 digits, e.g. 98765 43210">
              <input id="phone" className="input" type="tel" inputMode="numeric" autoComplete="tel" placeholder="98765 43210" maxLength={13} value={form.phone} onBlur={touch("phone")} onChange={(e) => setForm({ ...form, phone: sanitizePhone(e.target.value) })} />
            </Field>
            <Field id="password" label="Password" error={errs.password} touched={touched.password}>
              <input id="password" className="input" type="password" autoComplete="new-password" value={form.password} onBlur={touch("password")} onChange={(e) => setForm({ ...form, password: e.target.value })} />
              <PasswordChecklist checks={passwordChecks(form.password)} />
            </Field>
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
          <motion.div key="s2" className="space-y-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
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
