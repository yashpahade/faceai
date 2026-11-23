# Phase E: Production Hardening

> Goal: ek school/coaching ke liye asli deployment: HTTPS, Postgres, secrets, abuse se bachav,
> backups, aur saaf upgrade path.

## 1. Stack

```
Internet ──HTTPS──► web (Caddy: Let's Encrypt, React build, security headers)
                       └── /v1 ──► api (FastAPI + GPU/CPU inference) ──► db (Postgres 16)
                                         └── biodata volume (encrypted SQLite biometric store)
                     backup (pg_dump daily, 7-day retention)
```

```powershell
cp deploy/env/prod.env.example .env.prod      # secrets bharo (git-ignored)
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
docker compose -f docker-compose.prod.yml exec api python -m faceai.attendance.migrate
docker compose -f docker-compose.prod.yml exec api python -m faceai.attendance.create_admin --email you@school.in
docker compose -f docker-compose.prod.yml exec api python -m faceai.registry pull --alias champion   # model (Phase 3)
```

## 2. Kya kiya, kyun

| Area | Kya | Kyun |
|---|---|---|
| **HTTPS** | Caddy auto-TLS (`FACEAI_DOMAIN`), HSTS | Camera sirf HTTPS pe; passwords/JWT plain HTTP pe nahi |
| **Security headers** | CSP (`'self'` only), `X-Frame-Options DENY`, `Permissions-Policy camera=(self)` | XSS/clickjacking; sirf humara origin camera maange |
| **/metrics** | Caddy pe 404 | Internal data internet pe nahi; Prometheus internal network se scrape |
| **Postgres** | `FACEAI_PRODUCT_DB_URL=postgresql+psycopg://...`, `psycopg` image build-arg se | Concurrent writes, backups, managed DB options |
| **Migrations** | Alembic (`0001_initial_schema`), `test_upgrade_head_matches_models` | Prod data ke saath schema badalna; model badla aur migration bhool gaye → CI fail |
| **Rate limiting** | Token bucket per IP: login 10/min, signup 5/min, face-login 10/min, liveness 20/min → **429 + Retry-After** | Password/face brute force, signup spam |
| **Real client IP** | `X-Forwarded-For` sirf `FACEAI_TRUSTED_PROXIES` (Caddy) se | Warna attacker header bhejke har request ko naya IP bana de |
| **Secrets** | `.env.prod` (git-ignored), compose `:?` = missing secret pe start hi nahi | Fail closed (Phase 7 ke saath) |
| **Environments** | `deploy/env/{staging,prod}.env.example` | Har release pehle staging pe, alag secrets |
| **Backups** | `pg_dump` daily (7 din) + `python -m faceai.ops.backup` (SQLite online backup + integrity check) | Restore = asli test; retention = purana deleted data bhi expire |
| **Caching** | `/assets/*` 1 year immutable, `index.html`/`sw.js` no-cache | Naya deploy turant dikhe, assets dobara download na hon |

## 3. Ek bug jo Windows ne pakda

`with sqlite3.connect(...) as c:` connection **close nahi karta** (sirf commit/rollback). Linux pe
khula handle file delete hone deta hai, Windows pe nahi → backup prune fail. Fix: `contextlib.closing`.
Sabak: context manager kya guarantee karta hai, docs se confirm karo.

## 4. Abhi bhi single-node (honest)

Biometric store (SQLite), FAISS index, liveness challenges aur rate limiter process memory/volume
mein hain → **ek `api` replica**. Multi-replica ke liye: pgvector, Redis (challenges + rate limit),
alag inference service. Details: `docs/architecture.md` §6.

## 5. Release checklist

1. CI green (lint, tests, eval freshness + gate, docker)
2. `python -m faceai.eval.calibrate` apne cameras ke data pe → `FACEAI_MATCH_THRESHOLD`
3. Staging deploy → face login + live scan phone pe test
4. `git tag vX.Y.Z` → release workflow image push
5. Prod: `migrate` → restart → `/health/ready` → Grafana dekho
6. Restore drill (har mahine): latest backup naye DB mein restore karke app chalao

## Self-check questions

1. Rate limit ke bina face-login endpoint pe kya attack possible hai?
2. `X-Forwarded-For` ko har request se kyun nahi maan sakte?
3. Backup lena aur restore test karna: dono kyun zaroori hain?
4. Do `api` replicas chala diye to liveness kaise toot sakta hai?
