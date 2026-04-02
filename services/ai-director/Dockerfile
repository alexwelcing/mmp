# AI Director — Multi-stage Docker build
# Base image: Python 3.11 slim for minimal attack surface.

# ── Stage 1: dependency resolver ─────────────────────────────────────
FROM python:3.11-slim AS deps

WORKDIR /app

# Install system deps required by some Python packages (e.g. libsecp256k1
# for eth-account, libgmp for cryptography).
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libssl-dev \
    libgmp-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: runtime image ────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Security: run as non-root user.
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

# Copy installed packages from the deps stage.
COPY --from=deps /install /usr/local

# Copy application source.
COPY . .

# Filestore NFS mount point (created at runtime by Kubernetes volume mount).
RUN mkdir -p /mnt/filestore && chown appuser:appgroup /mnt/filestore

USER appuser

# FastAPI on port 8080 (matches Kubernetes Service definition).
EXPOSE 8080

# Healthcheck for Kubernetes liveness probe.
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
