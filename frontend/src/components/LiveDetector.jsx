import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";

import { api, fd } from "../api/client";
import FaceCamera from "./FaceCamera";
import { spring } from "./motion";
import { StatusBadge } from "./ui";

// Admin kiosk: har few seconds ek frame /v1/admin/attendance/scan pe bhejo, results ki live feed.
// Ek request khatam hone ke baad hi agli (overlap nahi) -> server overload nahi, slow network pe
// requests jama nahi hoti. Tab hidden ho to scanning ruk jaati hai (battery + server).
export default function LiveDetector({ intervalMs = 2500, facing = "user" }) {
  const cam = useRef(null);
  const [running, setRunning] = useState(false);
  const [feed, setFeed] = useState([]);
  const [error, setError] = useState(null);
  const [stats, setStats] = useState({ frames: 0, lastMs: null });

  useEffect(() => {
    if (!running) return;
    let stop = false;
    let timer;
    async function tick() {
      if (stop) return;
      if (document.visibilityState === "visible" && cam.current?.ready()) {
        const t0 = performance.now();
        try {
          const blob = await cam.current.capture();
          const results = await api("/v1/admin/attendance/scan", { method: "POST", form: fd([["file", new File([blob], "frame.jpg", { type: "image/jpeg" })]]) });
          setError(null);
          setStats((s) => ({ frames: s.frames + 1, lastMs: Math.round(performance.now() - t0) }));
          const fresh = results.filter((r) => r.status !== "already_marked");
          if (fresh.length) {
            const at = new Date().toLocaleTimeString();
            setFeed((f) => [...fresh.map((r) => ({ ...r, at })), ...f].slice(0, 50));
          }
        } catch (e) {
          setError(e.message);
        }
      }
      timer = setTimeout(tick, intervalMs);
    }
    tick();
    return () => {
      stop = true;
      clearTimeout(timer);
    };
  }, [running, intervalMs]);

  return (
    <div className="grid gap-4 lg:grid-cols-[3fr_2fr]">
      <div className="space-y-3">
        <FaceCamera ref={cam} facing={facing} overlay={running} state={running ? "scanning" : "idle"} hint={running ? "Scanning… look at the camera" : null} />
        <div className="flex items-center gap-3">
          <button className={running ? "btn-secondary flex-1" : "btn-primary flex-1"} onClick={() => setRunning((r) => !r)}>
            {running ? "Stop scanning" : "Start live attendance"}
          </button>
          <span className="text-xs text-slate-500 tabular-nums">
            {stats.frames} frames{stats.lastMs ? ` · ${stats.lastMs} ms` : ""}
          </span>
        </div>
        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
      </div>
      <div className="card p-4">
        <h2 className="mb-3 font-semibold">Marked just now</h2>
        {feed.length === 0 ? (
          <p className="text-sm text-slate-500">Recognized students appear here.</p>
        ) : (
          <ul className="max-h-[60vh] space-y-2 overflow-y-auto" aria-live="polite">
            <AnimatePresence initial={false}>
            {feed.map((r) => (
              <motion.li layout key={`${r.user_id}-${r.at}`} initial={{ opacity: 0, x: 24, scale: 0.95 }} animate={{ opacity: 1, x: 0, scale: 1 }} transition={spring} className="flex items-center justify-between gap-2 rounded-xl bg-slate-50 p-2.5 dark:bg-white/5">
                <div className="min-w-0">
                  <p className="truncate font-medium">{r.full_name}</p>
                  <p className="text-xs text-slate-500">
                    {r.at}
                    {r.status === "rejected" ? ` · ${r.reason}` : r.confidence != null ? ` · match ${r.confidence.toFixed(2)}` : ""}
                  </p>
                </div>
                <StatusBadge status={r.status} />
              </motion.li>
            ))}
            </AnimatePresence>
          </ul>
        )}
      </div>
    </div>
  );
}
