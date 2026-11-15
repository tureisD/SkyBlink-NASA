#!/usr/bin/env python3
"""Build the SPHEREx SkyBlink golden cache from real IRSA data.

The script is a read-only wrapper around the merged B2/B3 pipeline in
``backend/services/`` (imported as ``services.*`` with ``backend/`` on
``sys.path``).  For each target it:

1. queries IRSA at the target's **2025.8** coordinates (LAW 5),
2. builds the six-band, multi-epoch, inverse-variance coadds, the shared
   cross-epoch normalization, and the adjacent-epoch differences,
3. measures the O1 §9 HALO gate per band on the reprojected grid,
4. if the gate triggers, records ``halo_display_mode: true`` and re-renders the
   displayed frames with ``DISPLAY_BAD_MASK = HARD_BAD_MASK & ~(1 << 28)``
   (HALO stays in ``PHOTOMETRY_EXCLUDE_MASK`` and ``is_flagged_bad``),
5. copies the B3 ``spectrum.json`` server cache for the target (or builds it
   with the B3 service when missing),
6. attaches the real SkyView DSS2 Red / WISE and IRSA Gaia DR3 reference
   overlays (S4; display-only, ``is_simulated_fallback: false``), reusing
   SHA-256-verified assets instead of re-downloading them,
7. copies every referenced WebP frame into ``golden_cache/<target_id>/`` and
   writes ``manifest.json`` with the per-epoch collection/release,
   ``flag_summary``, normalization block, HALO decision, reference-overlay
   provenance, full provenance, and SHA-256 integrity maps.

The golden cache is **real data**: ``provenance.is_simulated_fallback`` is
checked to be ``false`` before anything is written. Synthetic product fixtures
and their generator were removed in audit Phase 1. New real products require
review and an updated approved inventory before packaging.

Usage
-----
    python scripts/build_golden_cache.py --target wise_0855
    python scripts/build_golden_cache.py --target all
    python scripts/build_golden_cache.py --target all --force-refresh
    python scripts/build_golden_cache.py --target wise_0855 --verify-only

Run with the shared Python 3.11 venv::

    ../.venv311/Scripts/python.exe scripts/build_golden_cache.py --target all

The script never reads the empty PrimaryHDU and never masks ``BIT_SOURCE``: all
FITS parsing is delegated to the B2 pipeline, which accesses extensions by
``EXTNAME`` and uses the Table 16 masks from ``backend/core/flags.py``.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
DEFAULT_GOLDEN_DIR = REPO_ROOT / "golden_cache"
TARGET_IDS = (
    "wise_0855",
    "barnards_star",
    "eps_indi_b",
    "rw_aurigae",
    "r_draconis",
)
SAFE_FILENAME = re.compile(r"^[A-Za-z0-9_.-]+$")
WEBP_GRID = (240, 240)
#: Revision 2 = S4 Stage 2: B8 telemetry sidecars, LVF geometry, dense spectra,
#: real SkyView/Gaia reference overlays.  Revision 1 was the O1-era cache.
GOLDEN_CACHE_VERSION = 2
HALO_FRACTION_THRESHOLD = 0.05
HALO_DECISION_RULE = (
    "O1 contract decision §9: use the display-only HALO mask when "
    "halo_fraction > 0.05 in any band or halo_aperture_fraction > 0 for the "
    "target. HALO remains hard for photometry and is_flagged_bad."
)

logger = logging.getLogger("skyblink.golden_cache")


# ---------------------------------------------------------------------------
# Backend imports (path set first so the canonical ``core.*``/``services.*``
# imports resolve exactly as in the running application).
# ---------------------------------------------------------------------------
def _backend_modules() -> dict[str, Any]:
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))
    from core import flags as flag_policy  # noqa: PLC0415 - deliberate late import
    from core.config import settings  # noqa: PLC0415
    from core.targets import TARGET_BY_ID, propagated_coordinates  # noqa: PLC0415
    from services import irsa_client, spherex_pipeline, spectrophotometry  # noqa: PLC0415

    return {
        "settings": settings,
        "flag_policy": flag_policy,
        "target_by_id": TARGET_BY_ID,
        "propagated_coordinates": propagated_coordinates,
        "irsa": irsa_client,
        "pipeline": spherex_pipeline,
        "spectrophotometry": spectrophotometry,
    }


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_text_bytes(content: bytes) -> str:
    """SHA-256 of text content with CRLF/CR normalized to LF.

    Reference JSON assets are committed as text.  With ``core.autocrlf=true``
    a clean checkout can materialize them with CRLF while the recorded hash
    was computed on the LF canonical form; normalizing before hashing keeps
    verification line-ending-stable.  Never use this for binary WebP/PNG/
    gzip assets.
    """
    normalized = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return _sha256_bytes(normalized)


def _reference_asset_digest(name: str, content: bytes) -> str:
    """Recorded digest for a reference asset (text-normalized JSON only)."""
    if name.lower().endswith(".json"):
        return _sha256_text_bytes(content)
    return _sha256_bytes(content)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False)
    _atomic_write_bytes(path, (text + "\n").encode("utf-8"))


# ---------------------------------------------------------------------------
# Frame discovery / copying
# ---------------------------------------------------------------------------
def _frame_filenames(manifest: dict[str, Any]) -> list[str]:
    """Every SPHEREx frame filename referenced by epochs and differences.

    Reference overlays are handled separately by
    :func:`reference_overlays.local_reference_filenames`: the golden manifest
    stores contract asset URLs (``/api/v1/assets/...``) for them, not bare
    filenames.
    """
    names: list[str] = []

    def _add(value: Any) -> None:
        name = str(value)
        if not SAFE_FILENAME.fullmatch(name):
            raise ValueError(f"Unsafe frame filename in pipeline manifest: {name!r}")
        if name not in names:
            names.append(name)

    for epoch in manifest.get("epochs", []):
        for filename in epoch.get("frames", {}).values():
            _add(filename)
    for pair in manifest.get("differences", {}).values():
        for filename in pair.get("frames", {}).values():
            _add(filename)
    return names


def _telemetry_filenames(manifest: dict[str, Any]) -> list[str]:
    """Telemetry sidecars referenced by ``epochs[].telemetry``.

    B8 writes ``telemetry_{epoch_id}.bin.gz`` next to the live frames and
    records the bare filename in the epoch payload.  A full URL is left alone
    (the API will not rewrite it); here we only need local filenames to copy
    and verify.
    """
    names: list[str] = []
    for epoch in manifest.get("epochs", []):
        block = epoch.get("telemetry")
        if not isinstance(block, dict):
            continue
        name = block.get("url")
        if not isinstance(name, str) or not name:
            continue
        if name.startswith(("http://", "https://", "/")):
            continue
        if not SAFE_FILENAME.fullmatch(name):
            raise ValueError(f"Unsafe telemetry filename: {name!r}")
        if name not in names:
            names.append(name)
    return names


def _overlay_module() -> Any:
    """Import the shared reference-overlay helper lazily."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from scripts import reference_overlays  # noqa: PLC0415 - lazy for test speed

    return reference_overlays


def _reference_filenames(manifest: dict[str, Any], target_id: str) -> list[str]:
    """Local golden-cache files referenced by ``reference_overlays``."""
    return _overlay_module().local_reference_filenames(manifest, target_id)


def _existing_manifest(target_dir: Path) -> dict[str, Any]:
    path = target_dir / "manifest.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _collect_assets(target_dir: Path, filenames: Iterable[str]) -> tuple[dict[str, str], int]:
    """Hash the current files on disk (after any display-mode re-render)."""
    hashes: dict[str, str] = {}
    total_bytes = 0
    for name in filenames:
        path = target_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"Golden-cache frame is missing: {path}")
        content = path.read_bytes()
        hashes[name] = _sha256_bytes(content)
        total_bytes += len(content)
    return hashes, total_bytes


def _collect_reference_assets(
    target_dir: Path, filenames: Iterable[str]
) -> tuple[dict[str, str], int]:
    """Hash reference assets; JSON text is normalized to LF before hashing."""
    hashes: dict[str, str] = {}
    total_bytes = 0
    for name in filenames:
        path = target_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"Golden-cache reference asset is missing: {path}")
        content = path.read_bytes()
        hashes[name] = _reference_asset_digest(name, content)
        total_bytes += len(content)
    return hashes, total_bytes


def _copy_frames(
    live_dir: Path,
    golden_dir: Path,
    filenames: Iterable[str],
    *,
    prune: bool,
    extra_referenced: Iterable[str] = (),
) -> tuple[dict[str, str], int]:
    """Copy referenced frames; return ``({filename: sha256}, total_bytes)``."""
    golden_dir.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    total_bytes = 0
    for name in filenames:
        source = live_dir / name
        if not source.is_file():
            raise FileNotFoundError(
                f"Pipeline frame is missing from the live cache: {source}"
            )
        content = source.read_bytes()
        digest = _sha256_bytes(content)
        destination = golden_dir / name
        existing = destination.read_bytes() if destination.is_file() else None
        if existing != content:
            _atomic_write_bytes(destination, content)
            logger.info("Copied %s (%d bytes)", name, len(content))
        hashes[name] = digest
        total_bytes += len(content)

    if prune:
        referenced = set(hashes) | set(extra_referenced)
        for stale in sorted(golden_dir.glob("*.webp")):
            if stale.name not in referenced:
                logger.warning("Pruning stale golden-cache frame %s", stale.name)
                stale.unlink()

    return hashes, total_bytes


