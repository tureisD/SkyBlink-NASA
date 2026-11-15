#!/usr/bin/env python3
"""Run historical display-smoke checks on the golden cache.

This card is not scientific acceptance. Rendered WebP metrics depend on
display stretches; configured target facts are not independent observations.
Raw-unit science checks live in scripts/phase3_science_validation.py.

* Bright targets (Barnard's Star, RW Aurigae, R Draconis, Epsilon Indi B) are
  saturated in SPHEREx; their cores can be hard-masked (``SUR_ERROR``), so the
  card uses the saturated-halo centroid, difference frames, and the B3 spectra
  instead of claiming clean core photometry.
* WISE 0855 is faint and crowded in the short-wavelength bands; its
  band-dependent signal is measured on **difference frames** (static field
  cancellation), not on a single crowded epoch frame.

The script defaults to ``docs/five-target-display-smoke.json`` and prints a table.
Every metric, threshold, and caveat is recorded so a failed check cannot be
mistaken for a discovery.

Usage::

    ../.venv311/Scripts/python.exe scripts/run_five_target_card.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
GOLDEN_DIR = REPO_ROOT / "golden_cache"
TARGET_IDS = (
    "wise_0855",
    "barnards_star",
    "eps_indi_b",
    "rw_aurigae",
    "r_draconis",
)
CENTER = 119.5
BOX_HALF = 20
HALO_BOX_HALF = 25
HALO_THRESHOLD = 240.0

logger = logging.getLogger("skyblink.five_target_card")


def _backend() -> dict[str, Any]:
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))
    from astropy.time import Time  # noqa: PLC0415
    from core.targets import get_target, propagated_coordinates  # noqa: PLC0415
    from services.spherex_pipeline import output_wcs  # noqa: PLC0415

    return {
        "Time": Time,
        "get_target": get_target,
        "propagated_coordinates": propagated_coordinates,
        "output_wcs": output_wcs,
    }


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_manifest(target_id: str) -> dict[str, Any]:
    return json.loads(
        (GOLDEN_DIR / target_id / "manifest.json").read_text(encoding="utf-8")
    )


def _load_spectrum(target_id: str) -> dict[str, Any] | None:
    path = GOLDEN_DIR / target_id / "spectrum.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _load_frame(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("L"), dtype=float)


def _box(image: np.ndarray, half: int = BOX_HALF) -> np.ndarray:
    center = int(round(CENTER))
    return image[center - half : center + half + 1, center - half : center + half + 1]


def _difference_stats(frame: np.ndarray) -> dict[str, float]:
    """Mean/std/p99 of a zero-centred difference frame in the central box."""
    residual = _box(frame) - 128.0
    return {
        "mean_adu": float(np.mean(residual)),
        "std_adu": float(np.std(residual)),
        "p99_abs_adu": float(np.percentile(np.abs(residual), 99.0)),
    }


def _halo_centroid(
    image: np.ndarray, x0: float, y0: float
) -> dict[str, float] | None:
    """Centroid/area of the saturated halo around a bright, flagged core."""
    xi = int(round(float(x0)))
    yi = int(round(float(y0)))
    sub = image[
        yi - HALO_BOX_HALF : yi + HALO_BOX_HALF + 1,
        xi - HALO_BOX_HALF : xi + HALO_BOX_HALF + 1,
    ]
    weights = np.clip(sub - HALO_THRESHOLD, 0.0, None)
    total = float(weights.sum())
    if total <= 0.0:
        return None
    yy, xx = np.indices(sub.shape)
    return {
        "x": float(xi - HALO_BOX_HALF + (weights * xx).sum() / total),
        "y": float(yi - HALO_BOX_HALF + (weights * yy).sum() / total),
        "weight_sum": total,
        "saturated_pixels": int(np.count_nonzero(sub >= HALO_THRESHOLD)),
    }


def _aperture_mean(
    image: np.ndarray, x0: float, y0: float, radius: float = 1.2
) -> float:
    yy, xx = np.indices(image.shape)
    mask = np.hypot(xx - x0, yy - y0) <= radius
    return float(np.mean(image[mask]))


def _expected_positions(
    target_id: str, manifest: dict[str, Any], backend: dict[str, Any]
) -> dict[str, tuple[float, float, float]]:
    target = backend["get_target"](target_id)
    wcs = backend["output_wcs"](
        float(manifest["query"]["ra"]), float(manifest["query"]["dec"])
    )
    positions: dict[str, tuple[float, float, float]] = {}
    for epoch in manifest["epochs"]:
        year = float(
            backend["Time"](
                epoch["mjd_mean"], format="mjd", scale="tt"
            ).decimalyear
        )
        coord = backend["propagated_coordinates"](target, year)
        x, y = wcs.world_to_pixel(coord)
        positions[str(epoch["epoch_id"])] = (float(x), float(y), year)
    return positions


def _spectrum_by_epoch_band(
    spectrum: dict[str, Any],
) -> dict[str, dict[int, list[float]]]:
    """Used-channel fluxes grouped by epoch and detector."""
    grouped: dict[str, dict[int, list[float]]] = {}
    for epoch in spectrum.get("epochs", []):
        per_band: dict[int, list[float]] = {}
        for channel in epoch.get("channels", []):
            if not channel.get("is_used_in_photometry"):
                continue
            flux = channel.get("flux_ujy")
            if flux is None or not np.isfinite(flux):
                continue
            per_band.setdefault(int(channel["detector"]), []).append(float(flux))
        grouped[str(epoch["epoch_id"])] = per_band
    return grouped


def _medians_by_band(
    spectrum: dict[str, Any],
) -> dict[int, list[float]]:
    """Median used flux per epoch, grouped by detector."""
    grouped = _spectrum_by_epoch_band(spectrum)
    bands: dict[int, list[float]] = {}
    for per_band in grouped.values():
        for band, fluxes in per_band.items():
            if fluxes:
                bands.setdefault(band, []).append(float(np.median(fluxes)))
    return bands


def _direction_dot(
    measured: tuple[float, float], expected: tuple[float, float]
) -> float:
    m = np.asarray(measured, dtype=float)
    e = np.asarray(expected, dtype=float)
    denominator = float(np.linalg.norm(m) * np.linalg.norm(e))
    if denominator == 0.0:
        return 0.0
    return float(np.dot(m, e) / denominator)


def _check(
    name: str,
    passed: bool,
    *,
    metric: Any,
    threshold: Any,
    note: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "classification": "historical_display_smoke",
        "scientific_acceptance": False,
        "passed": bool(passed),
        "metric": metric,
        "threshold": threshold,
        "note": note,
    }


# ---------------------------------------------------------------------------
# Per-target checks
# ---------------------------------------------------------------------------
def check_barnards_star(
    target_id: str, manifest: dict[str, Any], backend: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    band = "2"
    positions = _expected_positions(target_id, manifest, backend)
    epochs = [str(epoch["epoch_id"]) for epoch in manifest["epochs"]]
    first, last = epochs[0], epochs[-1]
    frames = {str(epoch["epoch_id"]): epoch["frames"] for epoch in manifest["epochs"]}

    first_centroid = _halo_centroid(
        _load_frame(GOLDEN_DIR / target_id / frames[first][band]),
        positions[first][0],
        positions[first][1],
    )
    last_centroid = _halo_centroid(
        _load_frame(GOLDEN_DIR / target_id / frames[last][band]),
        positions[last][0],
        positions[last][1],
    )
    checks: list[dict[str, Any]] = []
    caveats = [
        "The stellar core is saturated (OVERFLOW/SUR_ERROR); the position is "
        "measured from the saturated halo centroid, not clean core photometry."
    ]
    if first_centroid is None or last_centroid is None:
        checks.append(
            _check(
                "position_shift",
                False,
                metric=None,
                threshold="> 1.0 px and direction dot > 0.7",
                note="No saturated halo found around the target.",
            )
        )
        return checks, caveats

    measured = (
        last_centroid["x"] - first_centroid["x"],
        last_centroid["y"] - first_centroid["y"],
    )
    expected = (
        positions[last][0] - positions[first][0],
        positions[last][1] - positions[first][1],
    )
    separation = float(np.hypot(*measured))
    expected_separation = float(np.hypot(*expected))
    dot = _direction_dot(measured, expected)
    checks.append(
        _check(
            "position_shift",
            separation > 1.0 and dot > 0.7,
            metric={
                "band": int(band),
                "measured_dx_px": measured[0],
                "measured_dy_px": measured[1],
                "measured_separation_px": separation,
                "expected_separation_px": expected_separation,
                "direction_dot": dot,
                "first_epoch": first,
                "last_epoch": last,
            },
            threshold="measured separation > 1.0 px and direction dot > 0.7",
            note="Proper motion ~10.4 arcsec/yr = ~1.7 px per six-month epoch.",
        )
    )
    return checks, caveats


def check_wise_0855(
    target_id: str, manifest: dict[str, Any], backend: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    positions = _expected_positions(target_id, manifest, backend)
    epochs = [str(epoch["epoch_id"]) for epoch in manifest["epochs"]]
    band_rms: dict[int, list[float]] = {band: [] for band in range(1, 7)}
    motion_signals: dict[int, list[float]] = {band: [] for band in range(1, 7)}

    for pair_key, pair in (manifest.get("differences") or {}).items():
        later, earlier = str(pair_key).split("_minus_", 1)
        for band_key, filename in (pair.get("frames") or {}).items():
            if band_key not in {"1", "2", "3", "4", "5", "6"}:
                continue
            band = int(band_key)
            frame = _load_frame(GOLDEN_DIR / target_id / filename)
            band_rms[band].append(_difference_stats(frame)["std_adu"])
            if later in positions and earlier in positions:
                motion_signals[band].append(
                    _aperture_mean(frame, *positions[later][:2])
                    - _aperture_mean(frame, *positions[earlier][:2])
                )

    def _median(values: list[float]) -> float:
        return float(np.median(values)) if values else 0.0

    rms = {band: _median(values) for band, values in band_rms.items()}
    thermal_rms = max(rms[5], rms[6])
    short_rms = max(rms[1], rms[2], rms[3], rms[4])
    thermal_motion = max(
        float(np.max(motion_signals[5])) if motion_signals[5] else 0.0,
        float(np.max(motion_signals[6])) if motion_signals[6] else 0.0,
    )
    checks = [
        _check(
            "band_dependent_difference_signal",
            thermal_rms > 2.0 * short_rms,
            metric={
                "difference_frame_rms_adu_by_band": {
                    str(band): rms[band] for band in range(1, 7)
                },
                "thermal_rms_adu": thermal_rms,
                "short_wavelength_rms_adu": short_rms,
                "thermal_to_short_ratio": (
                    thermal_rms / short_rms if short_rms > 0 else None
                ),
            },
            threshold="max(B5,B6) difference-frame RMS > 2x max(B1-B4)",
            note=(
                "Single-epoch B1-B4 frames are crowded; the band dependence is "
                "measured on adjacent-epoch difference frames where static "
                "field stars cancel."
            ),
        ),
        _check(
            "proper_motion_signal",
            thermal_motion > 5.0,
            metric={
                "max_thermal_new_minus_old_adu": thermal_motion,
                "per_band_max_motion_adu": {
                    str(band): (float(np.max(motion_signals[band])) if motion_signals[band] else 0.0)
                    for band in range(1, 7)
                },
                "expected_motion_px": {
                    pair: float(
                        np.hypot(
                            positions[str(pair).split("_minus_")[0]][0]
                            - positions[str(pair).split("_minus_")[1]][0],
                            positions[str(pair).split("_minus_")[0]][1]
                            - positions[str(pair).split("_minus_")[1]][1],
                        )
                    )
                    for pair in (manifest.get("differences") or {})
                    if str(pair).split("_minus_")[0] in positions
                    and str(pair).split("_minus_")[1] in positions
                },
            },
            threshold="thermal (B5/B6) new-minus-old aperture signal > 5 ADU",
            note=(
                "The source moves ~4 arcsec/epoch (~1.3 px); the difference "
                "aperture at the old/new propagated positions isolates it."
            ),
        ),
    ]
    caveats = [
        "The field is crowded; single-epoch B1-B4 frames do not show an "
        "obvious isolated source. The band-dependent result is a difference-"
        "mode measurement.",
        "The B3 spectrum has used channels in all bands, but the 12.3\" "
        "aperture is contaminated; do not quote it as clean photometry.",
    ]
    return checks, caveats


def check_eps_indi_b(
    target_id: str, manifest: dict[str, Any], backend: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    spectrum = _load_spectrum(target_id)
    checks: list[dict[str, Any]] = []
    caveats = [
        "Epsilon Indi Ba/Bb are 0.6 arcsec apart; at 3.075 arcsec/pixel they "
        "are unresolved (0.2 pixel separation). The tool must explain the "
        "blend, not claim a resolved pair."
    ]
    separation_px = 0.6 / 3.075
    checks.append(
        _check(
            "unresolved_blend",
            separation_px < 1.0,
            metric={"separation_arcsec": 0.6, "separation_px": separation_px},
            threshold="separation < 1 output pixel",
            note="The pair is blended inside one 6.15 arcsec native pixel.",
        )
    )

    used_bands: set[int] = set()
    thermal_rms: list[float] = []
    short_rms: list[float] = []
    if spectrum is not None:
        for per_band in _spectrum_by_epoch_band(spectrum).values():
            used_bands.update(per_band)
    for pair_key, pair in (manifest.get("differences") or {}).items():
        for band_key, filename in (pair.get("frames") or {}).items():
            if band_key not in {"1", "2", "3", "4", "5", "6"}:
                continue
            stats = _difference_stats(
                _load_frame(GOLDEN_DIR / target_id / filename)
            )["std_adu"]
            if int(band_key) in (5, 6):
                thermal_rms.append(stats)
            else:
                short_rms.append(stats)
    thermal = float(np.median(thermal_rms)) if thermal_rms else 0.0
    short = float(np.median(short_rms)) if short_rms else 0.0
    checks.append(
        _check(
            "composite_spectrum",
            len(used_bands) >= 4,
            metric={
                "bands_with_used_channels": sorted(used_bands),
                "epochs": [
                    str(epoch["epoch_id"]) for epoch in (spectrum or {}).get("epochs", [])
                ],
            },
            threshold="used channels in at least 4 bands",
            note="B3 used-channel photometry; many bright-core channels are flagged.",
        )
    )
    checks.append(
        _check(
            "thermal_difference_signal",
            thermal > 1.5 * short,
            metric={
                "thermal_difference_rms_adu": thermal,
                "short_wavelength_difference_rms_adu": short,
                "ratio": thermal / short if short > 0 else None,
            },
            threshold="thermal difference-frame RMS > 1.5x short-wavelength",
            note="The T-dwarf pair is red; the difference signal is thermal-dominated.",
        )
    )
    return checks, caveats


def check_rw_aurigae(
    target_id: str, manifest: dict[str, Any], backend: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    spectrum = _load_spectrum(target_id)
    checks: list[dict[str, Any]] = []
    caveats = [
        "The bright stellar core is saturated (OVERFLOW); several spectral "
        "channels are hard-bad or have clean_fraction < 0.5.",
        "The variability is measured from used-channel spectra and difference "
        "frames, not from a calibrated light curve.",
    ]
    if spectrum is None:
        checks.append(
            _check(
                "epoch_variability",
                False,
                metric=None,
                threshold="band flux variation > 20% or NIR excess > 2",
                note="No spectrum.json.",
            )
        )
        return checks, caveats

    medians = _medians_by_band(spectrum)
    variations: dict[str, float] = {}
    for band, values in medians.items():
        if len(values) >= 2:
            median = float(np.median(values))
            if median > 0:
                variations[str(band)] = float(
                    (max(values) - min(values)) / median
                )
    max_variation = max(variations.values()) if variations else 0.0
    nir_ratio = None
    if 1 in medians and 6 in medians:
        b1 = float(np.median(medians[1]))
        b6 = float(np.median(medians[6]))
        if b1 > 0:
            nir_ratio = b6 / b1
    checks.append(
        _check(
            "epoch_variability_or_nir_excess",
            max_variation >= 0.20 or (nir_ratio is not None and nir_ratio >= 2.0),
            metric={
                "per_band_epoch_variation": variations,
                "max_variation": max_variation,
                "nir_b6_over_b1": nir_ratio,
            },
            threshold="max variation >= 20% or B6/B1 >= 2",
            note="A T Tauri disk can vary between epochs and/or show a strong NIR excess.",
        )
    )
    return checks, caveats


def check_r_draconis(
    target_id: str, manifest: dict[str, Any], backend: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    checks: list[dict[str, Any]] = []
    caveats = [
        "The Mira core is saturated and hard-masked (OVERFLOW/SUR_ERROR); the "
        "display frame shows a saturated halo with a black core hole.",
        "Variability is therefore measured from the difference-frame mean "
        "level, not from calibrated aperture photometry.",
    ]
    flags: set[str] = set()
    for epoch in manifest["epochs"]:
        flags.update(epoch["flag_summary"].get("active_warning_flags") or [])
    checks.append(
        _check(
            "saturation_flags_visible",
            bool(flags & {"OVERFLOW", "HALO", "TRANSIENT"}),
            metric={"active_warning_flags_union": sorted(flags)},
            threshold="OVERFLOW, HALO, or TRANSIENT present",
            note="Saturation/artifact flags are expected for this bright Mira.",
        )
    )

    best_abs_mean = 0.0
    per_band: dict[str, float] = {}
    for pair_key, pair in (manifest.get("differences") or {}).items():
        for band_key, filename in (pair.get("frames") or {}).items():
            if band_key not in {"1", "2", "3", "4", "5", "6"}:
                continue
            stats = _difference_stats(
                _load_frame(GOLDEN_DIR / target_id / filename)
            )
            value = abs(stats["mean_adu"])
            per_band[f"{pair_key}_D{band_key}"] = stats["mean_adu"]
            best_abs_mean = max(best_abs_mean, value)
    checks.append(
        _check(
            "epoch_variability",
            best_abs_mean > 20.0,
            metric={
                "max_abs_difference_central_mean_adu": best_abs_mean,
                "difference_central_mean_adu": per_band,
            },
            threshold="> 20 ADU coherent central change",
            note="Large coherent difference levels indicate brightness changes.",
        )
    )
    return checks, caveats


CHECKERS = {
    "wise_0855": check_wise_0855,
    "barnards_star": check_barnards_star,
    "eps_indi_b": check_eps_indi_b,
    "rw_aurigae": check_rw_aurigae,
    "r_draconis": check_r_draconis,
}

#: W0 feasibility verdicts (docs/research/w0-feasibility-report.md).  These are not
#: target checks; they are recorded so a regenerated validation report cannot
#: silently lose the measured NO-GO/GO decisions.
W0_FINDINGS = {
    "source": "docs/research/w0-feasibility-report.md",
    "metrics": "golden_cache/w0_overlay_metrics.json",
    "psf_wing_photometry": {
        "verdict": "NO-GO",
        "measured": (
            "Barnard's Star 0/54 and R Draconis 0/60 channels pass "
            "f_wing >= 0.12 with >=8 clean wing pixels; even with no flags "
            "only 23/38 and 10/56 pass. The 1.2-4.2 native-px annulus is "
            "dominated by BIT_SOURCE/OVERFLOW/SUR_ERROR."
        ),
        "decision": (
            "PSF-wing photometry is dropped; no psf_wing_fit photometry "
            "method is emitted. Saturation remains an honest limitation."
        ),
    },
    "r_draconis_nep_clustering": {
        "verdict": "NO-GO",
        "measured": (
            "2,483 TAP rows form one continuous 520.4-day season "
            "(MJD 60789.9-61310.3; largest night-to-night gap 37.8 days). "
            "Only one all-6-band block at a 10-day gap; D2/D5 have 89 "
            "exposures each."
        ),
        "decision": (
            "Keep the existing four R Draconis epochs; do not interpolate or "
            "invent epochs. 2024_E1 remains B3/B6-only."
        ),
    },
    "telemetry_sidecar_budget": {
        "verdict": "GO (revised budget)",
        "measured_gzip_kib": [78.5, 101.0],
        "measured_base64_json_kib": [104.1, 134.0],
        "claim_lt_45_kb": False,
        "decision": (
            "Ship the float16 MJy/sr + uint32 Table 16 gzipped sidecar, but "
            "state the measured 80-105 KiB gzip (104-134 KiB base64) budget. "
            "Do not claim <45 KB."
        ),
    },
    "cds_hips2fits": {
        "verdict": "NO-GO",
        "measured": "6/6 CDS hips2fits requests timed out from this environment.",
        "decision": "Use SkyView FITS cutouts for the real reference overlays.",
    },
    "skyview_overlays_gaia": {
        "verdict": "GO",
        "measured": (
            "DSS2 Red 240x240 on the exact golden TAN grid (21.4 KB WebP, "
            "3/3); WISE 3.4 240x240 with retry (5.8 KB WebP, 2/3 with one "
            "blank 1-element FITS); Gaia DR3 fields available, G<=16 cap."
        ),
        "decision": (
            "Real DSS2 Red + WISE 3.4 (plus WISE 4.6 for WISE 0855) and Gaia "
            "DR3 G<=16 pins are attached to the golden cache."
        ),
    },
    "lvf_visits": {
        "verdict": "GO-METADATA",
        "measured": (
            "12 visits per band/epoch adds +106 distinct 5-nm samples on "
            "WISE 0855 and +172 on Epsilon Indi B; 12 visits cost about "
            "15-17 s per band including downloads."
        ),
        "decision": (
            "Use 12 visits/band/epoch as the target tier with 9/6/available "
            "fallbacks; no 102-channel claim."
        ),
    },
    "live_multi_epoch_blink": {
        "verdict": "NO-GO as scoped",
        "measured": (
            "3 epochs x B3/B5/B6 = 34.6 s cold / 20.3 s warm; best case "
            "2 epochs x B5+B6 = 22.7 s cold / 10.1 s warm. The PSF cube is "
            "96.9% of a cutout, so 0.08 deg saves only 3.4%."
        ),
        "decision": (
            "Do not promise a <15 s cold multi-epoch arbitrary blink; keep "
            "the bounded best-effort path."
        ),
    },
}


def _spectrum_counts(target_id: str) -> dict[str, Any]:
    spectrum = _load_spectrum(target_id)
    if spectrum is None:
        return {"available": False}
    counts: dict[str, Any] = {}
    for epoch in spectrum.get("epochs") or []:
        channels = epoch.get("channels") or []
        counts[str(epoch.get("epoch_id"))] = {
            "total": len(channels),
            "used": sum(
                1 for channel in channels if channel.get("is_used_in_photometry")
            ),
        }
    return {
        "available": True,
        "max_visits_per_band": spectrum.get("max_visits_per_band"),
        "confidence": spectrum.get("confidence"),
        "by_epoch": counts,
    }


def _telemetry_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    by_epoch: dict[str, Any] = {}
    for epoch in manifest.get("epochs") or []:
        block = epoch.get("telemetry")
        if not isinstance(block, dict):
            continue
        by_epoch[str(epoch.get("epoch_id"))] = {
            "file": str(block.get("url", "")).rsplit("/", 1)[-1],
            "byte_size": int(block.get("byte_size", 0) or 0),
            "kib": round(int(block.get("byte_size", 0) or 0) / 1024.0, 1),
            "flux_band": block.get("flux_band"),
            "format": block.get("format"),
        }
    return {
        "count": len(by_epoch),
        "total_bytes": int(sum(item["byte_size"] for item in by_epoch.values())),
        "by_epoch": by_epoch,
    }


def _reference_digest(name: str, content: bytes) -> str:
    """Hash reference assets; JSON is hashed after CRLF/CR -> LF normalization."""
    if name.lower().endswith(".json"):
        content = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(content).hexdigest()


def _real_overlay_summary(
    manifests: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Verify the committed real reference overlays and Gaia DR3 pins.

    Mirrors ``backend/tests/test_reference_overlays.py`` without touching the
    network: every recorded asset must exist, hash-match its provenance, be a
    240 x 240 WebP (or valid JSON), and be labeled real (not simulated).
    """
    grid = (240, 240)
    per_target: dict[str, Any] = {}
    verified = 0
    for target_id, manifest in manifests.items():
        directory = GOLDEN_DIR / target_id
        provenance = manifest.get("reference_overlay_provenance") or {}
        recorded = provenance.get("assets") or {}
        files: dict[str, Any] = {}
        all_ok = bool(recorded)
        for name, entry in sorted(recorded.items()):
            path = directory / name
            item: dict[str, Any] = {
                "present": path.is_file(),
                "is_simulated_fallback": bool(
                    entry.get("is_simulated_fallback")
                ),
            }
            ok = bool(item["present"])
            if ok:
                content = path.read_bytes()
                digest = _reference_digest(name, content)
                canonical = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
                item["bytes"] = len(canonical)
                item["sha256"] = digest
                item["sha256_matches"] = digest == entry.get("sha256")
                ok = ok and bool(item["sha256_matches"])
                if name.lower().endswith(".webp"):
                    item["webp_magic"] = (
                        content[:4] == b"RIFF" and content[8:12] == b"WEBP"
                    )
                    with Image.open(path) as image:
                        item["width"], item["height"] = image.size
                    item["is_240x240"] = (item["width"], item["height"]) == grid
                    ok = ok and item["webp_magic"] and item["is_240x240"]
                elif name.lower().endswith(".json"):
                    json.loads(canonical)
                    item["json_valid"] = True
            ok = ok and not item["is_simulated_fallback"]
            item["ok"] = ok
            all_ok = all_ok and ok
            files[name] = item

        overlay_keys = sorted((manifest.get("reference_overlays") or {}).keys())
        required_keys = {
            "optical_dss_gaia",
            "optical_dss2_red",
            "mid_ir_wise",
            "mid_ir_wise_w1",
            "gaia_sources_url",
            "attribution",
        }
        key_ok = required_keys <= set(overlay_keys)

        gaia_payload = json.loads(
            (directory / "gaia_dr3.json").read_text(encoding="utf-8")
        )
        gaia_query = gaia_payload.get("query") or {}
        gaia_sources = gaia_payload.get("sources") or []
        gaia = {
            "sources": len(gaia_sources),
            "g_limit": gaia_query.get("g_limit"),
            "cap": gaia_query.get("cap"),
            "returned": gaia_query.get("returned"),
            "truncated": bool(gaia_query.get("truncated")),
            "is_simulated_fallback": bool(
                gaia_payload.get("is_simulated_fallback")
            ),
            "source": gaia_payload.get("source"),
        }
        gaia_ok = (
            gaia["sources"] > 0
            and gaia["returned"] == gaia["sources"]
            and gaia["sources"] <= int(gaia["cap"] or 0)
            and float(gaia["g_limit"] or 99.0) <= 16.0
            and not gaia["is_simulated_fallback"]
            and "Gaia DR3" in str(gaia["source"])
        )
        target_ok = all_ok and key_ok and gaia_ok
        verified += 1 if target_ok else 0
        per_target[target_id] = {
            "ok": target_ok,
            "overlay_keys": overlay_keys,
            "assets": files,
            "gaia_dr3": gaia,
        }

    return {
        "grid": "240x240 TAN golden WCS",
        "sources": "NASA/GSFC SkyView (DSS2 Red, AllWISE 3.4/4.6 um); "
        "NASA/IPAC IRSA TAP (Gaia DR3)",
        "verified_targets": verified,
        "total_targets": len(manifests),
        "result": f"{verified}/{len(manifests)}",
        "targets": per_target,
    }


