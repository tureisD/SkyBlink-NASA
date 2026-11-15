"""Conservative live blink selection from measured spectral WCS samples.

This bounded visual-comparison gate is not calibrated spectral matching.
The full raw-data/background/PSF validation remains a separate science task.
"""
from itertools import combinations
from io import BytesIO
from typing import Callable
from heapq import nsmallest

import numpy as np
from astropy import units as u
from astropy.io import fits
from astropy.wcs import WCS
from scipy.spatial import cKDTree

from services.irsa_client import IRSANoData, IRSAUnavailable


def _footprint_vectors(record):
    """Use recorded corner order (including orientation); never infer wavelengths."""
    tokens = str(getattr(record, "s_region", None) or "").split()
    if tokens[:2] != ["POLYGON", "ICRS"]:
        return None
    try:
        vertices = np.asarray([float(value) for value in tokens[2:]]).reshape(-1, 2)
    except ValueError:
        return None
    if len(vertices) == 5 and np.allclose(vertices[0], vertices[-1], rtol=0, atol=1e-10):
        vertices = vertices[:-1]
    if vertices.shape != (4, 2) or not np.all(np.isfinite(vertices)) or np.any(np.abs(vertices[:, 1]) > 90):
        return None
    ra, dec = np.deg2rad(vertices).T
    return np.column_stack((np.cos(dec)*np.cos(ra), np.cos(dec)*np.sin(ra), np.sin(dec)))


def ranked_candidate_pairs(epochs, fallback_candidates, max_pairs=24, check_deadline=None):
    """Rank cross-epoch pairs before downloading, retaining both sides together.

    Similar corresponding detector corners favor similar target detector
    positions and roll. This is only an acquisition heuristic: every selected
    product still passes measured coarse/dense WCS and usable-pixel checks.
    SIA detector-wide em_min/em_max are deliberately not local wavelengths.
    Eight nearest flattened-corner neighbors per exposure form a bounded
    shortlist, reranked by mean corner separation. This approximate heuristic
    does not promise the globally closest pair. Without footprints, use the
    existing bounded visit sample, balanced by pair.
    """
    check = check_deadline or (lambda: None)
    vectors = {}
    for epoch in epochs:
        for index, record in enumerate(epoch.records):
            if index % 64 == 0:
                check()
            vectors[record] = _footprint_vectors(record)
    ranked = []
    for later, earlier in combinations(reversed(epochs), 2):
        for band in range(1, 7):
            check()
            left = sorted((r for r in earlier.records if r.band == band and vectors[r] is not None), key=lambda r:r.uri)
            right = sorted((r for r in later.records if r.band == band and vectors[r] is not None), key=lambda r:r.uri)
            if left and right:
                tree = cKDTree(np.array([vectors[r].ravel() for r in right]))
                neighbors = tree.query(np.array([vectors[r].ravel() for r in left]),
                                       k=list(range(1, min(8, len(right))+1)))[1]
                check()
                def neighbor_pairs():
                    for index, first in enumerate(left):
                        if index % 64 == 0:
                            check()
                        for other in neighbors[index]:
                            second = right[int(other)]
                            score = float(np.mean(np.linalg.norm(vectors[first]-vectors[second], axis=1)))
                            yield (score, first, second, "recorded_footprint_neighbor_shortlist")
                ranked.extend(nsmallest(4, neighbor_pairs(), key=lambda row:(row[0],-row[2].mjd_mid,-row[1].mjd_mid,row[1].uri,row[2].uri)))
            for first in fallback_candidates.get((earlier.epoch_id, band), []):
                for second in fallback_candidates.get((later.epoch_id, band), []):
                    if vectors[first] is None or vectors[second] is None:
                        ranked.append((float("inf"), first, second, "balanced_time_sample_without_footprints"))
    ranked.sort(key=lambda row: (row[0], -row[2].mjd_mid, -row[1].mjd_mid, row[1].band, row[1].uri, row[2].uri))
    # Avoid spending the entire bounded search on near-duplicate candidates of
    # one detector. Each detector/epoch pair contributes at most four attempts.
    counts = {}
    record_epochs = {r: epoch.epoch_id for epoch in epochs for r in epoch.records}
    result = []
    fallback_reserve = min(2, max_pairs, sum(not np.isfinite(row[0]) for row in ranked))
    geometry_count = 0
    for score, first, second, method in ranked:
        is_geometry = bool(np.isfinite(score))
        if is_geometry and geometry_count >= max_pairs - fallback_reserve:
            continue
        group = (record_epochs[first], record_epochs[second], first.band)
        if is_geometry and counts.get(group, 0) >= 4:
            continue
        counts[group] = counts.get(group, 0) + 1
        geometry_count += int(is_geometry)
        result.append({"first": first, "second": second, "method": method,
                       "corner_chord_distance": score if np.isfinite(score) else None})
        if len(result) >= max_pairs:
            break
    return result


def spectral_signature(content: bytes, ra: float, dec: float, size: float) -> np.ndarray:
    """Return wavelength/bandwidth at a 3x3 tangent-plane grid in microns."""
    return _signature(content, ra, dec, size, 3, .9)


def dense_spectral_signature(content: bytes, ra: float, dec: float, size: float) -> np.ndarray:
    """Evaluate the exact contract-grid pixels retained by field_pixel_mask."""
    grid = WCS(naxis=2)
    grid.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    grid.wcs.crval = [ra, dec]
    grid.wcs.crpix = [120.5, 120.5]
    grid.wcs.cdelt = [-0.0008541667, 0.0008541667]
    yy, xx = np.indices((240, 240))
    retained = field_pixel_mask(size)
    return _sample_signature(content, grid.pixel_to_world(xx[retained], yy[retained]))