# ---------------------------------------------------------------------------
# Pipeline manifest inputs (reconstructed from the pipeline manifest itself so
# the display-mode rebuild uses exactly the same visits as the photometric
# build; no second target selection and no second TAP query).
# ---------------------------------------------------------------------------
def _record_release_and_collection(epoch: dict[str, Any]) -> tuple[str, str]:
    release = str(epoch.get("release", "unknown"))
    if release not in {"DR1", "QR2", "QR3"}:
        return "unknown", "spherex"
    return release, f"spherex_{release.lower()}"


def _load_manifest_inputs(
    manifest: dict[str, Any],
    query_ra: float,
    query_dec: float,
    modules: dict[str, Any],
) -> tuple[dict[tuple[str, int], list[Any]], dict[Any, bytes]]:
    """Rebuild the selected visits per epoch/band and fetch their cutouts."""
    irsa = modules["irsa"]
    client = irsa.IrsaClient()
    cutout_size = float(manifest["query"]["cutout_size_deg"])
    records_by_key: dict[tuple[str, int], list[Any]] = {}
    all_records: list[Any] = []
    for epoch in manifest.get("epochs", []):
        epoch_id = str(epoch["epoch_id"])
        release, collection = _record_release_and_collection(epoch)
        for band_key, stats in (epoch.get("band_stats") or {}).items():
            band = int(band_key)
            records = []
            for uri in stats.get("artifact_uris") or []:
                record = irsa.ArtifactRecord(
                    uri=str(uri),
                    mjd_lower=float(epoch["mjd_mean"]),
                    mjd_upper=None,
                    band=band,
                    band_name=f"SPHEREx-D{band}",
                    planeid="",
                    release=release,
                    collection=collection,
                    contentlength=None,
                )
                records.append(record)
                all_records.append(record)
            if records:
                records_by_key[(epoch_id, band)] = records

    contents = (
        client.fetch_cutouts(all_records, query_ra, query_dec, cutout_size)
        if all_records
        else {}
    )
    if not contents:
        raise RuntimeError("No cutouts could be loaded for the HALO measurement")
    logger.info(
        "Loaded %d cutouts for %d epoch/band groups",
        len(contents),
        len(records_by_key),
    )
    return records_by_key, contents


# ---------------------------------------------------------------------------
# O1 §9 HALO measurement and decision
# ---------------------------------------------------------------------------
def _measure_halo(
    manifest: dict[str, Any],
    records_by_key: dict[tuple[str, int], list[Any]],
    contents: dict[Any, bytes],
    out_wcs: Any,
    query_ra: float,
    query_dec: float,
    modules: dict[str, Any],
) -> tuple[dict[str, Any], dict[tuple[str, int], Any], dict[tuple[str, int], Any]]:
    """Measure HALO per epoch/band on the reprojected grid.

    Returns ``(measurements, halo_masks, coverage_masks)``.  The numerator is
    the union of native HALO pixels reprojected with nearest-neighbor; the
    denominator is the reprojected coverage (not the hard-masked finite image,
    which would erase HALO pixels and hide the artifact).
    """
    import numpy as np
    from reproject import reproject_interp

    pipeline = modules["pipeline"]
    flag_policy = modules["flag_policy"]
    shape = (pipeline.GRID_HEIGHT, pipeline.GRID_WIDTH)
    yy, xx = np.indices(shape)
    aperture = (
        np.hypot(xx - pipeline.CENTER_PIXEL, yy - pipeline.CENTER_PIXEL)
        <= pipeline.APERTURE_RADIUS_ARCSEC / pipeline.PIXEL_SCALE_ARCSEC
    )
    aperture_count = int(np.count_nonzero(aperture))

    measurements: dict[str, Any] = {}
    halo_masks: dict[tuple[str, int], Any] = {}
    coverage_masks: dict[tuple[str, int], Any] = {}

    for epoch in manifest.get("epochs", []):
        epoch_id = str(epoch["epoch_id"])
        for band_key, stats in (epoch.get("band_stats") or {}).items():
            band = int(band_key)
            halo_union = np.zeros(shape, dtype=bool)
            coverage_union = np.zeros(shape, dtype=bool)
            native_halo = 0
            native_total = 0
            used_visits = 0
            for record in records_by_key.get((epoch_id, band), []):
                content = contents.get(record)
                if content is None:
                    continue
                parsed = pipeline.parse_cutout(content, query_ra, query_dec)
                halo_pixels = (parsed.flags & flag_policy.HALO_BIT) != 0
                # HALO pixels are NaN in the hard-masked image, so include them
                # explicitly or the fraction would always be zero.
                valid_native = np.isfinite(parsed.image_mjy_sr) | halo_pixels
                halo_native = halo_pixels.astype(np.uint8)
                coverage_native = valid_native.astype(np.uint8)
                halo_out, _ = reproject_interp(
                    (halo_native, parsed.spatial_wcs),
                    out_wcs,
                    shape_out=shape,
                    order="nearest-neighbor",
                )
                coverage_out, _ = reproject_interp(
                    (coverage_native, parsed.spatial_wcs),
                    out_wcs,
                    shape_out=shape,
                    order="nearest-neighbor",
                )
                halo_union |= np.asarray(halo_out, dtype=float) > 0.5
                coverage_union |= np.asarray(coverage_out, dtype=float) > 0.5
                native_halo += int(parsed.halo_pixel_count)
                native_total += int(np.count_nonzero(valid_native))
                used_visits += 1

            coverage_count = int(np.count_nonzero(coverage_union))
            halo_count = int(np.count_nonzero(halo_union & coverage_union))
            halo_aperture_count = int(np.count_nonzero(halo_union & aperture))
            reprojected_fraction = (
                halo_count / coverage_count if coverage_count else 0.0
            )
            native_fraction_coverage = (
                native_halo / native_total if native_total else 0.0
            )
            native_fraction_pipeline = float(stats.get("halo_fraction", 0.0) or 0.0)
            native_aperture_fraction = float(
                stats.get("halo_aperture_fraction", 0.0) or 0.0
            )
            reprojected_aperture_fraction = (
                halo_aperture_count / aperture_count if aperture_count else 0.0
            )
            triggered = bool(
                max(native_fraction_coverage, reprojected_fraction)
                > HALO_FRACTION_THRESHOLD
                or native_aperture_fraction > 0.0
                or reprojected_aperture_fraction > 0.0
            )
            key = f"{epoch_id}_D{band}"
            measurements[key] = {
                "epoch_id": epoch_id,
                "band": band,
                "used_visits": used_visits,
                "halo_pixels_native": native_halo,
                "native_pixels": native_total,
                "halo_fraction_native_coverage": native_fraction_coverage,
                "halo_fraction_native_pipeline": native_fraction_pipeline,
                "halo_pixels_reprojected": halo_count,
                "coverage_pixels_reprojected": coverage_count,
                "halo_fraction_reprojected": reprojected_fraction,
                "halo_aperture_pixels_native": int(
                    stats.get("halo_aperture_pixel_count", 0) or 0
                ),
                "aperture_pixels": aperture_count,
                "halo_aperture_fraction_native": native_aperture_fraction,
                "halo_aperture_pixels_reprojected": halo_aperture_count,
                "halo_aperture_fraction_reprojected": reprojected_aperture_fraction,
                "triggered": triggered,
            }
            halo_masks[(epoch_id, band)] = halo_union
            coverage_masks[(epoch_id, band)] = coverage_union

    return measurements, halo_masks, coverage_masks


def _halo_decision(
    measurements: dict[str, Any],
    flag_policy: Any,
    pipeline: Any,
) -> dict[str, Any]:
    """Record the O1 §9 gate and the masks used for display vs photometry."""
    triggering = [
        item for item in measurements.values() if bool(item.get("triggered"))
    ]
    triggering.sort(
        key=lambda item: (
            item["epoch_id"],
            item["band"],
        )
    )
    worst = None
    if measurements:
        worst = max(
            measurements.values(),
            key=lambda item: max(
                float(item["halo_fraction_native_coverage"]),
                float(item["halo_fraction_reprojected"]),
                float(item["halo_aperture_fraction_native"]),
                float(item["halo_aperture_fraction_reprojected"]),
            ),
        )
    original_hard = int(flag_policy.HARD_BAD_MASK)
    display_bad = original_hard & ~int(flag_policy.HALO_BIT)
    return {
        "evaluated": True,
        "rule": HALO_DECISION_RULE,
        "thresholds": {
            "halo_fraction": HALO_FRACTION_THRESHOLD,
            "halo_aperture_fraction": 0.0,
        },
        "triggered": bool(triggering),
        "halo_display_mode": bool(triggering),
        "triggering_measurements": triggering,
        "triggering_epoch_bands": [
            f"{item['epoch_id']}_D{item['band']}" for item in triggering
        ],
        "worst_measurement": worst,
        "bands_with_halo": sorted(
            {
                int(item["band"])
                for item in measurements.values()
                if int(item["halo_pixels_native"]) > 0
                or int(item["halo_pixels_reprojected"]) > 0
            }
        ),
        "hard_bad_mask": original_hard,
        "halo_bit": int(flag_policy.HALO_BIT),
        "display_bad_mask": display_bad if triggering else original_hard,
        "display_bad_mask_rule": (
            "HARD_BAD_MASK & ~(1 << 28)" if triggering else "HARD_BAD_MASK"
        ),
        "photometry_exclude_mask": int(flag_policy.PHOTOMETRY_EXCLUDE_MASK),
        "photometry_includes_halo": bool(
            int(flag_policy.PHOTOMETRY_EXCLUDE_MASK) & int(flag_policy.HALO_BIT)
        ),
        "is_flagged_bad_includes_halo": bool(
            original_hard & int(flag_policy.HALO_BIT)
        ),
        "grid_width": int(pipeline.GRID_WIDTH),
        "grid_height": int(pipeline.GRID_HEIGHT),
        "frames_rebuilt": False,
        "per_epoch_band": measurements,
    }


