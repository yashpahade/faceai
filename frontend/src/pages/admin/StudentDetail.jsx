import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api, fd } from "../../api/client";
import AttendanceTable from "../../components/AttendanceTable";
import FaceCamera from "../../components/FaceCamera";
import { ErrorBox, PageHeader, Spinner, StatsCard, useBatches } from "../../components/ui";
import { compressFile } from "../../lib/image";
import { useAuth } from "../../store/auth";

// Forgot password ka rasta jab student ka face enrolled nahi hai. Temporary password sirf ek
// baar dikhta hai (server pe sirf hash) -> admin student ko de, student Profile se badal le.
function ResetPassword({ id, name }) {
  const [stage, setStage] = useState("idle"); // idle | confirm | busy | done
  const [temp, setTemp] = useState(null);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

  async function reset() {
    setStage("busy");
    setError(null);
    try {
      const r = await api(`/v1/admin/students/${id}/reset-password`, { method: "POST" });
      setTemp(r.temporary_password);
      setStage("done");
    } catch (e) {
      setError(e.message);
      setStage("idle");
    }
  }

  return (
    <div className="space-y-2 border-t border-stone-200 pt-3 dark:border-white/10">
      <p className="text-sm font-medium">Password</p>
      {stage === "done" ? (
        <div className="space-y-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-100">
          <p>
            Temporary password for <b>{name}</b> (shown once):
          </p>
          <div className="flex items-center gap-2">
            <code className="rounded bg-white px-2 py-1 font-mono text-base text-stone-900 dark:bg-black/30 dark:text-stone-100">{temp}</code>
            <button
              type="button"
              className="btn-secondary min-h-[36px] px-3 py-1 text-sm"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(temp);
                  setCopied(true);
                } catch {
                  setCopied(false);
                }
              }}
            >
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <p className="text-xs">Their old password and all their sessions no longer work. Ask them to change it in Profile after signing in.</p>
        </div>
      ) : stage === "confirm" || stage === "busy" ? (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span>Reset {name}'s password? Their current password will stop working.</span>
          <button type="button" className="btn-primary min-h-[36px] px-3 py-1 text-sm" disabled={stage === "busy"} onClick={reset}>
            {stage === "busy" ? "Resetting…" : "Yes, reset"}
          </button>
          <button type="button" className="btn-secondary min-h-[36px] px-3 py-1 text-sm" disabled={stage === "busy"} onClick={() => setStage("idle")}>
            Cancel
          </button>
        </div>
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-sm text-slate-500">Forgot their password? Give them a temporary one.</span>
          <button type="button" className="btn-secondary min-h-[36px] px-3 py-1 text-sm" onClick={() => setStage("confirm")}>
            Reset password
          </button>
        </div>
      )}
      <ErrorBox error={error} />
    </div>
  );
}

