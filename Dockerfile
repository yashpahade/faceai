# ---------- Stage 1: builder (dependencies compile/install) ----------
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Pehle sirf dependency files copy -> code badalne pe ye layer cache se aati hai (fast rebuild)
COPY pyproject.toml requirements.lock ./
# Container mein CPU runtime. (GPU container ke liye nvidia/cuda base image + onnxruntime-gpu chahiye)
ARG ORT_PACKAGE=onnxruntime==1.22.0
RUN pip install -r requirements.lock "$ORT_PACKAGE"

COPY src ./src
RUN pip install --no-deps .

# ---------- Stage 2: runtime (chhoti, bina compilers ke) ----------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    FACEAI_ENV=prod FACEAI_LOG_JSON=true FACEAI_DATA_DIR=/app/data \
    FACEAI_MODELS_DIR=/app/models FACEAI_DEVICE=cpu

# Security: root user se mat chalao
RUN useradd --create-home --uid 1000 faceai
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
RUN mkdir -p /app/data && chown -R faceai:faceai /app
USER faceai

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/ready').status==200 else 1)"

CMD ["uvicorn", "faceai.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