def _apply_halo_flag_summary(
    manifest: dict[str, Any],
    decision: dict[str, Any],
    halo_masks: dict[tuple[str, int], Any],
) -> None:
    """Surface HALO in the epochs where the overlay actually contains it."""
    if not decision["triggered"]:
        return
    epochs_with_halo: list[str] = []
    for epoch in manifest.get("epochs", []):
        epoch_id = str(epoch["epoch_id"])
        epoch_halo = False
        for band in epoch.get("bands") or []:
            mask = halo_masks.get((epoch_id, int(band)))
            if mask is not None and bool(mask.any()):
                epoch_halo = True
                break
        if not epoch_halo:
            continue
        epochs_with_halo.append(epoch_id)
        summary = epoch["flag_summary"]
        names = sorted(set(summary.get("active_warning_flags", [])) | {"HALO"})
        summary["active_warning_flags"] = names
        if str(summary.get("status")) == "NOMINAL":
            summary["status"] = "CAUTION"
        summary["human_explanation"] = (
            str(summary.get("human_explanation", "")).rstrip()
            + " HALO display-only mode is active: HALO pixels are visible in "
            "the displayed frames and flag overlay, but remain hard-bad for "
            "photometry and is_flagged_bad."
        )
    decision["epochs_with_halo"] = epochs_with_halo


# ---------------------------------------------------------------------------
# Display-mode re-render (HALO restored in displayed frames only)
# ---------------------------------------------------------------------------
def _display_limits_from_epoch(
    epoch: dict[str, Any], band: int, image: Any, pipeline: Any
) -> tuple[float, float] | None:
    raw = (epoch.get("display_limits") or {}).get(str(band))
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        try:
            return (float(raw[0]), float(raw[1]))
        except (TypeError, ValueError):
            pass
    return pipeline._display_limits(image)


def _rebuild_display_frames(
    target_dir: Path,
    manifest: dict[str, Any],
    records_by_key: dict[tuple[str, int], list[Any]],
    contents: dict[Any, bytes],
    out_wcs: Any,
    query_ra: float,
    query_dec: float,
    halo_masks: dict[tuple[str, int], Any],
    decision: dict[str, Any],
    modules: dict[str, Any],
    target_id: str,
) -> None:
    """Re-render displayed frames with HALO restored (photometry untouched)."""
    import numpy as np

    pipeline = modules["pipeline"]
    flag_policy = modules["flag_policy"]
    original_hard = int(flag_policy.HARD_BAD_MASK)
    display_bad = original_hard & ~int(flag_policy.HALO_BIT)
    scales = (manifest.get("normalization") or {}).get("scale_by_epoch_band") or {}
    epochs = manifest.get("epochs", [])
    epoch_ids = [str(epoch["epoch_id"]) for epoch in epochs]

    display_coadds: dict[tuple[str, int], Any] = {}
    rendered: list[str] = []
    failures: list[str] = []
    try:
        # ``parse_cutout`` reads the module-level mask at call time.  The
        # background mask (which includes HALO) and PHOTOMETRY_EXCLUDE_MASK are
        # separate constants and stay unchanged.
        flag_policy.HARD_BAD_MASK = display_bad
        for (epoch_id, band), records in sorted(records_by_key.items()):
            available = {
                record: contents[record] for record in records if record in contents
            }
            if not available:
                continue
            coadd = pipeline._coadd_band(
                epoch_id,
                band,
                records,
                available,
                out_wcs,
                query_ra,
                query_dec,
            )
            if coadd is not None:
                display_coadds[(epoch_id, band)] = coadd
    finally:
        flag_policy.HARD_BAD_MASK = original_hard

    if not display_coadds:
        decision["render_failures"] = ["no display coadds could be built"]
        return

    def _scaled(epoch_id: str, band: int) -> Any:
        coadd = display_coadds[(epoch_id, band)]
        scale = float(
            (scales.get(epoch_id) or {}).get(str(band), 1.0)
        )
        return coadd.image_mjy_sr * scale

    # Mirror the shared cross-epoch normalization onto the display coadds so
    # the telemetry sidecar matches the rendered WebP exactly (LAW 8).
    for (epoch_id, band), coadd in display_coadds.items():
        scale = float((scales.get(epoch_id) or {}).get(str(band), 1.0))
        coadd.scale = scale
        coadd.normalized_image_mjy_sr = coadd.image_mjy_sr * scale
        if coadd.variance_mjy_sr2 is not None:
            coadd.normalized_variance_mjy_sr2 = coadd.variance_mjy_sr2 * (
                scale**2
            )

    # Per-band frames.
    for epoch in epochs:
        epoch_id = str(epoch["epoch_id"])
        for band in epoch.get("bands") or []:
            band = int(band)
            filename = (epoch.get("frames") or {}).get(str(band))
            if filename is None or (epoch_id, band) not in display_coadds:
                continue
            image = _scaled(epoch_id, band)
            limits = _display_limits_from_epoch(epoch, band, image, pipeline)
            try:
                pipeline.render_webp(image, target_dir / filename, limits=limits)
                rendered.append(filename)
            except Exception as exc:  # noqa: BLE001 - keep the photometric frame
                failures.append(f"{filename}: {exc}")
                logger.warning("Display re-render failed for %s: %s", filename, exc)

    # Combined all/thermal frames: derive one stretch from the reference epoch.
    reference_epoch = (manifest.get("normalization") or {}).get("reference_epoch")
    if not isinstance(reference_epoch, str) or reference_epoch not in epoch_ids:
        reference_epoch = epoch_ids[0] if epoch_ids else None

    def _combined(epoch_id: str, bands: list[int]) -> Any:
        images = [
            _scaled(epoch_id, band)
            for band in bands
            if (epoch_id, band) in display_coadds
        ]
        return pipeline._combine_arrays(images) if images else None

    def _combined_limits(bands: list[int]) -> tuple[float, float] | None:
        if reference_epoch is None:
            return None
        combined = _combined(reference_epoch, bands)
        return pipeline._display_limits(combined) if combined is not None else None

    all_limits_by_epoch: dict[str, tuple[float, float] | None] = {}
    thermal_limits_by_epoch: dict[str, tuple[float, float] | None] = {}
    for epoch in epochs:
        epoch_id = str(epoch["epoch_id"])
        available_bands = [
            int(band)
            for band in epoch.get("bands") or []
            if (epoch_id, int(band)) in display_coadds
        ]
        if not available_bands:
            continue
        all_image = _combined(epoch_id, available_bands)
        if all_image is not None:
            all_limits_by_epoch[epoch_id] = _combined_limits(available_bands)
        thermal_bands = [
            band for band in (5, 6) if band in available_bands
        ]
        if thermal_bands:
            thermal_image = _combined(epoch_id, thermal_bands)
            if thermal_image is not None:
                thermal_limits_by_epoch[epoch_id] = _combined_limits(thermal_bands)

    for epoch in epochs:
        epoch_id = str(epoch["epoch_id"])
        frames = epoch.get("frames") or {}
        available_bands = [
            int(band)
            for band in epoch.get("bands") or []
            if (epoch_id, int(band)) in display_coadds
        ]
        if not available_bands:
            continue
        if "all" in frames:
            all_image = _combined(epoch_id, available_bands)
            if all_image is not None:
                try:
                    pipeline.render_webp(
                        all_image,
                        target_dir / frames["all"],
                        limits=all_limits_by_epoch.get(epoch_id),
                    )
                    rendered.append(frames["all"])
                except Exception as exc:  # noqa: BLE001
                    failures.append(f"{frames['all']}: {exc}")
                    logger.warning("Display re-render failed for %s: %s", frames["all"], exc)
        thermal_bands = [band for band in (5, 6) if band in available_bands]
        if "thermal" in frames and thermal_bands:
            thermal_image = _combined(epoch_id, thermal_bands)
            if thermal_image is not None:
                try:
                    pipeline.render_webp(
                        thermal_image,
                        target_dir / frames["thermal"],
                        limits=thermal_limits_by_epoch.get(epoch_id),
                    )
                    rendered.append(frames["thermal"])
                except Exception as exc:  # noqa: BLE001
                    failures.append(f"{frames['thermal']}: {exc}")
                    logger.warning(
                        "Display re-render failed for %s: %s", frames["thermal"], exc
                    )

        # HALO must be visible in the flag overlay (O1 §9).
        if "flag_overlay" in frames:
            overlay = np.zeros(
                (pipeline.GRID_HEIGHT, pipeline.GRID_WIDTH), dtype=bool
            )
            for band in available_bands:
                coadd = display_coadds[(epoch_id, band)]
                overlay |= coadd.warning_mask
                halo = halo_masks.get((epoch_id, band))
                if halo is not None:
                    overlay |= halo
            pipeline.render_mask_webp(overlay, target_dir / frames["flag_overlay"])
            rendered.append(frames["flag_overlay"])

        # B8 telemetry: rebuild the sidecar from the *display* coadds so the
        # float16 MJy/sr plane and Table 16 flag plane match the displayed
        # frame (HALO visible, BIT_SOURCE preserved).  The photometric build's
        # sidecar is hard-masked and must not be served here.
        writer = getattr(pipeline, "write_epoch_telemetry", None)
        if writer is not None:
            epoch_coadds = {
                band: display_coadds[(epoch_id, band)]
                for band in available_bands
            }
            try:
                telemetry_payload = writer(
                    target_dir,
                    epoch_id,
                    epoch_coadds,
                    available_bands,
                    target_id,
                )
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{epoch_id} telemetry: {exc}")
                logger.warning(
                    "Display telemetry failed for %s/%s: %s",
                    target_id,
                    epoch_id,
                    exc,
                )
                telemetry_payload = None
            epoch["telemetry"] = telemetry_payload
            if telemetry_payload:
                rendered.append(str(telemetry_payload["url"]))
                decision.setdefault("telemetry_rebuilt", []).append(epoch_id)

    # Difference frames use un-normalized display coadds (HALO visible).
    pair_diffs: dict[tuple[str, int], Any] = {}
    for pair_key, pair in (manifest.get("differences") or {}).items():
        try:
            later_id, earlier_id = str(pair_key).split("_minus_", 1)
        except ValueError:
            continue
        common_bands = [
            int(band)
            for band in pair.get("common_bands") or []
            if (later_id, int(band)) in display_coadds
            and (earlier_id, int(band)) in display_coadds
        ]
        for band in common_bands:
            pair_diffs[(pair_key, band)] = (
                display_coadds[(later_id, band)].image_mjy_sr
                - display_coadds[(earlier_id, band)].image_mjy_sr
            )

    band_limits = {
        band: pipeline._symmetric_limit(
            [
                diff
                for (pair_key, diff_band), diff in pair_diffs.items()
                if diff_band == band
            ]
        )
        for band in range(1, 7)
    }
    combined_all = [
        pipeline._combine_arrays(
            [
                pair_diffs[(pair_key, band)]
                for band in range(1, 7)
                if (pair_key, band) in pair_diffs
            ]
        )
        for pair_key in {key for key, _ in pair_diffs}
    ]
    all_limits = pipeline._symmetric_limit(
        [array for array in combined_all if array is not None]
    )
    combined_thermal = [
        pipeline._combine_arrays(
            [
                pair_diffs[(pair_key, band)]
                for band in (5, 6)
                if (pair_key, band) in pair_diffs
            ]
        )
        for pair_key in {key for key, _ in pair_diffs}
    ]
    thermal_limits = pipeline._symmetric_limit(
        [array for array in combined_thermal if array is not None]
    )

    for pair_key, pair in (manifest.get("differences") or {}).items():
        frames = pair.get("frames") or {}
        try:
            later_id, earlier_id = str(pair_key).split("_minus_", 1)
        except ValueError:
            continue
        common_bands = [
            int(band)
            for band in pair.get("common_bands") or []
            if (later_id, int(band)) in display_coadds
            and (earlier_id, int(band)) in display_coadds
        ]
        for band in common_bands:
            filename = frames.get(str(band))
            if filename is None:
                continue
            try:
                pipeline.render_difference_webp(
                    pair_diffs[(pair_key, band)],
                    target_dir / filename,
                    vmax=band_limits.get(band),
                )
                rendered.append(filename)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{filename}: {exc}")
                logger.warning("Display difference failed for %s: %s", filename, exc)
        if "all" in frames:
            all_diff = pipeline._combine_arrays(
                [
                    pair_diffs[(pair_key, band)]
                    for band in common_bands
                    if (pair_key, band) in pair_diffs
                ]
            )
            if all_diff is not None:
                try:
                    pipeline.render_difference_webp(
                        all_diff, target_dir / frames["all"], vmax=all_limits
                    )
                    rendered.append(frames["all"])
                except Exception as exc:  # noqa: BLE001
                    failures.append(f"{frames['all']}: {exc}")
        if "thermal" in frames and all(band in common_bands for band in (5, 6)):
            thermal_diff = pipeline._combine_arrays(
                [pair_diffs[(pair_key, band)] for band in (5, 6)]
            )
            if thermal_diff is not None:
                try:
                    pipeline.render_difference_webp(
                        thermal_diff,
                        target_dir / frames["thermal"],
                        vmax=thermal_limits,
                    )
                    rendered.append(frames["thermal"])
                except Exception as exc:  # noqa: BLE001
                    failures.append(f"{frames['thermal']}: {exc}")

    decision["frames_rebuilt"] = True
    decision["rendered_frames"] = len(set(rendered))
    decision["render_failures"] = failures
    logger.info(
        "Display-mode rebuild: %d frames re-rendered, %d failures",
        len(set(rendered)),
        len(failures),
    )


