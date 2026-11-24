import { useRef, useState } from "react";

import { api, fd } from "../api/client";
import FaceCamera from "../components/FaceCamera";
import Field, { PasswordChecklist } from "../components/Field";
import ThemePicker from "../components/ThemePicker";
import { ErrorBox, PageHeader } from "../components/ui";
import { nameError, passwordChecks, passwordError, phoneError, sanitizeName, sanitizePhone } from "../lib/validate";
import { useAuth } from "../store/auth";

// Purana password zaroori: koi khula phone utha ke akele password na badal de.
function ChangePassword() {
  const setSession = useAuth((s) => s.setSession);
  const empty = { current: "", password: "", confirm: "" };
  const [f, setF] = useState(empty);
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);
  const errs = {
    current: f.current ? null : "Enter your current password",
    password: passwordError(f.password),
    confirm: f.confirm && f.confirm === f.password ? null : "Passwords don't match",
  };

  async function submit(e) {
    e.preventDefault();
    setTouched(true);
    setError(null);
    setDone(false);
    if (errs.current || errs.password || errs.confirm) return;
    setBusy(true);
    try {
      const r = await api("/v1/me/password", { method: "POST", json: { current_password: f.current, password: f.password } });
      setSession(r.access_token, r.user); // is device pe logged-in raho (baaki devices logout)
      setF(empty);
      setTouched(false);
      setDone(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate className="card space-y-4 p-5">
      <div>
        <h2 className="text-lg font-semibold">Change password</h2>
        <p className="text-sm text-slate-500">You'll stay signed in here. Other devices will be signed out.</p>
      </div>
      <Field id="cur-pw" label="Current password" error={errs.current} touched={touched}>
        <input id="cur-pw" className="input" type="password" autoComplete="current-password" value={f.current} onChange={(e) => setF({ ...f, current: e.target.value })} />
      </Field>
      <Field id="new-pw" label="New password" error={errs.password} touched={touched}>
        <input id="new-pw" className="input" type="password" autoComplete="new-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} />
        <PasswordChecklist checks={passwordChecks(f.password)} />
      </Field>
      <Field id="confirm-pw" label="Confirm new password" error={errs.confirm} touched={touched}>
        <input id="confirm-pw" className="input" type="password" autoComplete="new-password" value={f.confirm} onChange={(e) => setF({ ...f, confirm: e.target.value })} />
      </Field>
      <ErrorBox error={error} />
      {done && <p role="status" className="rounded-md bg-green-50 p-3 text-sm text-green-800 dark:bg-green-500/10 dark:text-green-200">Password changed.</p>}
      <button className="btn-primary" disabled={busy}>{busy ? "Changing…" : "Change password"}</button>
    </form>
  );
}

export default function Profile() {
  const { user, setUser } = useAuth();
  const [form, setForm] = useState({ full_name: user.full_name, phone: user.phone || "" });
  const [msg, setMsg] = useState(null);
  const [error, setError] = useState(null);
  const [enrolling, setEnrolling] = useState(false);
  const [busy, setBusy] = useState(false);
  const cam = useRef(null);

  const errs = { full_name: nameError(form.full_name), phone: phoneError(form.phone) };
  async function save(e) {
    e.preventDefault();
    setError(null);
    if (errs.full_name || errs.phone) return setError(errs.full_name || errs.phone);
    try {
      setUser(await api("/v1/me", { method: "PATCH", json: { full_name: form.full_name, phone: form.phone || null } }));
      setMsg("Profile saved");
    } catch (err) {
      setError(err.message);
    }
  }

  async function enroll() {
    setBusy(true);
    setError(null);
    try {
      const blob = await cam.current.capture({ maxSide: 1280, quality: 0.9 });
      const replace = user.face_enrolled ? "?replace=true" : "";
      await api(`/v1/me/face${replace}`, { method: "POST", form: fd([["file", new File([blob], "face.jpg", { type: "image/jpeg" })]]) });
      setUser(await api("/v1/me"));
      setEnrolling(false);
      setMsg("Face enrolled");
    } catch (err) {
      setError(err.detail?.message || err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-xl space-y-6">
      <PageHeader title="Profile" />
      {msg && <p className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200">{msg}</p>}
      <ErrorBox error={error} />

      <form onSubmit={save} className="card space-y-4 p-5">
        <Field id="name" label="Full name" error={errs.full_name} touched>
          <input id="name" className="input" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: sanitizeName(e.target.value) })} />
        </Field>
        <Field id="phone" label="Mobile" error={errs.phone} touched hint="10 digits">
          <input id="phone" className="input" type="tel" inputMode="numeric" maxLength={13} value={form.phone} onChange={(e) => setForm({ ...form, phone: sanitizePhone(e.target.value) })} />
        </Field>
        <p className="text-sm text-slate-500">Email: {user.email}</p>
        <button className="btn-primary">Save</button>
      </form>

      <ChangePassword />

      <div className="card space-y-4 p-5">
        <div>
          <h2 className="font-semibold">Appearance</h2>
          <p className="text-sm text-slate-500">Saved on this device</p>
        </div>
        <ThemePicker />
      </div>

      <div className="card space-y-4 p-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-semibold">Face ID</h2>
            <p className="text-sm text-slate-500">{user.face_enrolled ? "Enrolled. Re-enroll if recognition fails often." : "Not enrolled"}</p>
          </div>
          {!enrolling && <button className="btn-secondary" onClick={() => setEnrolling(true)}>{user.face_enrolled ? "Re-enroll" : "Enroll"}</button>}
        </div>
        {enrolling && (
          <>
            <FaceCamera ref={cam} hint="Face inside the oval, look straight" />
            <div className="flex gap-2">
              <button className="btn-primary flex-1" onClick={enroll} disabled={busy}>{busy ? "Saving…" : "Capture"}</button>
              <button className="btn-secondary" onClick={() => setEnrolling(false)}>Cancel</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
