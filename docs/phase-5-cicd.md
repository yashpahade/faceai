# Phase 5: CI/CD with an Eval Gate (GitHub Actions)

> Goal: koi bhi change `main` mein tabhi jaaye jab (1) code sahi ho, (2) model ki quality na giri ho,
> aur (3) wo deployable image ban sake. Ye sab insaan ki yaaddasht pe nahi, machine pe chhodo.

## 1. Teen workflows

| Workflow | Kab | Kya karta hai | Runner |
|---|---|---|---|
| `ci.yml` | har push/PR | lint → tests (+coverage ≥ 70%, ratchet) → eval freshness + gate → Docker build + container smoke test | GitHub hosted (CPU) |
| `release.yml` | `git tag v1.2.3` push | gate dobara → image build → `ghcr.io/<repo>:1.2.3` push | GitHub hosted |
| `eval-full.yml` | manual (Actions tab) | LFW download → GPU embed → metrics → gate → MLflow log | **self-hosted GPU** |

```
PR ──► lint ─┐
       test ─┼─► docker build + smoke ──► (sab green) ──► merge ──► tag ──► release: image push
 eval-gate ──┘
   ├─ freshness: committed metrics ABHI ke code se bane?
   └─ gate:      metrics >= params.yaml minimums?
```

## 2. Sabse interesting hissa: eval gate CI mein kaise, bina GPU/data ke?

Full evaluation ko GPU aur 200 MB data chahiye. Har PR pe ye chalana mehenga/slow hai, aur hosted
runners pe GPU hai bhi nahi. Trick:

1. Developer GPU machine pe `dvc repro` chalata hai, aur `dvc.lock` + `reports/eval/metrics.json`
   commit karta hai.
2. CI do sawaal poochta hai:
   - **Freshness** (`python -m faceai.eval.freshness`): `dvc status` se pata karo ki koi *code ya
     params* dependency `dvc.lock` ke baad badli to nahi. Kisi ne `vision/align.py` badla aur
     eval dobara nahi chalaya? **Fail.** Warna gate purane (achhe) numbers dekh ke pass kar deta.
   - **Gate** (`python -m faceai.eval.gate`): committed metrics minimum se upar hain?
3. `data/` aur `models/` CI mein nahi hote, isliye unki "missing" entries freshness ignore karta hai.

Isse "tests green the, par model chupke se kharab ho gaya" wali situation band ho jaati hai.

### Line endings: ek asli bug jo yahin pakda gaya

DVC file ke *bytes* hash karta hai. Windows pe files CRLF mein bani thi, aur git unhe LF mein store
karta hai (`.gitattributes: eol=lf`). Natija: `dvc.lock` ke hashes Linux CI pe kabhi match nahi
karte, aur freshness check hamesha fail hota. Fix:
- `evaluate.py` reports LF mein likhta hai (`newline="\n"`)
- pre-commit hook `mixed-line-ending --fix=lf` working copy ko bhi LF rakhta hai
- generated files (`dvc.lock`, `reports/`) whitespace hooks se exclude hain, kyunki hook unhe badle
  to recorded hashes toot jaate hain

Sabak: reproducibility sirf "same code" nahi, "same bytes" hai.

## 3. Container smoke test

CI image build karke chalata hai aur check karta hai: `/health/live` = 200, `/health/ready` = 503
(models mount nahi kiye, to "not ready" hi sahi jawab hai). Isse pakda jaata hai:
- image build hoti hai par start nahi hoti (missing dependency, galat CMD)
- app bina model ke "ready" bol de (load balancer traffic bhej dega, sab fail)

## 4. Release: immutable tags

Image tag = git tag (`1.2.3`) + commit SHA (`sha-abc1234`). Production hamesha exact tag deploy
karta hai, `latest` kabhi nahi. Tab "prod mein kya chal raha hai?" ka exact jawab hota hai, aur
rollback ka matlab hai purana tag dobara deploy karna.

Model weights image mein **nahi** hain (license + 180 MB + alag release cycle). Deploy ke time
`python -m faceai.registry pull --alias champion` se aate hain (Phase 3). Code version aur model
version alag-alag track hote hain, aur `/version` dono dikhata hai.

## 5. Setup (ek baar)

1. GitHub pe repo banao, `git remote add origin ...`, `git push -u origin main`
2. Settings → Branches → `main`: "Require status checks" = `lint`, `test`, `eval-gate`, `docker`
3. (Optional) self-hosted GPU runner, label `gpu`, `eval-full` ke liye. Variable
   `MLFLOW_TRACKING_URI` set karo agar team MLflow server hai.

Local pe CI jaisa check:
```powershell
python -m ruff check . ; python -m ruff format --check .
python -m pytest --cov=faceai --cov-fail-under=70
python -m faceai.eval.freshness ; python -m faceai.eval.gate
docker build -t faceai:ci .
```

## Self-check questions

1. Freshness check na ho to kaunsa PR gate ko dhoka de sakta hai? Ek concrete example do.
2. Full LFW eval har PR pe kyun nahi chalate? Kab chalana *zaroori* hai?
3. `latest` tag se deploy karne mein kya problem hai?
4. Model weights Docker image ke andar bake karne ke kya fayde/nuksaan hain?
