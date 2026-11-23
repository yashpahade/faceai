import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";

import { api } from "../../api/client";
import Field from "../../components/Field";
import { Stagger, StaggerItem, toast } from "../../components/motion";
import { EmptyState, ErrorBox, PageHeader, Spinner, useBatches } from "../../components/ui";
import { nameError, phoneError, sanitizeName, sanitizePhone } from "../../lib/validate";

// Admin: teachers + their batches. Teacher sirf assigned batches ke students/attendance/reports dekhta hai.
export default function Teachers() {
  const { batches } = useBatches();
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);
  const [adding, setAdding] = useState(false);
  const [created, setCreated] = useState(null);

  const load = () => api("/v1/admin/teachers").then(setRows).catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);

  async function toggle(t, batchId) {
    const ids = t.batch_ids.includes(batchId) ? t.batch_ids.filter((x) => x !== batchId) : [...t.batch_ids, batchId];
    try {
      await api(`/v1/admin/teachers/${t.id}/batches`, { method: "PUT", json: { batch_ids: ids } });
      setRows((rs) => rs.map((r) => (r.id === t.id ? { ...r, batch_ids: ids } : r)));
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader title="Teachers" subtitle="A teacher only sees the batches you assign">
        <button className="btn-primary" onClick={() => setAdding(true)}>+ Add teacher</button>
      </PageHeader>
      {created && (
        <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} className="card border-emerald-300 bg-emerald-50 p-4 text-sm dark:bg-emerald-500/10">
          <b>{created.student.full_name}</b> added. Temporary password (shown once): <code className="rounded bg-white px-1 dark:bg-slate-900">{created.temporary_password}</code>
          <button className="ml-3 underline" onClick={() => setCreated(null)}>Dismiss</button>
        </motion.div>
      )}
      <AnimatePresence>{adding && <AddTeacher batches={batches} onClose={() => setAdding(false)} onCreated={(r) => { setCreated(r); setAdding(false); toast(`${r.student.full_name} added`); load(); }} />}</AnimatePresence>
      <ErrorBox error={error} />
      {rows === null ? (
        <Spinner />
      ) : rows.length === 0 ? (
        <EmptyState title="No teachers yet">Add a teacher and assign their batches.</EmptyState>
      ) : (
        <Stagger className="grid gap-3 md:grid-cols-2">
          {rows.map((t) => (
            <StaggerItem key={t.id} className="card p-4">
              <p className="font-semibold">{t.full_name}</p>
              <p className="text-xs text-slate-500">{t.email}{t.phone ? ` · ${t.phone}` : ""}</p>
              <p className="mb-2 mt-3 text-xs font-semibold uppercase tracking-wider text-slate-500">Batches</p>
              <div className="flex flex-wrap gap-2">
                {batches.length === 0 && <span className="text-sm text-slate-500">Create a batch first</span>}
                {batches.map((b) => {
                  const on = t.batch_ids.includes(b.id);
                  return (
                    <button key={b.id} onClick={() => toggle(t, b.id)} aria-pressed={on} className={`min-h-[36px] rounded-full border px-3 text-sm font-medium transition ${on ? "border-brand-600 bg-brand-600 text-white" : "border-slate-300 text-slate-600 hover:border-brand-400 dark:border-white/15 dark:text-slate-300"}`}>
                      {on ? "✓ " : ""}{b.name}
                    </button>
                  );
                })}
              </div>
            </StaggerItem>
          ))}
        </Stagger>
      )}
    </div>
  );
}

function AddTeacher({ batches, onClose, onCreated }) {
  const [f, setF] = useState({ full_name: "", email: "", phone: "", batch_ids: [] });
  const [tried, setTried] = useState(false);
  const [error, setError] = useState(null);
  const errs = {
    full_name: nameError(f.full_name),
    email: /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(f.email) ? null : "Enter a valid email",
    phone: phoneError(f.phone),
  };
  async function submit(e) {
    e.preventDefault();
    setTried(true);
    setError(null);
    if (Object.values(errs).some(Boolean)) return;
    try {
      onCreated(await api("/v1/admin/teachers", { method: "POST", json: { ...f, phone: f.phone || null } }));
    } catch (err) {
      setError(err.message);
    }
  }
  return (
    <motion.form initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} onSubmit={submit} noValidate className="card grid gap-3 overflow-hidden p-4 sm:grid-cols-3">
      <Field id="t-name" label="Full name" error={errs.full_name} touched={tried}>
        <input id="t-name" className="input" value={f.full_name} onChange={(e) => setF({ ...f, full_name: sanitizeName(e.target.value) })} />
      </Field>
      <Field id="t-email" label="Email" error={errs.email} touched={tried}>
        <input id="t-email" className="input" type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value.trim() })} />
      </Field>
      <Field id="t-phone" label="Mobile" error={errs.phone} touched={tried} hint="optional">
        <input id="t-phone" className="input" type="tel" inputMode="numeric" maxLength={13} value={f.phone} onChange={(e) => setF({ ...f, phone: sanitizePhone(e.target.value) })} />
      </Field>
      <fieldset className="sm:col-span-3">
        <legend className="label">Batches</legend>
        <div className="flex flex-wrap gap-2">
          {batches.map((b) => {
            const on = f.batch_ids.includes(b.id);
            return (
              <button type="button" key={b.id} aria-pressed={on} onClick={() => setF({ ...f, batch_ids: on ? f.batch_ids.filter((x) => x !== b.id) : [...f.batch_ids, b.id] })} className={`min-h-[36px] rounded-full border px-3 text-sm ${on ? "border-brand-600 bg-brand-600 text-white" : "border-slate-300 dark:border-white/15"}`}>
                {b.name}
              </button>
            );
          })}
        </div>
      </fieldset>
      <div className="sm:col-span-3"><ErrorBox error={error} /></div>
      <div className="flex gap-2 sm:col-span-3">
        <button className="btn-primary">Add teacher</button>
        <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
      </div>
    </motion.form>
  );
}
