import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { api } from "../../api/client";
import { BatchSelector, ErrorBox, PageHeader, Spinner, daysAgo, today } from "../../components/ui";

const RANGES = [
  ["7", "Last 7 days"],
  ["30", "Last 30 days"],
  ["90", "Last 90 days"],
];

export default function Reports() {
  const [range, setRange] = useState("30");
  const [batch, setBatch] = useState(null);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const params = () => {
    const p = new URLSearchParams({ from: daysAgo(Number(range) - 1), to: today() });
    if (batch) p.set("batch_id", batch);
    return p;
  };
  useEffect(() => {
    setData(null);
    api(`/v1/admin/reports/summary?${params()}`).then(setData).catch((e) => setError(e.message));
  }, [range, batch]);

  async function exportCsv() {
    try {
      const res = await api(`/v1/admin/reports/export.csv?${params()}`, { raw: true });
      const url = URL.createObjectURL(await res.blob());
      const a = Object.assign(document.createElement("a"), { href: url, download: `attendance_${today()}.csv` });
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader title="Reports">
        <button className="btn-secondary" onClick={exportCsv}>Export CSV</button>
      </PageHeader>
      <div className="flex flex-col gap-2 sm:flex-row">
        <select className="input sm:w-48" value={range} onChange={(e) => setRange(e.target.value)} aria-label="Range">
          {RANGES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <BatchSelector value={batch} onChange={setBatch} className="sm:w-56" />
      </div>
      <ErrorBox error={error} />
      {!data ? (
        <Spinner />
      ) : (
        <>
          <div className="card p-4">
            <h2 className="mb-3 font-semibold">Daily attendance</h2>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.days} margin={{ left: -20 }}>
                  <defs>
                    <linearGradient id="g-present" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#34d399" /><stop offset="100%" stopColor="#059669" /></linearGradient>
                    <linearGradient id="g-late" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#fbbf24" /><stop offset="100%" stopColor="#d97706" /></linearGradient>
                    <linearGradient id="g-absent" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#fb7185" /><stop offset="100%" stopColor="#e11d48" /></linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#94a3b833" />
                  <XAxis dataKey="day" tickFormatter={(d) => d.slice(5)} fontSize={11} />
                  <YAxis allowDecimals={false} fontSize={11} />
                  <Tooltip cursor={{ fill: "rgba(99,102,241,.08)" }} contentStyle={{ borderRadius: 12, border: "none", boxShadow: "0 10px 30px -10px rgba(15,23,42,.3)" }} />
                  <Legend />
                  <Bar dataKey="present" stackId="a" fill="url(#g-present)" name="Present" animationDuration={900} />
                  <Bar dataKey="late" stackId="a" fill="url(#g-late)" name="Late" animationDuration={900} />
                  <Bar dataKey="absent" stackId="a" fill="url(#g-absent)" name="Absent" animationDuration={900} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="card overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 text-xs uppercase text-slate-500 dark:border-slate-800">
                <tr>
                  <th className="px-4 py-3">Student</th>
                  <th className="px-4 py-3">Batch</th>
                  <th className="px-4 py-3 text-right">Present</th>
                  <th className="px-4 py-3 text-right">Late</th>
                  <th className="px-4 py-3 text-right">Absent</th>
                  <th className="px-4 py-3 text-right">%</th>
                </tr>
              </thead>
              <tbody>
                {data.students.map((s) => (
                  <tr key={s.user_id} className="border-b border-slate-100 last:border-0 dark:border-slate-800/60">
                    <td className="px-4 py-2 font-medium">{s.full_name}</td>
                    <td className="px-4 py-2">{s.batch}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{s.present}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{s.late}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{s.absent}</td>
                    <td className={`px-4 py-2 text-right font-semibold tabular-nums ${s.attendance_pct != null && s.attendance_pct < 75 ? "text-red-600" : ""}`}>
                      {s.attendance_pct ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data.students.length === 0 && <p className="p-4 text-sm text-slate-500">No data in this range.</p>}
          </div>
          <p className="text-xs text-slate-500">Below 75% is highlighted (common minimum attendance rule).</p>
        </>
      )}
    </div>
  );
}