def _stage2_summary(manifests: dict[str, dict[str, Any]]) -> dict[str, Any]:
    telemetry = {
        target_id: _telemetry_summary(manifest)
        for target_id, manifest in manifests.items()
    }
    kib_by_target = {
        target_id: [item["kib"] for item in summary["by_epoch"].values()]
        for target_id, summary in telemetry.items()
    }
    dense_counts = {
        target_id: {
            epoch: f"{counts['used']}/{counts['total']}"
            for epoch, counts in _spectrum_counts(target_id)["by_epoch"].items()
        }
        for target_id in manifests
    }
    return {
        "golden_cache_revision": 3,
        "rebuild": (
            "S7: live IRSA DR1+QR3 refresh (B10 release labels; "
            "B8 telemetry/LVF + dense spectra)"
        ),
        "spectrum_max_visits_per_band": 12,
        "dense_channels_note": (
            "Channels are measured from the committed spectrum.json; the tier "
            "is up to 12 visits/band/epoch (72 when all six detectors yield "
            "distinct samples). Saturated targets keep null/unused channels; "
            "nothing is fabricated."
        ),
        "dense_channel_counts_used_total": dense_counts,
        "telemetry_format": "float16_uint32_le_gzip",
        "telemetry_layout": "240x240 float16 MJy/sr + 240x240 uint32 Table 16 flags",
        "telemetry_sidecar_kib_by_target": kib_by_target,
        "telemetry_budget_note": (
            "Measured gzip sizes across all 17 sidecars: 82.6-111.4 KiB. "
            "WISE 0855 100.0-102.3 KiB, Barnard's Star 107.7-111.4 KiB, "
            "Epsilon Indi B 89.1-93.6 KiB, RW Aurigae 106.4-109.3 KiB, "
            "R Draconis 82.6-95.2 KiB; the real budget is 80-112 KiB, "
            "not <45 KB."
        ),
        "telemetry_flux_band": {
            "wise_0855": "thermal",
            "other_targets": "all",
        },
        "ivw_psf_matching": (
            "Not applied: the B8 PSF-matched/IVW residual criterion was not "
            "met, so frames keep the documented direct-subtraction behaviour."
        ),
        "crowded_diff_6.8": (
            "Not implemented; channels use the standard 12.3 arcsec aperture."
        ),
        "r_draconis_epochs": (
            "Unchanged four epochs; no NEP re-clustering (W0 NO-GO)."
        ),
    }


