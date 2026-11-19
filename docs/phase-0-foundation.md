# Phase 0: Foundation

> Goal: ML code likhne se pehle aisa base banana jahan har cheez **reproducible**, **configurable**,
> **observable** aur **tested** ho. MLOps ka 80% kaam yahi "boring" engineering hai.

## 1. Git + branching

- `main` par legacy code ka snapshot commit hai, taaki kuch toot jaye to wapas ja sako.
- Har phase ka kaam alag branch (`phase-0-foundation`) par hota hai, phir `main` mein merge.
- `.gitignore` mein `data/`, `models/`, `*.faiss`, `.env` hain.
  **Kyun?** Git code ke liye hai. Bade data/model files ke liye DVC aur MLflow use honge (Phase 2-3).
  Secrets (`.env`) kabhi commit nahi hote.

**Khud try karo:** `git log --oneline --all --graph`

## 2. Packaging: `src/` layout + `pyproject.toml`

- Legacy code `sys.path.append(...)` jaise hacks se imports chalata tha. Ab `pip install -e .`
  se `faceai` ek proper package hai, kahin se bhi `import faceai` chalega.
- `src/` layout ka fayda: tests installed package ko test karte hain, accidentally local folder ko nahi.
- **Dependency pinning:**
  - `pyproject.toml`: direct dependencies (jo hum use karte hain)
  - `requirements.lock`: poori tree ke exact versions. Docker yahi use karta hai, isliye
    aaj aur 6 mahine baad bilkul same environment banega. Ise **reproducibility** kehte hain.

## 3. Config: `pydantic-settings`

```
env var FACEAI_PORT=abc  ->  app start hi nahi hoga (ValidationError)
```
- **12-factor app principle:** config code mein nahi, environment mein hoti hai. Same Docker image
  dev/staging/prod mein chalegi, bas env vars alag honge.
- **Fail fast:** galat config ka pata startup pe chale, raat 2 baje production mein nahi.

**Khud try karo:** `$env:FACEAI_PORT="abc"; .venv\Scripts\python -m faceai` (phir `Remove-Item Env:FACEAI_PORT`)

## 4. Structured logging + Request ID

Dev mein readable text, prod (`FACEAI_LOG_JSON=true`) mein har line ek JSON object:
```json
{"ts": "...", "level": "INFO", "msg": "GET /version -> 200 (0.8 ms)", "request_id": "demo-42", "latency_ms": 0.8}
```
- JSON logs ko Loki/ELK seedha query kar sakte hain: "saari requests jinki latency > 500ms".
- `request_id` se ek request ke saare logs jod sakte ho, chahe wo 5 services se guzri ho.
  Ye **distributed tracing** ka pehla kadam hai.
- `latency_ms` field Phase 6 mein metrics/alerts ka base banega.

## 5. Health checks: liveness vs readiness

| | Sawaal | Fail hone par orchestrator kya karta hai |
|---|---|---|
| `/health/live` | Process zinda hai? | Container restart |
| `/health/ready` | Traffic le sakta hai? (model loaded?) | Traffic bhejna band |

ML services mein model load hone mein 10-30 sec lagte hain. Us dauran service "live" hai par "ready"
nahi. Ye farak na ho to load balancer requests bhejega aur sab fail hongi.

## 6. Testing

- `tests/conftest.py`: **fixtures** se har test ko fresh app + temporary data folder milta hai.
- Config validation ke tests hain, kyunki galat config production bugs ka bada source hai.
- `pytest --cov` coverage dikhata hai. 100% target nahi hai, critical paths covered hone chahiye.
- Phase 2 mein ek alag type ka test aayega: **model quality test** (accuracy threshold se neeche
  gayi to fail).

## 7. Code quality: ruff + pre-commit

- `ruff`: linter (bugs, unused imports) + formatter. Sab ka code ek jaisa dikhta hai.
- `pre-commit`: har commit se pehle automatically chalta hai, aur 1MB+ files (galti se model/dataset)
  commit hone se rokta hai.

## 8. Docker: production-grade image

- **Multi-stage build:** builder stage mein install, runtime stage mein sirf zaroori cheezein.
- **Layer caching:** `requirements.lock` pehle copy hoti hai, isliye code badalne pe dependencies
  dobara install nahi hoti.
- **Non-root user:** container hack ho jaye to bhi attacker root nahi hoga.
- **HEALTHCHECK:** Docker khud `/health/ready` check karta hai.
- Image mein `ENV FACEAI_ENV=prod FACEAI_LOG_JSON=true`, matlab same code, alag behaviour, sirf config se.

## Self-check questions

1. `.env` ko git mein kyun nahi daalte, aur `.env.example` ko kyun daalte hain?
2. `pyproject.toml` aur `requirements.lock` mein kya farak hai? Dono kyun chahiye?
3. Model load ho raha ho tab `/health/live` aur `/health/ready` kya return karenge?
4. Ek user complain kare "meri request fail hui". Request ID se tum logs mein kaise dhoondhoge?