# ---------------------------------------------------------------------------
# Spectrum cache (B3)
# ---------------------------------------------------------------------------
def _attach_spectrum(
    target: Any,
    golden_dir: Path,
    modules: dict[str, Any],
    *,
    query_ra: float,
    query_dec: float,
    rebuild: bool,
    build_if_missing: bool,
) -> dict[str, Any]:
    """Copy (or build) the B3 spectrum cache and validate its provenance."""
    settings = modules["settings"]
    spectrophotometry = modules["spectrophotometry"]
    live_path = settings.live_cache_dir / target.id / "spectrum.json"
    target_dir = golden_dir / target.id
    destination = target_dir / "spectrum.json"

    rebuild_error: str | None = None
    if rebuild or (build_if_missing and not live_path.is_file()):
        try:
            spectrophotometry.build_spectrum(
                target.id,
                query_ra,
                query_dec,
                confidence="high",
                max_visits_per_band=settings.spectrum_max_visits_per_band,
                target_record=target,
                force_refresh=rebuild,
            )
        except Exception as exc:  # noqa: BLE001 - sky cache must still build
            rebuild_error = f"{type(exc).__name__}: {exc}"
            logger.warning("Spectrum build failed for %s: %s", target.id, exc)

    if not live_path.is_file():
        if destination.exists():
            destination.unlink()
        return {
            "available": False,
            "reason": rebuild_error or "B3 spectrum cache not found",
            "expected_path": str(live_path),
        }

    content = live_path.read_bytes()
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"available": False, "reason": f"invalid spectrum JSON: {exc}"}

    problems: list[str] = []
    if int(payload.get("version", -1)) != 2:
        problems.append(f"unsupported version {payload.get('version')!r}")
    query = payload.get("query") or {}
    if abs(float(query.get("ra", -999.0)) - query_ra) > 1e-6:
        problems.append("spectrum query RA mismatch")
    if abs(float(query.get("dec", -999.0)) - query_dec) > 1e-6:
        problems.append("spectrum query Dec mismatch")
    if str(payload.get("confidence")) != "high":
        problems.append("catalog spectrum confidence must be 'high'")
    provenance = payload.get("provenance") or {}
    if provenance.get("is_simulated_fallback") is not False:
        problems.append("spectrum provenance is not real data")
    epochs = payload.get("epochs") or []
    if not epochs:
        problems.append("spectrum has no epochs")
    for epoch in epochs:
        if not epoch.get("collection") or not epoch.get("release"):
            problems.append(f"spectrum epoch {epoch.get('epoch_id')} lacks release fields")
        if not epoch.get("channels"):
            problems.append(f"spectrum epoch {epoch.get('epoch_id')} has no channels")
    if problems:
        if destination.exists():
            destination.unlink()
        return {
            "available": False,
            "reason": "; ".join(problems),
            "expected_path": str(live_path),
        }

    _atomic_write_bytes(destination, content)
    return {
        "available": True,
        "file": "spectrum.json",
        "path": str(destination.relative_to(REPO_ROOT).as_posix()),
        "sha256": _sha256_bytes(content),
        "size_bytes": len(content),
        "source": (
            live_path.relative_to(REPO_ROOT).as_posix()
            if live_path.is_relative_to(REPO_ROOT)
            else live_path.as_posix()
        ),
        "generated_at": payload.get("generated_at"),
        "confidence": str(payload.get("confidence")),
        "available_epoch_ids": [
            str(epoch["epoch_id"]) for epoch in epochs
        ],
        "channel_counts": {
            str(epoch["epoch_id"]): len(epoch.get("channels") or [])
            for epoch in epochs
        },
        "provenance": provenance,
    }


# ---------------------------------------------------------------------------
# Golden manifest assembly
# ---------------------------------------------------------------------------
def _validate_pipeline_manifest(
    manifest: dict[str, Any],
    target_id: str,
    target_ra: float,
    target_dec: float,
) -> None:
    provenance = manifest.get("provenance") or {}
    if provenance.get("is_simulated_fallback") is not False:
        raise ValueError(
            "Refusing to publish synthetic data as real: the pipeline manifest "
            "does not set provenance.is_simulated_fallback=false."
        )
    query = manifest.get("query") or {}
    if abs(float(query.get("ra", -999.0)) - float(target_ra)) > 1e-6:
        raise ValueError(f"Pipeline query RA does not match {target_id} 2025.8")
    if abs(float(query.get("dec", -999.0)) - float(target_dec)) > 1e-6:
        raise ValueError(f"Pipeline query Dec does not match {target_id} 2025.8")
    epochs = manifest.get("epochs") or []
    if not epochs:
        raise ValueError("Pipeline manifest contains no epochs; refusing to cache")
    for epoch in epochs:
        for key in ("epoch_id", "label", "collection", "release", "mjd_mean", "date_iso"):
            if key not in epoch:
                raise ValueError(f"Epoch is missing contract field {key!r}: {epoch!r}")
        summary = epoch.get("flag_summary") or {}
        for key in (
            "status",
            "source_bit_set",
            "artifact_pixel_fraction",
            "active_warning_flags",
            "human_explanation",
        ):
            if key not in summary:
                raise ValueError(
                    f"Epoch {epoch.get('epoch_id')} flag_summary is missing {key!r}"
                )
        if str(summary["status"]) not in {"NOMINAL", "CAUTION", "ALERT"}:
            raise ValueError(f"Invalid flag status: {summary['status']!r}")
    normalization = provenance.get("flux_normalization") or {}
    for key in (
        "method",
        "scope",
        "reference_epoch",
        "applied",
        "status",
        "clamped",
        "raw_stats_location",
    ):
        if key not in normalization:
            raise ValueError(f"provenance.flux_normalization is missing {key!r}")
    if provenance.get("zodi_subtracted") is not True:
        raise ValueError("provenance.zodi_subtracted must be true for real frames")
    if provenance.get("background_subtracted") is not True:
        raise ValueError("provenance.background_subtracted must be true for real frames")


