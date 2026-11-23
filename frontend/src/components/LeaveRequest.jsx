import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";

import { api } from "../api/client";
import { toast } from "./motion";
import { ErrorBox, StatusBadge, today } from "./ui";

// Student: leave request + status. Approve hone ke baad un dinon absent nahi gina jaata.
export default function LeaveRequest() {
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ start: today(), end: today(), reason: "" });
  const [rows, setRows] = useState([]);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = () => api("/v1/me/leaves").then(setRows).catch(() => {});
  useEffect(() => {
    load();
  }, []);

  async function submit(e) {
    e.preventDefault();
    setError(null);
    if (f.end < f.start) return setError("End date can't be before start date");
    if (f.reason.trim().length < 3) return setError("Please add a short reason");
    setBusy(true);
    try {
      await api("/v1/me/leaves", { method: "POST", json: f });
      toast("Leave request sent", "success", "Your teacher will review it");
      setOpen(false);
      setF({ start: today(), end: today(), reason: "" });
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card p-4 sm:p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Leave</h2>
        {!open && <button className="btn-secondary" onClick={() => setOpen(true)}>Request leave</button>}
      </div>
      <AnimatePresence>
        {open && (
          <motion.form initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} onSubmit={submit} className="mt-3 grid gap-3 overflow-hidden sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="lv-start">From</label>
              <input id="lv-start" type="date" className="input" value={f.start} onChange={(e) => setF({ ...f, start: e.target.value, end: e.target.value > f.end ? e.target.value : f.end })} />
            </div>
            <div>
              <label className="label" htmlFor="lv-end">To</label>
              <input id="lv-end" type="date" className="input" min={f.start} value={f.end} onChange={(e) => setF({ ...f, end: e.target.value })} />
            </div>
            <div className="sm:col-span-2">
              <label className="label" htmlFor="lv-reason">Reason</label>
              <textarea id="lv-reason" className="input min-h-[80px]" maxLength={500} placeholder="e.g. fever, family function" value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} />
            </div>
            <div className="sm:col-span-2"><ErrorBox error={error} /></div>
            <div className="flex gap-2 sm:col-span-2">
              <button className="btn-primary" disabled={busy}>{busy ? "Sending…" : "Send request"}</button>
              <button type="button" className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button>
            </div>
          </motion.form>
        )}
      </AnimatePresence>
      {rows.length > 0 && (
        <ul className="mt-3 divide-y divide-slate-100 dark:divide-white/5">
          {rows.slice(0, 5).map((lv) => (
            <li key={lv.id} className="flex items-center justify-between gap-2 py-2 text-sm">
              <span>
                <span className="font-medium">{lv.start === lv.end ? lv.start : `${lv.start} → ${lv.end}`}</span>
                <span className="block text-xs text-slate-500">{lv.reason}</span>
              </span>
              <StatusBadge status={lv.status} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
