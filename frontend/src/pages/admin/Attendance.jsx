import { useCallback, useEffect, useState } from "react";

import { api } from "../../api/client";
import AttendanceTable from "../../components/AttendanceTable";
import { BatchSelector, ErrorBox, PageHeader, Spinner, today, usePolling } from "../../components/ui";

// Ek din ka attendance + manual override.
export default function Attendance() {
  const [day, setDay] = useState(today());
  const [batch, setBatch] = useState(null);
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);

  const fetchRows = useCallback(() => {
    const p = new URLSearchParams({ from: day, to: day });
    if (batch) p.set("batch_id", batch);
    return api(`/v1/admin/attendance?${p}`).then(setRows).catch((e) => setError(e.message));
  }, [day, batch]);
  const load = () => {
    setRows(null);
    fetchRows();
  };
  useEffect(load, [day, batch]);
  usePolling(fetchRows, 15000); // background refresh: list "flash" nahi karti

  // "Absent" rows sirf beete hue dinon ke liye aate hain; aaj ke unmarked students ko override
  // karne ke liye Students page / student detail use karo.
  async function override(r, status) {
    try {
      await api("/v1/admin/attendance/manual", { method: "POST", json: { user_id: r.user_id, day: r.day, status } });
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader title="Attendance" />
      <div className="flex flex-col gap-2 sm:flex-row">
        <input type="date" className="input sm:w-48" value={day} max={today()} onChange={(e) => setDay(e.target.value)} aria-label="Date" />
        <BatchSelector value={batch} onChange={setBatch} className="sm:w-56" />
      </div>
      <ErrorBox error={error} />
      {rows === null ? (
        <Spinner />
      ) : (
        <AttendanceTable
          rows={rows}
          actions={(r) => (
            <select className="input w-auto py-1 text-xs" value={r.status} onChange={(e) => override(r, e.target.value)} aria-label={`Override ${r.full_name}`}>
              <option value="present">present</option>
              <option value="late">late</option>
              <option value="absent">absent</option>
            </select>
          )}
        />
      )}
    </div>
  );
}
