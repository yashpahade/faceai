import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../../api/client";
import { Stagger, StaggerItem, toast } from "../../components/motion";
import { BatchSelector, EmptyState, ErrorBox, PageHeader, Spinner, StatusBadge, useBatches } from "../../components/ui";

// Student CRM: list, search, batch filter, add.
export default function Students() {
  const { batches } = useBatches();
  const [q, setQ] = useState("");
  const [batch, setBatch] = useState(null);
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);
  const [adding, setAdding] = useState(false);
  const [created, setCreated] = useState(null);

  const load = () => {
    const p = new URLSearchParams();
    if (q) p.set("q", q);
    if (batch) p.set("batch_id", batch);
    api(`/v1/admin/students?${p}`).then(setRows).catch((e) => setError(e.message));
  };
  useEffect(() => {
    const t = setTimeout(load, 250); // debounce search
    return () => clearTimeout(t);
  }, [q, batch]);

  const batchName = (id) => batches.find((b) => b.id === id)?.name || "—";

  return (
    <div className="space-y-4">
      <PageHeader title="Students">
        <button className="btn-primary" onClick={() => setAdding(true)}>+ Add student</button>
      </PageHeader>
      {created && (
        <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} className="card border-emerald-300 bg-emerald-50 p-4 text-sm dark:bg-emerald-500/10">
          <b>{created.student.full_name}</b> added. Temporary password (shown once): <code className="rounded bg-white px-1 dark:bg-slate-900">{created.temporary_password}</code>
          <button className="ml-3 underline" onClick={() => setCreated(null)}>Dismiss</button>
        </motion.div>
      )}
      <AnimatePresence>{adding && <AddStudent batches={batches} onClose={() => setAdding(false)} onCreated={(r) => { setCreated(r); setAdding(false); toast(`${r.student.full_name} added`); load(); }} />}</AnimatePresence>

      <div className="flex flex-col gap-2 sm:flex-row">
        <input className="input" placeholder="Search name, email, roll no…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search students" />
        <BatchSelector value={batch} onChange={setBatch} batches={batches} className="sm:w-56" />
      </div>
      <ErrorBox error={error} />
      {rows === null ? (
        <Spinner />
      ) : rows.length === 0 ? (
        <EmptyState title="No students found">Add one, or change the search.</EmptyState>
      ) : (
        <Stagger key={`${q}-${batch}-${rows.length}`} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {rows.map((s) => (
            <StaggerItem key={s.id}>
              <StudentCard s={s} batch={batchName(s.batch_id)} />
            </StaggerItem>
          ))}
        </Stagger>
      )}
    </div>
  );
}

export function StudentCard({ s, batch }) {
  const initials = s.full_name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  return (
    <Link to={`/admin/students/${s.id}`} className="card card-hover group flex items-center gap-3 p-4">
      <div className="relative flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-500 to-accent-500 font-bold text-white shadow-glow transition group-hover:rotate-3 group-hover:scale-105">
        {initials}
        {s.face_enrolled && <span className="absolute -bottom-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500 text-[10px] ring-2 ring-white dark:ring-ink-850" title="Face enrolled">✓</span>}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate font-semibold">{s.full_name}</p>
        <p className="truncate text-xs text-slate-500">{s.roll_no ? `${s.roll_no} · ` : ""}{batch}</p>
        <div className="mt-1 flex gap-1">
          <StatusBadge status={s.status} />
          {!s.face_enrolled && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">no face</span>}
        </div>
      </div>
    </Link>
  );
}

function AddStudent({ batches, onClose, onCreated }) {
  const [f, setF] = useState({ full_name: "", email: "", phone: "", roll_no: "", batch_id: "", consent: false });
  const [error, setError] = useState(null);
  async function submit(e) {
    e.preventDefault();
    setError(null);
    try {
      const body = { ...f, phone: f.phone || null, roll_no: f.roll_no || null, batch_id: f.batch_id || null };
      onCreated(await api("/v1/admin/students", { method: "POST", json: body }));
    } catch (err) {
      setError(err.message);
    }
  }
  return (
    <motion.form initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} onSubmit={submit} className="card grid gap-3 overflow-hidden p-4 sm:grid-cols-2">
      {[
        ["full_name", "Full name", true],
        ["email", "Email", true],
        ["phone", "Phone", false],
        ["roll_no", "Roll no", false],
      ].map(([k, label, req]) => (
        <div key={k}>
          <label className="label" htmlFor={`new-${k}`}>{label}</label>
          <input id={`new-${k}`} className="input" required={req} type={k === "email" ? "email" : "text"} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} />
        </div>
      ))}
      <div>
        <label className="label" htmlFor="new-batch">Batch</label>
        <select id="new-batch" className="input" value={f.batch_id} onChange={(e) => setF({ ...f, batch_id: e.target.value })}>
          <option value="">— none —</option>
          {batches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
      </div>
      <label className="flex items-start gap-2 text-sm sm:col-span-2">
        <input type="checkbox" className="mt-1 h-5 w-5" required checked={f.consent} onChange={(e) => setF({ ...f, consent: e.target.checked })} />
        Student has given written consent for face data processing.
      </label>
      <div className="sm:col-span-2"><ErrorBox error={error} /></div>
      <div className="flex gap-2 sm:col-span-2">
        <button className="btn-primary">Add</button>
        <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
      </div>
    </motion.form>
  );
}
