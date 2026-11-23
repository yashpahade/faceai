# Phase A: Accuracy (measure first), Calibration, Active Liveness

> Goal: "detection accurate nahi hai" ko numbers mein badalna, har idea ko **naapna**, aur sirf
> wahi lagana jo sach mein behtar kare. Plan ke 4 ideas mein se 3 naapne pe fail hue, aur ek
> (det_size 1280) poora system tod deta.

## 1. Experiment (ek run, 7 variants, same metrics)

`python scripts/accuracy_experiments.py` → `reports/experiments/phase_a.json`
(LFW: 7,701 images, 6,000 pairs; RTX 3050 Laptop; Phase 2 ke same metrics).

Teen detection passes (640, 1280, 640+CLAHE), unse saare variants derive: 7 alag full runs ki jagah ~1 ghanta.

| Variant | Missed faces | 10-fold acc | EER | TAR@FAR=1e-4 | TAR@FAR=1e-3 | Detector ms |
|---|---|---|---|---|---|---|
| Baseline (640, thr 0.5) | 0.14% | 99.633% | 0.60% | 99.333% | 99.333% | 18 |
| **thr 0.4** | **0.06%** | **99.733%** | **0.43%** | **99.533%** | **99.533%** | 18 |
| Flip-TTA | 0.14% | 99.650% | 0.60% | 99.333% | 99.333% | 18 (+2× embed) |
| det_size 1280 | **90.2%** | 50.6% | 49.4% | 0.07% | 0.33% | 137 |
| Multi-scale 640+1280 | 0.14% | 99.633% | 0.60% | 99.333% | 99.333% | 155 |
| CLAHE | 0.14% | 99.650% | 0.63% | 99.200% | 99.333% | 108 |
| CLAHE + flip-TTA | 0.14% | 99.650% | 0.63% | 99.233% | 99.333% | 108 |

Baseline Phase 2 ke numbers exactly reproduce karta hai (99.633%, 99.333%): setup sahi hai, comparison fair hai.

## 2. Decisions

| Idea (plan) | Verdict | Kyun |
|---|---|---|
| `det_threshold` 0.5 → 0.4 | ✅ **Adopted** (serving + eval) | Aadhe missed faces wapas, TAR +0.2%, EER −30%. Enroll pe alag gate (det ≥ 0.6) hai, isliye kharab faces enroll nahi honge; recognize mein extra galat detection "unknown" ban jaata hai. |
| `det_size` 640 → 1280 | ❌ Rejected | **90% faces miss.** LFW 250×250 image 1280 pe upscale → face itna bada ki SCRFD ke anchors (training scales) se bahar. Bada input sirf *chhote faces + badi images* (group photo, door camera) pe madad karta hai. 7× slow bhi. |
| Multi-scale | ❌ Rejected | Koi gain nahi (merge 640 wale detections hi rakhta hai), 8× detection cost. |
| CLAHE | ❌ Rejected | Accuracy same/thodi kam (TAR@1e-4 99.33 → 99.20%), +90 ms CPU. ArcFace already lighting-robust training se aata hai. |
| Flip-TTA | ❌ Not worth it | +1 pair (99.633 → 99.650%), embedding cost 2×. Option rehta hai (`FACEAI_FLIP_TTA`). |

Sab options config mein rehte hain (default off), taaki **apne data pe** dobara naap sako: kisi
classroom camera pe 1280 sach mein madad kare, to data dikhayega.

**Sabak:** "Resolution badhao, threshold ghatao, contrast enhance karo" sunne mein sahi lagta hai.
Naapne pe ek ne madad ki, teen ne nahi, ek ne system tod diya. Isiliye Phase 2 ki eval pipeline
pehle bani thi.

## 3. EXIF orientation

Phone photos ke pixels sideways save hote hain + EXIF tag "ghuma ke dikhao". `decode_image`
(OpenCV `IMREAD_COLOR`) tag apply karta hai; test `test_decode_applies_exif_rotation` ise lock
karta hai. Frontend bhi gallery uploads pe `createImageBitmap(imageOrientation: "from-image")`.

## 4. Threshold: LFW ka nahi, apna

LFW threshold (0.253 @ FAR 1e-3) news photos ka hai. Apne cameras pe:

```powershell
# data/calibration/<person>/*.jpg  (10+ log, 3+ photos each, alag din/lighting, consent ke saath)
python -m faceai.eval.calibrate --far 0.001
# -> reports/calibration/metrics.json -> "Set FACEAI_MATCH_THRESHOLD=..."
```

Tool genuine + impostor pairs banata hai, aur kam data pe warning deta hai (FAR=1e-3 ke liye
~1000+ impostor pairs chahiye).

## 5. Active liveness (anti-spoofing, basic)

Random 2 steps (turn left/right/center) → har step ka frame → server: ek face, sahi yaw (5
landmarks), saare frames mein same insaan, challenge 60s + single-use → **token jismein wahi
verified embedding hai**. Face login / self attendance usi embedding se hote hain.

| Rokta hai | Nahi rokta |
|---|---|
| Printed photo, phone pe static photo | Us insaan ka video jo sahi order mein sir ghumaye |
| Purane successful answer ka replay | 3D mask, deepfake camera stream |
| Liveness ek ka, login doosre ka | (Passive PAD model chahiye: license + APCER/BPCER evaluation) |

Blink detection plan mein tha, par SCRFD ke 5 landmarks mein palkein nahi hain; extra 106-point
model chahiye (buffalo_l mein, non-commercial). Head-turn isi pipeline se ho jaata hai.

## Self-check questions

1. det_size 1280 ne LFW pe 90% faces kyun miss kiye? Kis tarah ke camera setup pe 1280 madad karega?
2. det_threshold 0.4 se false detections badh sakte hain. Enrollment ko isse kya bachata hai?
3. Flip-TTA ne +1 pair diya. Kab ek option "worth it" hota hai, kab nahi?
4. Liveness token mein embedding kyun rakhte hain, sirf "pass/fail" kyun nahi?
