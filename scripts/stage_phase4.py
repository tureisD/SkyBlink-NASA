"""Build a separate Phase 4 review set from real, recorded exposure URIs.

This is a partial pinned inventory, never a claim of complete archive discovery.
No approved golden asset is modified or automatically promoted.
"""
from __future__ import annotations

import argparse
import io
import json
import math
import shutil
import sys
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from astropy.io import fits  # noqa: E402
from core.config import settings  # noqa: E402
from core.target_profiles import corrected_targets  # noqa: E402
from services.irsa_client import ArtifactRecord, IRSAUnavailable, IrsaClient  # noqa: E402
from services.provenance import (ProvenanceError, canonical_json, content_hash, store_input, store_key,
                                 utc_now, validate_source_url)  # noqa: E402


@dataclass(frozen=True)
class ProductLocator:
    """Download locator only: no invented exposure time or detector metadata."""
    uri: str

    @property
    def access_url(self) -> str:
        return self.uri if self.uri.startswith("https://") else "https://irsa.ipac.caltech.edu/" + self.uri.lstrip("/")

    def cutout_url(self, ra: float, dec: float, size_deg: float, **kwargs: Any) -> str:
        validate_source_url(self.access_url)
        if "?" in self.access_url:
            raise ProvenanceError("Snapshot URIs must identify original products, not nested cutouts")
        return f"{self.access_url}?center={ra:.6f},{dec:.6f}&size={size_deg:.6f}"


def recorded_uris(manifest: dict[str, Any]) -> list[str]:
    found: dict[str, None] = {}
    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "artifact_uris":
                    if not isinstance(item, list) or not all(isinstance(uri, str) for uri in item):
                        raise ProvenanceError("Historical artifact URI index is malformed")
                    for uri in item:
                        validate_source_url(ProductLocator(uri).access_url)
                        found[uri] = None
                else:
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(manifest)
    return list(found)


def record_from_fits(uri: str, content: bytes) -> tuple[ArtifactRecord, dict[str, Any]]:
    """Read actual observation dates/detector; no dates inferred from filenames."""
    validate_source_url(ProductLocator(uri).access_url)
    with fits.open(io.BytesIO(content), memmap=False, cache=False) as hdul:
        required = {"IMAGE", "FLAGS", "VARIANCE", "ZODI", "WCS-WAVE"}
        if not required.issubset({str(hdu.name).upper() for hdu in hdul}):
            raise ProvenanceError("Snapshot input lacks required SPHEREx science extensions")
        header = hdul["IMAGE"].header
        timesys = str(header.get("TIMESYS", "")).strip().upper()
        if timesys != "UTC":
            raise ProvenanceError(f"Unverified FITS time system {timesys!r}; expected recorded UTC")
        begin, end = float(header["MJD-BEG"]), float(header["MJD-END"])
        detector = int(header["DETECTOR"])
        if not (math.isfinite(begin) and math.isfinite(end) and 40000 < begin <= end < 100000):
            raise ProvenanceError("Invalid actual FITS exposure time range")
        if detector != header["DETECTOR"] or not 1 <= detector <= 6:
            raise ProvenanceError("Invalid actual FITS detector")
        metadata = {"mjd_begin": begin, "mjd_end": end, "time_scale": "utc",
                    "detector": detector, "observation_id": str(header.get("OBSID", "")),
                    "date_obs": str(header.get("DATE-OBS", "")),
                    "processing_date": str(header.get("DATE", ""))}
    release = "DR1" if "/dr1/" in uri.lower() else "QR3" if "/qr3/" in uri.lower() else None
    if release is None:
        raise ProvenanceError("Snapshot is not a current DR1/QR3 exposure")
    return ArtifactRecord(uri=uri, mjd_lower=begin, mjd_upper=end, band=detector,
                          band_name=f"SPHEREx-D{detector}", planeid=metadata["observation_id"],
                          release=release, collection=f"spherex_{release.lower()}",
                          contentlength=len(content)), metadata


