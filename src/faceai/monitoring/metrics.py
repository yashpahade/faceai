"""
Prometheus metrics. `GET /metrics` -> Prometheus har 15s scrape karta hai -> Grafana graph + alerts.

Teen tarah ke sawaal, teen tarah ke metrics:
1. Service healthy hai? (RED: Rate, Errors, Duration)  -> http_requests_total, request_duration
2. Model kya kar raha hai?                             -> faces/image, top-1 similarity, unknowns
3. Duniya badal gayi? (drift)                          -> drift_psi{feature}

Metric types:
- Counter:   sirf badhta hai (requests). Grafana mein `rate(x[5m])` = per-second.
- Histogram: values ko buckets mein ginta hai -> p95 latency `histogram_quantile(0.95, ...)`.
- Gauge:     upar-neeche (index size, in-flight requests, PSI).

LABEL CARDINALITY: `route` label mein `/v1/persons/{person_id}` (template) jaata hai, asli URL
`/v1/persons/3f9a...` NAHI. Har person ID ek nayi time-series banata, aur Prometheus ki memory
khatam ho jaati. Labels mein kabhi user IDs, image names ya free text mat daalo.
"""

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

# Apni registry (global default nahi): tests mein kai apps bante hain, aur process-level
# python_gc_* jaise metrics humein nahi chahiye.
REGISTRY = CollectorRegistry()

HTTP_REQUESTS = Counter(
    "faceai_http_requests_total",
    "HTTP requests",
    ["method", "route", "status"],
    registry=REGISTRY,
)
HTTP_LATENCY = Histogram(
    "faceai_http_request_duration_seconds",
    "End-to-end request latency",
    ["route"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=REGISTRY,
)
INFERENCE_LATENCY = Histogram(
    "faceai_inference_duration_seconds",
    "Model time per request by stage",
    ["stage"],  # inference (detect+align+embed), search
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
    registry=REGISTRY,
)
FACES_PER_IMAGE = Histogram(
    "faceai_faces_per_image",
    "Faces detected per recognize request",
    buckets=(0, 1, 2, 3, 5, 10, 20),
    registry=REGISTRY,
)
RECOGNITIONS = Counter(
    "faceai_recognitions_total",
    "Recognized faces by outcome",
    ["result"],  # match | unknown
    registry=REGISTRY,
)
TOP1_SIMILARITY = Histogram(
    "faceai_top1_similarity",
    "Best gallery similarity per face (output distribution)",
    buckets=tuple(round(-0.2 + 0.1 * i, 1) for i in range(13)),
    registry=REGISTRY,
)
DET_SCORE = Histogram(
    "faceai_det_score",
    "Detector confidence per face",
    buckets=(0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0),
    registry=REGISTRY,
)
ENROLLMENTS = Counter(
    "faceai_enrollments_total",
    "Enrollment attempts",
    ["result"],  # ok | rejected
    registry=REGISTRY,
)
REJECTED = Counter(
    "faceai_overload_rejections_total",
    "Requests rejected by admission control (503)",
    registry=REGISTRY,
)

# Scrape ke time app state se set hote hain
READY = Gauge("faceai_ready", "1 if the model is loaded and serving", registry=REGISTRY)
INDEX_SIZE = Gauge("faceai_index_embeddings", "Embeddings in the vector index", registry=REGISTRY)
PERSONS = Gauge("faceai_persons", "Enrolled persons", registry=REGISTRY)
IN_FLIGHT = Gauge(
    "faceai_inference_in_flight", "Requests holding an inference slot", registry=REGISTRY
)
BATCH_SIZE = Gauge("faceai_embed_batch_avg_size", "Avg micro-batch size", registry=REGISTRY)
DRIFT_PSI = Gauge("faceai_drift_psi", "PSI vs reference window", ["feature"], registry=REGISTRY)
MODEL_INFO = Gauge(
    "faceai_model_info",
    "Served model (value always 1; info in labels)",
    ["model_id", "version", "device"],
    registry=REGISTRY,
)


def refresh_gauges(state) -> None:
    """/metrics scrape se pehle: app.state se current values gauges mein daalo."""
    svc = getattr(state, "service", None)
    READY.set(1 if getattr(state, "ready", False) else 0)
    if svc is not None:
        INDEX_SIZE.set(len(svc.index))
        PERSONS.set(svc.db.count_persons())
        card = getattr(state, "model_card", None) or {}
        MODEL_INFO.clear()
        version = str(card.get("version", "none"))
        MODEL_INFO.labels(svc.engine.model_id, version, svc.engine.device).set(1)
    limiter = getattr(state, "limiter", None)
    if limiter is not None:
        IN_FLIGHT.set(limiter.in_flight)
    batcher = getattr(state, "batcher", None)
    if batcher is not None:
        BATCH_SIZE.set(batcher.avg_batch_size)
    drift = getattr(state, "drift", None)
    if drift is not None:
        for feature, value in drift.scores().items():
            if value is not None:
                DRIFT_PSI.labels(feature).set(value)
