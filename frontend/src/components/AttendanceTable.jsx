import { AnimatePresence, motion } from "framer-motion";
import { useMemo, useState } from "react";

import { StatusBadge } from "./ui";

// Sortable + filterable attendance grid. Mobile pe cards, desktop pe table.
const COLS = [
  ["day", "Date"],
  ["full_name", "Student"],
  ["batch", "Batch"],
  ["status", "Status"],
  ["method", "Method"],
  ["confidence", "Match"],
];

export default function AttendanceTable({ rows, showStudent = true, actions }) {
  const [sort, setSort] = useState({ key: "day", dir: -1 });
  const [filter, setFilter] = useState("");
  const [status, setStatus] = useState("");

  const view = useMemo(() => {
    const f = filter.trim().toLowerCase();
    return rows
      .filter((r) => (!status || r.status === status) && (!f || `${r.full_name} ${r.roll_no || ""} ${r.batch}`.toLowerCase().includes(f)))
      .sort((a, b) => {
        const x = a[sort.key] ?? "";
        const y = b[sort.key] ?? "";
        return (x > y ? 1 : x < y ? -1 : 0) * sort.dir;
      });
  }, [rows, sort, filter, status]);

  const cols = showStudent ? COLS : COLS.filter(([k]) => k !== "full_name" && k !== "batch");
  const toggle = (key) => setSort((s) => ({ key, dir: s.key === key ? -s.dir : 1 }));

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {showStudent && <input className="input flex-1" placeholder="Search name / roll no…" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Search" />}
        <select className="input w-auto" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status filter">
          <option value="">All statuses</option>
          <option value="present">Present</option>
          <option value="late">Late</option>
          <option value="absent">Absent</option>
          <option value="leave">Leave</option>
          <option value="holiday">Holiday</option>
        </select>
      </div>
      <p className="text-xs text-slate-500">{view.length} {view.length === 1 ? "record" : "records"}</p>

      {/* mobile cards */}
      <ul className="space-y-2 md:hidden">
        <AnimatePresence initial={false}>
        {view.slice(0, 200).map((r, i) => (
          <motion.li layout key={`${r.user_id}-${r.day}`} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0, transition: { delay: Math.min(i, 12) * 0.03 } }} exit={{ opacity: 0 }} className="card flex items-center justify-between gap-3 p-3">
            <div className="min-w-0">
              {showStudent && <p className="truncate font-semibold">{r.full_name}</p>}
              <p className="text-xs text-slate-500">
                {r.day} · {r.batch}
                {r.method ? ` · ${r.method}` : ""}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge status={r.status} />
              {actions?.(r)}
            </div>
          </motion.li>
        ))}
        </AnimatePresence>
      </ul>

      {/* desktop table */}
      <div className="card hidden overflow-x-auto md:block">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-xs uppercase text-slate-500 dark:border-slate-800">
            <tr>
              {cols.map(([k, label]) => (
                <th key={k} className="px-4 py-3">
                  <button onClick={() => toggle(k)} className="font-semibold uppercase">
                    {label} {sort.key === k ? (sort.dir > 0 ? "▲" : "▼") : ""}
                  </button>
                </th>
              ))}
              {actions && <th className="px-4 py-3" />}
            </tr>
          </thead>
          <tbody>
            {view.map((r) => (
              <tr key={`${r.user_id}-${r.day}`} className="border-b border-slate-100 transition-colors last:border-0 hover:bg-brand-50/40 dark:border-white/5 dark:hover:bg-white/[0.03]">
                <td className="px-4 py-2 tabular-nums">{r.day}</td>
                {showStudent && <td className="px-4 py-2 font-medium">{r.full_name}</td>}
                {showStudent && <td className="px-4 py-2">{r.batch}</td>}
                <td className="px-4 py-2">
                  <StatusBadge status={r.status} />
                </td>
                <td className="px-4 py-2 capitalize">{r.method || "—"}</td>
                <td className="px-4 py-2 tabular-nums">{r.confidence != null ? r.confidence.toFixed(2) : "—"}</td>
                {actions && <td className="px-4 py-2 text-right">{actions(r)}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
