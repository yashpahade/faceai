import { useState } from "react";

import { api } from "../../api/client";
import { EmptyState, ErrorBox, PageHeader, useBatches } from "../../components/ui";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const EMPTY = { name: "", start_time: "09:00", end_time: "10:00", days: "0,1,2,3,4", late_after_min: 10, open_before_min: 15 };

export default function Batches() {
  const { batches, reload, error: loadErr } = useBatches();
  const [form, setForm] = useState(null); // null | {..} (id => edit)
  const [error, setError] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setError(null);
    const { id, student_count, ...body } = form;
    try {
      await api(id ? `/v1/admin/batches/${id}` : "/v1/admin/batches", { method: id ? "PATCH" : "POST", json: body });
      setForm(null);
      reload();
    } catch (err) {
      setError(err.message);
    }
  }

  async function remove(b) {
    if (!window.confirm(`Delete batch ${b.name}? Its attendance records are deleted too.`)) return;
    await api(`/v1/admin/batches/${b.id}`, { method: "DELETE" });
    reload();
  }

  const days = (form?.days || "").split(",").filter(Boolean);
  const toggleDay = (i) => {
    const set = new Set(days);
    set.has(String(i)) ? set.delete(String(i)) : set.add(String(i));
    setForm({ ...form, days: [...set].sort().join(",") });
  };

  return (
    <div className="space-y-4">
      <PageHeader title="Batches">
        <button className="btn-primary" onClick={() => setForm(EMPTY)}>+ New batch</button>
      </PageHeader>
      <ErrorBox error={loadErr || error} />

      {form && (
        <form onSubmit={submit} className="card grid gap-3 p-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className="label" htmlFor="b-name">Name</label>
            <input id="b-name" className="input" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className="label" htmlFor="b-start">Starts</label>
            <input id="b-start" type="time" className="input" required value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })} />
          </div>
          <div>
            <label className="label" htmlFor="b-end">Ends</label>
            <input id="b-end" type="time" className="input" required value={form.end_time} onChange={(e) => setForm({ ...form, end_time: e.target.value })} />
          </div>
          <div>
            <label className="label" htmlFor="b-late">Late after (min)</label>
            <input id="b-late" type="number" min="0" className="input" value={form.late_after_min} onChange={(e) => setForm({ ...form, late_after_min: Number(e.target.value) })} />
          </div>
          <div>
            <label className="label" htmlFor="b-open">Opens before start (min)</label>
            <input id="b-open" type="number" min="0" className="input" value={form.open_before_min} onChange={(e) => setForm({ ...form, open_before_min: Number(e.target.value) })} />
          </div>
          <fieldset className="sm:col-span-2">
            <legend className="label">Days</legend>
            <div className="flex flex-wrap gap-2">
              {DAYS.map((d, i) => (
                <button type="button" key={d} onClick={() => toggleDay(i)} aria-pressed={days.includes(String(i))} className={`min-h-[40px] min-w-[52px] rounded-lg border text-sm font-medium ${days.includes(String(i)) ? "border-brand-600 bg-brand-600 text-white" : "border-slate-300 dark:border-slate-700"}`}>
                  {d}
                </button>
              ))}
            </div>
          </fieldset>
          <div className="flex gap-2 sm:col-span-2">
            <button className="btn-primary" disabled={!days.length}>{form.id ? "Save" : "Create"}</button>
            <button type="button" className="btn-secondary" onClick={() => setForm(null)}>Cancel</button>
          </div>
        </form>
      )}

      {batches.length === 0 && !form ? (
        <EmptyState title="No batches yet">Create a batch to start taking attendance.</EmptyState>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {batches.map((b) => (
            <div key={b.id} className="card p-4">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-semibold">{b.name}</p>
                  <p className="text-sm text-slate-500">
                    {b.start_time}–{b.end_time} · {b.days.split(",").map((i) => DAYS[i]).join(" ")}
                  </p>
                  <p className="text-xs text-slate-500">Late after {b.late_after_min} min · {b.student_count} students</p>
                </div>
              </div>
              <div className="mt-3 flex gap-2">
                <button className="btn-secondary flex-1" onClick={() => setForm(b)}>Edit</button>
                <button className="btn-secondary text-red-600" onClick={() => remove(b)}>Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
