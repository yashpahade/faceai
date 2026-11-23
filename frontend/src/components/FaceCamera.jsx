import { AnimatePresence, motion } from "framer-motion";
import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";

import { captureJpeg } from "../lib/image";

// Reusable webcam with an animated face-oval overlay.
// state: "idle" | "scanning" | "success" | "error"  -> ring color + motion.
// Mobile: front camera ("user"), playsInline (iOS fullscreen nahi). Preview CSS se mirror,
// captured frames un-mirrored (backend liveness image coordinates use karta hai).
const RING = {
  idle: "from-white/80 to-white/40",
  scanning: "from-brand-400 via-accent-400 to-brand-400",
  success: "from-emerald-400 to-teal-300",
  error: "from-red-500 to-rose-400",
};

const FaceCamera = forwardRef(function FaceCamera(
  { facing = "user", mirror = true, overlay = true, hint, state = "idle", className = "" },
  ref,
) {
  const videoRef = useRef(null);
  const [error, setError] = useState(null);
  const [ready, setReady] = useState(false);
  const [flash, setFlash] = useState(0);

  useEffect(() => {
    let stream;
    let cancelled = false;
    async function start() {
      setReady(false);
      setError(null);
      if (!navigator.mediaDevices?.getUserMedia) {
        setError("Camera needs HTTPS (or localhost) in a modern browser.");
        return;
      }
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: { facingMode: facing, width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 24, max: 30 } },
        });
        if (cancelled) return stream.getTracks().forEach((t) => t.stop());
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setReady(true);
      } catch (e) {
        setError(
          e.name === "NotAllowedError"
            ? "Camera permission denied. Allow camera access in your browser settings."
            : e.name === "NotFoundError"
              ? "No camera found on this device."
              : `Camera error: ${e.message}`,
        );
      }
    }
    start();
    return () => {
      cancelled = true;
      stream?.getTracks().forEach((t) => t.stop()); // page chhodte hi camera light band
    };
  }, [facing]);

  useImperativeHandle(ref, () => ({
    ready: () => ready,
    capture: async (opts) => {
      if (!ready) throw new Error("Camera not ready yet");
      setFlash((n) => n + 1); // shutter feedback
      return captureJpeg(videoRef.current, opts);
    },
    video: () => videoRef.current,
  }));

  return (
    <div className={`relative aspect-[3/4] w-full overflow-hidden rounded-[1.75rem] bg-ink-950 shadow-lift ring-1 ring-black/5 sm:aspect-video ${className}`}>
      <video
        ref={videoRef}
        muted
        playsInline
        aria-label="Camera preview"
        className={`h-full w-full object-cover transition-opacity duration-700 ${ready ? "opacity-100" : "opacity-0"} ${mirror && facing === "user" ? "-scale-x-100" : ""}`}
      />

      {overlay && ready && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          {/* dim outside the oval */}
          <div className="absolute inset-0 bg-ink-950/35 [mask-image:radial-gradient(ellipse_28%_33%_at_50%_50%,transparent_96%,black_100%)] sm:[mask-image:radial-gradient(ellipse_17%_36%_at_50%_50%,transparent_96%,black_100%)]" />
          <div className="relative h-[66%] w-[56%] max-w-[270px] sm:h-[72%] sm:w-[34%]">
            {state === "scanning" && <span className="absolute inset-0 animate-ring rounded-[50%] border-2 border-brand-300/70" />}
            {/* gradient ring via padding + mask */}
            <motion.div
              className={`absolute inset-0 rounded-[50%] bg-gradient-to-tr p-[3px] ${RING[state]} [mask:linear-gradient(#000_0_0)_content-box,linear-gradient(#000_0_0)] [mask-composite:exclude] [-webkit-mask-composite:xor]`}
              animate={state === "scanning" ? { rotate: 360 } : state === "error" ? { x: [0, -8, 8, -5, 5, 0] } : { rotate: 0, x: 0 }}
              transition={state === "scanning" ? { repeat: Infinity, duration: 3, ease: "linear" } : { duration: 0.45 }}
            />
            {state === "scanning" && (
              <div className="absolute inset-0 overflow-hidden rounded-[50%]">
                <span className="absolute left-0 right-0 h-16 -translate-y-1/2 animate-scan bg-gradient-to-b from-transparent via-brand-300/40 to-transparent" />
              </div>
            )}
          </div>
          {/* corner brackets */}
          {["left-4 top-4 border-l-2 border-t-2 rounded-tl-xl", "right-4 top-4 border-r-2 border-t-2 rounded-tr-xl", "bottom-4 left-4 border-b-2 border-l-2 rounded-bl-xl", "bottom-4 right-4 border-b-2 border-r-2 rounded-br-xl"].map((c) => (
            <span key={c} className={`absolute h-7 w-7 border-white/70 ${c}`} />
          ))}
        </div>
      )}

      {/* shutter flash */}
      <AnimatePresence>
        {flash > 0 && <motion.div key={flash} className="pointer-events-none absolute inset-0 bg-white" initial={{ opacity: 0.55 }} animate={{ opacity: 0 }} transition={{ duration: 0.35 }} />}
      </AnimatePresence>

      <AnimatePresence mode="wait">
        {hint && ready && (
          <motion.div
            key={hint}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.3 }}
            className="absolute inset-x-3 bottom-3 rounded-2xl bg-black/55 px-4 py-3 text-center text-base font-semibold text-white backdrop-blur-md"
          >
            {hint}
          </motion.div>
        )}
      </AnimatePresence>

      {!ready && !error && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-sm text-slate-300">
          <span className="h-10 w-10 animate-spin rounded-full border-2 border-brand-400 border-t-transparent" />
          Starting camera…
        </div>
      )}
      {error && (
        <div role="alert" className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-6 text-center text-sm text-red-200">
          <svg viewBox="0 0 24 24" className="h-8 w-8" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M15 10l4.5-2.5v9L15 14M4 7h11v10H4zM3 3l18 18" />
          </svg>
          {error}
        </div>
      )}
    </div>
  );
});

export default FaceCamera;