class PinnedArchive:
    """Production-compatible adapter with explicit partial discovery provenance."""
    def __init__(self, *, target, uris: list[str], config, deadline_at: float,
                 max_inputs: int = 0, offline: bool = False, input_stages: list[Path] | None = None):
        self.target = target
        self.ra, self.dec = target.ra_epoch2025, target.dec_epoch2025
        self.client = IrsaClient(config, deadline_at=deadline_at)
        self.config = config
        self.offline = offline
        self.input_stages = input_stages or []
        self.records: list[ArtifactRecord] = []
        self.content: dict[str, bytes] = {}
        if max_inputs and len(uris) > max_inputs:
            indices = ([0] if max_inputs == 1 else
                       [round(index * (len(uris) - 1) / (max_inputs - 1)) for index in range(max_inputs)])
            selected = [uris[index] for index in indices]
        else:
            selected = uris
        self.selected_uris = selected
        self.discovery_metadata = {
            "method": "historical_golden_recorded_uri_snapshot",
            "complete_archive_discovery": False,
            "limitation": "Only image contributor URIs recorded in the older saved manifest; spectrum-only/unrecorded archive visits are absent.",
            "initial_uri_count": len(uris), "initial_uris": uris,
            "attempted_uri_count": len(selected), "attempted_uris": selected,
            "max_inputs": max_inputs or None,
            "omitted_by_bound": [uri for uri in uris if uri not in selected],
            "bound_selection": "evenly spaced original manifest order; no flux-based selection",
            "verified_exposures": [], "failed_inputs": [], "cutout_requests": [],
        }

    def _seed_exact_cache(self, locator: ProductLocator, size_deg: float) -> None:
        """Reuse Phase 3 bytes only if the exact archive cutout URL matches."""
        destination = self.client._cutout_cache_path(locator, self.ra, self.dec, size_deg)
        if destination.exists():
            return
        manifest = ROOT / "docs/evidence/phase3/phase3-science-results.json"
        wanted = locator.cutout_url(self.ra, self.dec, size_deg)
        for stage_root in self.input_stages:
            prior = json.loads((stage_root / "stage-report.json").read_text(encoding="utf-8"))
            for target in prior["targets"]:
                for descriptor in target.get("discovery", {}).get("cutout_requests", []):
                    if descriptor["source_url"] != wanted:
                        continue
                    digest = descriptor["sha256"]
                    if descriptor["store_key"] != store_key(digest):
                        raise ProvenanceError("Retained stage input has an unsafe store key")
                    source_root = (stage_root / "cache/analysis-inputs").resolve()
                    source = (source_root / descriptor["store_key"]).resolve()
                    if not source.is_relative_to(source_root):
                        raise ProvenanceError("Retained stage input escapes its content store")
                    content = source.read_bytes()
                    if len(content) != descriptor["size_bytes"] or content_hash(content) != digest:
                        raise ProvenanceError("Retained stage input hash mismatch")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(content)
                    return
            # An interrupted stage may have retained bytes before publishing its
            # report. The URL-derived cache key and content-addressed object must
            # both exist and agree; no unverified cache file alone is accepted.
            old_cache = (stage_root / "cache/cutouts" / destination.name).resolve()
            if not old_cache.is_relative_to(stage_root.resolve()):
                raise ProvenanceError("Retained cutout path escapes its stage")
            if old_cache.is_file():
                content = old_cache.read_bytes()
                digest = content_hash(content)
                retained_root = (stage_root / "cache/analysis-inputs").resolve()
                retained = (retained_root / store_key(digest)).resolve()
                if not retained.is_relative_to(retained_root):
                    raise ProvenanceError("Retained object path escapes its stage")
                if retained.is_file() and retained.read_bytes() == content:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(content)
                    return
        if not manifest.is_file():
            return
        for sample in json.loads(manifest.read_text(encoding="utf-8"))["samples"]:
            if sample.get("download_status") != "success":
                continue
            candidate = ProductLocator(sample["uri"]).cutout_url(sample["ra"], sample["dec"], sample["fetch_size_deg"])
            if candidate != wanted:
                continue
            source = (ROOT / sample["path"]).resolve()
            if not source.is_relative_to((ROOT / "backend/.cache/phase3").resolve()):
                raise ProvenanceError("Audit input path escapes its expected cache")
            if source.is_file():
                content = source.read_bytes()
                if len(content) != sample["bytes"] or content_hash(content) != sample["sha256"]:
                    raise ProvenanceError("Real Phase 3 retained input hash mismatch")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
            return

    def _fetch(self, locators: list, size_deg: float) -> dict:
        available = {}
        pending = []
        for locator in locators:
            url = locator.cutout_url(self.ra, self.dec, size_deg)
            if url in self.content:
                available[locator] = self.content[url]
                continue
            self._seed_exact_cache(ProductLocator(locator.uri), size_deg)
            path = self.client._cutout_cache_path(locator, self.ra, self.dec, size_deg)
            if self.offline:
                if path.is_file():
                    content = path.read_bytes()
                    if not content.startswith(b"SIMPLE  ="):
                        raise ProvenanceError("Retained cutout is not FITS; offline replay cannot replace it")
                    available[locator] = content
                else:
                    self.discovery_metadata["failed_inputs"].append({"uri": locator.uri, "source_url": url,
                        "reason": "EXACT_CUTOUT_NOT_RETAINED_OFFLINE"})
            else:
                pending.append(locator)
        if pending:
            try:
                available.update(self.client.fetch_cutouts(pending, self.ra, self.dec, size_deg))
            except Exception as exc:
                self.discovery_metadata["failed_inputs"].append({"reason": "BATCH_ACQUISITION_FAILED",
                                                                  "message": str(exc),
                                                                  "uris": [item.uri for item in pending]})
        for locator in pending:
            url = locator.cutout_url(self.ra, self.dec, size_deg)
            if locator not in available:
                self.discovery_metadata["failed_inputs"].append({"uri": locator.uri, "source_url": url,
                                                                  "reason": "CUTOUT_DOWNLOAD_FAILED_OR_DEADLINE"})
        for locator, content in list(available.items()):
            url = locator.cutout_url(self.ra, self.dec, size_deg)
            if url not in self.content:
                descriptor = store_input(content, self.config.cache_dir / "analysis-inputs", source_url=url,
                                         cutout={"ra": self.ra, "dec": self.dec, "size_deg": size_deg})
                self.discovery_metadata["cutout_requests"].append(descriptor)
                self.content[url] = content
        return available

    def prepare(self, size_deg: float) -> None:
        locators = [ProductLocator(uri) for uri in self.selected_uris]
        contents = self._fetch(locators, size_deg)
        for locator in locators:
            if locator not in contents:
                continue
            try:
                record, metadata = record_from_fits(locator.uri, contents[locator])
                self.records.append(record)
                self.discovery_metadata["verified_exposures"].append({"uri": locator.uri, **metadata})
            except Exception as exc:
                self.discovery_metadata["failed_inputs"].append({"uri": locator.uri,
                    "reason": "INVALID_EXPOSURE_METADATA", "message": str(exc)})
        self.records.sort(key=lambda record: (record.mjd_mid, record.uri))
        self.discovery_metadata["verified_exposure_count"] = len(self.records)
        self.discovery_metadata["status"] = "partial_recorded_inventory"

    def query_artifacts(self, ra: float, dec: float, *, bands=None, **kwargs) -> list[ArtifactRecord]:
        if (float(ra), float(dec)) != (self.ra, self.dec):
            raise ProvenanceError("Pinned archive query position differs from corrected target")
        if not self.records:
            raise IRSAUnavailable("No snapshot exposures were verified; see acquisition failures")
        return [record for record in self.records if bands is None or record.band in bands]

    def fetch_cutouts(self, records, ra: float, dec: float, size_deg: float, **kwargs) -> dict:
        if (float(ra), float(dec)) != (self.ra, self.dec) or any(record not in self.records for record in records):
            raise ProvenanceError("Pipeline requested an input outside the pinned snapshot")
        return self._fetch(records, size_deg)


