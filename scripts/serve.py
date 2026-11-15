#!/usr/bin/env python3
"""Single-origin production server for SPHEREx SkyBlink.

The FastAPI app already serves ``/api/v1/*``.  This wrapper mounts the Vite
build (``frontend/dist``) at ``/`` so the public deployment has one origin, no
CORS configuration, and one port.  The API routes are registered before the
static mount, so ``/api/v1/*`` keeps precedence; unknown API paths are not
silently replaced by ``index.html``.

Environment
-----------
``SPHEREX_FRONTEND_DIST``
    Directory containing ``index.html`` and ``assets/`` (default:
    ``<repo>/frontend/dist``).
``PORT`` / ``HOST``
    Bind address (defaults ``8000`` / ``0.0.0.0``).
``FORWARDED_ALLOW_IPS``
    Trusted reverse-proxy addresses (default ``127.0.0.1``); set explicitly for
    a controlled deployment network. Do not trust arbitrary public clients.
``LOG_LEVEL``
    Uvicorn log level (default ``info``).

Run::

    python scripts/serve.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi import FastAPI  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from app.main import app  # noqa: E402

DIST_DIR = Path(
    os.environ.get("SPHEREX_FRONTEND_DIST", str(REPO_ROOT / "frontend" / "dist"))
).expanduser().resolve()


def mount_frontend(application: FastAPI, dist_dir: Path = DIST_DIR) -> bool:
    """Mount the built frontend at ``/``; return ``False`` when it is absent."""
    if not (dist_dir / "index.html").is_file():
        print(
            f"[serve] frontend build not found at {dist_dir}; serving API only",
            file=sys.stderr,
        )
        return False
    application.mount(
        "/",
        StaticFiles(directory=str(dist_dir), html=True),
        name="frontend",
    )
    return True


FRONTEND_MOUNTED = mount_frontend(app)


def main() -> None:
    import uvicorn

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    log_level = os.environ.get("LOG_LEVEL", "info").lower()
    print(
        f"[serve] API + frontend on http://{host}:{port} "
        f"(dist={DIST_DIR if FRONTEND_MOUNTED else 'missing'})"
    )
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=log_level,
        proxy_headers=True,
        forwarded_allow_ips=os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1"),
    )


if __name__ == "__main__":
    main()
