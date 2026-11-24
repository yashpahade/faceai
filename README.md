# FaceAI

Production-style face recognition service, built phase by phase to learn MLOps, now grown into
**FaceAI Pro**: a mobile-first biometric attendance app (React PWA + FastAPI).

| Phase | Topic | Status |
|---|---|---|
| 0 | Foundation: git, packaging, config, logging, tests, Docker | ✅ done |
| 1 | Core pipeline: aligned ArcFace embeddings, GPU, vector index | ✅ done |
| 2 | Evaluation: benchmark, ROC, TAR@FAR, DVC | ✅ done |
| 3 | Experiment tracking + model registry: MLflow | ✅ done |
| 4 | Serving: batching, performance | ✅ done |
| 5 | CI/CD with eval gate: GitHub Actions | ✅ done |
| 6 | Monitoring + drift: Prometheus, Grafana | ✅ done |
| 7 | Trust & safety: liveness, encryption, data deletion | ✅ done |

**FaceAI Pro (product phases)**

| Phase | Topic | Status |
|---|---|---|
| A | Accuracy: measured experiments, EXIF, calibration, active liveness | ✅ done |
| B | Backend: JWT auth, roles, students, batches, attendance rules, reports | ✅ done |
| C | React frontend: 11 pages, design system, motion | ✅ done |
| D | Mobile: PWA, phone HTTPS dev, camera + bandwidth | ✅ done |
| E | Production: HTTPS, Postgres, migrations, rate limits, backups | ✅ done |

Architecture (system, database, face pipeline): [`docs/architecture.md`](docs/architecture.md).

Learning notes per phase: [`docs/`](docs/). Old code for reference: [`legacy/`](legacy/).

## Project layout

```
src/faceai/
  config.py         # typed settings (env vars FACEAI_*)
  logging.py        # structured/JSON logging + request IDs
  api/              # FastAPI app factory, /v1 routes, schemas
  service.py        # business rules: enroll, recognize, delete
  vision/           # SCRFD detector, alignment, ArcFace embedder, quality gates
  store/            # SQLite (source of truth) + FAISS index (cache)
  models/download.py# model artifact download + SHA-256 verification
  eval/             # LFW benchmark, metrics (ROC/TAR@FAR/EER), quality gate
  registry.py       # MLflow: log eval runs, model versions, candidate/champion aliases
  models/card.py    # model_card.json reader (serving knows which registered version it runs)
  serving/          # embedding micro-batcher, admission control (503 + Retry-After)
  monitoring/       # Prometheus metrics (/metrics), drift detection (PSI)
  security/         # AES-GCM embedding encryption, API keys, liveness interface, retention
deploy/             # Prometheus config + alert rules, Grafana datasource + dashboard
tests/              # pytest
legacy/             # pre-refactor code (read-only reference)
dvc.yaml, dvc.lock # evaluation pipeline + exact record of its inputs/outputs
params.yaml        # eval params + quality-gate thresholds
reports/eval/      # metrics.json, ROC, score histograms, error analysis
pyproject.toml      # deps + tool config
requirements.lock   # exact pinned runtime versions (used by Docker)
```

## FaceAI Pro quickstart

```powershell
.venv\Scripts\python -m faceai.attendance.create_admin --email you@school.in   # first admin (once)
.venv\Scripts\python -m faceai                                                 # API :8000
cd frontend; npm install; npm run dev          # http://localhost:5173
npm run dev:phone                              # HTTPS on LAN -> open https://<PC-IP>:5173 on your phone
```

Production: [`docs/phase-e-production.md`](docs/phase-e-production.md) (`docker-compose.prod.yml`).

**Forgot password** (no email server needed):
- Student/staff with an enrolled face: login page -> *Forgot password?* -> email + new password -> face check (liveness). The face must belong to that email's account.
- No face enrolled: admin opens the student page -> *Reset password* -> temporary password (shown once).
- Logged in: *Profile -> Change password* (needs the current password).
- Every reset signs the account out everywhere else. Admins reset their own password with `python -m faceai.attendance.create_admin --email ...`.

## Local development (Windows, PowerShell)

```powershell
.venv\Scripts\python -m pip install -e ".[gpu,dev]"   # install (once); no NVIDIA GPU -> ".[cpu,dev]"
.venv\Scripts\python -m faceai.models.download      # model files -> models/ (once, ~180 MB)
.venv\Scripts\python -m pre_commit install         # git hooks (once)
copy .env.example .env                              # config (once)

.venv\Scripts\python -m faceai                     # run server -> http://127.0.0.1:8000/docs
.venv\Scripts\python -m pytest --cov=faceai        # tests + coverage
.venv\Scripts\python -m ruff check . ; .venv\Scripts\python -m ruff format .   # lint + format
```

