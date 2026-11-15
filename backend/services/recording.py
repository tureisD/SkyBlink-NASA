"""Pipeline adapters for scientific lineage. Raw bytes stay outside served assets."""
from dataclasses import asdict
from pathlib import Path
import hashlib
import math

import numpy as np

from core.config import settings
from services import provenance


def json_values(value):
    """Explicitly encode unavailable diagnostics as null; arrays are not serialized."""
    if isinstance(value, dict):
        return {str(key): json_values(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_values(item) for item in value]
    if isinstance(value, (np.integer, np.bool_)):
        return value.item()
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(value) else None
    return value


def discovery_identity(value):
    """Transport timestamps belong in the envelope, not scientific identity."""
    if isinstance(value, dict):
        return {key: discovery_identity(item) for key, item in value.items()
                if key not in {"retrieved_at", "elapsed_seconds"}}
    if isinstance(value, list):
        return [discovery_identity(item) for item in value]
    return value


def retain_inputs(contents, ra: float, dec: float, size: float, *, acquisition=None):
    from services.irsa_client import canonical_cutout_position
    serialized_ra, serialized_dec = canonical_cutout_position(ra, dec)
    receipts = {item.get("source_url", item.get("url")): item for item in (acquisition or [])}
    result = {}
    for record, content in sorted(contents.items(), key=lambda item: (item[0].mjd_lower, item[0].band, item[0].uri)):
        result[record] = provenance.store_input(
            content, settings.cache_dir / "analysis-inputs",
            source_url=record.cutout_url(ra, dec, size),
            cutout={"ra": serialized_ra, "dec": serialized_dec, "size_deg": round(size, 6)},
            retrieved_at=receipts.get(record.cutout_url(ra, dec, size), {}).get("retrieved_at"),
        )
    return result


def unique_inputs(descriptors):
    unique = {item["sha256"]: item for item in descriptors.values()}
    return [unique[key] for key in sorted(unique)]


def plane_digest(array, *, flags=False):
    data = np.array(array, dtype="<u4" if flags else "<f8", copy=True, order="C")
    if not flags:
        data[np.isnan(data)] = np.nan  # Canonicalize NaN payload bits.
    return hashlib.sha256(data.tobytes(order="C")).hexdigest()


def science_planes(coadds):
    return {
        f"{epoch_id}:D{band}": {
            "measurement_sha256": plane_digest(coadd.image_mjy_sr),
            "variance_sha256": plane_digest(coadd.variance_mjy_sr2),
            "flags_sha256": plane_digest(coadd.flags, flags=True),
            "normalized_display_sha256": plane_digest(coadd.normalized_image_mjy_sr),
            "finite_measurement_pixels": int(np.count_nonzero(np.isfinite(coadd.image_mjy_sr))),
        }
        for (epoch_id, band), coadd in sorted(coadds.items())
    }


def product_assets(product, asset_dir):
    names = {name for epoch in product["epochs"] for name in epoch["frames"].values()}
    names.update(epoch["telemetry"]["url"] for epoch in product["epochs"] if epoch.get("telemetry"))
    names.update(name for pair in product.get("differences", {}).values() for name in pair["frames"].values())
    return {name: provenance.content_hash((asset_dir / name).read_bytes()) for name in sorted(names)}


def freeze_product_assets(product, asset_dir: Path):
    """Publish content-named copies so a refresh cannot change an old result.

    Render scratch names remain internal. Keep filename prefixes/suffixes for
    telemetry validation and retain prior content until explicit cache cleanup.
    """
    from core.cachekeys import is_valid_filename
    mapping = {}
    def freeze(name):
        if name in mapping:
            return mapping[name]
        if not is_valid_filename(name):
            raise provenance.ProvenanceError("Invalid rendered asset filename")
        content = (asset_dir / name).read_bytes()
        digest = provenance.content_hash(content)
        suffix = "".join(Path(name).suffixes)
        stem = name[:-len(suffix)] if suffix else name
        frozen = name if stem.endswith("_" + digest) else f"{stem}_{digest}{suffix}"
        destination = asset_dir / frozen
        if destination.exists():
            if provenance.content_hash(destination.read_bytes()) != digest:
                raise provenance.ProvenanceError("Content-addressed output has changed")
        else:
            provenance._publish_bytes(destination, content)
        mapping[name] = frozen
        return frozen
    for epoch in product["epochs"]:
        epoch["frames"] = {key: freeze(name) for key, name in epoch["frames"].items()}
        if epoch.get("telemetry"):
            epoch["telemetry"]["url"] = freeze(epoch["telemetry"]["url"])
    for pair in product.get("differences", {}).values():
        pair["frames"] = {key: freeze(name) for key, name in pair["frames"].items()}


def image_method(*, halo_display_mode: bool, field_size_deg: float):
    from core import flags
    from services.spherex_pipeline import CACHE_VERSION, CDELT_DEG, ASINH_A
    return {
        "name": "matched_image_comparison", "version": CACHE_VERSION,
        "halo_display_mode": halo_display_mode, "field_size_deg": field_size_deg,
        "output_grid": {"width": 240, "height": 240, "cdelt_deg": CDELT_DEG, "crpix": 120.5},
        "measurement_exclude_mask": int(flags.PHOTOMETRY_EXCLUDE_MASK),
        "display_bad_mask": int(flags.HALO_DISPLAY_BAD_MASK if halo_display_mode else flags.HARD_BAD_MASK),
        "cross_band_combination": "finite_pixel_mean",
        "spectral_gate": {"narrower_bandwidth_fraction": .25, "minimum_bandwidth_ratio": .8},
        "maximum_within_epoch_span_days": 30, "asinh_a": ASINH_A,
        "verification": "exact_float64_plane_and_flag_hashes_in_recorded_environment",
        "asset_naming": "content_sha256",
        "science_validation": "not_established_by_replay",
    }


def publish_record(asset_dir: Path, product: dict, record: dict, filename: str):
    # Keep an internal current alias, but public links identify immutable content.
    provenance.write_record(asset_dir / filename, record)
    filename = f"analysis_{record['analysis_id'].removeprefix('sha256:')}.json"
    provenance.write_record(asset_dir / filename, record)
    product["analysis_record"] = filename
    product["provenance"].update({
        "generated_at": product["generated_at"],
        "analysis_id": record["analysis_id"],
        "analysis_record_url": f"/api/v1/assets/{product['asset_key']}/{filename}",
        "processing_version": f"{record['identity']['method']['name']}/{record['identity']['method']['version']}",
    })


def record_images(product, contents, all_records, candidate_selection, selected_selection,
                  processed_epochs, coadds, *, ra, dec, download_size, field_size,
                  halo_display_mode, asset_dir, discovery=None, acquisition=None):
    freeze_product_assets(product, asset_dir)
    descriptors = retain_inputs(contents, ra, dec, download_size, acquisition=acquisition)
    record_epochs = {record: epoch_id for (epoch_id, _), values in candidate_selection.items() for record in values}
    attempted = {record for values in selected_selection.values() for record in values}
    used = {record for epoch in processed_epochs for record in epoch.records
            if (epoch.epoch_id, record.band) in coadds}
    exposures = [{
        "input_sha256": descriptors[record]["sha256"], "epoch_id": record_epochs[record],
        "detector": record.band, "extraction": {"ra": ra, "dec": dec},
        "artifact": asdict(record), "selected": record in used, "selection_attempted": record in attempted,
        "selection_reason": ("SELECTED_COMPARABLE_INPUT" if record in used else
                             "NO_USABLE_OUTPUT_BAND" if record in attempted else "NOT_SELECTED_BY_BOUNDED_MATCHER"),
    } for record in sorted(contents, key=lambda item: (record_epochs[item], item.band, item.mjd_lower, item.uri))]
    record = provenance.make_record(
        kind="image", query=dict(product["query"], asset_key=product["asset_key"]), inputs=unique_inputs(descriptors), exposures=exposures,
        method=image_method(halo_display_mode=halo_display_mode, field_size_deg=field_size),
        selection=json_values({
            "scope": discovery_identity(discovery) or {"source": "query_artifacts_returned_records", "raw_query_response_retained": False},
            "discovered_records": [asdict(item) for item in all_records],
            "candidate_selection": [{"epoch_id": eid, "detector": band, "uris": [r.uri for r in values]}
                                    for (eid, band), values in candidate_selection.items()],
            "missing_downloads": [asdict(item) for values in candidate_selection.values() for item in values if item not in contents],
            "selected_epochs": [dict(asdict(epoch), records=[asdict(r) for r in epoch.records]) for epoch in processed_epochs],
            "comparison": product["comparison_selection"],
            "live_acquisition": product.get("live_selection"),
        }),
        outputs={"science_planes": science_planes(coadds), "normalization": json_values(product["normalization"]),
                 "band_diagnostics": json_values({epoch["epoch_id"]: epoch.get("band_stats", {}) for epoch in product["epochs"]}),
                 "assets": product_assets(product, asset_dir)},
        created_at=product["generated_at"],
        acquisition=json_values({"discovery": discovery, "cutouts": acquisition}),
    )
    publish_record(asset_dir, product, record, "image_analysis.json")
    return record
