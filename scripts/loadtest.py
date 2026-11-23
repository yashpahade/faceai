"""
HTTP load test: N concurrent clients, D seconds, ek image baar-baar /v1/recognize pe.

    python -m faceai &                        # server (doosre terminal mein)
    python scripts/loadtest.py data/samples/t1.jpg --concurrency 1 8 32 --duration 15

Report: throughput (req/s), latency p50/p95/p99, status codes (503 = admission control ne roka).

Average latency kyun nahi? Average 100 ms ho sakta hai jab 5% users ko 3 second lag rahe hon.
Users tail (p95/p99) mehsoos karte hain, isliye SLO hamesha percentiles mein likhte hain.
"""

import argparse
import asyncio
import json
import time
from collections import Counter
from pathlib import Path

import httpx


async def run(url: str, image: bytes, concurrency: int, duration: float) -> dict:
    latencies: list[float] = []
    statuses: Counter = Counter()
    stop_at = time.perf_counter() + duration

    async def worker(client: httpx.AsyncClient) -> None:
        while time.perf_counter() < stop_at:
            t0 = time.perf_counter()
            try:
                r = await client.post(url, files={"file": ("img.jpg", image, "image/jpeg")})
                statuses[r.status_code] += 1
            except httpx.HTTPError as e:
                statuses[type(e).__name__] += 1
                continue
            if r.status_code == 200:
                latencies.append((time.perf_counter() - t0) * 1000)

    limits = httpx.Limits(max_connections=concurrency)
    async with httpx.AsyncClient(timeout=30, limits=limits) as client:
        t0 = time.perf_counter()
        await asyncio.gather(*(worker(client) for _ in range(concurrency)))
        elapsed = time.perf_counter() - t0

    latencies.sort()

    def pct(p: float) -> float:
        return round(latencies[int(p * (len(latencies) - 1))], 1) if latencies else float("nan")

    return {
        "concurrency": concurrency,
        "rps": round(len(latencies) / elapsed, 1),
        "p50_ms": pct(0.50),
        "p95_ms": pct(0.95),
        "p99_ms": pct(0.99),
        "statuses": {str(k): v for k, v in statuses.items()},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image", type=Path)
    ap.add_argument("--url", default="http://127.0.0.1:8000/v1/recognize")
    ap.add_argument("--concurrency", type=int, nargs="+", default=[1, 4, 16])
    ap.add_argument("--duration", type=float, default=15)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    image = args.image.read_bytes()
    rows = []
    for c in args.concurrency:
        r = asyncio.run(run(args.url, image, c, args.duration))
        rows.append(r)
        print(
            f"c={c:3d}  {r['rps']:6.1f} req/s  p50={r['p50_ms']:7.1f}  p95={r['p95_ms']:7.1f}  "
            f"p99={r['p99_ms']:7.1f} ms  {r['statuses']}"
        )
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(rows, indent=2) + "\n", newline="\n")


if __name__ == "__main__":
    main()
