# Phase 4: Serving Performance (batching, backpressure, load testing)

> Goal: "fast hai" ko numbers mein badalna, aur overload mein service ko gracefully fail karwana.
> Sabse bada sabak: **optimization pehle naapo, phir lagao**. Yahan ek "obvious" optimization
> (batching) ne naapne pe fayda nahi diya.

## 1. Pehle micro-benchmark: time kahan jaata hai?

`python scripts/benchmark_engine.py data/samples/t1.jpg` (RTX 3050 Laptop, 1280×886, 6 faces).
Raw numbers: `reports/perf/engine_gpu.json`, `engine_cpu.json`.

| Detector `det_size` | GPU p50 | CPU p50 |
|---|---|---|
| 320 | 10.6 ms | 37.5 ms |
| 480 | 14.4 ms | 76.3 ms |
| 640 | 22.9 ms | 140.6 ms |

| Embedder batch | GPU per-face | CPU per-face |
|---|---|---|
| 1 | 10.6 ms | 63.9 ms |
| 4 | 5.4 ms | 57.9 ms |
| 16 | **4.4 ms** | 57.5 ms |
| 32 | 4.9 ms | 55.0 ms |

Seekh:
- GPU pe batching per-face cost ~2.4× kam karta hai (16 tak), CPU pe lagbhag kuch nahi. CPU
  already saare cores use kar raha hai; GPU ko chhote batch pe "khaali" chalna padta hai.
- `det_size` 640 → 320 detector ko ~2× (GPU) / ~4× (CPU) fast karta hai. **Accuracy ka kya?** Ye
  sirf speed hai. `params.yaml → eval.det_size: 320` karke `dvc repro` chalao aur TAR@FAR dekho.
  Speed/accuracy trade-off ko hamesha **dono taraf** se naapo (Phase 2 pipeline yahi kaam aati hai).

## 2. Dynamic micro-batching (`serving/batcher.py`)

```
request A ─┐
request B ─┼─► queue ─► worker: max_batch YA max_wait_ms, jo pehle ─► ek embedder call
request C ─┘                                                              │
        ◄───────── har request ko uske apne rows wapas ◄──────────────────┘
```

- Sirf embedder: ArcFace ka input `['None', 3, 112, 112]` (dynamic batch). SCRFD detector
  `[1, 3, ?, ?]` hai (fixed batch 1), use batch nahi kar sakte.
- Ek batch fail ho to us batch ke **saare** callers ko error milta hai (koi request hang nahi hoti).
- `FACEAI_BATCHING=off|on|auto`, `FACEAI_BATCH_MAX_SIZE=16`, `FACEAI_BATCH_MAX_WAIT_MS=3`.

## 3. Load test: batching ne fayda NAHI diya

`python scripts/loadtest.py <image> --concurrency 1 4 16 --duration 15` (raw: `reports/perf/loadtest_*.json`)

| Image | Batching | c=1 req/s (p50) | c=4 req/s (p50) | c=16 req/s (p50 / p99) |
|---|---|---|---|---|
| 1 face | off | 15.3 (42 ms) | 15.5 (228 ms) | 21.8 (469 / 1706 ms) |
| 1 face | on | 15.5 (63 ms) | 12.7 (389 ms) | 13.7 (1533 / 2017 ms) |
| 6 faces | off | 12.5 (71 ms) | 14.6 (182 ms) | 14.5 (1092 / 1535 ms) |
| 6 faces | on | 10.9 (92 ms) | 15.5 (194 ms) | 10.1 (1480 / 2054 ms) |

Kyun? Micro-benchmark ne kaha tha 2.4× fayda hoga.
1. **Bottleneck embedder nahi hai.** Per request detector (~23 ms) + image decode + Python kaam
   embedder se zyada hai. Jo hissa 30% time leta hai use 2× fast karo, to total ~15% hi bachega.
2. **Ek request already batch hai.** 6-face image = 6 ka batch. Cross-request batching sirf tab
   chamakta hai jab har request mein 1 face ho *aur* embedder bottleneck ho.
3. **Ek worker thread GPU calls ko serialize karta hai.** Bina batcher ke 4 request threads
   detector aur embedder ko GPU pe overlap kar sakte hain.
4. `max_wait_ms` akeli request ko bhi rok deta hai (c=1 p50: 42 → 63 ms).
5. Laptop GPU noisy hai (display driver, thermal throttling): same config do baar mein 32 aur
   15 req/s. Ek run pe kabhi decision mat lo.

**Decision:** default `FACEAI_BATCHING=off`. Feature rakha hai (opt-in), kyunki server GPU
(T4/A10, alag detector service, ya 1-face selfie traffic) pe tasveer alag ho sakti hai. Wahan
dobara naapo. Isi ko **data-driven engineering** kehte hain: intuition se nahi, measurement se.

## 4. Saturation aur admission control (`serving/limiter.py`)

Table mein dekho: concurrency 1 → 16 karne se throughput ~15 req/s pe ruk jaata hai, par p50 latency
45 ms → 1.5 s ho jaati hai. GPU saturated hai, aur extra requests sirf **queue mein intezaar** kar
rahi hain (Little's law: latency ≈ in-flight / throughput).

Bina limit ke yahi queue badhti rehti hai → har user ko timeout → clients retry → aur load →
"retry storm". Isliye:
- `FACEAI_MAX_CONCURRENT_INFERENCE=4`: ek saath max 4 requests GPU pe
- `FACEAI_MAX_QUEUE_WAIT_MS=2000`: slot ke liye max 2 s intezaar, phir **503 + `Retry-After: 1`**

"Kuch users ko turant 'abhi busy hoon'" behtar hai "sabko 30 s baad timeout" se. Capacity planning:
~15 req/s per GPU ×  safety margin → kitne replicas chahiye, ye isi data se nikalta hai.

## 5. Aur knobs

- `FACEAI_ORT_INTRA_OP_THREADS`: CPU pe multiple workers/requests ho to har ONNX session saare cores
  na maange (oversubscription latency badhata hai). GPU pe asar nahi.
- `FACEAI_DET_SIZE`: speed vs small-face recall; eval pipeline se validate karke hi badlo.

## Self-check questions

1. Micro-benchmark ne 2.4× kaha, load test ne 1×. Kaunsa sach hai, aur dono kyun zaroori hain?
2. Average latency 100 ms hai par p99 2 s. Users kya mehsoos karenge? SLO kaise likhoge?
3. `max_concurrent_inference=1000` kar diya. Overload mein kya hoga?
4. Kis traffic pattern mein cross-request batching sach mein fayda dega?
