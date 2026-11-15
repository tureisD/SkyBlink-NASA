"""Golden-cache manifest loader and validator for catalog targets.

The S1/S2 golden cache is authoritative for a catalog target when
``golden_cache/{target_id}/manifest.json`` is present, matches the target's
2025.8 coordinates, and its referenced WebP assets pass the recorded SHA-256
checks.  This module never touches IRSA; callers fall back to the live
pipeline when it returns ``None``.

The golden manifest schema is the B2 pipeline manifest plus golden-cache
metadata (``golden_cache_version``, ``target``, ``assets``, ``pipeline``).
A HALO display decision is resolved from the manifest/gate via
:mod:`services.halo`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.cachekeys import is_valid_filename
from core.config import settings
from core.targets import TargetRecord
from services.halo import HaloDecision, resolve_halo_decision

logger = logging.getLogger(__name__)

COORDINATE_TOLERANCE_DEG = 1e-6

#: ``reference_overlays`` keys that carry human-readable metadata, not an
#: asset.  ``attribution`` prose is preserved verbatim: it is never validated
#: as a filename, never required to resolve, and never rewritten.  Both the
#: legacy ``"/DSS2 Red ..."`` prefixed form and clean ``"DSS2 Red ..."`` prose
#: are accepted so the manifest cleanup needs no second backend change.
REFERENCE_OVERLAY_METADATA_KEYS = frozenset({"attribution"})

_CACHE: dict[str, tuple[int, int, "GoldenManifest | None"]] = {}
_GOLDEN_SPECTRUM_CACHE: dict[str, tuple[int, int, dict[str, Any] | None]] = {}


@dataclass(frozen=True)
class GoldenManifest:
    """A validated golden manifest and its resolved HALO policy."""

    target_id: str
    path: Path
    manifest: dict[str, Any]
    halo: HaloDecision


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check_coordinate(value: Any, expected: float) -> bool:
    try:
        return abs(float(value) - float(expected)) <= COORDINATE_TOLERANCE_DEG
    except (TypeError, ValueError):
        return False


def _asset_filenames(manifest: dict[str, Any]) -> set[str]:
    filenames: set[str] = set()

    for epoch in manifest.get("epochs", []) or []:
        for filename in (epoch.get("frames") or {}).values():
            if isinstance(filename, str):
                filenames.add(filename)

    for pair in (manifest.get("differences") or {}).values():
        if isinstance(pair, dict):
            for filename in (pair.get("frames") or {}).values():
                if isinstance(filename, str):
                    filenames.add(filename)

    for key, filename in (manifest.get("reference_overlays") or {}).items():
        if str(key) in REFERENCE_OVERLAY_METADATA_KEYS:
            continue
        if isinstance(filename, str) and not filename.startswith(
            ("http://", "https://", "/")
        ):
            filenames.add(filename)

    return filenames


def _validate_manifest(
    target: TargetRecord,
    manifest: dict[str, Any],
    directory: Path,
) -> bool:
    version = manifest.get("golden_cache_version")
    if not isinstance(version, int) or version < 1:
        logger.warning("Golden manifest %s has unsupported version %r", directory, version)
        return False
    if manifest.get("target_id") != target.id:
        logger.warning(
            "Golden manifest %s target_id %r does not match %r",
            directory,
            manifest.get("target_id"),
            target.id,
        )
        return False

    manifest_target = manifest.get("target")
    if not isinstance(manifest_target, dict):
        logger.warning("Golden manifest %s has no target block", directory)
        return False
    if not _check_coordinate(manifest_target.get("ra_epoch2025"), target.ra_epoch2025):
        return False
    if not _check_coordinate(manifest_target.get("dec_epoch2025"), target.dec_epoch2025):
        return False

    query = manifest.get("query")
    if not isinstance(query, dict):
        return False
    if not _check_coordinate(query.get("ra"), target.ra_epoch2025):
        return False
    if not _check_coordinate(query.get("dec"), target.dec_epoch2025):
        return False

    provenance = manifest.get("provenance")
    if not isinstance(provenance, dict):
        return False
    if provenance.get("is_simulated_fallback") is not False:
        logger.warning("Refusing golden data without real-data provenance for %s", target.id)
        return False

    epochs = manifest.get("epochs")
    if not isinstance(epochs, list) or not epochs:
        logger.warning("Golden manifest %s has no epochs", directory)
        return False
    epoch_ids: list[str] = []
    for epoch in epochs:
        if not isinstance(epoch, dict):
            return False
        epoch_id = epoch.get("epoch_id")
        if not isinstance(epoch_id, str) or not epoch_id:
            return False
        epoch_ids.append(epoch_id)
        if not isinstance(epoch.get("frames"), dict) or not isinstance(
            epoch.get("flag_summary"), dict
        ):
            logger.warning("Golden epoch %s is incomplete", epoch_id)
            return False

    available = manifest.get("available_epoch_ids")
    if not isinstance(available, list):
        return False
    if set(str(item) for item in available) != set(epoch_ids):
        logger.warning("Golden manifest %s epoch IDs do not match", directory)
        return False

    differences = manifest.get("differences", {})
    if not isinstance(differences, dict):
        return False
    for pair in differences.values():
        if not isinstance(pair, dict) or not isinstance(pair.get("frames"), dict):
            return False

    referenced = _asset_filenames(manifest)
    for filename in referenced:
        if not is_valid_filename(filename):
            logger.warning("Unsafe golden filename %r", filename)
            return False
        path = directory / filename
        if not path.is_file() or path.stat().st_size == 0:
            logger.warning("Golden asset missing: %s", path)
            return False

    assets = manifest.get("assets")
    expected_hashes = (assets or {}).get("sha256") if isinstance(assets, dict) else None
    if isinstance(expected_hashes, dict):
        for filename, expected in expected_hashes.items():
            if not isinstance(filename, str) or not is_valid_filename(filename):
                return False
            path = directory / filename
            if not path.is_file():
                return False
            if _sha256_file(path) != str(expected):
                logger.warning("Golden asset hash mismatch: %s", path)
                return False

    return True


def load_golden_manifest(target: TargetRecord) -> GoldenManifest | None:
    """Return a validated golden manifest for ``target`` or ``None``.

    Validation is cached until the manifest file changes (mtime/size).  Asset
    hashes are checked whenever the manifest is first seen or rewritten.
    """
    path = settings.golden_cache_dir / target.id / "manifest.json"
    if not path.is_file():
        return None
    try:
        stat = path.stat()
    except OSError:
        return None

    cached = _CACHE.get(target.id)
    if (
        cached is not None
        and cached[0] == stat.st_mtime_ns
        and cached[1] == stat.st_size
    ):
        return cached[2]

    result: GoldenManifest | None = None
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(manifest, dict) and _validate_manifest(
            target, manifest, path.parent
        ):
            result = GoldenManifest(
                target_id=target.id,
                path=path,
                manifest=manifest,
                halo=resolve_halo_decision(manifest),
            )
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("Could not read golden manifest %s: %s", path, exc)

    _CACHE[target.id] = (stat.st_mtime_ns, stat.st_size, result)
    return result


def _valid_spectrum_channel(channel: Any) -> bool:
    if not isinstance(channel, dict):
        return False
    try:
        detector = int(channel["detector"])
        wavelength = float(channel["wavelength_um"])
        bandwidth = float(channel["bandwidth_um"])
        flags = int(channel["flags"])
        clean_fraction = float(channel["clean_fraction"])
    except (KeyError, TypeError, ValueError):
        return False
    if not 1 <= detector <= 6:
        return False
    if not (
        math.isfinite(wavelength)
        and wavelength > 0
        and math.isfinite(bandwidth)
        and bandwidth > 0
    ):
        return False
    if flags < 0:
        return False
    if not (0.0 <= clean_fraction <= 1.0):
        return False
    if not isinstance(channel.get("is_flagged_bad"), bool):
        return False
    if not isinstance(channel.get("is_used_in_photometry"), bool):
        return False
    for key in ("flux_ujy", "flux_err_ujy"):
        value = channel.get(key)
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            return False
        if not math.isfinite(number):
            return False
    return True


def _validate_golden_spectrum(
    target: TargetRecord,
    payload: dict[str, Any],
) -> bool:
    version = payload.get("version")
    if not isinstance(version, int) or version < 1:
        return False
    asset_key = payload.get("asset_key")
    if asset_key is not None and str(asset_key) != target.id:
        return False
    query = payload.get("query")
    if not isinstance(query, dict):
        return False
    if not _check_coordinate(query.get("ra"), target.ra_epoch2025):
        return False
    if not _check_coordinate(query.get("dec"), target.dec_epoch2025):
        return False

    confidence = payload.get("confidence")
    if confidence not in {"high", "low"}:
        return False

    epochs = payload.get("epochs")
    if not isinstance(epochs, list) or not epochs:
        return False
    epoch_ids: list[str] = []
    for epoch in epochs:
        if not isinstance(epoch, dict):
            return False
        epoch_id = epoch.get("epoch_id")
        if not isinstance(epoch_id, str) or not epoch_id:
            return False
        epoch_ids.append(epoch_id)
        if not isinstance(epoch.get("label"), str):
            return False
        if not isinstance(epoch.get("collection"), str):
            return False
        if not isinstance(epoch.get("release"), str):
            return False
        channels = epoch.get("channels")
        if not isinstance(channels, list) or not channels:
            return False
        if not all(_valid_spectrum_channel(channel) for channel in channels):
            return False

    available = payload.get("available_epoch_ids")
    if not isinstance(available, list):
        return False
    if set(str(item) for item in available) != set(epoch_ids):
        return False

    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        return False
    for key in (
        "source",
        "collection",
        "release",
        "citation",
    ):
        if not isinstance(provenance.get(key), str):
            return False
    for key in ("zodi_subtracted", "background_subtracted", "is_simulated_fallback"):
        if not isinstance(provenance.get(key), bool):
            return False
    if provenance["is_simulated_fallback"] is not False:
        return False
    return True


def load_golden_spectrum(target: TargetRecord) -> dict[str, Any] | None:
    """Return a validated golden ``spectrum.json`` for ``target`` or ``None``.

    The spectrum cache is static (no TTL); validation is cached until the file
    changes.  Corrupt or coordinate-mismatched files return ``None`` so the
    caller can fall back to the live IRSA path.
    """
    path = settings.golden_cache_dir / target.id / "spectrum.json"
    if not path.is_file():
        return None
    try:
        stat = path.stat()
    except OSError:
        return None

    cached = _GOLDEN_SPECTRUM_CACHE.get(target.id)
    if (
        cached is not None
        and cached[0] == stat.st_mtime_ns
        and cached[1] == stat.st_size
    ):
        return cached[2]

    result: dict[str, Any] | None = None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and _validate_golden_spectrum(target, payload):
            result = payload
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("Could not read golden spectrum %s: %s", path, exc)

    _GOLDEN_SPECTRUM_CACHE[target.id] = (stat.st_mtime_ns, stat.st_size, result)
    return result
