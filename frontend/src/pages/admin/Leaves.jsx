import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useState } from "react";

import { api } from "../../api/client";
import { spring, toast } from "../../components/motion";
import { EmptyState, ErrorBox, PageHeader, Spinner, StatusBadge, usePolling } from "../../components/ui";

const TABS = [
  ["pending", "Pending"],
  ["approved", "Approved"],
  ["rejected", "Rejected"],
];

// Staff: student leave requests. Approved leave ke din absent nahi gine jaate.
export default function Leaves() {
  const [tab, setTab] = useState("pending");
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(() => api(`/v1/admin/leaves?status=${tab}`).then(setRows).catch((e) => setError(e.message)), [tab]);
  useEffect(() => {
    setRows(null);
    load();
  }, [load]);
  usePolling(load, 20000);

  async function decide(lv, approve) {
    try {
      await api(`/v1/admin/leaves/${lv.id}`, { method: "PATCH", json: { approve } });
      toast(`${lv.full_name}: leave ${approve ? "approved" : "rejected"}`, approve ? "success" : "info");
      setRows((rs) => rs.filter((r) => r.id !== lv.id));
    } catch (e) {
      setError(e.message);
    }
  }

  const days = (lv) => Math.round((new Date(lv.end) - new Date(lv.start)) / 864e5) + 1;

  return (
    <div className="max-w-3xl space-y-4">
      <PageHeader title="Leave requests" subtitle="Approved leave days don't count as absent" />
      <div className="inline-flex rounded-2xl bg-slate-100/80 p-1 dark:bg-white/5" role="tablist">
        {TABS.map(([k, label]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)} className={`relative min-h-[40px] rounded-xl px-4 text-sm font-semibold ${tab === k ? "text-slate-900 dark:text-white" : "text-slate-500"}`}>
            {tab === k && <motion.span layoutId="leave-tab" transition={spring} className="absolute inset-0 rounded-xl bg-white shadow-soft dark:bg-white/10" />}
            <span className="relative">{label}</span>
          </button>
        ))}
      </div>
      <ErrorBox error={error} />
      {rows === null ? (
        <Spinner />
      ) : rows.length === 0 ? (
        <EmptyState title={tab === "pending" ? "No pending requests" : `No ${tab} leaves`} />
      ) : (
        <ul className="space-y-2">
          <AnimatePresence initial={false}>
            {rows.map((lv) => (
              <motion.li layout key={lv.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, x: 40 }} className="card p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold">{lv.full_name}</p>
                    <p className="text-sm text-slate-500">
                      {lv.start} → {lv.end} · {days(lv)} day{days(lv) > 1 ? "s" : ""}
                    </p>
                    <p className="mt-2 text-sm">{lv.reason}</p>
                  </div>
                  {lv.status === "pending" ? (
                    <div className="flex gap-2">
                      <button className="btn-primary" onClick={() => decide(lv, true)}>Approve</button>
                      <button className="btn-secondary" onClick={() => decide(lv, false)}>Reject</button>
                    </div>
                  ) : (
                    <StatusBadge status={lv.status} />
                  )}
                </div>
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      )}
    </div>
  );
}