def run_card(golden_dir: Path = GOLDEN_DIR) -> dict[str, Any]:
    global GOLDEN_DIR
    GOLDEN_DIR = golden_dir
    backend = _backend()
    manifests = {target_id: _load_manifest(target_id) for target_id in TARGET_IDS}
    report: dict[str, Any] = {
        "generated_at": _now_utc(),
        "classification": "display_smoke_and_saved_metadata_checks",
        "scientific_acceptance": "not_evaluated",
        "roadmap": "ROADMAP.md §10.3 five-target test card",
        "golden_cache_revision": 3,
        "golden_cache_revision_note": (
            "Revision 3: rebuilt from live IRSA DR1+QR3 after B10 "
            "(spherex_dr1/DR1, spherex_qr3/QR3, mixed/DR1+QR3 release labels), "
            "with re-measured dense 12-visit/band spectra and per-epoch "
            "telemetry sidecars. The real SkyView DSS2 Red / AllWISE overlays "
            "and Gaia DR3 pins were reused SHA-256-verified. No synthetic data "
            "is used in the five real target caches."
        ),
        "golden_dir": str(golden_dir),
        "method": (
            "Historical UI smoke checks using stretched WebP pixels and saved "
            "metadata. Ratios/RMS in display values are not physical flux ratios "
            "or variability significance. A pass never certifies target science."
        ),
        "w0_findings": W0_FINDINGS,
        "revision_3_build": {
            "source": "S7 rebuild log (2026-11-13)",
            "command": (
                "python scripts/build_golden_cache.py --target all "
                "--force-refresh --rebuild-spectrum --verbose"
            ),
            "started_at_utc": "2026-11-13T19:21:50Z",
            "completed_at_utc": "2026-11-13T20:00:31Z",
            "wall_clock_seconds": 2321.2,
            "result": "5/5 targets built, 0 failures",
            "transient_irsa_503_retries": 170,
            "verify_only_require_telemetry": "5/5 targets, 17/17 sidecars",
            "overlays": (
                "5/5 targets reused SHA-256-verified SkyView DSS2 Red / "
                "AllWISE / Gaia DR3 assets; no downloads were needed"
            ),
        },
        "stage2": _stage2_summary(manifests),
        "real_overlay_verification": _real_overlay_summary(manifests),
        "targets": {},
        "summary": {"pass": 0, "partial": 0, "fail": 0},
    }
    for target_id in TARGET_IDS:
        manifest = manifests[target_id]
        checks, caveats = CHECKERS[target_id](target_id, manifest, backend)
        passed = sum(1 for check in checks if check["passed"])
        if passed == len(checks):
            status = "pass"
        elif passed > 0:
            status = "partial"
        else:
            status = "fail"
        report["summary"][status] += 1
        report["targets"][target_id] = {
            "target_name": manifest.get("target_name"),
            "status": status,
            "checks_passed": passed,
            "checks_total": len(checks),
            "checks": checks,
            "epochs": [str(epoch["epoch_id"]) for epoch in manifest["epochs"]],
            "missing_bands_by_epoch": (
                manifest.get("data_quality") or {}
            ).get("missing_bands_by_epoch", {}),
            "halo_display_mode": bool(manifest.get("halo_display_mode")),
            "reference_overlays": sorted(
                (manifest.get("reference_overlays") or {}).keys()
            ),
            "telemetry": _telemetry_summary(manifest),
            "spectrum": _spectrum_counts(target_id),
            "caveats": caveats,
        }
        logger.info(
            "%s: %s (%d/%d checks)",
            target_id,
            status.upper(),
            passed,
            len(checks),
        )
    report["summary"]["total"] = len(TARGET_IDS)
    report["summary"]["result"] = (
        f"{report['summary']['pass']}/{len(TARGET_IDS)}"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the ROADMAP §10.3 five-target test card.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--golden-dir",
        type=Path,
        default=GOLDEN_DIR,
        help="Golden cache root.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "docs/five-target-display-smoke.json",
        help="Report path.",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    report = run_card(args.golden_dir.expanduser().resolve())
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["summary"], indent=2))
    print(f"report: {output}")
    return 0 if report["summary"]["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
