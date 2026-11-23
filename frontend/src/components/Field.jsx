import { AnimatePresence, motion } from "framer-motion";

// Label + input + animated inline error (sirf tab jab user ne field chhua ho).
export default function Field({ id, label, error, touched, hint, children }) {
  const show = touched && error;
  return (
    <div>
      <label className="label" htmlFor={id}>{label}</label>
      {children}
      <AnimatePresence initial={false}>
        {show ? (
          <motion.p key="err" id={`${id}-err`} role="alert" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="mt-1 text-xs font-medium text-red-600 dark:text-red-400">
            {error}
          </motion.p>
        ) : hint ? (
          <p className="mt-1 text-xs text-slate-500">{hint}</p>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

export function PasswordChecklist({ checks }) {
  return (
    <ul className="mt-2 flex flex-wrap gap-2" aria-label="Password requirements">
      {checks.map(([label, ok]) => (
        <motion.li key={label} animate={{ scale: ok ? [1, 1.08, 1] : 1 }} className={`chip transition-colors ${ok ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300" : "bg-slate-100 text-slate-500 dark:bg-white/5"}`}>
          {ok ? "✓" : "•"} {label}
        </motion.li>
      ))}
    </ul>
  );
}
