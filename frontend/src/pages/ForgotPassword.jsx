// Forgot password, bina email server ke: email + naya password -> chehra verify (liveness) ->
// server check karta hai ki chehra USI email ke account ka hai -> password badla + login.
// Face enroll nahi hai to rasta: admin "Reset password" (temporary password deta hai).
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "../api/client";
import Field, { PasswordChecklist } from "../components/Field";
import LivenessFlow from "../components/LivenessFlow";
import { toast } from "../components/motion";
import { ErrorBox } from "../components/ui";
import { passwordChecks, passwordError } from "../lib/validate";
import { useAuth } from "../store/auth";
import { AuthShell } from "./Login";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function ForgotPassword() {
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({ email: "", password: "", confirm: "" });
  const [touched, setTouched] = useState({});
  const [error, setError] = useState(null);
  const setSession = useAuth((s) => s.setSession);
  const nav = useNavigate();

  const errs = {
    email: EMAIL.test(form.email.trim()) ? null : "Enter the email you signed up with",
    password: passwordError(form.password),
    confirm: form.confirm && form.confirm === form.password ? null : "Passwords don't match",
  };
  const touch = (k) => () => setTouched((t) => ({ ...t, [k]: true }));

  function next(e) {
    e.preventDefault();
    setTouched({ email: true, password: true, confirm: true });
    setError(null);
    if (!errs.email && !errs.password && !errs.confirm) setStep(2);
  }

  async function reset(token) {
    try {
      const r = await api("/v1/auth/reset-password/face", {
        method: "POST",
        auth: false,
        json: { email: form.email.trim(), liveness_token: token, password: form.password },
      });
      await new Promise((res) => setTimeout(res, 600)); // "verified" dikhne do
      setSession(r.access_token, r.user);
      toast("Password changed", "success", "You're signed in with your new password");
      nav(r.user.role === "student" ? "/dashboard" : "/admin", { replace: true });
    } catch (err) {
      // LivenessFlow ye message apne andar dikhata hai aur "Try again" deta hai
      if (err.status === 401) throw new Error("We couldn't verify it's you for this email. Check the email, or ask your admin to reset your password.");
      if (err.status === 429) throw new Error("Too many attempts. Wait a minute and try again.");
      throw new Error(err.message);
    }
  }

  return (
    <AuthShell title="Reset your password" subtitle={step === 1 ? "Choose a new password, then confirm it's you with your face" : "Look at the camera to confirm it's you"}>
      {step === 1 ? (
        <form onSubmit={next} noValidate className="space-y-4">
          <Field id="email" label="Email" error={errs.email} touched={touched.email}>
            <input id="email" className="input" type="email" autoComplete="username" placeholder="you@school.in" value={form.email} onBlur={touch("email")} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </Field>
          <Field id="password" label="New password" error={errs.password} touched={touched.password}>
            <input id="password" className="input" type="password" autoComplete="new-password" value={form.password} onBlur={touch("password")} onChange={(e) => setForm({ ...form, password: e.target.value })} />
            <PasswordChecklist checks={passwordChecks(form.password)} />
          </Field>
          <Field id="confirm" label="Confirm new password" error={errs.confirm} touched={touched.confirm}>
            <input id="confirm" className="input" type="password" autoComplete="new-password" value={form.confirm} onBlur={touch("confirm")} onChange={(e) => setForm({ ...form, confirm: e.target.value })} />
          </Field>
          <ErrorBox error={error} />
          <button className="btn-primary w-full">Continue</button>
          <p className="rounded-md border border-stone-200 bg-white p-3 text-sm text-stone-600 dark:border-white/10 dark:bg-white/[0.03] dark:text-stone-400">
            This works only if your face is enrolled. If it isn't, ask your admin to reset your password from your student page.
          </p>
        </form>
      ) : (
        <div className="space-y-4">
          <p className="text-sm text-stone-600 dark:text-stone-400">
            Resetting for <b className="text-stone-900 dark:text-stone-100">{form.email.trim()}</b>{" "}
            <button type="button" onClick={() => setStep(1)} className="font-semibold text-brand-700 underline decoration-brand-300 underline-offset-2 dark:text-brand-300">
              change
            </button>
          </p>
          <LivenessFlow onToken={reset} actionLabel="Verify my face and reset" successTitle="Face verified" />
        </div>
      )}

      <p className="mt-8 border-t border-stone-200 pt-5 text-sm text-stone-600 dark:border-white/10 dark:text-stone-400">
        Remembered it?{" "}
        <Link to="/login" className="font-semibold text-brand-700 underline decoration-brand-300 underline-offset-2 hover:decoration-brand-700 dark:text-brand-300">
          Back to sign in
        </Link>
      </p>
    </AuthShell>
  );
}
