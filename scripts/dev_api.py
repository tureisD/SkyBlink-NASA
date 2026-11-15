"""Run the development API while watching only backend source directories.

Invoke from the repository root with the project's Python environment:
    python scripts/dev_api.py

Raw FITS, live products and research tools under backend/.cache are outside the
watch roots. This is a development launcher; use scripts/serve.py for a built UI.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
WATCH_DIRECTORIES = tuple(BACKEND / name for name in ("app", "core", "models", "routers", "services"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-reload", action="store_true", help="Use for hidden/background Windows processes; restart explicitly after source changes")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    uvicorn.run(
        "app.main:app",
        app_dir=str(BACKEND),
        reload=not args.no_reload,
        reload_dirs=None if args.no_reload else [str(directory) for directory in WATCH_DIRECTORIES],
        host=args.host,
        port=args.port,
    )


# Required for Windows multiprocessing spawn: importing the launcher in a child
# must not start another reloader or bind another listening socket.
if __name__ == "__main__":
    main()
