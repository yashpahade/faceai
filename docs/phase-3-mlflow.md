# Phase 3: Experiment Tracking + Model Registry (MLflow)

> Goal: har experiment ka record rakhna, aur "production mein kaunsa model hai, kyun hai, aur
> wapas kaise jaayein?" ka jawab ek command mein dena.

## 1. DVC vs MLflow: dono kyun?

| | DVC (Phase 2) | MLflow (Phase 3) |
|---|---|---|
| Kya track karta hai | Data + pipeline (kaunsi file kis file se bani) | Runs (params → metrics) + deployable models |
| Sawal | "Ye metrics kis data/code se nikle?" | "Saare experiments mein best kaunsa tha? Prod mein kya hai?" |
| Storage | git + DVC cache | Tracking DB + artifact store |

Dono saath kaam karte hain: har MLflow run mein `dvc.lock` ke hashes **tags** ki tarah save hote hain
(`dvc.embed_lfw.data/lfw = <md5>`). Run se seedha exact data version tak pahunch sakte ho.

## 2. Run, Model Version, Alias

```
dvc repro ─► reports/eval/metrics.json
                     │
python -m faceai.registry log
                     │
                     ├─► MLflow RUN      params, metrics, eval reports, git commit, dvc hashes
                     │
                     └─► MODEL VERSION   onnx weights + model_card.json   (sirf jab weights NAYE hon)
                              │
                         alias: candidate ──(promote: gate ✓, champion se kharab nahi)──► champion
                                                                                          │
                                         python -m faceai.registry pull --alias champion ─┘
                                                     │
                                          models/buffalo_l/ + model_card.json ─► API /version
```

- **Run** = ek experiment. Same model ko `det_size` badal ke 5 baar evaluate karo, 5 runs.
- **Model version** = ek *unique* set of weights (sha256). Same weights dobara evaluate karne se naya
  version nahi banta. 180 MB har run mein copy karna bekaar hai, aur "v1 aur v2 mein farak kya hai?"
  ka jawab "kuch nahi" nahi hona chahiye.
- **Alias** = version ke liye ek naam. Serving `champion` maangti hai, "v7" nahi. Rollback ka matlab
  hai `champion` alias ko purane version pe le jaana, bina koi code badle.

## 3. Champion / challenger

`promote` do checks karta hai:
1. **Quality gate** (Phase 2 wala, `params.yaml → gate`). Fail hua to version promote nahi hoga.
2. **No regression**: naya `TAR@FAR=1e-3` current champion se `0.002` se zyada kam nahi hona chahiye.
   "Model naya hai" use promote karne ki wajah nahi hai.

`--force` se override ho sakta hai, par wo ek *insaan ka* decision hai, isliye explicit flag hai.

## 4. Model card

`model_card.json` har version ke saath jaata hai: weights ke sha256, preprocessing settings, eval
numbers, recommended threshold, license. Serving startup pe `faceai/models/card.py`:
- card padhta hai aur **disk ki files ka sha256 card se match karta hai**. Mismatch hone par app
  ready nahi hoti, kyunki galat version info dikhane se behtar hai fail ho jaana.
- `/version` mein `model_version`, `model_alias`, `recommended_threshold` dikhata hai.

`match_threshold` ab bhi config se aata hai, card se automatic nahi. Card ka threshold LFW se
nikla hai, aur Phase 2 ka domain-shift wala sabak yaad rakho: apne data pe validate kiye bina usko
seedha production threshold mat banao. `/version` dono dikhata hai, taaki farak nazar aaye.

## 5. Commands

```powershell
.venv\Scripts\python -m pip install -e ".[mlops]"
python -m dvc repro                              # eval (Phase 2)
python -m faceai.registry log                    # run + (naye weights pe) version, alias candidate
python -m faceai.registry list                   # versions, aliases, metrics
python -m faceai.registry promote                # candidate -> champion (checks ke saath)
python -m faceai.registry pull --alias champion  # serving ke liye files + card
mlflow ui --backend-store-uri sqlite:///mlflow.db   # http://127.0.0.1:5000
```

Tracking store default `sqlite:///mlflow.db` hai (local, git-ignored). Team ke liye ek MLflow
server chalao aur `MLFLOW_TRACKING_URI=http://...` set karo. Code wahi rahega.

## Self-check questions

1. Same weights ko alag `det_size` ke saath evaluate kiya. Naya model version banna chahiye ya naya run?
2. Serving `models:/faceai-recognizer/7` ki jagah `@champion` kyun maangti hai?
3. Challenger ka TAR champion se 0.01 kam hai par latency 2x behtar hai. `promote` mana karega. Ye
   decision kaun lega, aur kaise record hoga?
4. Disk pe `w600k_r50.onnx` badal di gayi par `model_card.json` purana hai. App kya karegi, aur kyun?
