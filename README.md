# FaceAI

Production-style face recognition service, built phase by phase to learn MLOps.

| Phase | Topic | Status |
|---|---|---|
| 0 | Foundation: git, packaging, config, logging, tests, Docker | ✅ done |
| 1 | Core pipeline: aligned ArcFace embeddings, GPU, vector index | ✅ done |
| 2 | Evaluation: benchmark, ROC, TAR@FAR, DVC | |
| 3 | Experiment tracking + model registry: MLflow | |
| 4 | Serving: batching, performance | |
| 5 | CI/CD with eval gate: GitHub Actions | |
| 6 | Monitoring + drift: Prometheus, Grafana | |
| 7 | Trust & safety: liveness, encryption, data deletion | |

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
tests/              # pytest
legacy/             # pre-refactor code (read-only reference)
pyproject.toml      # deps + tool config
requirements.lock   # exact pinned runtime versions (used by Docker)
```

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

## Docker

```powershell
docker compose up --build
curl http://127.0.0.1:8000/health/ready
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health/live` | Liveness: is the process alive? |
| GET | `/health/ready` | Readiness: are models loaded? 503 if not |
| GET | `/version` | App version, model id, device |
| POST | `/v1/persons` | Create person `{"name": "..."}` |
| GET | `/v1/persons` | List persons |
| GET / DELETE | `/v1/persons/{id}` | Get / delete person (+ all embeddings) |
| POST | `/v1/persons/{id}/faces` | Enroll a face photo (exactly one face, quality-checked) |
| POST | `/v1/recognize` | Identify all faces in a photo |

> Models: InsightFace `buffalo_l`, **non-commercial research use only**.

Every response has an `X-Request-ID` header. Send your own to trace a request through the logs.
