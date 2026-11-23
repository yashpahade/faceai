"""
Model quality gate: metrics minimum se neeche => exit code 1 => CI fail => deploy nahi hoga.

    python -m faceai.eval.gate --metrics reports/eval/metrics.json

Normal tests check karte hain "code chalta hai?". Ye check karta hai "model ACHHA hai?".
Koi preprocessing change (e.g. galat normalization) code ko todta nahi par accuracy chupke se
gira deta hai - ye gate usi ko pakadta hai. Phase 5 mein GitHub Actions ise har PR pe chalayega.
"""

import argparse
import json
import sys
from pathlib import Path

from faceai.eval.params import load_params


def check(metrics: dict, gate: dict) -> list[str]:
    failures = []
    if metrics["kfold_accuracy"] < gate["min_kfold_accuracy"]:
        failures.append(
            f"kfold_accuracy {metrics['kfold_accuracy']} < {gate['min_kfold_accuracy']}"
        )
    for far, min_tar in gate["min_tar_at_far"].items():
        got = metrics["tar_at_far"].get(far, {}).get("tar")
        if got is None:
            failures.append(f"TAR@FAR={far} missing from metrics")
        elif got < min_tar:
            failures.append(f"TAR@FAR={far} {got} < {min_tar}")
    if metrics["failure_to_detect_rate"] > gate["max_failure_to_detect_rate"]:
        failures.append(
            f"failure_to_detect_rate {metrics['failure_to_detect_rate']} > "
            f"{gate['max_failure_to_detect_rate']}"
        )
    return failures


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics", type=Path, default=Path("reports/eval/metrics.json"))
    args = ap.parse_args()
    metrics = json.loads(args.metrics.read_text())
    failures = check(metrics, load_params()["gate"])
    if failures:
        print("QUALITY GATE FAILED:")
        for f in failures:
            print("  x", f)
        return 1
    print(f"QUALITY GATE PASSED ({metrics['model_id']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
