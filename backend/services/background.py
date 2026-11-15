"""Masked background estimation with a conservative, held-out 2D-plane gate.

This models smooth gradients, not arbitrary nebulosity. Selection thresholds
are fixed before inspecting validation targets; insufficient support is explicit.
"""
from dataclasses import dataclass

import numpy as np

from core.flags import BACKGROUND_EXCLUDE_MASK


@dataclass(frozen=True)
class BackgroundEstimate:
    model: np.ndarray
    metadata: dict


def _mad(values):
    values = np.asarray(values, dtype=float)
    return float(1.4826 * np.median(np.abs(values - np.median(values))))


def estimate_background(image: np.ndarray, flags: np.ndarray) -> BackgroundEstimate:
    image = np.asarray(image, dtype=float)
    clean = np.isfinite(image) & ((flags & BACKGROUND_EXCLUDE_MASK) == 0)
    count = int(clean.sum())
    info = {"method": "none", "status": "insufficient", "clean_pixels": count,
            "valid_cells": 0, "subtracted": False}
    if count < 11:
        return BackgroundEstimate(np.zeros_like(image), info)
    # A handful of clean pixels in one corner is not a supported background
    # for the whole cutout, even if its median is numerically defined.
    cy, cx = np.nonzero(clean)
    ny, nx = image.shape
    quadrants = set(zip(cx >= nx/2, cy >= ny/2))
    info.update(clean_fraction=count / image.size, covered_quadrants=len(quadrants))
    if count < .05 * image.size or len(quadrants) < 3 or np.ptp(cx) < .5 * (nx-1) or np.ptp(cy) < .5 * (ny-1):
        info["status"] = "insufficient_spatial_support"
        return BackgroundEstimate(np.zeros_like(image), info)
    scalar = float(np.median(image[clean]))
    info.update(method="masked_median", status="ok_scalar", subtracted=True,
                scalar_mjy_sr=scalar, robust_scatter_mjy_sr=_mad(image[clean]))
    result = np.full_like(image, scalar)
    ny, nx = image.shape
    if min(ny, nx) < 16 or count < 128:
        info["status"] = "scalar_limited_support"
        return BackgroundEstimate(result, info)
    yy, xx = np.indices(image.shape)
    xn, yn = (xx - (nx - 1)/2) / max(nx-1, 1), (yy - (ny - 1)/2) / max(ny-1, 1)
    cells, medians, errors, parity = [], [], [], []
    for iy, ys in enumerate(np.array_split(np.arange(ny), 4)):
        for ix, xs in enumerate(np.array_split(np.arange(nx), 4)):
            region = np.ix_(ys, xs)
            good = clean[region]
            if good.sum() < max(8, good.size * .2):
                continue
            values = image[region][good]
            cells.append([1., float(np.median(xn[region][good])), float(np.median(yn[region][good]))])
            medians.append(float(np.median(values)))
            errors.append(1.2533 * _mad(values) / np.sqrt(good.sum()))
            parity.append((ix + iy) % 2)
    info["valid_cells"] = len(cells)
    if len(cells) < 12:
        info["status"] = "scalar_limited_support"
        return BackgroundEstimate(result, info)
    design, values = np.asarray(cells), np.asarray(medians)
    parity = np.asarray(parity)
    if np.ptp(design[:, 1]) < .5 or np.ptp(design[:, 2]) < .5:
        info["status"] = "scalar_limited_support"
        return BackgroundEstimate(result, info)
    baseline, residual = [], []
    for fold in (0, 1):
        train, test = parity == fold, parity != fold
        if train.sum() < 4 or np.linalg.matrix_rank(design[train]) < 3:
            return BackgroundEstimate(result, info)
        coefficients = np.linalg.lstsq(design[train], values[train], rcond=None)[0]
        baseline.extend(values[test] - np.median(values[train]))
        residual.extend(values[test] - design[test] @ coefficients)
    # Use absolute held-out error, including offsets, rather than demeaning
    # away a biased fit. A scalar remains preferable for an unsupported slope.
    scalar_error = float(np.median(np.abs(baseline)))
    plane_error = float(np.median(np.abs(residual)))
    coefficients = np.linalg.lstsq(design, values, rcond=None)[0]
    for _ in range(3):
        delta = values - design @ coefficients
        spread = _mad(delta)
        keep = np.abs(delta - np.median(delta)) <= max(3 * spread, np.finfo(float).eps)
        if keep.sum() < 8 or np.linalg.matrix_rank(design[keep]) < 3:
            break
        coefficients = np.linalg.lstsq(design[keep], values[keep], rcond=None)[0]
    amplitude = float(abs(coefficients[1]) + abs(coefficients[2]))
    info.update(scalar_holdout_abs_mjy_sr=scalar_error, plane_holdout_abs_mjy_sr=plane_error,
                candidate_gradient_mjy_sr=amplitude)
    if scalar_error > 0 and plane_error <= .9 * scalar_error and amplitude > 3 * float(np.median(errors)):
        result = coefficients[0] + coefficients[1] * xn + coefficients[2] * yn
        info.update(method="masked_plane_2d", status="ok_2d", coefficients=coefficients.tolist())
    return BackgroundEstimate(result, info)
