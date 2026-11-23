# Phase 2: Evaluation + Data Versioning

> Goal: "model achha hai" ko ek **number** banana, us number ko **reproducible** banana, aur
> production threshold ko andaaze se nahi, **data se** chunna.

## 1. Verification metrics

Har pair (do photos) ka ek cosine similarity score aata hai. Threshold `t` se upar ho to "same person".

| Metric | Matlab | Kaun parwah karta hai |
|---|---|---|
| **TAR** (True Accept Rate) | Asli user ko sahi accept kiya | User experience |
| **FAR** (False Accept Rate) | Impostor ko galti se accept kiya | Security |
| **FRR** = 1 − TAR | Asli user reject hua | User pareshaan |
| **ROC curve** | Har threshold pe (FAR, TAR) | Poora trade-off ek graph mein |
| **AUC** | ROC ke neeche area (1.0 = perfect) | Model comparison |
| **EER** | Wo point jahan FAR = FRR | Model comparison, ek number mein |
| **TAR @ FAR=1e-3** | "1000 mein 1 impostor allow, tab kitne genuine pass?" | **Industry standard** |

**"Accuracy" kyun kaafi nahi?** Real system mein impostor attempts genuine se kahin zyada ho sakte
hain (ya kam). Accuracy dono galtiyon ko barabar maanti hai, jabki unki keemat alag hoti hai.
Bank ke liye galat accept (FAR) mehenga hai, attendance app ke liye galat reject (FRR) annoying hai.

**Threshold ek business decision hai**, ML decision nahi. ML aapko trade-off curve deta hai, aur
business decide karta hai ki curve par kis point par baithna hai. `params.yaml` mein
`operating_far: 0.001` wahi decision hai.

## 2. 10-fold protocol: test data pe tune mat karo

LFW ke 6,000 pairs 10 folds mein hain. Har fold ke liye: baaki 9 par best threshold chuno, is ek
par accuracy naapo. Jis data par tune kiya, usi par score naapna **data leakage** hai. Number
achha aayega, par jhootha hoga. `test_kfold_threshold_not_tuned_on_test_fold` dekho.

## 3. Failures chhupao mat

Kuch photos mein detector face nahi dhoondh paata. Unhe evaluation se *hata dena* number ko
behtar dikhata hai, par production mein wo user fail hi hoga. Isliye un pairs ko score `-1`
(worst case) diya jaata hai aur `failure_to_detect_rate` alag se report hota hai.

## 4. Error analysis

`reports/eval/errors.json` mein sabse "confident" galat accepts aur sabse buri rejects hain.
**Un photos ko khud kholo aur dekho.** Pattern dikhega: profile faces, sunglasses, low resolution,
ya LFW ke label mein hi galti. Model ka *agla* improvement yahin se aata hai, metrics ko
ghoorne se nahi.

## 5. DVC: data aur pipeline ka git

```
params.yaml ──┐
models/ ──────┤
data/lfw ─────┼─► dvc.yaml stages ─► reports/eval/metrics.json
src/ ─────────┘         │
                        └─► dvc.lock  (har input/output ka exact hash)
```

- `dvc.lock` git mein commit hota hai. Isse 6 mahine baad bhi pata chalega ki yeh metrics kis
  data, kis model aur kis code version se nikle the. Ise **lineage** kehte hain.
- `dvc repro` sirf woh stages chalata hai jinke inputs badle. `operating_far` badlo to sirf evaluate
  dobara chalega (seconds mein), embed nahi (jo minutes leta hai). Yeh **pipeline caching** hai.
- `dvc metrics diff main` se branch aur main ke metrics compare kar sakte ho, jaise code ka diff.
- Data git mein nahi, DVC cache mein rehta hai (`.dvc/cache`). Team ke saath share karne ke liye
  `dvc remote add` (S3/GDrive/SSH) karke `dvc push` / `dvc pull`.
- `cache.type hardlink` set hai, taaki data disk par do baar na bane.

## 6. Quality gate

`python -m faceai.eval.gate`: metrics `params.yaml → gate` ke minimum se neeche gaye to exit code 1.
Normal tests poochte hain "code chalta hai?", aur gate poochta hai "model achha hai?". Preprocessing
mein chhoti galti (jaise RGB/BGR swap) code nahi todti, par accuracy gira deti hai. Gate use pakad
leta hai. Phase 5 mein CI ise har PR par chalayega.

## 7. Sabse zaroori sabak: domain shift

LFW mein zyaadatar celebrities ki news photos hain: achhi lighting, professional cameras, kuch
specific demographics. Aapke users ho sakte hain webcam par, kam roshni mein, ya alag umar aur
skin tones ke. **LFW par 99.8% ka matlab yeh nahi ki aapke users par bhi 99.8% aayega.**
Production threshold ke liye:
1. Apne deployment jaisa data collect karo (consent ke saath!)
2. Isi pipeline mein naya dataset stage add karo
3. Alag-alag groups (umar, gender, skin tone, lighting) ke liye TAR/FAR **alag-alag** naapo. Kisi
   ek group par model bura chal raha ho to average mein chhup jaata hai. Ise **fairness evaluation**
   kehte hain.

## Self-check questions

1. Ek attendance app aur ek bank vault ke liye `operating_far` alag kyun hoga?
2. Agar hum threshold seedha saare 6,000 pairs par tune karke unhi par accuracy report karein, to galat kya hai?
3. `dvc.lock` ko git mein commit kyun karte hain, aur `data/lfw` ko kyun nahi?
4. Face na milne wale pairs ko evaluation se hata dena kyun galat hai?
5. LFW par TAR@FAR=1e-3 = 0.99 aaya. Kya ab yeh threshold apne office attendance system mein seedha laga do?
