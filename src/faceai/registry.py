"""
Experiment tracking + Model Registry (MLflow).

    python -m faceai.registry log                      # eval run -> MLflow (+ model version)
    python -m faceai.registry list                     # versions, aliases, headline metrics
    python -m faceai.registry promote                  # candidate -> champion (gate, no regression)
    python -m faceai.registry pull --alias champion    # champion ki files -> models/<pack>/

Concepts:
- RUN = ek experiment (params + metrics + artifacts + git commit). "Kis setting se kya number aaya?"
  ka jawab 6 mahine baad bhi milta hai.
- REGISTERED MODEL VERSION = ek deployable artifact (weights + model card). Ek version = ek unique
  set of weights (sha256). Same weights dobara evaluate karo to naya version NAHI banta, sirf naya
  run us version se link hota hai (180 MB baar-baar copy nahi hote).
- ALIASES: `candidate` (naya, abhi test ho raha) aur `champion` (production). Serving kabhi
  "version 7" hardcode nahi karti, alias se maangti hai. Rollback = alias purane version pe le jao.
- Champion/challenger: naya model tabhi champion banega jab quality gate pass kare AUR current
  champion se kharab na ho. "Naya hai" promote karne ki wajah nahi hai.

Tracking store: default `sqlite:///mlflow.db` (registry ke liye DB backend chahiye).
`MLFLOW_TRACKING_URI` env var set ho to wahi use hoga (team server, e.g. http://mlflow:5000).
UI:  mlflow ui --backend-store-uri sqlite:///mlflow.db   -> http://127.0.0.1:5000
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

from faceai.eval.gate import check

MODEL_NAME = "faceai-recognizer"
EXPERIMENT = "faceai-eval"
CARD_FILE = "model_card.json"
DEFAULT_TRACKING_URI = "sqlite:///mlflow.db"
CANDIDATE, CHAMPION = "candidate", "champion"
# Promotion tolerance: challenger itna kharab ho sakta hai (noise), usse zyada nahi
MAX_REGRESSION = 0.002


def _client(tracking_uri: str | None = None):
    import mlflow
    from mlflow import MlflowClient

    uri = tracking_uri or os.environ.get("MLFLOW_TRACKING_URI") or DEFAULT_TRACKING_URI
    mlflow.set_tracking_uri(uri)
    return mlflow, MlflowClient(uri)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def flatten_metrics(metrics: dict[str, Any]) -> dict[str, float]:
    """metrics.json (nested) -> MLflow metrics (flat, numeric). Strings (model_id, device) skip."""
    out: dict[str, float] = {}
    for k, v in metrics.items():
        if isinstance(v, bool | str):
            continue
        if isinstance(v, int | float):
            out[k] = float(v)
        elif k == "tar_at_far":
            for far, d in v.items():
                out[f"tar_at_far_{far}"] = float(d["tar"])
                out[f"threshold_at_far_{far}"] = float(d["threshold"])
        elif k == "recommended_threshold":
            out["recommended_threshold"] = float(v["threshold"])
    return out


def _git(*args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def dvc_lineage(lock_path: Path) -> dict[str, str]:
    """dvc.lock se data/model/code ke hashes -> MLflow tags. Run ko EXACT inputs se jodta hai."""
    if not lock_path.exists():
        return {}
    lock = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    tags = {}
    for stage, spec in lock.get("stages", {}).items():
        for dep in spec.get("deps", []):
            if dep["path"].startswith(("data/", "models/")):
                tags[f"dvc.{stage}.{dep['path']}"] = dep.get("md5", "?")
    return tags


def build_card(
    pack_dir: Path, model_id: str, metrics: dict, params: dict, run_id: str
) -> dict[str, Any]:
    """Model card: is version ke baare mein sab kuch jo serving/humans ko jaanna chahiye."""
    return {
        "name": MODEL_NAME,
        "model_id": model_id,
        "files": {p.name: sha256(p) for p in sorted(pack_dir.glob("*.onnx"))},
        "preprocessing": {
            "det_size": params["eval"]["det_size"],
            "det_threshold": params["eval"]["det_threshold"],
        },
        "evaluation": {
            "dataset": metrics.get("dataset"),
            "kfold_accuracy": metrics.get("kfold_accuracy"),
            "tar_at_far": metrics.get("tar_at_far"),
            "failure_to_detect_rate": metrics.get("failure_to_detect_rate"),
            "run_id": run_id,
        },
        # LFW pe nikla threshold. Apne domain pe dobara validate karo (docs/phase-2, domain shift).
        "recommended_threshold": metrics.get("recommended_threshold"),
        "license": "InsightFace buffalo_l: non-commercial research use only",
    }


def _find_version_by_weights(client, files: dict[str, str]):
    for mv in client.search_model_versions(f"name='{MODEL_NAME}'"):
        if mv.tags.get("weights_sha256") == _weights_key(files):
            return mv
    return None


def _weights_key(files: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()[:16]


def log_evaluation(
    metrics_path: Path = Path("reports/eval/metrics.json"),
    params_path: Path = Path("params.yaml"),
    pack_dir: Path = Path("models/buffalo_l"),
    reports_dir: Path | None = None,
    lock_path: Path = Path("dvc.lock"),
    tracking_uri: str | None = None,
) -> dict[str, Any]:
    """Eval run log karo; weights naye hain to naya model version banao (alias: candidate)."""
    mlflow, client = _client(tracking_uri)
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    params = yaml.safe_load(params_path.read_text(encoding="utf-8"))
    reports_dir = reports_dir or metrics_path.parent
    gate_failures = check(metrics, params["gate"])

    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run(run_name=f"eval-{metrics['model_id']}") as run:
        mlflow.log_params({f"eval.{k}": v for k, v in params["eval"].items()})
        mlflow.log_metrics(flatten_metrics(metrics))
        mlflow.set_tags(
            {
                "model_id": metrics["model_id"],
                "dataset": metrics.get("dataset", "?"),
                "device": metrics.get("device", "?"),
                "git_commit": _git("rev-parse", "HEAD"),
                "git_dirty": str(bool(_git("status", "--porcelain", "--untracked-files=no"))),
                "gate_passed": str(not gate_failures),
                **dvc_lineage(lock_path),
            }
        )
        for f in sorted(reports_dir.glob("*")):
            mlflow.log_artifact(str(f), artifact_path="eval")
        mlflow.log_artifact(str(params_path))
        if lock_path.exists():
            mlflow.log_artifact(str(lock_path))

        card = build_card(pack_dir, metrics["model_id"], metrics, params, run.info.run_id)
        existing = _find_version_by_weights(client, card["files"])
        if existing is None:
            with tempfile.TemporaryDirectory() as tmp:
                mdir = Path(tmp) / "model"
                mdir.mkdir()
                for name in card["files"]:
                    shutil.copy2(pack_dir / name, mdir / name)
                (mdir / CARD_FILE).write_text(json.dumps(card, indent=2), encoding="utf-8")
                mlflow.log_artifacts(str(mdir), artifact_path="model")
            with contextlib.suppress(Exception):  # pehle se bana hai to theek hai
                client.create_registered_model(MODEL_NAME, description="Face embedding model")
            mv = client.create_model_version(
                MODEL_NAME,
                source=f"{run.info.artifact_uri}/model",
                run_id=run.info.run_id,
                tags={
                    "weights_sha256": _weights_key(card["files"]),
                    "model_id": metrics["model_id"],
                    "gate_passed": str(not gate_failures),
                },
                description=f"{metrics['model_id']} evaluated on {metrics.get('dataset')}",
            )
            version, created = str(mv.version), True
        else:
            version, created = str(existing.version), False
        mlflow.set_tag("model_version", version)

    # har eval run ka latest result version ke saath (promotion isi pe decide hota hai)
    for k, v in flatten_metrics(metrics).items():
        client.set_model_version_tag(MODEL_NAME, version, f"metric.{k}", str(v))
    client.set_model_version_tag(MODEL_NAME, version, "gate_passed", str(not gate_failures))
    client.set_model_version_tag(MODEL_NAME, version, "latest_run_id", run.info.run_id)
    if created:
        client.set_registered_model_alias(MODEL_NAME, CANDIDATE, version)
    return {
        "run_id": run.info.run_id,
        "version": version,
        "created": created,
        "gate_failures": gate_failures,
    }


def _version_metrics(mv) -> dict[str, float]:
    return {k[7:]: float(v) for k, v in mv.tags.items() if k.startswith("metric.")}


def promote(
    version: str | None = None,
    key_metric: str = "tar_at_far_1e-3",
    force: bool = False,
    tracking_uri: str | None = None,
) -> str:
    """candidate (ya diya gaya version) -> champion. Gate fail ya regression => ValueError."""
    _, client = _client(tracking_uri)
    mv = (
        client.get_model_version(MODEL_NAME, version)
        if version
        else client.get_model_version_by_alias(MODEL_NAME, CANDIDATE)
    )
    if mv.tags.get("gate_passed") != "True":
        raise ValueError(f"version {mv.version} did not pass the quality gate; not promoting")
    try:
        champ = client.get_model_version_by_alias(MODEL_NAME, CHAMPION)
    except Exception:
        champ = None
    if champ is not None and str(champ.version) != str(mv.version) and not force:
        new, old = _version_metrics(mv).get(key_metric), _version_metrics(champ).get(key_metric)
        if new is None or old is None:
            raise ValueError(f"{key_metric} missing on version {mv.version} or champion")
        if new < old - MAX_REGRESSION:
            raise ValueError(
                f"challenger v{mv.version} {key_metric}={new} is worse than champion "
                f"v{champ.version} ({old}); use --force to override"
            )
    client.set_registered_model_alias(MODEL_NAME, CHAMPION, mv.version)
    return str(mv.version)


def pull(
    alias: str = CHAMPION, dest: Path = Path("models/buffalo_l"), tracking_uri: str | None = None
) -> dict[str, Any]:
    """Registry se model files + card download, sha256 verify, phir `dest` mein copy."""
    mlflow, client = _client(tracking_uri)
    mv = client.get_model_version_by_alias(MODEL_NAME, alias)
    with tempfile.TemporaryDirectory() as tmp:
        local = Path(mlflow.artifacts.download_artifacts(artifact_uri=mv.source, dst_path=tmp))
        card = json.loads((local / CARD_FILE).read_text(encoding="utf-8"))
        for name, expected in card["files"].items():
            if sha256(local / name) != expected:
                raise RuntimeError(f"checksum mismatch for {name} in version {mv.version}")
        dest.mkdir(parents=True, exist_ok=True)
        for name in card["files"]:
            shutil.copy2(local / name, dest / name)
    card["version"] = str(mv.version)
    card["alias"] = alias
    (dest / CARD_FILE).write_text(json.dumps(card, indent=2), encoding="utf-8")
    return card


def list_versions(tracking_uri: str | None = None) -> list[dict[str, Any]]:
    _, client = _client(tracking_uri)
    try:
        aliases = client.get_registered_model(MODEL_NAME).aliases
    except Exception:
        return []
    by_version: dict[str, list[str]] = {}
    for a, v in aliases.items():
        by_version.setdefault(str(v), []).append(a)
    rows = []
    for mv in client.search_model_versions(f"name='{MODEL_NAME}'"):
        m = _version_metrics(mv)
        rows.append(
            {
                "version": str(mv.version),
                "aliases": sorted(by_version.get(str(mv.version), [])),
                "model_id": mv.tags.get("model_id"),
                "gate_passed": mv.tags.get("gate_passed"),
                "tar_at_far_1e-3": m.get("tar_at_far_1e-3"),
                "kfold_accuracy": m.get("kfold_accuracy"),
            }
        )
    return sorted(rows, key=lambda r: int(r["version"]))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m faceai.registry")
    sub = ap.add_subparsers(dest="cmd", required=True)
    lg = sub.add_parser("log", help="log reports/eval to MLflow, register new weights")
    lg.add_argument("--metrics", type=Path, default=Path("reports/eval/metrics.json"))
    lg.add_argument("--pack-dir", type=Path, default=Path("models/buffalo_l"))
    sub.add_parser("list", help="model versions + aliases")
    pr = sub.add_parser("promote", help="candidate -> champion")
    pr.add_argument("--version")
    pr.add_argument("--force", action="store_true", help="skip no-regression check")
    pl = sub.add_parser("pull", help="download a version into models/")
    pl.add_argument("--alias", default=CHAMPION)
    pl.add_argument("--dest", type=Path, default=Path("models/buffalo_l"))
    args = ap.parse_args(argv)

    try:
        if args.cmd == "log":
            r = log_evaluation(args.metrics, pack_dir=args.pack_dir)
            what = "new version" if r["created"] else "existing version (same weights)"
            print(f"run {r['run_id']} -> {MODEL_NAME} v{r['version']} ({what})")
            if r["gate_failures"]:
                print("gate FAILED:", "; ".join(r["gate_failures"]))
        elif args.cmd == "list":
            for row in list_versions():
                print(json.dumps(row))
        elif args.cmd == "promote":
            print(f"{MODEL_NAME} v{promote(args.version, force=args.force)} is now '{CHAMPION}'")
        elif args.cmd == "pull":
            card = pull(args.alias, args.dest)
            print(f"pulled {MODEL_NAME} v{card['version']} ({args.alias}) -> {args.dest}")
    except ValueError as e:
        print("refused:", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
