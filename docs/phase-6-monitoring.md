# Phase 6: Monitoring + Drift (Prometheus, Grafana)

> Goal: production mein kuch bigde to *user ke complain karne se pehle* pata chale, aur ye bhi
> pata chale ki problem service mein hai ya duniya badal gayi hai.

## 1. Stack

```
api:8000/metrics ◄── scrape (15s) ── Prometheus:9090 ──► alerts.yml rules
                                          │
                                          └──► Grafana:3000  (dashboard "FaceAI", auto-provisioned)
```

```powershell
docker compose up --build        # api + prometheus + grafana
# http://127.0.0.1:3000  (admin / admin)  -> Dashboards -> FaceAI
# http://127.0.0.1:9090/alerts           -> alert rules + state
```

## 2. Teen layers ke metrics

| Sawaal | Metrics | Alert |
|---|---|---|
| **Service** healthy hai? (RED) | `faceai_http_requests_total{route,status}`, `faceai_http_request_duration_seconds` | down, 5xx > 5%, p95 > 1s, overload |
| **Model** kya kar raha hai? | `faceai_recognitions_total{result}`, `faceai_top1_similarity`, `faceai_faces_per_image`, `faceai_det_score` | unknown rate > 50% |
| **Duniya** badli? (drift) | `faceai_drift_psi{feature}` | PSI > 0.25 |

Plus capacity (`faceai_inference_in_flight`, `faceai_overload_rejections_total`, avg batch size) aur
`faceai_model_info{model_id,version,device}`, taaki har graph pe pata ho kaunsa model chal raha tha.

### Label cardinality (production ka classic outage)

`route` label mein **template** jaata hai (`/v1/persons/{person_id}`), asli URL nahi. Har person
ID ek nayi time-series banata, aur 1 lakh users = 1 lakh series, Prometheus ki memory khatam. Galat
URLs (`/wp-admin`, scanners) sab ek `route="unmatched"` mein jaate hain. Test:
`test_unmatched_routes_share_one_label`.

## 3. Drift: labels ke bina model ki sehat

Production mein ground truth nahi hota ("ye sach mein Omkar tha?"). Isliye accuracy seedhe nahi
naap sakte. Par distributions naap sakte hain:

| Feature | Kya badla to | Matlab |
|---|---|---|
| `brightness` | gira | kam roshni, naya camera, raat ki shift |
| `face_px` | gira | log camera se door, ya resolution kam |
| `det_score` | gira | blur, mask, occlusion |
| `top1_similarity` | gira | **output drift**: model users ko pehchaan nahi pa raha |

**PSI** (Population Stability Index) reference distribution aur abhi ki distribution ko ek number
mein compare karta hai: `< 0.1` stable, `0.1-0.25` nazar rakho, `> 0.25` investigate.

- Reference = deploy ke baad ke pehle 500 observations, `data/drift_reference.json` mein save,
  taaki restart pe reset na ho.
- Current = sabse naye 500 observations (rolling window).
- Jaan-boojh ke badlaav kiya (naye cameras)? Reference file delete karo, naya reference banega.

Drift ≠ bug. Drift ek *sawaal* hai: "kya model abhi bhi theek hai?" Jawab ke liye naye domain ka
labeled sample lo aur Phase 2 pipeline pe evaluate karo (domain shift wala sabak).

## 4. Achhe alerts ke rules

- **Symptom pe alert, cause pe nahi**: "p95 > 1s" (user ko dikhta hai), "GPU 90%" nahi.
- **`for:` duration**: 2-30 min. Ek spike pe raat 3 baje kisi ko mat jagao.
- **Severity**: `page` = abhi uthna padega (service down), `ticket` = kal dekh lenge (drift).
- Har alert ke saath **runbook**: alert aaye to pehla step kya hai.

## Self-check questions

1. `route` label mein raw path daal diya. 1 mahine baad kya hoga?
2. Unknown rate 10% se 40% ho gaya, par latency/errors normal hain. Teen possible causes batao,
   aur har ek ko kaise confirm karoge?
3. PSI `brightness` pe 0.4 hai par `top1_similarity` pe 0.02. Kya action lena chahiye?
4. Accuracy ko directly monitor kyun nahi kar sakte? Agar karna ho to kya chahiye?
