import { motion } from "framer-motion";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../../api/client";
import { SkeletonCards, Stagger, StaggerItem } from "../../components/motion";
import { ErrorBox, PageHeader, StatsCard, StatusBadge, usePolling } from "../../components/ui";

const ago = (iso) => {
  const s = Math.max(1, Math.round((Date.now() - new Date(iso)) / 1000));
  return s < 60 ? `${s}s ago` : s < 3600 ? `${Math.round(s / 60)}m ago` : s < 86400 ? `${Math.round(s / 3600)}h ago` : new Date(iso).toLocaleDateString();
};

export default function Overview() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const load = useCallback(() => {
    api("/v1/admin/overview").then((d) => { setData(d); setError(null); }).catch((e) => setError(e.message));
  }, []);
  useEffect(load, [load]);
  usePolling(load, 10000); // live kiosk se lagi attendance yahan khud dikhe

  const marked = data ? data.today.present + data.today.late : 0;
  const rate = data?.students ? Math.round((100 * marked) / data.students) : null;

  return (
    <div className="space-y-6">
      <PageHeader title="Overview" subtitle={new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })}>
        <Link to="/admin/live" className="btn-primary">
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-white opacity-75" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-white" />
          </span>
          Start live attendance
        </Link>
      </PageHeader>
      <ErrorBox error={error} />

      {!data ? (
        <SkeletonCards />
      ) : (
        <Stagger className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatsCard label="Students" value={data.students} sub={`${data.batches} batches`} icon="users" />
          <StatsCard label="Face enrolled" value={data.face_enrolled} sub={data.students ? `${Math.round((100 * data.face_enrolled) / data.students)}% of students` : "—"} tone="green" icon="face" />
          <StatsCard label="Marked today" value={marked} sub={rate != null ? `${rate}% turnout` : "—"} tone="green" icon="check" />
          <StatsCard label="Late today" value={data.today.late} tone="amber" icon="clock" />
        </Stagger>
      )}

      <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        <section className="card p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-semibold">Recent activity</h2>
            <Link to="/admin/attendance" className="text-sm font-medium text-brand-600 hover:underline dark:text-brand-300">View all</Link>
          </div>
          {!data ? null : data.recent.length === 0 ? (
            <p className="py-6 text-center text-sm text-slate-500">No attendance yet. Start a live session to begin.</p>
          ) : (
            <Stagger as="ul" className="space-y-1">
              {data.recent.map((r, i) => (
                <StaggerItem as="li" key={i} className="flex items-center gap-3 rounded-xl p-2 transition hover:bg-slate-50 dark:hover:bg-white/5">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand-100 to-accent-400/30 text-xs font-bold text-brand-700 dark:from-brand-500/30 dark:text-brand-100">
                    {r.full_name.split(" ").map((p) => p[0]).slice(0, 2).join("")}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold">{r.full_name}</span>
                    <span className="block text-xs capitalize text-slate-500">{r.method} · {ago(r.marked_at)}</span>
                  </span>
                  <StatusBadge status={r.status} />
                </StaggerItem>
              ))}
            </Stagger>
          )}
        </section>

        <section className="card relative overflow-hidden p-5">
          <div className="pointer-events-none absolute -right-10 -top-10 h-40 w-40 rounded-full bg-gradient-to-br from-brand-400/30 to-accent-400/30 blur-2xl" />
          <h2 className="relative font-semibold">Quick actions</h2>
          <div className="relative mt-4 grid gap-2">
            {[
              ["/admin/students", "Add or manage students"],
              ["/admin/batches", "Set up batch timings"],
              ["/admin/reports", "Download monthly report"],
            ].map(([to, label], i) => (
              <motion.div key={to} initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 + i * 0.07 }}>
                <Link to={to} className="group flex items-center justify-between rounded-xl border border-slate-200/70 px-3.5 py-3 text-sm font-medium transition hover:border-brand-300 hover:bg-brand-50/50 dark:border-white/10 dark:hover:bg-white/5">
                  {label}
                  <span className="text-slate-400 transition group-hover:translate-x-1 group-hover:text-brand-600">→</span>
                </Link>
              </motion.div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
