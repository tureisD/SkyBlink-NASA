# syntax=docker/dockerfile:1
# SPHEREx SkyBlink — one image, one origin: FastAPI + built React frontend.

# ---------------------------------------------------------------------------
# 1. Frontend build (Vite + TypeScript)
# ---------------------------------------------------------------------------
FROM node:24-alpine AS frontend-build
WORKDIR /build/frontend

# Install exactly the locked dependency set first (cache-friendly).
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# 2. Runtime: Python API + static frontend
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/backend \
    CACHE_DIR=/data/cache \
    GOLDEN_CACHE_DIR=/app/golden_cache \
    SPHEREX_FRONTEND_DIST=/app/frontend/dist \
    PORT=8000

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/ /app/backend/
COPY data/catalog-exposure-index.json /app/data/catalog-exposure-index.json
COPY golden_cache/wise_0855/ /app/golden_cache/wise_0855/
COPY golden_cache/barnards_star/ /app/golden_cache/barnards_star/
COPY golden_cache/eps_indi_b/ /app/golden_cache/eps_indi_b/
COPY golden_cache/rw_aurigae/ /app/golden_cache/rw_aurigae/
COPY golden_cache/r_draconis/ /app/golden_cache/r_draconis/
COPY scripts/serve.py /app/scripts/serve.py
COPY scripts/verify_real_data.py /app/scripts/verify_real_data.py
COPY docs/evidence/phase1/phase1-data-inventory.json /app/docs/evidence/phase1/phase1-data-inventory.json
COPY --from=frontend-build /build/frontend/dist /app/frontend/dist
RUN python scripts/verify_real_data.py --require-dist

# Persistent live/cutout cache.  The named volume in docker-compose.yml is
# mounted here; the directory is created so the API works without a volume too.
RUN groupadd --gid 10001 skyblink \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin skyblink \
    && mkdir -p /data/cache \
    && chown 10001:10001 /data/cache
USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=20s --start-period=30s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=15).status == 200 else 1)"

CMD ["python", "/app/scripts/serve.py"]
