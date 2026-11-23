"""
Eval freshness check (CI): kya committed metrics ABHI ke code se nikle hain?

    python -m faceai.eval.freshness

Gate (`faceai.eval.gate`) committed `reports/eval/metrics.json` padhta hai. Par agar kisi PR ne
preprocessing badla aur `dvc repro` chalana bhool gaya, to gate PURANE (achhe) numbers dekh ke pass
kar dega. Ye check `dvc status` se poochta hai: kisi stage ka CODE ya PARAMS dependency badla hai
jiske baad eval dobara nahi chala? Haan => fail.

CI mein LFW data aur model weights nahi hote (bade hain), isliye `data/` aur `models/` wali
"deleted/missing" entries ignore hoti hain. Hum sirf wo pakadte hain jo git mein hai: code, params.
"""

import json
import subprocess
import sys

IGNORED_PREFIXES = ("data/", "models/", "reports/")


def stale_deps(status: dict) -> list[str]:
    """`dvc status --json` -> ["stage: path (modified)", ...] sirf code/params ke liye."""
    problems = []
    for stage, entries in status.items():
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for path, state in entry.get("changed deps", {}).items():
                norm = path.replace("\\", "/")
                if norm.startswith(IGNORED_PREFIXES) or state == "deleted":
                    continue
                problems.append(f"{stage}: {norm} ({state})")
    return problems


def main() -> int:
    out = subprocess.run(
        [sys.executable, "-m", "dvc", "status", "--json"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    problems = stale_deps(json.loads(out or "{}"))
    if problems:
        print("EVAL IS STALE - model-affecting code/params changed since the last `dvc repro`:")
        for p in problems:
            print("  x", p)
        print("Run `python -m dvc repro` on a machine with the data + GPU and commit dvc.lock.")
        return 1
    print("eval is fresh: dvc.lock matches current code + params")
    return 0


if __name__ == "__main__":
    sys.exit(main())