def _build_golden_manifest(
    manifest: dict[str, Any],
    target: Any,
    *,
    query_ra: float,
    query_dec: float,
    live_manifest_path: Path,
    source_manifest_sha256: str,
    frame_hashes: dict[str, str],
    total_bytes: int,
    halo_decision: dict[str, Any],
    spectrum_meta: dict[str, Any],
    reference_overlays: dict[str, str] | None = None,
    reference_provenance: dict[str, Any] | None = None,
    reference_bytes: int = 0,
    telemetry_hashes: dict[str, str] | None = None,
    telemetry_bytes: int = 0,
) -> dict[str, Any]:
    provenance = dict(manifest["provenance"])
    provenance["generated_at"] = _now_utc()
    if provenance.get("is_simulated_fallback") is not False:
        raise ValueError("Golden cache provenance must set is_simulated_fallback=false")

    missing_bands: dict[str, list[int]] = {}
    for epoch in manifest.get("epochs", []):
        bands = [int(band) for band in epoch.get("bands") or []]
        missing = [band for band in range(1, 7) if band not in bands]
        if missing:
            missing_bands[str(epoch["epoch_id"])] = missing

    halo_display_mode = bool(halo_decision.get("halo_display_mode"))
    epochs_payload = _golden_epochs(manifest, target.id)
    telemetry_count = len(telemetry_hashes or {})
    notes = [
        "Real NASA/IPAC IRSA SPHEREx data; is_simulated_fallback=false.",
        "Frames are pre-normalized by the B2 pipeline (LAW 8); do not re-normalize.",
        "Difference frames use un-normalized, ZODI/background-subtracted coadds.",
        (
            "HALO display-only mode is active: displayed frames and flag_overlay "
            "show HALO pixels; photometry, clean_fraction, and is_flagged_bad "
            "keep HALO hard."
            if halo_display_mode
            else "HALO remains hard-masked in displayed frames (gate not triggered)."
        ),
        "spectrum.json is copied from the B3 spectrophotometry cache when available.",
        (
            "Per-epoch telemetry sidecars carry the float16 MJy/sr display coadd "
            "and the raw uint32 Table 16 flag plane (BIT_SOURCE preserved); "
            "they are separate from frames and never feed photometry."
            if telemetry_count
            else "No telemetry sidecars are attached to this golden cache."
        ),
        (
            "Real reference overlays (DSS2 Red, WISE 3.4/4.6, Gaia DR3 pins) "
            "are display-only and marked is_simulated_fallback=false."
            if reference_overlays
            else "No reference overlays are attached to this golden cache."
        ),
    ]

    golden_manifest: dict[str, Any] = {
        "golden_cache_version": GOLDEN_CACHE_VERSION,
        "target_id": target.id,
        "target_name": target.name,
        "generated_at": _now_utc(),
        "generated_by": "scripts/build_golden_cache.py",
        "target": target.to_contract().model_dump(mode="json"),
        "query": manifest["query"],
        "available_epoch_ids": list(manifest.get("available_epoch_ids") or []),
        "epochs": epochs_payload,
        "differences": manifest.get("differences", {}),
        "reference_overlays": reference_overlays or {},
        "normalization": manifest.get("normalization", {}),
        "provenance": provenance,
        "reference_overlay_provenance": reference_provenance or {},
        "halo_display_mode": halo_display_mode,
        "halo_decision": halo_decision,
        "spectrum": spectrum_meta,
        "pipeline": {
            "module": "services.spherex_pipeline",
            "cache_version": manifest.get("version"),
            "max_visits_per_band": manifest.get("max_visits_per_band"),
            "cutout_size_deg": manifest["query"].get("cutout_size_deg"),
            "source_manifest": (
                live_manifest_path.relative_to(REPO_ROOT).as_posix()
                if live_manifest_path.is_relative_to(REPO_ROOT)
                else live_manifest_path.as_posix()
            ),
            "source_manifest_sha256": source_manifest_sha256,
            "source_generated_at": manifest.get("generated_at"),
        },
        "assets": {
            "count": len(frame_hashes),
            "total_bytes": int(total_bytes),
            "image_shape": list(WEBP_GRID),
            "sha256": dict(sorted(frame_hashes.items())),
            "reference_count": len(reference_provenance.get("assets", {}))
            if reference_provenance
            else 0,
            "reference_total_bytes": int(reference_bytes),
            "telemetry": {
                "count": telemetry_count,
                "total_bytes": int(telemetry_bytes),
                "sha256": dict(sorted((telemetry_hashes or {}).items())),
                "format": "float16_uint32_le_gzip",
                "width": 240,
                "height": 240,
            },
        },
        "data_quality": {
            "missing_bands_by_epoch": missing_bands,
            "normalization_status": provenance["flux_normalization"]["status"],
            "flag_status_by_epoch": {
                str(epoch["epoch_id"]): epoch["flag_summary"]["status"]
                for epoch in manifest.get("epochs", [])
            },
            "halo_display_mode": halo_display_mode,
            "halo_triggering_epoch_bands": list(
                halo_decision.get("triggering_epoch_bands") or []
            ),
        },
        "notes": notes,
    }
    return golden_manifest


# ---------------------------------------------------------------------------
# Build / verify one target
# ---------------------------------------------------------------------------
def build_target(
    target_id: str,
    *,
    golden_dir: Path,
    cutout_size_deg: float,
    max_visits_per_band: int,
    force_refresh: bool,
    prune: bool,
    rebuild_spectrum: bool,
    build_spectrum_if_missing: bool,
    fetch_reference_overlays: bool = True,
    force_reference_overlays: bool = False,
    require_telemetry: bool = False,
) -> dict[str, Any]:
    """Run the B2/B3 pipelines and materialize one target's golden cache."""
    modules = _backend_modules()
    settings = modules["settings"]
    target = modules["target_by_id"].get(target_id)
    if target is None:
        raise KeyError(f"Unknown target id {target_id!r}")

    query_ra = float(target.ra_epoch2025)
    query_dec = float(target.dec_epoch2025)
    # Independent astropy propagation: the stored 2025.8 values are the
    # contract, but a >1" discrepancy means a coordinate regression.
    propagated = modules["propagated_coordinates"](target)
    offset_arcsec = (
        propagated.separation(
            type(propagated)(ra=query_ra, dec=query_dec, unit="deg", frame="icrs")
        ).to_value("arcsec")
    )
    if offset_arcsec > 1.0:
        raise ValueError(
            f"{target_id}: stored 2025.8 coordinate differs from Astropy "
            f"propagation by {offset_arcsec:.2f} arcsec"
        )

    logger.info(
        "%s: building with ra=%.5f dec=%.5f (2025.8), cutout=%.3f deg, visits=%d",
        target_id,
        query_ra,
        query_dec,
        cutout_size_deg,
        max_visits_per_band,
    )

    manifest = modules["pipeline"].build_manifest(
        asset_key=target.id,
        ra=query_ra,
        dec=query_dec,
        cutout_size_deg=cutout_size_deg,
        max_visits_per_band=max_visits_per_band,
        force_refresh=force_refresh,
    )
    _validate_pipeline_manifest(manifest, target.id, query_ra, query_dec)

    live_dir = settings.live_cache_dir / target.id
    live_manifest_path = live_dir / "frame.json"
    if not live_manifest_path.is_file():
        raise FileNotFoundError(f"Pipeline manifest not found: {live_manifest_path}")
    source_sha = _sha256_file(live_manifest_path)

    # Reconstruct the exact selected visits from the pipeline manifest and load
    # their cutouts once.  The same inputs are used for the HALO measurement and
    # the optional display-mode re-render.
    records_by_key, contents = _load_manifest_inputs(
        manifest, query_ra, query_dec, modules
    )
    out_wcs = modules["pipeline"].output_wcs(query_ra, query_dec)
    measurements, halo_masks, _coverage_masks = _measure_halo(
        manifest,
        records_by_key,
        contents,
        out_wcs,
        query_ra,
        query_dec,
        modules,
    )
    decision = _halo_decision(
        measurements, modules["flag_policy"], modules["pipeline"]
    )
    logger.info(
        "%s: HALO gate %s; triggering %s",
        target_id,
        "TRIGGERED" if decision["triggered"] else "not triggered",
        decision["triggering_epoch_bands"] or "none",
    )

    filenames = _frame_filenames(manifest)
    target_dir = golden_dir / target.id
    target_dir.mkdir(parents=True, exist_ok=True)

    # Real reference overlays and Gaia DR3 pins (S4).  They are display-only
    # assets: they never enter the SPHEREx frames, photometry, or flags.
    overlay_module = _overlay_module()
    existing = _existing_manifest(target_dir)
    reference_provenance = overlay_module.ensure_reference_overlays(
        target.id,
        target_dir,
        query_ra,
        query_dec,
        fetch_missing=fetch_reference_overlays,
        force=force_reference_overlays,
        reuse=existing.get("reference_overlay_provenance"),
    )
    reference_overlays = overlay_module.reference_overlay_url_map(target.id)
    reference_filenames = _reference_filenames(
        {"reference_overlays": reference_overlays}, target.id
    )

    _copy_frames(
        live_dir,
        target_dir,
        filenames,
        prune=prune,
        extra_referenced=reference_filenames,
    )
    telemetry_filenames = _telemetry_filenames(manifest)
    if telemetry_filenames and not decision["triggered"]:
        # No display rebuild: the pipeline's photometric sidecar is the
        # displayed coadd, so copy it as-is.
        _copy_frames(
            live_dir,
            target_dir,
            telemetry_filenames,
            prune=False,
        )
    if prune:
        referenced_telemetry = set(telemetry_filenames)
        for stale in sorted(target_dir.glob("*.bin.gz")):
            if stale.name not in referenced_telemetry:
                logger.warning("Pruning stale telemetry sidecar %s", stale.name)
                stale.unlink()

    if decision["triggered"]:
        _apply_halo_flag_summary(manifest, decision, halo_masks)
        _rebuild_display_frames(
            target_dir,
            manifest,
            records_by_key,
            contents,
            out_wcs,
            query_ra,
            query_dec,
            halo_masks,
            decision,
            modules,
            target.id,
        )
        # Safety net: any epoch the display rebuild could not regenerate falls
        # back to the pipeline sidecar (logged by the rebuild as a failure).
        for name in _telemetry_filenames(manifest):
            destination = target_dir / name
            if destination.is_file():
                continue
            source = live_dir / name
            if source.is_file():
                logger.warning(
                    "Display telemetry missing for %s; copying the pipeline "
                    "sidecar (HALO may be hard-masked)",
                    name,
                )
                _atomic_write_bytes(destination, source.read_bytes())
    else:
        decision["epochs_with_halo"] = []

    spectrum_meta = _attach_spectrum(
        target,
        golden_dir,
        modules,
        query_ra=query_ra,
        query_dec=query_dec,
        rebuild=rebuild_spectrum,
        build_if_missing=build_spectrum_if_missing,
    )

    # Hash the final files after any display-mode re-render.
    telemetry_filenames = _telemetry_filenames(manifest)
    frame_hashes, total_bytes = _collect_assets(target_dir, filenames)
    reference_hashes, reference_bytes = _collect_reference_assets(
        target_dir, reference_filenames
    )
    telemetry_hashes, telemetry_bytes = _collect_assets(
        target_dir, telemetry_filenames
    )
    recorded_assets = reference_provenance.get("assets") or {}
    for name, digest in reference_hashes.items():
        entry = recorded_assets.get(name)
        if isinstance(entry, dict) and entry.get("sha256") != digest:
            entry["sha256"] = digest
    golden_manifest = _build_golden_manifest(
        manifest,
        target,
        query_ra=query_ra,
        query_dec=query_dec,
        live_manifest_path=live_manifest_path,
        source_manifest_sha256=source_sha,
        frame_hashes=frame_hashes,
        total_bytes=total_bytes,
        halo_decision=decision,
        spectrum_meta=spectrum_meta,
        reference_overlays=reference_overlays,
        reference_provenance=reference_provenance,
        reference_bytes=reference_bytes,
        telemetry_hashes=telemetry_hashes,
        telemetry_bytes=telemetry_bytes,
    )
    manifest_path = target_dir / "manifest.json"
    _atomic_write_json(manifest_path, golden_manifest)

    summary = verify_target(
        target_id, golden_dir=golden_dir, require_telemetry=require_telemetry
    )
    summary["manifest_path"] = str(manifest_path)
    return summary


