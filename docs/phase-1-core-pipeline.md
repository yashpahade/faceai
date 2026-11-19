# Phase 1: Core Recognition Pipeline

> Goal: face recognition ko *sahi* tareeke se karna. Ek pass, aligned faces, cosine similarity,
> aur data jo kabhi desync na ho.

## 1. Pipeline: image se identity tak

```
image (BGR)
  │
  ├─► SCRFD detector (det_10g.onnx) ─► bbox + 5 landmarks + det_score   [har face]
  │
  ├─► Alignment (Umeyama similarity transform) ─► 112×112 aligned crop
  │
  ├─► ArcFace (w600k_r50.onnx) ─► 512-dim vector ─► L2 normalize       [saare faces ek batch]
  │
  └─► FAISS IndexFlatIP ─► top-k similar embeddings ─► person-level max ─► threshold ─► match / unknown
```

Code map: `vision/detector.py` → `vision/align.py` → `vision/embedder.py` → `store/index.py`,
jode gaye `vision/engine.py` mein, business rules `service.py` mein.

## 2. Legacy code kyun galat tha

| Legacy | Problem | Ab |
|---|---|---|
| bbox crop → resize 112 | Face tilted/offset, ArcFace ne aisa kabhi dekha hi nahi | Landmarks se alignment |
| Crop pe dobara detect | Chhote crop pe detection fail → 4 fallbacks | Ek pass, koi fallback nahi |
| `faces_full[face_index]` | Detection order ki guarantee nahi → **galat insaan ki embedding** | Har face apne landmarks se |
| 2× `FaceAnalysis` load | Double RAM, slow startup | Ek detector + ek recognizer session |
| `IndexFlatL2` + "confidence %" | L2 distance ko % bolna misleading | `IndexFlatIP` = cosine similarity |
| FAISS file + pickle metadata | Ek save ho, doosra crash → desync | SQLite = truth, FAISS = cache |

## 3. Detection: SCRFD decode

Model boxes nahi deta, **dense predictions** deta hai. Image ko stride 8/16/32 ke grids mein
baanto (80×80, 40×40, 20×20 cells), har cell pe 2 anchors. Har anchor ke liye:
- `score`: face hai ya nahi
- `bbox`: anchor center se left/top/right/bottom tak ki doori (× stride)
- `kps`: 5 landmarks ka offset

Threshold se filter, phir **NMS**: ek face pe kai overlapping boxes aate hain, IoU > 0.4 wale
duplicates hata do. `test_nms_removes_overlapping_duplicates` dekho.

## 4. Alignment: sabse underrated step

ArcFace ko training mein har face aise dikhaya gaya ki aankhein, naak, honth 112×112 mein **fixed
pixels** pe hon (`ARCFACE_TEMPLATE`). Humare 5 detected points ko template pe map karne wala
rotation + scale + shift (similarity transform) **Umeyama** algorithm se nikalte hain (SVD,
least squares). `test_umeyama_recovers_known_similarity_transform` iski math verify karta hai.

## 5. Embeddings aur cosine similarity

- ArcFace face → 512 numbers. ArcFace loss ne aisa train kiya ki same insaan ke vectors ke beech
  **angle** chhota ho.
- L2-normalize (length = 1) ke baad: `cosine_similarity(a, b) = a · b`, range −1..1.
- Isliye FAISS `IndexFlatIP` (inner product), L2 nahi.
- **Similarity probability NAHI hai.** 0.45 ka matlab "45% sure" nahi. Ye sirf ek score hai;
  kis score pe "same person" bolein, ye **threshold** decide karta hai, aur threshold
  data se aata hai (Phase 2: FAR/FRR trade-off).

## 6. Storage design: source of truth vs cache

```
SQLite (data/faceai.db)        FAISS (memory)
  persons                        IndexIDMap2(IndexFlatIP)
  embeddings ──── startup pe ───► rebuild
    + model_id                   (sirf current model_id ki)
```
- **Embedding versioning:** har embedding ke saath `model_id`. Model badla (e.g. buffalo_l →
  koi naya)? Purani embeddings naye model ke saath compare nahi ho sakti (alag "vector space").
  Startup pe warning aati hai. Ye real production gotcha hai.
- **Person-level search:** ek insaan ki kai photos → top-k embeddings → har person ka best score.
- **Delete = sach mein delete:** person delete → `ON DELETE CASCADE` se embeddings bhi gayab,
  index se bhi. (Privacy law: right to erasure.)

## 7. Enrollment quality gates

Register karte waqt strict rehte hain, kyunki ek kharab enrollment se us insaan ki har future recognition kharab hoti hai:
detection score, face size (px), sharpness (Laplacian variance), frontal pose (yaw ratio).
Recognize karte waqt ye checks nahi lagte. Thresholds abhi andaaze hain, Phase 2 mein data se tune honge.

## 8. Serving concepts

- **Model artifact + checksum:** `python -m faceai.models.download`. URL aur SHA-256 code mein
  pinned hain. Hash mismatch hone par load hi nahi hoga.
- **Warmup:** pehli GPU inference slow hoti hai, isliye startup pe ek dummy run.
- **Readiness:** model load fail → app zinda (`/health/live` 200), par `/health/ready` 503 aur
  API 503. Test: `test_not_ready_when_model_missing`.
- **Dependency injection:** `create_app(settings, engine=FakeEngine())`, taaki tests bina GPU/model ke chalein.
- **Batching:** ek image ke saare faces ArcFace ke ek hi call mein jaate hain.
- **API versioning:** `/v1/...`

## 9. License (zaroori)

InsightFace ke `buffalo_l` models **sirf non-commercial research** ke liye hain. Commercial product
ke liye InsightFace se license lo, ya permissive license wala model use karo.

## Self-check questions

1. Bina alignment ke embedding kyun kharab aati hai?
2. Cosine similarity 0.45 ko "45% confidence" bolna galat kyun hai?
3. FAISS index ko source of truth kyun nahi banaya? Server crash ho jaye to kya hoga?
4. Model `buffalo_l` se kisi naye model pe upgrade kiya. Purane enrolled logon ka kya karna padega, aur kyun?
5. Enrollment pe quality check strict kyun hai, aur recognition pe kyun nahi?
