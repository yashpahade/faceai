import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import AttendanceTable from "../components/AttendanceTable";
import LeaveRequest from "../components/LeaveRequest";
import LivenessFlow from "../components/LivenessFlow";
import { ProgressRing, Stagger, SuccessBurst, toast } from "../components/motion";
import { ErrorBox, Spinner, StatsCard } from "../components/ui";
import { useAuth } from "../store/auth";

const greet = () => {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
};

export default function Dashboard() {
  const user = useAuth((s) => s.user);
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);
  const [marking, setMarking] = useState(false);
  const [result, setResult] = useState(null);

  const load = () => api("/v1/me/attendance").then(setRows).catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);

  async function mark(token) {
    const r = await api("/v1/me/attendance", { method: "POST", json: { liveness_token: token } });
    setResult(r);
    setMarking(false);
    if (r.status === "present" || r.status === "late") toast(r.status === "late" ? "Marked late" : "Attendance marked", r.status === "late" ? "info" : "success");
    else if (r.status === "rejected") toast("Not marked", "error", r.reason);
    load();
  }

  const count = (s) => rows?.filter((r) => r.status === s).length ?? 0;
  const total = rows?.length ?? 0;
  const pct = total ? (100 * (count("present") + count("late"))) / total : null;
  const markedToday = rows?.some((r) => r.day === new Date().toLocaleDateString("en-CA") && r.status !== "absent");

  return (
    <div className="space-y-6">
      {/* hero */}
      <motion.section initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="relative overflow-hidden rounded-[1.75rem] bg-gradient-to-br from-brand-600 via-brand-500 to-accent-500 p-5 text-white shadow-glow sm:p-7">
        <div className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-white/15 blur-2xl" />
        <div className="pointer-events-none absolute -bottom-20 left-10 h-48 w-48 rounded-full bg-accent-400/40 blur-3xl" />
        <div className="relative flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium text-white/80">{greet()},</p>
            <h1 className="text-3xl font-bold tracking-tight">{user.full_name.split(" ")[0]} 👋</h1>
            <p className="mt-2 text-sm text-white/85">
              {markedToday ? "You're marked for today. See you tomorrow!" : "Ready? Mark today's attendance with your face."}
            </p>
          </div>
          {!marking && !markedToday && (
            <button
              className="inline-flex min-h-[48px] items-center justify-center gap-2 rounded-2xl bg-white px-5 font-semibold text-brand-700 shadow-lg transition hover:scale-[1.02] active:scale-[0.98] disabled:opacity-60"
              disabled={!user.face_enrolled}
              onClick={() => {
                setResult(null);
                setMarking(true);
              }}
            >
              <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
                <path d="M9 10h.01M15 10h.01M9.5 15a3.5 3.5 0 0 0 5 0M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3" />
              </svg>
              Mark attendance
            </button>
          )}
        </div>
      </motion.section>

      {!user.face_enrolled && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card flex items-center justify-between gap-3 border-amber-200 bg-amber-50/80 p-4 text-sm dark:border-amber-500/20 dark:bg-amber-500/10">
          <span>Your face isn't enrolled yet, so face login and attendance are off.</span>
          <Link to="/profile" className="btn-primary shrink-0">Enroll</Link>
        </motion.div>
      )}

      <AnimatePresence mode="wait">
        {marking && (
          <motion.div key="mark" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
            <div className="card p-4 sm:p-6">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-lg font-semibold">Verify it's you</h2>
                <button className="text-sm text-slate-500 hover:text-slate-800 dark:hover:text-white" onClick={() => setMarking(false)}>Cancel</button>
              </div>
              <LivenessFlow onToken={mark} actionLabel="Start" successTitle="It's you!" />
            </div>
          </motion.div>
        )}
        {result && !marking && (
          <motion.div key="res" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="card p-4">
            {result.status === "present" || result.status === "late" ? (
              <SuccessBurst title={result.status === "late" ? "Marked late" : "You're present!"} subtitle={new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} tone={result.status === "late" ? "amber" : "green"} />
            ) : (
              <p className="p-2 text-center text-sm">{result.status === "already_marked" ? "Already marked today ✓" : result.reason}</p>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      <div className="grid gap-4 lg:grid-cols-[auto_1fr]">
        <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.1 }} className="card flex items-center gap-5 p-5">
          <ProgressRing value={pct} label="30 days" />
          <div className="text-sm">
            <p className="font-semibold">Attendance rate</p>
            <p className="mt-1 max-w-[12rem] text-slate-500">{pct == null ? "No classes yet." : pct >= 75 ? "Great going, above the 75% mark." : "Below 75%. Try not to miss classes."}</p>
          </div>
        </motion.div>
        <Stagger className="grid grid-cols-3 gap-3">
          <StatsCard label="Present" value={count("present")} tone="green" icon="check" />
          <StatsCard label="Late" value={count("late")} tone="amber" icon="clock" />
          <StatsCard label="Absent" value={count("absent")} tone="red" icon="x" />
        </Stagger>
      </div>

      <LeaveRequest />

      <section>
        <h2 className="mb-3 text-lg font-semibold">My history</h2>
        <ErrorBox error={error} />
        {rows === null ? <Spinner /> : <AttendanceTable rows={rows} showStudent={false} />}
      </section>
    </div>
  );
}