def _golden_epochs(manifest: dict[str, Any], target_id: str) -> list[dict[str, Any]]:
    """Epoch payloads with telemetry URLs rewritten to contract asset URLs.

    B8 writes a bare ``telemetry_{epoch_id}.bin.gz`` filename into the live
    manifest.  The golden manifest (and therefore ``/sky``) exposes the full
    ``/api/v1/assets/{target_id}/...`` URL, matching the reference overlays.
    """
    epochs = copy.deepcopy(manifest.get("epochs") or [])
    prefix = f"/api/v1/assets/{target_id}/"
    for epoch in epochs:
        block = epoch.get("telemetry")
        if not isinstance(block, dict):
            continue
        name = block.get("url")
        if not isinstance(name, str) or not name:
            continue
        if name.startswith(prefix):
            continue
        if name.startswith(("http://", "https://", "/")):
            raise ValueError(
                f"Telemetry URL for {epoch.get('epoch_id')} is not a local "
                f"golden-cache file: {name!r}"
            )
        if not SAFE_FILENAME.fullmatch(name):
            raise ValueError(f"Unsafe telemetry filename: {name!r}")
        block["url"] = prefix + name
    return epochs


def _local_telemetry_filenames(
    manifest: dict[str, Any], target_id: str
) -> list[str]:
    """Local sidecars referenced by golden ``epochs[].telemetry.url``."""
    names: list[str] = []
    prefix = f"/api/v1/assets/{target_id}/"
    for epoch in manifest.get("epochs", []):
        block = epoch.get("telemetry")
        if not isinstance(block, dict):
            continue
        value = block.get("url")
        if not isinstance(value, str) or not value:
            continue
        name = value
        if name.startswith(prefix):
            name = name[len(prefix) :]
        elif name.startswith(("http://", "https://", "/")):
            continue
        if not SAFE_FILENAME.fullmatch(name):
            raise ValueError(f"Unsafe telemetry filename: {name!r}")
        if name not in names:
            names.append(name)
    return names


