"""Test bootstrap: make ``backend/`` and the repo root importable.

The canonical import path is ``models.*``/``core.*``/``services.*`` with
``backend/`` on ``sys.path`` (``docs/decisions/o1-contract-decisions.md`` §7).  The repo
root is also added so tests can import ``scripts.build_golden_cache`` without installing the repo.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"

for candidate in (str(BACKEND_ROOT), str(REPO_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)
