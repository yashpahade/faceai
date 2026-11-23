import { AnimatePresence, motion } from "framer-motion";
import { useRef, useState } from "react";

import { api, fd } from "../api/client";
import FaceCamera from "./FaceCamera";
import { SuccessBurst } from "./motion";

// Active liveness: server random steps deta hai, har step pe ek frame -> verify -> single-use token.
// Direction: backend "turn_left" = naak IMAGE ke left. Mirrored preview mein user ko apna RIGHT.
const STEP = {
  turn_left: { text: "Turn your head right", arrow: "right" },
  turn_right: { text: "Turn your head left", arrow: "left" },
  center: { text: "Look straight at the camera", arrow: null },
};
const HOLD_MS = 1500;

function Arrow({ dir }) {
  if (!dir) return null;
  return (
    <motion.svg
      viewBox="0 0 24 24"
      className="h-7 w-7"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      animate={{ x: dir === "right" ? [0, 6, 0] : [0, -6, 0] }}
      transition={{ repeat: Infinity, duration: 0.9 }}
      aria-hidden="true"
    >
      <path d={dir === "right" ? "M5 12h14M13 6l6 6-6 6" : "M19 12H5M11 6l-6 6 6 6"} />
    </motion.svg>
  );
}

export default function LivenessFlow({ onToken, actionLabel = "Start face check", successTitle = "Verified" }) {
  const cam = useRef(null);
  const [phase, setPhase] = useState("idle"); // idle | running | verifying | done | error
  const [steps, setSteps] = useState([]);
  const [current, setCurrent] = useState(-1);
  const [error, setError] = useState(null);

  async function run() {
    setError(null);
    setPhase("running");
    try {
      const ch = await api("/v1/liveness/challenge", { method: "POST", auth: false });
      setSteps(ch.steps);
      const frames = [];
      for (let i = 0; i < ch.steps.length; i++) {
        setCurrent(i);
        await new Promise((r) => setTimeout(r, HOLD_MS));
        frames.push(await cam.current.capture());
      }
      setCurrent(ch.steps.length);
      setPhase("verifying");
      const form = fd([["challenge_id", ch.challenge_id], ...frames.map((f, i) => ["frames", new File([f], `f${i}.jpg`, { type: "image/jpeg" })])]);
      const r = await api("/v1/liveness/verify", { method: "POST", form, auth: false });
      if (!r.live) throw new Error(friendly(r.reason));
      setPhase("done");
      await onToken(r.token);
    } catch (e) {
      setError(e.message);
      setPhase("error");
      setCurrent(-1);
    }
  }

  const busy = phase === "running" || phase === "verifying";
  const step = steps[current];
  const camState = phase === "running" || phase === "verifying" ? "scanning" : phase === "done" ? "success" : phase === "error" ? "error" : "idle";

  return (
    <div className="space-y-4">
      <div className="relative">
        <FaceCamera ref={cam} state={camState} hint={phase === "verifying" ? "Verifying…" : null} />
        <AnimatePresence mode="wait">
          {phase === "running" && step && (
            <motion.div
              key={current}
              initial={{ opacity: 0, y: 16, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.35 }}
              className="absolute inset-x-3 bottom-3 flex items-center justify-center gap-3 rounded-2xl bg-black/60 px-4 py-3 text-base font-semibold text-white backdrop-blur-md"
              role="status"
            >
              {STEP[step]?.arrow === "left" && <Arrow dir="left" />}
              {STEP[step]?.text || step}
              {STEP[step]?.arrow === "right" && <Arrow dir="right" />}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* step progress */}
      {steps.length > 0 && busy && (
        <div className="flex items-center justify-center gap-2" aria-hidden="true">
          {steps.map((_, i) => (
            <motion.span
              key={i}
              className="h-1.5 rounded-full bg-brand-500"
              animate={{ width: i === current ? 32 : 10, opacity: i <= current ? 1 : 0.25 }}
              transition={{ duration: 0.35 }}
            />
          ))}
        </div>
      )}

      <AnimatePresence>
        {phase === "done" && <SuccessBurst title={successTitle} subtitle="Liveness confirmed" />}
      </AnimatePresence>

      <AnimatePresence>
        {error && (
          <motion.p initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-700 dark:bg-red-500/10 dark:text-red-300">
            {error}
          </motion.p>
        )}
      </AnimatePresence>

      {phase !== "done" && (
        <button onClick={run} disabled={busy} className="btn-primary w-full">
          {phase === "running" ? "Follow the instructions…" : phase === "verifying" ? "Verifying…" : error ? "Try again" : actionLabel}
        </button>
      )}
      <p className="text-center text-xs text-slate-500">Good light · face inside the oval · no mask or sunglasses</p>
    </div>
  );
}

function friendly(reason = "") {
  if (reason.includes("not performed")) return "Head movement not detected. Follow each prompt slowly.";
  if (reason.includes("exactly one face")) return "Exactly one face must be visible.";
  if (reason.includes("different faces")) return "Face changed during the check. Try again.";
  if (reason.includes("expired")) return "Check timed out. Try again.";
  return reason || "Liveness check failed";
}