export default function StudentDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { batches } = useBatches();
  const [s, setS] = useState(null);
  const [rows, setRows] = useState([]);
  const [error, setError] = useState(null);
  const [msg, setMsg] = useState(null);
  const [camOpen, setCamOpen] = useState(false);
  const cam = useRef(null);
  const isAdmin = useAuth((st) => st.user?.role === "admin");

  const load = () => {
    api(`/v1/admin/students/${id}`).then(setS).catch((e) => setError(e.message));
    api(`/v1/admin/attendance?user_id=${id}`).then(setRows).catch(() => {});
  };
  useEffect(load, [id]);

  async function save(changes) {
    setError(null);
    try {
      setS(await api(`/v1/admin/students/${id}`, { method: "PATCH", json: changes }));
      setMsg("Saved");
    } catch (e) {
      setError(e.message);
    }
  }

  async function enroll(blob) {
    setError(null);
    try {
      const replace = s.face_enrolled ? "?replace=true" : "";
      await api(`/v1/admin/students/${id}/face${replace}`, { method: "POST", form: fd([["file", new File([blob], "face.jpg", { type: "image/jpeg" })]]) });
      setCamOpen(false);
      setMsg("Face enrolled");
      load();
    } catch (e) {
      setError(e.detail?.message || e.message);
    }
  }

  async function remove() {
    if (!window.confirm(`Delete ${s.full_name} and all their face data? This cannot be undone.`)) return;
    try {
      await api(`/v1/admin/students/${id}`, { method: "DELETE" });
      nav("/admin/students", { replace: true });
    } catch (e) {
      setError(e.message);
    }
  }

  async function override(row, status) {
    await api("/v1/admin/attendance/manual", { method: "POST", json: { user_id: id, day: row.day, status } });
    load();
  }

  if (!s) return error ? <ErrorBox error={error} /> : <Spinner />;
  const count = (st) => rows.filter((r) => r.status === st).length;
  return (
    <div className="space-y-6">
      <PageHeader title={s.full_name}>{isAdmin && <button className="btn-danger" onClick={remove}>Delete</button>}</PageHeader>
      {msg && <p className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200">{msg}</p>}
      <ErrorBox error={error} />

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card space-y-3 p-4">
          <h2 className="font-semibold">Details</h2>
          <p className="text-sm text-slate-500">{s.email}{s.phone ? ` · ${s.phone}` : ""} · enrolled {s.enrollment_date}</p>
          <fieldset disabled={!isAdmin} className="grid gap-3 disabled:opacity-70 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="roll">Roll no</label>
              <input id="roll" className="input" defaultValue={s.roll_no || ""} onBlur={(e) => e.target.value !== (s.roll_no || "") && save({ roll_no: e.target.value || null })} />
            </div>
            <div>
              <label className="label" htmlFor="batch">Batch</label>
              <select id="batch" className="input" value={s.batch_id || ""} onChange={(e) => save({ batch_id: e.target.value || null })}>
                <option value="">— none —</option>
                {batches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="status">Status</label>
              <select id="status" className="input" value={s.status} onChange={(e) => save({ status: e.target.value })}>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </div>
          </fieldset>
          {isAdmin && <ResetPassword id={id} name={s.full_name} />}
        </div>

        <div className="card space-y-3 p-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Face ID</h2>
            <span className="text-sm text-slate-500">{s.face_enrolled ? "Enrolled" : "Not enrolled"}</span>
          </div>
          {camOpen ? (
            <>
              <FaceCamera ref={cam} facing="environment" mirror={false} hint="Student's face inside the oval" />
              <div className="flex gap-2">
                <button className="btn-primary flex-1" onClick={async () => enroll(await cam.current.capture({ maxSide: 1280, quality: 0.9 }))}>Capture</button>
                <button className="btn-secondary" onClick={() => setCamOpen(false)}>Cancel</button>
              </div>
            </>
          ) : (
            <div className="flex flex-wrap gap-2">
              <button className="btn-secondary" onClick={() => setCamOpen(true)}>Use camera</button>
              <label className="btn-secondary cursor-pointer">
                Upload photo
                <input type="file" accept="image/*" className="hidden" onChange={async (e) => e.target.files[0] && enroll(await compressFile(e.target.files[0], 1280))} />
              </label>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <StatsCard label="Present" value={count("present")} tone="green" />
        <StatsCard label="Late" value={count("late")} tone="amber" />
        <StatsCard label="Absent" value={count("absent")} tone="red" />
      </div>
      <h2 className="font-semibold">Attendance (last 30 days)</h2>
      <AttendanceTable
        rows={rows}
        showStudent={false}
        actions={(r) => (
          <select className="input w-auto py-1 text-xs" value={r.status} onChange={(e) => override(r, e.target.value)} aria-label={`Override ${r.day}`}>
            <option value="present">present</option>
            <option value="late">late</option>
            <option value="absent">absent</option>
          </select>
        )}
      />
    </div>
  );
}
