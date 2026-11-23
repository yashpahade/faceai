import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";

import { api, fd } from "../api/client";
import FaceCamera from "./FaceCamera";
import { spring, toast } from "./motion";
import { StatusBadge } from "./ui";

// Admin kiosk: har ~2.5s ek frame /v1/admin/attendance/scan pe. Ek request khatam hone ke baad hi
// agli (overlap nahi), tab hidden ho to pause. HAR frame ka nateeja dikhta hai (face nahi /
// anjaan / pehchana + kyun reject), taaki "kuch update nahi hua" kabhi chupchaap na ho.
const DEDUPE_MS = 30000; // same insaan + same nateeja 30s tak dobara feed mein nahi

export default function LiveDetector({ intervalMs = 2500, facing = "user" }) {
  const cam = useRef(null);
  const seen = useRef(new Map());
  const [running, setRunning] = useState(false);
  const [feed, setFeed] = useState([]);
  const [error, setError] = useState(null);
  const [frame, setFrame] = useState(null); // last frame summary
  const [stats, setStats] = useState({ frames: 0, lastMs: null, marked: 0 });

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
          const r = await api("/v1/admin/attendance/scan", { method: "POST", form: fd([["file", new File([blob], "frame.jpg", { type: "image/jpeg" })]]) });
          setError(null);
          setFrame(r);
          const now = Date.now();
          const at = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
          const fresh = [];
          for (const x of r.results) {
            const key = `${x.user_id}:${x.status}:${x.reason}`;
            if (now - (seen.current.get(key) || 0) < DEDUPE_MS) continue;
            seen.current.set(key, now);
            fresh.push({ ...x, at, id: `${key}:${now}` });
            if (x.status === "present" || x.status === "late") toast(`${x.full_name} marked ${x.status}`, x.status === "late" ? "info" : "success");
          }
          if (r.unknown > 0 && now - (seen.current.get("unknown") || 0) > 10000) {
            seen.current.set("unknown", now);
            fresh.push({ id: `unknown:${now}`, full_name: r.unknown > 1 ? `${r.unknown} unknown faces` : "Unknown face", status: "unknown", reason: "not enrolled, or low match", at });
          }
          if (fresh.length) setFeed((f) => [...fresh, ...f].slice(0, 50));
          setStats((s) => ({
            frames: s.frames + 1,
            lastMs: Math.round(performance.now() - t0),
            marked: s.marked + r.results.filter((x) => x.status === "present" || x.status === "late").length,
          }));
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

  const recognized = frame ? frame.faces - frame.unknown : 0;
  const summary = !frame ? null : frame.faces === 0 ? "No face in view" : `${frame.faces} face${frame.faces > 1 ? "s" : ""} · ${recognized} recognized${frame.unknown ? ` · ${frame.unknown} unknown` : ""}`;

  return (
    <div className="grid gap-4 lg:grid-cols-[3fr_2fr]">
      <div className="space-y-3">
        <FaceCamera ref={cam} facing={facing} overlay={running} state={running ? "scanning" : "idle"} hint={running ? summary || "Scanning… look at the camera" : null} />
        <div className="flex items-center gap-3">
          <button className={running ? "btn-secondary flex-1" : "btn-primary flex-1"} onClick={() => setRunning((r) => !r)}>
            {running ? "Stop scanning" : "Start live attendance"}
          </button>
          <span className="text-right text-xs tabular-nums text-slate-500">
            {stats.marked} marked · {stats.frames} frames
            {stats.lastMs ? <br /> : null}
            {stats.lastMs ? `${stats.lastMs} ms/frame` : ""}
          </span>
        </div>
        {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-700 dark:bg-red-500/10 dark:text-red-300">{error}</p>}
      </div>

      <div className="card p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-semibold">Live feed</h2>
          {running && (
            <span className="flex items-center gap-1.5 text-xs font-medium text-emerald-600">
              <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-500" /> live
            </span>
          )}
        </div>
        {feed.length === 0 ? (
          <p className="text-sm text-slate-500">{running ? "Waiting for a face…" : "Press start. Every detection shows up here, including faces that can't be marked and why."}</p>
        ) : (
          <ul className="max-h-[60vh] space-y-2 overflow-y-auto" aria-live="polite">
            <AnimatePresence initial={false}>
              {feed.map((r) => (
                <motion.li layout key={r.id} initial={{ opacity: 0, x: 24, scale: 0.95 }} animate={{ opacity: 1, x: 0, scale: 1 }} transition={spring} className="flex items-center justify-between gap-2 rounded-xl bg-slate-50 p-2.5 dark:bg-white/5">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{r.full_name}</p>
                    <p className="text-xs text-slate-500">
                      {r.at}
                      {r.status === "rejected" || r.status === "unknown" ? ` · ${r.reason}` : r.confidence != null ? ` · match ${r.confidence.toFixed(2)}` : ""}
                    </p>
                  </div>
                  {r.status === "unknown" ? <span className="chip bg-slate-200 text-slate-700 dark:bg-white/10 dark:text-slate-300">unknown</span> : <StatusBadge status={r.status} />}
                </motion.li>
              ))}
            </AnimatePresence>
          </ul>
        )}
      </div>
    </div>
  );
}
