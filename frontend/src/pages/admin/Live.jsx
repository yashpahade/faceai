import { useState } from "react";

import LiveDetector from "../../components/LiveDetector";
import { PageHeader } from "../../components/ui";

export default function Live() {
  const [facing, setFacing] = useState("user");
  return (
    <div className="space-y-4">
      <PageHeader title="Live attendance">
        <button className="btn-secondary" onClick={() => setFacing((f) => (f === "user" ? "environment" : "user"))}>
          Switch camera
        </button>
      </PageHeader>
      <p className="text-sm text-slate-500">
        Place the device where students face it. Each recognized student is marked once per day, following batch time rules.
      </p>
      <LiveDetector key={facing} facing={facing} />
    </div>
  );
}