def field_pixel_mask(size: float) -> np.ndarray:
    """The same fixed TAN-plane crop used by measurement and display coadds."""
    yy, xx = np.indices((240, 240))
    return (np.abs(xx - 119.5) * 0.0008541667 <= size / 2) & (np.abs(yy - 119.5) * 0.0008541667 <= size / 2)


def _signature(content, ra, dec, size, side, extent):
    grid = WCS(naxis=2)
    grid.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    grid.wcs.crval = [ra, dec]
    grid.wcs.crpix = [(side + 1)/2, (side + 1)/2]
    # Sample the requested field out to 90% of its width, avoiding rounding
    # at cutout boundaries. Both exposures must cover every sample.
    step = size * extent / (side - 1)
    grid.wcs.cdelt = [-step, step]
    yy, xx = np.indices((side, side))
    positions = grid.pixel_to_world(xx.ravel(), yy.ravel())
    return _sample_signature(content, positions)


def _sample_signature(content, positions):
    with fits.open(BytesIO(content), memmap=False) as hdul:
        header = hdul["IMAGE"].header
        spatial = WCS(header)
        x, y = spatial.world_to_pixel(positions)
        ny, nx = hdul["IMAGE"].data.shape
        inside = (x >= 0) & (y >= 0) & (x <= nx - 1) & (y <= ny - 1)
        spectral = WCS(header, fobj=hdul, key="W")
        spectral.sip = None
        wave, width = spectral.pixel_to_world(x, y)
        result = np.array([wave.to_value(u.um), width.to_value(u.um)])
        result[:, ~inside] = np.nan
        return result


def compatible(first: np.ndarray, second: np.ndarray) -> bool:
    """Every sample: centre shift <=1/4 narrower width, widths within 20%."""
    return bool(
        np.all(np.isfinite(first)) and np.all(np.isfinite(second))
        and np.all(first > 0) and np.all(second > 0)
        and np.all(np.minimum(first[1], second[1]) >= .8 * np.maximum(first[1], second[1]))
        and np.all(np.abs(first[0] - second[0]) <= 0.25 * np.minimum(first[1], second[1]))
    )


def select_pair(epochs, candidates: dict, contents: dict, ra: float, dec: float,
                size: float, check_deadline: Callable[[], None], is_usable: Callable | None = None):
    """Choose the most recent usable pair with identical band composition.

    Inputs are an explicitly bounded visit sample, not exhaustive coverage.
    Missing downloads raise upstream errors in the caller, not a fake epoch.
    """
    signatures = {}
    dense = {}
    for record, content in contents.items():
        check_deadline()
        try:
            signatures[record] = spectral_signature(content, ra, dec, size)
        except (KeyError, ValueError, TypeError, OSError) as exc:
            raise IRSAUnavailable("A downloaded cutout has invalid spectral WCS; comparison could not be checked.") from exc
    for later, earlier in combinations(reversed(epochs), 2):
        selected = {}
        for band in range(1, 7):
            pairs = []
            for a in candidates.get((earlier.epoch_id, band), []):
                for b in candidates.get((later.epoch_id, band), []):
                    check_deadline()
                    if a in signatures and b in signatures and compatible(signatures[a], signatures[b]):
                        distance = float(np.max(np.abs(signatures[a][0] - signatures[b][0])))
                        pairs.append((distance, a, b))
            # Preserve the minimum-distance decision, but validate in that
            # order and stop after its first valid pair. There is no reason to
            # reproject worse candidates once the best admissible pair exists.
            for _, a, b in sorted(pairs, key=lambda item: item[0]):
                for record in (a, b):
                    if record not in dense:
                        check_deadline()
                        dense[record] = dense_spectral_signature(contents[record], ra, dec, size)
                if not compatible(dense[a], dense[b]):
                    continue
                if is_usable is not None and (not is_usable(a) or not is_usable(b)):
                    continue
                selected[(earlier.epoch_id, band)] = [a]
                selected[(later.epoch_id, band)] = [b]
                break
        if selected:
            return [earlier, later], compact_selection([earlier, later], selected)
    raise IRSANoData(
        "No spectrally comparable epoch pair was found in the bounded live sample. "
        "Try a smaller field; additional archive observations may still be available.",
        collections_tried=sorted({r.collection for r in contents}),
        detail={"ra": ra, "dec": dec, "reason": "NO_COMPARABLE_EPOCHS",
                "candidate_epochs": [e.epoch_id for e in epochs],
                "wavelength_tolerance": "quarter of narrower bandwidth and width ratio >=0.8 over the output field"},
    )


def compact_selection(epochs, selected: dict, max_span_days: float = 30.0) -> dict:
    """Largest common band subset spanning <=30 days in EACH epoch.

    One exposure per band avoids within-band temporal smearing. The remaining
    composite is not simultaneous; actual min/max MJD must accompany it.
    """
    bands = sorted({band for _, band in selected})
    for count in range(len(bands), 0, -1):
        for subset in combinations(bands, count):
            keep = {key: value for key, value in selected.items() if key[1] in subset}
            valid = True
            for epoch in epochs:
                records = [record for (eid, _), values in keep.items() if eid == epoch.epoch_id for record in values]
                if not records or max(r.mjd_mid for r in records) - min(r.mjd_mid for r in records) > max_span_days:
                    valid = False
                    break
            if valid:
                return keep
    return {}