def _publish_report(path: Path, report: dict[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(canonical_json(report) + b"\n")
    temporary.replace(path)


def stage(args) -> dict[str, Any]:
    output = args.output.resolve()
    approved = settings.golden_cache_dir.resolve()
    if output == approved or output.is_relative_to(approved) or output.is_relative_to((ROOT / "golden_cache").resolve()):
        raise ProvenanceError("Staging must be outside the approved golden cache")
    output.mkdir(parents=True, exist_ok=False)
    from services import spherex_pipeline as images
    from services import spectrophotometry as spectra
    from services import recording
    config = replace(settings, cache_dir=output / "cache", max_workers=args.workers,
                     retries=1, request_timeout_seconds=args.request_timeout)
    config.ensure_dirs()
    images.settings = config
    spectra.settings = config
    recording.settings = config
    report = {"created_at": utc_now(), "status": "running", "promotion_eligible": False,
              "source_scope": "partial historical recorded image URI inventory; not complete archive discovery",
              "limits": {"max_inputs_per_target": args.max_inputs or None,
                         "deadline_seconds_per_target": args.deadline, "offline": args.offline},
              "reference_overlays": "omitted; corrected WCS requires independently rebuilt references",
              "targets": []}
    report_path = output / "stage-report.json"
    _publish_report(report_path, report)
    targets = [target for target in corrected_targets() if args.target == "all" or target.id == args.target]
    if not targets:
        raise ProvenanceError("Unknown staging target")
    for target in targets:
        started = time.monotonic()
        target_report = {"target_id": target.id, "corrected_target": recording.json_values(asdict(target)), "status": "running"}
        report["targets"].append(target_report)
        print(f"Staging {target.id}: acquiring recorded real exposures", flush=True)
        try:
            source_manifest = approved / target.id / "manifest.json"
            source_bytes = source_manifest.read_bytes()
            target_report["source_manifest_sha256"] = content_hash(source_bytes)
            uris = recorded_uris(json.loads(source_bytes))
            if not uris:
                raise ProvenanceError("No real exposure URIs were recorded in the historical manifest")
            archive = PinnedArchive(target=target, uris=uris, config=config,
                                    deadline_at=started + args.deadline,
                                    max_inputs=args.max_inputs, offline=args.offline,
                                    input_stages=args.input_stage)
            target_report["discovery"] = archive.discovery_metadata
            _publish_report(report_path, report)
            padded = math.sqrt(2.0) * images.GRID_WIDTH * images.CDELT_DEG + 2 * images.NATIVE_PIXEL_SCALE_ARCSEC / 3600
            archive.prepare(padded)
            _publish_report(report_path, report)
            for product in ("image", "spectrum"):
                remaining = args.deadline - (time.monotonic() - started)
                if remaining <= 0:
                    target_report[product] = {"status": "failed", "reason": "TARGET_DEADLINE_EXCEEDED"}
                    continue
                try:
                    if product == "image":
                        manifest = images._build_manifest(target.id, target.ra_epoch2025, target.dec_epoch2025,
                            cutout_size_deg=0.2, max_visits_per_band=args.visits, force_refresh=True,
                            deadline_seconds=remaining, archive_client=archive)
                        manifest.update(target_id=target.id, target_name=target.name, target=recording.json_values(asdict(target)),
                                        reference_overlays={}, reference_overlay_status=report["reference_overlays"],
                                        generated_by="scripts/stage_phase4.py", promotion_eligible=False)
                        images._write_manifest(manifest)
                    else:
                        spectra._build_spectrum(target.id, target.ra_epoch2025, target.dec_epoch2025,
                            confidence="low", max_visits_per_band=args.visits, target_record=target,
                            force_refresh=True, deadline_seconds=remaining, archive_client=archive)
                    target_report[product] = {"status": "built", "scope": "staged_unpromoted"}
                except Exception as exc:
                    target_report[product] = {"status": "failed", "exception": type(exc).__name__, "reason": str(exc)}
                _publish_report(report_path, report)
            asset_dir = config.live_cache_dir / target.id
            destination = output / "golden" / target.id
            destination.mkdir(parents=True, exist_ok=False)
            files = {}
            if asset_dir.is_dir():
                for path in sorted(asset_dir.iterdir()):
                    if path.is_symlink() or not path.is_file() or path.suffix not in (".json", ".webp", ".gz"):
                        continue
                    if path.name.startswith("ref_"):
                        raise ProvenanceError("Reference overlay unexpectedly present in a corrected-WCS staging set")
                    shutil.copy2(path, destination / path.name)
                    files[path.name] = {"sha256": content_hash(path.read_bytes()), "size_bytes": path.stat().st_size}
            target_report["files"] = files
            target_report["status"] = ("built_unpromoted" if all(target_report.get(key, {}).get("status") == "built"
                                                              for key in ("image", "spectrum")) else "partial_or_failed")
        except Exception as exc:
            target_report.update(status="failed", exception=type(exc).__name__, reason=str(exc))
        target_report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        _publish_report(report_path, report)
        print(f"Staging {target.id}: {target_report['status']}", flush=True)
    report["status"] = "complete_unpromoted"
    report["completed_at"] = utc_now()
    report["all_products_built"] = all(item["status"] == "built_unpromoted" for item in report["targets"])
    _publish_report(report_path, report)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="New staging directory, never approved golden_cache")
    parser.add_argument("--target", default="all", choices=["all", *(target.id for target in corrected_targets())])
    parser.add_argument("--max-inputs", type=int, default=0, help="0=all recorded URIs; positive explicit sampling bound")
    parser.add_argument("--visits", type=int, default=3, help="Production visit-selection bound per band/epoch")
    parser.add_argument("--deadline", type=float, default=900.0, help="Total seconds per target")
    parser.add_argument("--request-timeout", type=float, default=30.0)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--input-stage", type=Path, action="append", default=[],
                        help="Reuse hash-verified exact URL inputs from a previous stage; repeatable")
    args = parser.parse_args(argv)
    if (args.max_inputs < 0 or args.visits < 1 or not 1 <= args.workers <= 8
            or not math.isfinite(args.deadline) or args.deadline <= 0
            or not math.isfinite(args.request_timeout) or args.request_timeout <= 0):
        parser.error("Invalid staging resource bounds")
    try:
        report = stage(args)
        return 0 if report["all_products_built"] else 1
    except (ProvenanceError, OSError) as exc:
        print(f"Staging failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