## Model evaluation (DVC pipeline)

```powershell
.venv\Scripts\python -m pip install -e ".[eval]"
$env:PATH = "$PWD\.venv\Scripts;$env:PATH"   # so DVC stages find the venv python
python -m dvc repro                  # download LFW -> embed -> evaluate (only changed stages rerun)
python -m dvc metrics show           # headline numbers
python -m dvc plots show             # ROC + score histogram -> dvc_plots/index.html
python -m faceai.eval.gate           # fails (exit 1) if model quality is below params.yaml gate
python -m faceai.eval.freshness      # fails if code/params changed since the last `dvc repro` (CI uses this)
```

## Experiment tracking + model registry (MLflow)

```powershell
.venv\Scripts\python -m pip install -e ".[mlops]"
python -m faceai.registry log                    # eval run -> MLflow; new weights -> new version (alias: candidate)
python -m faceai.registry promote                # candidate -> champion (quality gate + no regression vs champion)
python -m faceai.registry pull --alias champion  # weights + model_card.json -> models/ (sha256 verified)
python -m faceai.registry list
mlflow ui --backend-store-uri sqlite:///mlflow.db   # http://127.0.0.1:5000
```

## Performance

```powershell
python scripts/benchmark_engine.py data/samples/t1.jpg          # detector vs det_size, embedder vs batch size
python scripts/loadtest.py data/samples/t1.jpg --concurrency 1 4 16   # against a running server
```

Measured numbers and the batching decision: [`docs/phase-4-serving.md`](docs/phase-4-serving.md).
Under overload the API returns `503` + `Retry-After` instead of queueing forever
(`FACEAI_MAX_CONCURRENT_INFERENCE`, `FACEAI_MAX_QUEUE_WAIT_MS`).

## CI/CD (GitHub Actions)

| Workflow | Trigger | Does |
|---|---|---|
| `ci.yml` | push / PR | ruff, pytest (+coverage ratchet), eval freshness + quality gate, Docker build + container smoke test |
| `release.yml` | tag `v*.*.*` | gate, then build + push `ghcr.io/<repo>:<version>` |
| `eval-full.yml` | manual | full LFW eval on a self-hosted GPU runner, gate, MLflow log |

Details: [`docs/phase-5-cicd.md`](docs/phase-5-cicd.md).

## Docker

```powershell
docker compose up --build                    # api + prometheus + grafana
curl http://127.0.0.1:8000/health/ready
```

| Service | URL |
|---|---|
| API docs | http://127.0.0.1:8000/docs |
| Metrics | http://127.0.0.1:8000/metrics |
| Prometheus (alerts) | http://127.0.0.1:9090/alerts |
| Grafana (dashboard "FaceAI") | http://127.0.0.1:3000 (admin / `GRAFANA_ADMIN_PASSWORD`) |

Monitoring and drift detection: [`docs/phase-6-monitoring.md`](docs/phase-6-monitoring.md).

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health/live` | Liveness: is the process alive? |
| GET | `/health/ready` | Readiness: are models loaded? 503 if not |
| GET | `/version` | App version, model id + registry version, device |
| GET | `/metrics` | Prometheus metrics (keep internal) |
| POST | `/v1/persons` | Create person `{"name": "...", "consent": true}` (consent required) |
| GET | `/v1/persons` | List persons |
| GET / DELETE | `/v1/persons/{id}` | Get / delete person (+ all embeddings); delete returns a receipt |
| POST | `/v1/persons/{id}/faces` | Enroll a face photo (exactly one face, quality-checked) |
| POST | `/v1/recognize` | Identify all faces in a photo |
| GET | `/v1/audit?person_id=` | Audit trail (who did what, no biometrics or names) |

> Models: InsightFace `buffalo_l`, **non-commercial research use only**.

Every response has an `X-Request-ID` header. Send your own to trace a request through the logs.

## Security (Phase 7)

- `/v1/*` needs `X-API-Key` when auth is on (`FACEAI_AUTH=auto` = on in prod). Generate: `python -m faceai.security.auth`
- Embeddings are AES-256-GCM encrypted at rest (`FACEAI_ENCRYPTION_KEYS`); encrypt old rows / rotate keys: `python -m faceai.security.migrate`
- `FACEAI_ENV=prod` refuses to become ready without encryption keys and API keys (fail closed)
- Photos are never stored; deletion removes DB rows + index entries (`secure_delete`), audit keeps proof
- Retention: `FACEAI_RETENTION_DAYS` or `python -m faceai.security.retention --days N`
- Liveness: interface only, **no anti-spoofing model is shipped**; see [`docs/phase-7-trust-safety.md`](docs/phase-7-trust-safety.md)
