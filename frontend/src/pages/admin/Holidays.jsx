import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";

import { api } from "../../api/client";
import { toast } from "../../components/motion";
import { EmptyState, ErrorBox, PageHeader, Spinner, today, useBatches } from "../../components/ui";

// Holidays: absent nahi gina jaata, attendance mark nahi hoti. Batch khaali = sab batches.
export default function Holidays() {
  const { batches } = useBatches();
  const [rows, setRows] = useState(null);
  const [form, setForm] = useState({ day: today(), name: "", batch_id: "" });
  const [error, setError] = useState(null);

  const load = () => api("/v1/admin/holidays").then(setRows).catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);

  async function add(e) {
    e.preventDefault();
    setError(null);
    try {
      await api("/v1/admin/holidays", { method: "POST", json: { ...form, batch_id: form.batch_id || null } });
      toast(`${form.name} added`);
      setForm({ ...form, name: "" });
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function remove(h) {
    if (!window.confirm(`Remove holiday "${h.name}" on ${h.day}?`)) return;
    await api(`/v1/admin/holidays/${h.id}`, { method: "DELETE" });
    load();
  }

  const batchName = (id) => (id ? batches.find((b) => b.id === id)?.name || "—" : "All batches");
  const fmt = (d) => new Date(`${d}T00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short", year: "numeric" });

  return (
    <div className="max-w-3xl space-y-4">
      <PageHeader title="Holidays" subtitle="No class: nobody is marked absent, attendance is closed" />
      <form onSubmit={add} className="card grid gap-3 p-4 sm:grid-cols-[auto_1fr_auto_auto] sm:items-end">
        <div>
          <label className="label" htmlFor="h-day">Date</label>
          <input id="h-day" type="date" className="input" required value={form.day} onChange={(e) => setForm({ ...form, day: e.target.value })} />
        </div>
        <div>
          <label className="label" htmlFor="h-name">Name</label>
          <input id="h-name" className="input" required maxLength={100} placeholder="Diwali" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </div>
        <div>
          <label className="label" htmlFor="h-batch">For</label>
          <select id="h-batch" className="input" value={form.batch_id} onChange={(e) => setForm({ ...form, batch_id: e.target.value })}>
            <option value="">All batches</option>
            {batches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        </div>
        <button className="btn-primary">Add</button>
      </form>
      <ErrorBox error={error} />
      {rows === null ? (
        <Spinner />
      ) : rows.length === 0 ? (
        <EmptyState title="No upcoming holidays" />
      ) : (
        <ul className="space-y-2">
          <AnimatePresence initial={false}>
            {rows.map((h) => (
              <motion.li layout key={h.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, x: -20 }} className={`card flex items-center justify-between gap-3 p-3 ${h.day < today() ? "opacity-60" : ""}`}>
                <div className="flex items-center gap-3">
                  <span className="flex h-11 w-11 flex-col items-center justify-center rounded-xl bg-sky-100 text-sky-800 dark:bg-sky-500/15 dark:text-sky-200">
                    <span className="text-[10px] font-semibold uppercase leading-none">{new Date(`${h.day}T00:00`).toLocaleDateString(undefined, { month: "short" })}</span>
                    <span className="text-lg font-bold leading-none">{Number(h.day.slice(8))}</span>
                  </span>
                  <span>
                    <span className="block font-semibold">{h.name}</span>
                    <span className="block text-xs text-slate-500">{fmt(h.day)} · {batchName(h.batch_id)}</span>
                  </span>
                </div>
                <button className="rounded-lg px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-500/10" onClick={() => remove(h)}>Remove</button>
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      )}
    </div>
  );
}
