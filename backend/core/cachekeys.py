"""Canonical live-cache keys and asset-path validation (O1 decision §4).

The URL shape stays ``/api/v1/assets/{target_id}/{filename}``.  For arbitrary
positions the first segment is ``live_<sha256(canonical_query)[:16]>``.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence

from models.common import EPOCH_ID_PATTERN

LIVE_KEY_RE = re.compile(r"^live_[0-9a-f]{16}$")
ASSET_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
FILENAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

SIZE_MIN_DEG = 0.05
SIZE_MAX_DEG = 0.2


def canonical_bands(bands: str | Sequence[int] | None) -> str:
    """Return ``"all"`` or a sorted, deduplicated ``1-5-6``-style key."""
    if bands is None:
        return "all"
    if isinstance(bands, str):
        text = bands.strip()
        if not text or text.lower() == "all":
            return "all"
        parts = [part.strip() for part in text.split(",") if part.strip()]
        if any(part.lower() == "all" for part in parts):
            raise ValueError("'all' must be used alone")
        numbers = [int(part) for part in parts]
    else:
        numbers = [int(part) for part in bands]
        if not numbers:
            return "all"
    for number in numbers:
        if number < 1 or number > 6:
            raise ValueError(f"invalid band: {number!r}")
    return "-".join(str(number) for number in sorted(set(numbers)))


def canonical_epochs(epochs: str | Sequence[str] | None) -> str:
    """Return ``"all"`` or a lexicographically sorted ``2025_E1-2025_E2`` key."""
    if epochs is None:
        return "all"
    if isinstance(epochs, str):
        text = epochs.strip()
        if not text or text.lower() == "all":
            return "all"
        parts = [part.strip() for part in text.split(",") if part.strip()]
    else:
        parts = [str(part).strip() for part in epochs if str(part).strip()]
        if not parts:
            return "all"
    if any(part.lower() == "all" for part in parts):
        raise ValueError("'all' must be used alone")
    for part in parts:
        if not re.fullmatch(EPOCH_ID_PATTERN, part):
            raise ValueError(f"invalid epoch id: {part!r}")
    return "-".join(sorted(set(parts)))


def canonical_query(
    ra: float,
    dec: float,
    size: float,
    bands: str | Sequence[int] | None = "all",
    epochs: str | Sequence[str] | None = "all",
    include_diff: bool = True,
) -> str:
    """Build the canonical query string that is hashed for a live asset key."""
    ra_value = float(ra)
    dec_value = float(dec)
    size_value = min(max(float(size), SIZE_MIN_DEG), SIZE_MAX_DEG)
    bands_key = canonical_bands(bands)
    epochs_key = canonical_epochs(epochs)
    diff_key = 1 if include_diff else 0
    return (
        f"{ra_value:.6f}_{dec_value:.6f}_{size_value:.4f}"
        f"_b{bands_key}_e{epochs_key}_d{diff_key}"
    )


def live_asset_key(
    ra: float,
    dec: float,
    size: float,
    bands: str | Sequence[int] | None = "all",
    epochs: str | Sequence[str] | None = "all",
    include_diff: bool = True,
    *, discovery_mode: str = "live",
) -> str:
    """Return ``live_<16 hex chars>`` for an arbitrary-coordinate query."""
    if discovery_mode not in {"live", "known"}:
        raise ValueError("Unknown discovery mode")
    query = canonical_query(ra, dec, size, bands, epochs, include_diff)
    if discovery_mode == "known":
        query += "_discovery_known"
    digest = hashlib.sha256(query.encode("utf-8")).hexdigest()
    return f"live_{digest[:16]}"


def is_live_asset_key(value: str) -> bool:
    return bool(LIVE_KEY_RE.fullmatch(value))


def is_valid_asset_key(value: str) -> bool:
    """Catalog ID or live cache key; no path separators."""
    if not value or ".." in value or "/" in value or "\\" in value:
        return False
    return bool(ASSET_KEY_RE.fullmatch(value))


def is_valid_filename(value: str) -> bool:
    """Asset filename; reject separators and traversal sequences."""
    if not value or ".." in value or "/" in value or "\\" in value:
        return False
    return bool(FILENAME_RE.fullmatch(value))
