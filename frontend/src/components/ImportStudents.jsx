import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";

import { api, fd } from "../api/client";
import { SuccessBurst, toast } from "./motion";
import { ErrorBox } from "./ui";

// Bulk import: template -> file -> preview (dry run, row-wise errors) -> import -> credentials CSV.
// Server all-or-nothing hai: ek bhi row galat => kuch save nahi.
function download(name, text) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/csv" }));
  Object.assign(document.createElement("a"), { href: url, download: name }).click();
  URL.revokeObjectURL(url);
}

const csvCell = (v) => (/[",\n]/.test(v) ? `"${String(v).replace(/"/g, '""')}"` : v);

export default function ImportStudents({ onClose, onDone }) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [created, setCreated] = useState(null);

  async function template() {
    const res = await api("/v1/admin/import/students-template.csv", { raw: true });
    download("students_template.csv", await res.text());
  }

  async function send(dryRun) {
    setBusy(true);
    setError(null);
    try {
      const q = dryRun ? "dry_run=true" : "dry_run=false&consent=true";
      const r = await api(`/v1/admin/import/students?${q}`, { method: "POST", form: fd([["file", file]]) });
      if (dryRun) setPreview(r);
      else {
        setCreated(r.created);
        toast(`${r.created.length} students imported`);
        onDone();
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  function credentials() {
    const lines = ["full_name,email,temporary_password", ...created.map((c) => [c.full_name, c.email, c.temporary_password].map(csvCell).join(","))];
    download("student_logins.csv", lines.join("\n") + "\n");
  }

  return (
    <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="card overflow-hidden p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-semibold">Import students from CSV</h2>
        <button className="text-sm text-slate-500 hover:text-slate-900 dark:hover:text-white" onClick={onClose}>Close</button>
      </div>

      {created ? (
        <div className="space-y-3 text-center">
          <SuccessBurst title={`${created.length} students imported`} subtitle="Download their login details now. Passwords are shown only once." />
          <button className="btn-primary" onClick={credentials}>Download logins (CSV)</button>
        </div>
      ) : (
        <div className="space-y-4">
          <ol className="space-y-1 text-sm text-slate-600 dark:text-slate-300">
            <li>1. <button className="font-semibold text-brand-600 underline dark:text-brand-300" onClick={template}>Download the template</button> and fill it in Excel/Sheets (columns: full_name, email, phone, roll_no, batch).</li>
            <li>2. Save as <b>CSV UTF-8</b> and choose it below. Up to 2,000 rows.</li>
            <li>3. Check the preview. If any row has an error, nothing is imported until it's fixed.</li>
          </ol>
          <div className="flex flex-wrap items-center gap-2">
            <label className="btn-secondary cursor-pointer">
              {file ? file.name : "Choose CSV file"}
              <input type="file" accept=".csv,text/csv" className="hidden" onChange={(e) => { setFile(e.target.files[0] || null); setPreview(null); }} />
            </label>
            <button className="btn-primary" disabled={!file || busy} onClick={() => send(true)}>{busy ? "Checking…" : "Check file"}</button>
          </div>
          <ErrorBox error={error} />

          <AnimatePresence>
            {preview && (
              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
                <div className="flex flex-wrap gap-2 text-sm">
                  <span className="chip bg-slate-100 dark:bg-white/10">{preview.rows} rows</span>
                  <span className="chip bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300">{preview.valid} valid</span>
                  {preview.errors.length > 0 && <span className="chip bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300">{preview.errors.length} problems</span>}
                </div>
                {preview.errors.length > 0 ? (
                  <div className="max-h-64 overflow-auto rounded-xl border border-red-200 dark:border-red-500/20">
                    <table className="w-full text-left text-sm">
                      <thead className="bg-red-50 text-xs uppercase text-red-700 dark:bg-red-500/10 dark:text-red-300">
                        <tr><th className="px-3 py-2">Row</th><th className="px-3 py-2">Column</th><th className="px-3 py-2">Problem</th></tr>
                      </thead>
                      <tbody>
                        {preview.errors.map((e, i) => (
                          <tr key={i} className="border-t border-red-100 dark:border-red-500/10">
                            <td className="px-3 py-1.5 tabular-nums">{e.row}</td>
                            <td className="px-3 py-1.5">{e.field}</td>
                            <td className="px-3 py-1.5">{e.error}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <>
                    <label className="flex items-start gap-2 text-sm">
                      <input type="checkbox" className="mt-0.5 h-5 w-5 accent-brand-600" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
                      All these students have given written consent for face data processing.
                    </label>
                    <button className="btn-primary" disabled={!consent || busy} onClick={() => send(false)}>{busy ? "Importing…" : `Import ${preview.rows} students`}</button>
                  </>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
    </motion.div>
  );
}
