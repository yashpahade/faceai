import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api, fd } from "../../api/client";
import AttendanceTable from "../../components/AttendanceTable";
import FaceCamera from "../../components/FaceCamera";
import { ErrorBox, PageHeader, Spinner, StatsCard, useBatches } from "../../components/ui";
import { compressFile } from "../../lib/image";

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
      <PageHeader title={s.full_name}>
        <button className="btn-danger" onClick={remove}>Delete</button>
      </PageHeader>
      {msg && <p className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200">{msg}</p>}
      <ErrorBox error={error} />

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card space-y-3 p-4">
          <h2 className="font-semibold">Details</h2>
          <p className="text-sm text-slate-500">{s.email}{s.phone ? ` · ${s.phone}` : ""} · enrolled {s.enrollment_date}</p>
          <div className="grid gap-3 sm:grid-cols-2">
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
          </div>
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
