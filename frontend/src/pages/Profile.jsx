import { useRef, useState } from "react";

import { api, fd } from "../api/client";
import FaceCamera from "../components/FaceCamera";
import { ErrorBox, PageHeader } from "../components/ui";
import { useAuth } from "../store/auth";

export default function Profile() {
  const { user, setUser } = useAuth();
  const [form, setForm] = useState({ full_name: user.full_name, phone: user.phone || "" });
  const [msg, setMsg] = useState(null);
  const [error, setError] = useState(null);
  const [enrolling, setEnrolling] = useState(false);
  const [busy, setBusy] = useState(false);
  const cam = useRef(null);

  async function save(e) {
    e.preventDefault();
    setError(null);
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
        <div>
          <label className="label" htmlFor="name">Full name</label>
          <input id="name" className="input" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required />
        </div>
        <div>
          <label className="label" htmlFor="phone">Phone</label>
          <input id="phone" className="input" type="tel" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
        </div>
        <p className="text-sm text-slate-500">Email: {user.email}</p>
        <button className="btn-primary">Save</button>
      </form>

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
