"""Vercel entrypoint: the unchanged FastAPI app plus the built frontend.

Vercel's Python runtime looks for a FastAPI instance named ``app`` in a
root-level ``server.py``. This module only wires things together; the API
lives in ``backend/`` and local runs keep using ``scripts/serve.py``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# A Vercel Function can write only under /tmp, so the runtime cache goes there.
if os.environ.get("VERCEL"):
    os.environ.setdefault("CACHE_DIR", "/tmp/skyblink-cache")

from fastapi.staticfiles import StaticFiles  # noqa: E402

from app.main import app  # noqa: E402

DIST_DIR = REPO_ROOT / "frontend" / "dist"

# API routes are registered first, so /api/v1/* keeps precedence over the
# static frontend, exactly as in scripts/serve.py.
if (DIST_DIR / "index.html").is_file():
    app.mount("/", StaticFiles(directory=str(DIST_DIR), html=True), name="frontend")