def _verify_telemetry_assets(
    target_id: str,
    target_dir: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Validate telemetry sidecars and LVF geometry (contract 1.1.0).

    The layout is frozen: gzip of a little-endian 240 x 240 float16 MJy/sr
    plane followed by a 240 x 240 uint32 Table 16 flag plane (345,600 bytes
    decoded).  ``BIT_SOURCE`` is allowed and expected in the flag plane; this
    verifier checks the codec, declared byte size, hash and LVF metadata.
    """
    import gzip  # noqa: PLC0415

    import numpy as np  # noqa: PLC0415

    decoded_bytes = 240 * 240 * 6
    width, height = 240, 240
    expected_flux_band = "thermal" if target_id == "wise_0855" else "all"

    assets = (manifest.get("assets") or {}).get("telemetry") or {}
    hashes = assets.get("sha256") or {}
    files: list[str] = []
    by_epoch: dict[str, Any] = {}
    total_bytes = 0
    for epoch in manifest.get("epochs", []):
        epoch_id = str(epoch.get("epoch_id"))
        block = epoch.get("telemetry")
        if block is None:
            continue
        if not isinstance(block, dict):
            raise ValueError(f"{target_id}: {epoch_id} telemetry is not an object")
        for key in ("url", "format", "width", "height", "byte_size", "flux_band"):
            if key not in block:
                raise ValueError(
                    f"{target_id}: {epoch_id} telemetry is missing {key!r}"
                )
        if str(block["format"]) != "float16_uint32_le_gzip":
            raise ValueError(f"{target_id}: {epoch_id} telemetry format is wrong")
        if int(block["width"]) != width or int(block["height"]) != height:
            raise ValueError(f"{target_id}: {epoch_id} telemetry grid is not 240x240")
        if str(block["flux_band"]) not in {"thermal", "all"}:
            raise ValueError(f"{target_id}: {epoch_id} telemetry flux_band is invalid")
        if str(block["flux_band"]) != expected_flux_band:
            raise ValueError(
                f"{target_id}: {epoch_id} flux_band is {block['flux_band']!r}, "
                f"expected {expected_flux_band!r}"
            )

        url = str(block["url"])
        prefix = f"/api/v1/assets/{target_id}/"
        if url.startswith(prefix):
            name = url[len(prefix) :]
        elif url.startswith(("http://", "https://", "/")):
            raise ValueError(
                f"{target_id}: {epoch_id} telemetry URL is not local: {url!r}"
            )
        else:
            name = url
        if not SAFE_FILENAME.fullmatch(name):
            raise ValueError(f"{target_id}: unsafe telemetry filename {name!r}")
        path = target_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"{target_id}: missing telemetry sidecar {path}")
        content = path.read_bytes()
        if int(block["byte_size"]) != len(content):
            raise ValueError(
                f"{target_id}: {name} byte_size {block['byte_size']} != {len(content)}"
            )
        if _sha256_bytes(content) != hashes.get(name):
            raise ValueError(f"{target_id}: telemetry SHA-256 mismatch for {name}")
        if not content.startswith(b"\x1f\x8b"):
            raise ValueError(f"{target_id}: {name} is not gzip-compressed")
        try:
            raw = gzip.decompress(content)
        except OSError as exc:
            raise ValueError(f"{target_id}: {name} cannot be decompressed: {exc}")
        if len(raw) != decoded_bytes:
            raise ValueError(
                f"{target_id}: {name} decodes to {len(raw)} bytes, "
                f"expected {decoded_bytes}"
            )
        image = np.frombuffer(raw[: width * height * 2], dtype="<f2").astype(float)
        flags = np.frombuffer(raw[width * height * 2 :], dtype="<u4")
        if image.size != width * height or flags.size != width * height:
            raise ValueError(f"{target_id}: {name} plane sizes are wrong")
        finite_fraction = float(np.mean(np.isfinite(image)))
        if finite_fraction < 0.05:
            raise ValueError(
                f"{target_id}: {name} has only {finite_fraction:.2%} finite pixels"
            )
        if int(flags.max()) == 0:
            logger.warning("%s: %s has an all-zero flag plane", target_id, name)
        files.append(name)
        total_bytes += len(content)
        by_epoch[epoch_id] = {
            "file": name,
            "byte_size": len(content),
            "finite_fraction": finite_fraction,
            "flags_or": int(np.bitwise_or.reduce(flags)),
        }

        geometry = epoch.get("lvf_geometry")
        if geometry is not None:
            if not isinstance(geometry, list) or not geometry:
                raise ValueError(f"{target_id}: {epoch_id} lvf_geometry is empty")
            detectors: set[int] = set()
            for entry in geometry:
                if not isinstance(entry, dict):
                    raise ValueError(
                        f"{target_id}: {epoch_id} lvf_geometry entry is not an object"
                    )
                detector = int(entry.get("detector", 0))
                if detector not in range(1, 7) or detector in detectors:
                    raise ValueError(
                        f"{target_id}: {epoch_id} LVF detector {detector} is invalid"
                    )
                detectors.add(detector)
                pa = float(entry.get("pa_deg", float("nan")))
                grad = float(entry.get("grad_um_per_arcsec", float("nan")))
                if not (np.isfinite(pa) and np.isfinite(grad) and grad > 0):
                    raise ValueError(
                        f"{target_id}: {epoch_id} LVF geometry is not finite"
                    )

    return {
        "available": bool(files),
        "count": len(files),
        "total_bytes": total_bytes,
        "files": files,
        "format": "float16_uint32_le_gzip",
        "decoded_bytes": decoded_bytes,
        "expected_flux_band": expected_flux_band,
        "by_epoch": by_epoch,
    }


def _verify_reference_assets(
    target_id: str,
    target_dir: Path,
    manifest: dict[str, Any],
    reference_filenames: list[str],
) -> dict[str, Any]:
    """Verify the real overlay/Gaia assets and their recorded provenance."""
    import math  # noqa: PLC0415

    from PIL import Image  # noqa: PLC0415

    overlays = manifest.get("reference_overlays") or {}
    required_keys = (
        "optical_dss_gaia",
        "mid_ir_wise",
        "optical_dss2_red",
        "mid_ir_wise_w1",
        "gaia_sources_url",
        "attribution",
    )
    missing_keys = [key for key in required_keys if not overlays.get(key)]
    if missing_keys:
        raise ValueError(
            f"{target_id}: reference_overlays is missing {missing_keys}"
        )
    for key, value in overlays.items():
        if key == "attribution":
            # Human-readable prose metadata; the backend preserves it
            # verbatim.  The structured credits live in
            # attribution_json/ref_attribution.json.
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"{target_id}: reference_overlays['attribution'] must be "
                    "non-empty prose"
                )
            lowered = value.lower()
            for token in ("skyview", "wise", "gaia"):
                if token not in lowered:
                    raise ValueError(
                        f"{target_id}: attribution prose is missing {token!r}"
                    )
            continue
        if not isinstance(value, str) or not value.startswith(
            (f"/api/v1/assets/{target_id}/", "http://", "https://")
        ):
            raise ValueError(
                f"{target_id}: reference_overlays[{key!r}] is not an asset URL"
            )

    provenance = manifest.get("reference_overlay_provenance") or {}
    if provenance.get("is_simulated_fallback") is not False:
        raise ValueError(
            f"{target_id}: real overlays must record is_simulated_fallback=false"
        )
    recorded = provenance.get("assets") or {}
    if not reference_filenames:
        raise ValueError(f"{target_id}: no local reference assets are referenced")

    gaia_summary = {"returned": 0, "total_g_le_limit": 0}
    for name in reference_filenames:
        path = target_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"{target_id}: missing reference asset {path}")
        content = path.read_bytes()
        entry = recorded.get(name)
        if not isinstance(entry, dict):
            raise ValueError(
                f"{target_id}: reference_provenance is missing {name}"
            )
        if entry.get("is_simulated_fallback") is not False:
            raise ValueError(
                f"{target_id}: {name} must be real (is_simulated_fallback=false)"
            )
        if _reference_asset_digest(name, content) != entry.get("sha256"):
            raise ValueError(f"{target_id}: reference SHA-256 mismatch for {name}")

        if name.endswith(".webp"):
            if not (content.startswith(b"RIFF") and content[8:12] == b"WEBP"):
                raise ValueError(f"{target_id}: {name} is not a WebP file")
            with Image.open(path) as image:
                if image.size != WEBP_GRID:
                    raise ValueError(
                        f"{target_id}: {name} is {image.size}, expected {WEBP_GRID}"
                    )
        elif name.endswith(".json"):
            try:
                payload = json.loads(content.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"{target_id}: {name} is not valid JSON: {exc}")
            if payload.get("is_simulated_fallback") is not False:
                raise ValueError(
                    f"{target_id}: {name} must set is_simulated_fallback=false"
                )
            if name == "gaia_dr3.json":
                query = payload.get("query") or {}
                sources = payload.get("sources")
                if not isinstance(sources, list) or not sources:
                    raise ValueError(f"{target_id}: gaia_dr3.json has no sources")
                cap = int(query.get("cap", 0) or 0)
                g_limit = float(query.get("g_limit", 16.0) or 16.0)
                if cap and len(sources) > cap:
                    raise ValueError(
                        f"{target_id}: gaia_dr3.json has {len(sources)} > cap {cap}"
                    )
                previous_mag = -math.inf
                seen: set[str] = set()
                null_pm = 0
                for source in sources:
                    for key in (
                        "source_id",
                        "ra",
                        "dec",
                        "g_mag",
                        "pmra",
                        "pmdec",
                        "label",
                    ):
                        if key not in source:
                            raise ValueError(
                                f"{target_id}: Gaia source is missing {key!r}"
                            )
                    source_id = source["source_id"]
                    if not isinstance(source_id, str) or not source_id:
                        raise ValueError(
                            f"{target_id}: Gaia source_id must be a non-empty string"
                        )
                    if source_id in seen:
                        raise ValueError(
                            f"{target_id}: duplicate Gaia source_id {source_id}"
                        )
                    seen.add(source_id)
                    ra_value = float(source["ra"])
                    dec_value = float(source["dec"])
                    if not (-360.0 <= ra_value <= 360.0 and -90.0 <= dec_value <= 90.0):
                        raise ValueError(
                            f"{target_id}: Gaia coordinates out of range"
                        )
                    g_mag = source["g_mag"]
                    if g_mag is not None:
                        if float(g_mag) > g_limit + 1e-3:
                            raise ValueError(
                                f"{target_id}: Gaia G={g_mag} exceeds {g_limit}"
                            )
                        if float(g_mag) < previous_mag:
                            raise ValueError(
                                f"{target_id}: Gaia sources are not brightest-first"
                            )
                        previous_mag = float(g_mag)
                    if source["pmra"] is None or source["pmdec"] is None:
                        null_pm += 1
                recorded_query = {
                    "returned": len(sources),
                    "total_g_le_limit": int(
                        query.get("total_g_le_limit", len(sources)) or len(sources)
                    ),
                    "null_pm_count": int(
                        query.get("null_pm_count", null_pm) or 0
                    ),
                }
                if recorded_query["null_pm_count"] != null_pm:
                    raise ValueError(
                        f"{target_id}: gaia_dr3.json null_pm_count does not match"
                    )
                gaia_summary = recorded_query
            elif name == "ref_attribution.json":
                credits = payload.get("credits")
                if not isinstance(credits, list) or not credits:
                    raise ValueError(
                        f"{target_id}: ref_attribution.json has no credits"
                    )

    if target_id == "wise_0855" and "ref_wise_w2.webp" not in reference_filenames:
        raise ValueError(
            "wise_0855: the WISE 4.6 um reference (ref_wise_w2.webp) is required"
        )

    return {
        "count": len(reference_filenames),
        "files": list(reference_filenames),
        "keys": sorted(overlays),
        "is_simulated_fallback": False,
        "gaia_returned": int(gaia_summary["returned"]),
        "gaia_total_g_le_limit": int(gaia_summary["total_g_le_limit"]),
        "gaia_null_pm": int(gaia_summary.get("null_pm_count", 0) or 0),
    }


def verify_target(
    target_id: str,
    *,
    golden_dir: Path,
    require_telemetry: bool = False,
) -> dict[str, Any]:
    """Validate an existing golden cache; raise on any inconsistency."""
    from PIL import Image  # noqa: PLC0415 - only needed for verification

    target_dir = golden_dir / target_id
    manifest_path = target_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Golden manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if int(manifest.get("golden_cache_version", -1)) != GOLDEN_CACHE_VERSION:
        raise ValueError(
            f"{target_id}: unsupported golden_cache_version "
            f"{manifest.get('golden_cache_version')!r}"
        )
    if str(manifest.get("target_id")) != target_id:
        raise ValueError(f"{target_id}: manifest target_id mismatch")
    provenance = manifest.get("provenance") or {}
    if provenance.get("is_simulated_fallback") is not False:
        raise ValueError(
            f"{target_id}: real golden cache must set is_simulated_fallback=false"
        )
    if not manifest.get("epochs"):
        raise ValueError(f"{target_id}: golden manifest has no epochs")

    expected_query = manifest.get("query") or {}
    target = manifest.get("target") or {}
    if "ra_epoch2025" in target:
        if abs(float(expected_query["ra"]) - float(target["ra_epoch2025"])) > 1e-6:
            raise ValueError(f"{target_id}: query RA is not the 2025.8 coordinate")
        if abs(float(expected_query["dec"]) - float(target["dec_epoch2025"])) > 1e-6:
            raise ValueError(f"{target_id}: query Dec is not the 2025.8 coordinate")

    halo_display_mode = bool(manifest.get("halo_display_mode"))
    decision = manifest.get("halo_decision") or {}
    if bool(decision.get("triggered")) != halo_display_mode:
        raise ValueError(f"{target_id}: halo_display_mode and halo_decision disagree")
    if halo_display_mode:
        expected_display = int(decision.get("hard_bad_mask", 0)) & ~int(
            decision.get("halo_bit", 1 << 28)
        )
        if int(decision.get("display_bad_mask", -1)) != expected_display:
            raise ValueError(f"{target_id}: display_bad_mask is not HARD_BAD_MASK & ~HALO")
        if not (int(decision.get("photometry_exclude_mask", 0)) & int(decision.get("halo_bit", 1 << 28))):
            raise ValueError(f"{target_id}: HALO must remain in PHOTOMETRY_EXCLUDE_MASK")

    filenames = _frame_filenames(manifest)
    reference_filenames = _reference_filenames(manifest, target_id)
    hashes = (manifest.get("assets") or {}).get("sha256") or {}
    missing = [name for name in filenames if name not in hashes]
    if missing:
        raise ValueError(f"{target_id}: integrity map is missing {missing[:5]}")

    for name in filenames:
        path = target_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"{target_id}: missing frame {path}")
        content = path.read_bytes()
        if not (content.startswith(b"RIFF") and content[8:12] == b"WEBP"):
            raise ValueError(f"{target_id}: {name} is not a WebP file")
        digest = _sha256_bytes(content)
        if digest != hashes[name]:
            raise ValueError(f"{target_id}: SHA-256 mismatch for {name}")
        with Image.open(path) as image:
            if image.size != WEBP_GRID:
                raise ValueError(
                    f"{target_id}: {name} is {image.size}, expected {WEBP_GRID}"
                )

    reference_summary = _verify_reference_assets(
        target_id, target_dir, manifest, reference_filenames
    )
    telemetry_summary = _verify_telemetry_assets(target_id, target_dir, manifest)
    if require_telemetry and not telemetry_summary["available"]:
        raise ValueError(f"{target_id}: telemetry sidecars are required")
    telemetry_files = set(_local_telemetry_filenames(manifest, target_id))
    stale_sidecars = sorted(
        path.name
        for path in target_dir.glob("*.bin.gz")
        if path.name not in telemetry_files
    )
    if stale_sidecars:
        raise ValueError(
            f"{target_id}: unreferenced telemetry sidecars present: "
            f"{stale_sidecars[:5]}"
        )

    for epoch in manifest["epochs"]:
        summary = epoch.get("flag_summary") or {}
        if str(summary.get("status")) not in {"NOMINAL", "CAUTION", "ALERT"}:
            raise ValueError(f"{target_id}: invalid flag status in {epoch['epoch_id']}")
        fraction = float(summary.get("artifact_pixel_fraction", -1.0))
        if not 0.0 <= fraction <= 1.0:
            raise ValueError(f"{target_id}: artifact_pixel_fraction out of range")
        if not epoch.get("collection") or not epoch.get("release"):
            raise ValueError(f"{target_id}: epoch {epoch['epoch_id']} lacks release fields")
        if halo_display_mode and epoch["epoch_id"] in set(
            decision.get("epochs_with_halo") or []
        ):
            if "HALO" not in (summary.get("active_warning_flags") or []):
                raise ValueError(
                    f"{target_id}: HALO is missing from "
                    f"{epoch['epoch_id']} active_warning_flags"
                )
            if str(summary.get("status")) == "NOMINAL":
                raise ValueError(
                    f"{target_id}: HALO epoch {epoch['epoch_id']} must be at least CAUTION"
                )

    spectrum_meta = manifest.get("spectrum") or {}
    spectrum_path = target_dir / "spectrum.json"
    if spectrum_meta.get("available"):
        if not spectrum_path.is_file():
            raise FileNotFoundError(f"{target_id}: missing {spectrum_path}")
        content = spectrum_path.read_bytes()
        if _sha256_bytes(content) != spectrum_meta.get("sha256"):
            raise ValueError(f"{target_id}: spectrum.json SHA-256 mismatch")
        payload = json.loads(content.decode("utf-8"))
        if int(payload.get("version", -1)) != 2:
            raise ValueError(f"{target_id}: unsupported spectrum version")
        if (payload.get("provenance") or {}).get("is_simulated_fallback") is not False:
            raise ValueError(f"{target_id}: spectrum is not real data")
        if str(payload.get("confidence")) != "high":
            raise ValueError(f"{target_id}: catalog spectrum confidence must be high")
    elif spectrum_path.exists():
        raise ValueError(f"{target_id}: stale spectrum.json is present")

    referenced = set(filenames) | set(reference_filenames)
    stale = sorted(
        path.name for path in target_dir.glob("*.webp") if path.name not in referenced
    )
    if stale:
        raise ValueError(f"{target_id}: unreferenced golden frames present: {stale[:5]}")

    flag_status = manifest.get("data_quality", {}).get("flag_status_by_epoch") or {
        str(epoch["epoch_id"]): epoch["flag_summary"]["status"]
        for epoch in manifest["epochs"]
    }
    return {
        "target_id": target_id,
        "target_name": manifest.get("target_name"),
        "epochs": [str(epoch["epoch_id"]) for epoch in manifest["epochs"]],
        "frames": len(filenames),
        "total_bytes": int((manifest.get("assets") or {}).get("total_bytes", 0)),
        "collection": provenance.get("collection"),
        "release": provenance.get("release"),
        "normalization_status": (provenance.get("flux_normalization") or {}).get(
            "status"
        ),
        "flag_status": flag_status,
        "halo_display_mode": halo_display_mode,
        "halo_triggering_epoch_bands": list(
            decision.get("triggering_epoch_bands") or []
        ),
        "halo_bands_with_halo": list(decision.get("bands_with_halo") or []),
        "spectrum_available": bool(spectrum_meta.get("available")),
        "spectrum_epochs": list(spectrum_meta.get("available_epoch_ids") or []),
        "missing_bands": (manifest.get("data_quality") or {}).get(
            "missing_bands_by_epoch", {}
        ),
        "reference_assets": reference_summary,
        "telemetry_assets": telemetry_summary,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the real-data SPHEREx SkyBlink golden cache.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--target",
        default="wise_0855",
        choices=(*TARGET_IDS, "all"),
        help="Catalog target to cache.",
    )
    parser.add_argument(
        "--golden-dir",
        type=Path,
        default=DEFAULT_GOLDEN_DIR,
        help="Golden cache root directory.",
    )
    parser.add_argument(
        "--cutout-size",
        type=float,
        default=0.2,
        help="IRSA cutout size in degrees (contract golden grid is 0.205 deg).",
    )
    parser.add_argument(
        "--visits",
        type=int,
        default=3,
        help="Maximum visits coadded per band and epoch.",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Re-query IRSA and rebuild the sky manifest instead of using its cache.",
    )
    parser.add_argument(
        "--no-prune",
        action="store_true",
        help="Keep unreferenced *.webp files in the target directory.",
    )
    parser.add_argument(
        "--rebuild-spectrum",
        action="store_true",
        help="Force the B3 spectrophotometry cache to rebuild.",
    )
    parser.add_argument(
        "--no-spectrum",
        action="store_true",
        help="Do not copy or build spectrum.json.",
    )
    parser.add_argument(
        "--no-overlays",
        action="store_true",
        help=(
            "Do not fetch missing real reference overlays/Gaia pins; existing "
            "SHA-256-verified assets are still reused."
        ),
    )
    parser.add_argument(
        "--force-overlays",
        action="store_true",
        help="Re-download the DSS2/WISE overlays and Gaia DR3 pins.",
    )
    parser.add_argument(
        "--require-telemetry",
        action="store_true",
        help=(
            "Fail unless every epoch has a validated float16+uint32 gzip "
            "telemetry sidecar (S4 Stage 2)."
        ),
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Validate existing golden caches without querying IRSA.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Pipeline cache directory (overrides the CACHE_DIR environment variable).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    if args.cache_dir is not None:
        os.environ["CACHE_DIR"] = str(args.cache_dir.expanduser().resolve())

    targets = list(TARGET_IDS) if args.target == "all" else [args.target]
    golden_dir = args.golden_dir.expanduser().resolve()

    summaries: list[dict[str, Any]] = []
    failures: list[tuple[str, str]] = []
    for target_id in targets:
        try:
            if args.verify_only:
                summary = verify_target(
                    target_id,
                    golden_dir=golden_dir,
                    require_telemetry=args.require_telemetry,
                )
                summary["manifest_path"] = str(golden_dir / target_id / "manifest.json")
            else:
                summary = build_target(
                    target_id,
                    golden_dir=golden_dir,
                    cutout_size_deg=args.cutout_size,
                    max_visits_per_band=args.visits,
                    force_refresh=args.force_refresh,
                    prune=not args.no_prune,
                    rebuild_spectrum=args.rebuild_spectrum,
                    build_spectrum_if_missing=not args.no_spectrum,
                    fetch_reference_overlays=not args.no_overlays,
                    force_reference_overlays=args.force_overlays,
                    require_telemetry=args.require_telemetry,
                )
        except Exception as exc:  # noqa: BLE001 - report every target, then fail
            logger.error("%s: FAILED: %s", target_id, exc)
            failures.append((target_id, f"{type(exc).__name__}: {exc}"))
            continue
        summaries.append(summary)
        missing = summary.get("missing_bands") or {}
        logger.info(
            "%s: OK — %d epochs %s, %d frames, %.2f MB, collection=%s, "
            "normalization=%s, flags=%s, halo_display=%s%s%s%s",
            target_id,
            len(summary["epochs"]),
            summary["epochs"],
            summary["frames"],
            summary["total_bytes"] / 1e6,
            summary["collection"],
            summary["normalization_status"],
            summary["flag_status"],
            summary["halo_display_mode"],
            f", HALO trigger: {summary['halo_triggering_epoch_bands']}"
            if summary["halo_triggering_epoch_bands"]
            else "",
            f", missing bands: {missing}" if missing else "",
            (
                f", telemetry: {summary['telemetry_assets']['count']} sidecars"
                if (summary.get("telemetry_assets") or {}).get("available")
                else ""
            ),
        )

    print(
        json.dumps(
            {
                "ok": not failures,
                "golden_dir": str(golden_dir),
                "cached": summaries,
                "failures": [
                    {"target_id": target_id, "error": message}
                    for target_id, message in failures
                ],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
