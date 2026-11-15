"""LVF dispersion geometry from ``WCS-WAVE`` (B8, contract 1.1.0).

SPHEREx does not have a filter wheel: the linear-variable filter maps detector
position to wavelength.  For the LVF visualizer we need, per detector, the
direction and size of the wavelength gradient at the target position on the
sky:

* ``grad_um_per_arcsec`` — |grad(lambda)| in micrometres per arcsecond;
* ``pa_deg`` — position angle of increasing wavelength, East of North
  (``atan2(g_east, g_north)``, 0 deg = North, 90 deg = East).

The gradient is measured in detector pixels from ``WCS(..., key="W")`` with
``sip = None`` (LAW 3), then mapped onto the local sky tangent plane with the
``IMAGE`` spatial WCS.  Evaluating one pixel in +x and +y is enough because
the LVF is linear over a pixel; no smoothing or invented values are used.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from typing import Any

import astropy.units as u
import numpy as np
from astropy.wcs import WCS

ARCSEC_PER_DEG = 3600.0


def _wave_um(value: Any) -> float:
    """Extract the wavelength (first element) in micrometres."""
    if isinstance(value, (list, tuple)):
        value = value[0]
    return float(value.to(u.micrometer).value)


def _wrap_delta_deg(delta: float) -> float:
    return ((float(delta) + 180.0) % 360.0) - 180.0


def geometry_at(
    spectral_wcs: WCS,
    spatial_wcs: WCS,
    x: float,
    y: float,
    *,
    step: float = 1.0,
) -> tuple[float, float] | None:
    """Return ``(pa_deg, grad_um_per_arcsec)`` at detector pixel ``(x, y)``.

    ``spectral_wcs`` must be the ``WCS-WAVE`` WCS.  This helper defensively
    clears the SIP distortion again before use so a caller cannot corrupt the
    spectral lookup (LAW 3).  Returns ``None`` when the position is not on the
    detector or any value is non-finite/non-positive.
    """
    if spectral_wcs is None or spatial_wcs is None:
        return None
    try:
        x = float(x)
        y = float(y)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(x) and math.isfinite(y)):
        return None

    try:
        spectral_wcs.sip = None
        wave0 = _wave_um(spectral_wcs.pixel_to_world(x, y))
        wave_x = _wave_um(spectral_wcs.pixel_to_world(x + step, y))
        wave_y = _wave_um(spectral_wcs.pixel_to_world(x, y + step))

        sky0 = spatial_wcs.pixel_to_world(x, y)
        sky_x = spatial_wcs.pixel_to_world(x + step, y)
        sky_y = spatial_wcs.pixel_to_world(x, y + step)
    except Exception:  # noqa: BLE001 - a failed lookup is "no geometry"
        return None

    try:
        ra0 = float(sky0.ra.deg)
        dec0 = float(sky0.dec.deg)
        cos_dec = math.cos(math.radians(dec0))
        if not math.isfinite(cos_dec) or abs(cos_dec) < 1e-12:
            return None

        def _offset(sky: Any) -> tuple[float, float]:
            dra = _wrap_delta_deg(float(sky.ra.deg) - ra0)
            ddec = float(sky.dec.deg) - dec0
            return dra * cos_dec * ARCSEC_PER_DEG, ddec * ARCSEC_PER_DEG

        xi_x, eta_x = _offset(sky_x)
        xi_y, eta_y = _offset(sky_y)

        d_wave_dx = wave_x - wave0
        d_wave_dy = wave_y - wave0

        # J = [[xi_x, xi_y], [eta_x, eta_y]] maps detector pixel steps to the
        # sky tangent plane (arcsec per pixel).  The sky gradient is
        # J^-T * (dlambda/dx, dlambda/dy); solving the 2x2 system avoids
        # silently treating "per pixel" as "per arcsec".
        determinant = xi_x * eta_y - xi_y * eta_x
        if not math.isfinite(determinant) or abs(determinant) < 1e-12:
            return None
        g_east = (eta_y * d_wave_dx - eta_x * d_wave_dy) / determinant
        g_north = (-xi_y * d_wave_dx + xi_x * d_wave_dy) / determinant
    except (AttributeError, TypeError, ValueError):
        return None

    grad = math.hypot(g_east, g_north)
    if not (math.isfinite(grad) and grad > 0.0):
        return None
    pa_deg = math.degrees(math.atan2(g_east, g_north)) % 360.0
    if not (math.isfinite(pa_deg) and math.isfinite(grad)):
        return None
    return pa_deg, grad


def circular_mean(
    pa_deg_values: Iterable[float],
    grad_values: Iterable[float],
) -> tuple[float, float] | None:
    """Magnitude-weighted circular mean of one detector's per-visit geometry.

    The mean vector is the correct way to average directions; the resulting
    magnitude is ``hypot(mean(g sin PA), mean(g cos PA))``.  Entries are not
    weighted by exposure time because none is available in the manifest; each
    usable visit contributes equally.  Returns ``None`` when no finite,
    positive entry exists.
    """
    east: list[float] = []
    north: list[float] = []
    for pa_deg, grad in zip(pa_deg_values, grad_values):
        try:
            pa = math.radians(float(pa_deg))
            magnitude = float(grad)
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(pa) and math.isfinite(magnitude) and magnitude > 0.0):
            continue
        east.append(magnitude * math.sin(pa))
        north.append(magnitude * math.cos(pa))
    if not east:
        return None
    magnitude = math.hypot(float(np.mean(east)), float(np.mean(north)))
    if not (math.isfinite(magnitude) and magnitude > 0.0):
        return None
    pa_deg = math.degrees(math.atan2(float(np.mean(east)), float(np.mean(north))))
    return pa_deg % 360.0, magnitude


def aggregate_epoch_geometry(
    entries: Sequence[tuple[int, Sequence[float], Sequence[float]]],
) -> list[dict[str, float | int]]:
    """Build the ``epochs[].lvf_geometry`` payload.

    ``entries`` is ``(detector, pa_values, grad_values)`` per band/epoch.
    Missing or non-finite detectors are omitted, never fabricated.
    """
    payload: list[dict[str, float | int]] = []
    for detector, pa_values, grad_values in entries:
        result = circular_mean(pa_values, grad_values)
        if result is None:
            continue
        pa_deg, grad = result
        payload.append(
            {
                "detector": int(detector),
                "pa_deg": float(pa_deg),
                "grad_um_per_arcsec": float(grad),
            }
        )
    payload.sort(key=lambda item: int(item["detector"]))
    return payload


__all__ = [
    "aggregate_epoch_geometry",
    "circular_mean",
    "geometry_at",
]
