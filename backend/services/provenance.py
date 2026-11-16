"""Versioned, content-addressed scientific lineage and bounded input retention.

This is an internal record, not an API schema. No discovery or executable code
is taken from a record. Unknown/nonfinite numbers are rejected rather than
silently replaced with null; callers must explicitly represent unavailable data.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

SCHEMA_VERSION = "skyblink.analysis/1"
MAX_INPUT_BYTES = 128 * 1024 * 1024
MAX_RECORD_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 8 * 1024 * 1024 * 1024
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
REPO_ROOT = Path(__file__).resolve().parents[2]
# An explicit whitelist: never dump environment variables or installed packages
# wholesale (direct URLs / credentials may be present in package metadata).
DEPENDENCIES = ("numpy", "scipy", "astropy", "astropy-iers-data", "reproject",
                "photutils", "Pillow", "httpx", "pydantic", "fastapi", "pyerfa",
                "astropy-healpix", "dask", "zarr", "fsspec", "sep", "pyvo")
CHANNEL_FIELDS = ("detector", "wavelength_um", "bandwidth_um", "flux_ujy",
                  "flux_err_ujy", "flags", "is_flagged_bad", "clean_fraction",
                  "is_used_in_photometry", "photometry_method", "aperture_mode",
                  "aperture_radius_arcsec", "measurement_reasons")
FLOAT_CHANNEL_FIELDS = {"wavelength_um", "bandwidth_um", "flux_ujy", "flux_err_ujy",
                        "clean_fraction", "aperture_radius_arcsec"}
# Predeclared native extraction tolerance, not calibrated measurement precision.
# Integers, booleans, nulls, coordinates and method/mask selection remain exact.
NUMERICAL_TOLERANCE = {"rtol": 1e-10, "atol": 1e-10}


class ProvenanceError(ValueError):
    """The record or pinned bytes cannot safely reproduce the analysis."""


class RuntimeSourceChanged(RuntimeError):
    """Loaded application code no longer matches its recorded source files."""


_APPLICATION_SOURCE: tuple[Path, dict[str, Any]] | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_json(value: Any) -> None:
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ProvenanceError("Nonfinite JSON number; represent unavailable data explicitly")
        return
    if type(value) is list:
        for item in value:
            _check_json(item)
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for item in value.values():
            _check_json(item)
        return
    raise ProvenanceError(f"Unsupported canonical JSON type: {type(value).__name__}")


def canonical_json(value: Any) -> bytes:
    """UTF-8, sorted keys, compact separators, exact JSON scalar types only."""
    _check_json(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def fingerprint(identity: dict[str, Any]) -> str:
    return "sha256:" + content_hash(canonical_json({"schema_version": SCHEMA_VERSION,
                                                  "identity": identity}))


def _hash(value: Any) -> str:
    if not isinstance(value, str) or not SHA256.fullmatch(value):
        raise ProvenanceError("Expected a lowercase SHA-256 digest")
    return value


def store_key(digest: str) -> str:
    digest = _hash(digest)
    return f"sha256/{digest[:2]}/{digest}.bin"


def validate_source_url(url: str) -> str:
    """Only HTTPS IRSA product paths, no credentials, redirects or local URLs."""
    if not isinstance(url, str) or any(ord(char) < 33 for char in url) or "\\" in url:
        raise ProvenanceError("Unsafe source URL")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise ProvenanceError("Malformed source URL") from exc
    path = unquote(parsed.path)
    supported_product = (
        parsed.hostname == "irsa.ipac.caltech.edu" and path.startswith(
            ("/ibe/data/spherex/dr1/", "/ibe/data/spherex/qr3/", "/data/SPHEREx/"))
        or parsed.hostname == "nasa-irsa-spherex.s3.us-east-1.amazonaws.com" and path.startswith(
            ("/dr1/spectral_wcs/", "/qr3/spectral_wcs/"))
    )
    if (parsed.scheme != "https" or not supported_product
            or port not in (None, 443) or parsed.username or parsed.password
            or parsed.fragment or "\\" in path or "%" in path
            or any(part in (".", "..") for part in path.split("/"))):
        raise ProvenanceError("Only pinned HTTPS IRSA DR1/QR3/calibration product URLs are allowed")
    return url


def _descriptor(item: dict[str, Any]) -> None:
    if not isinstance(item, dict):
        raise ProvenanceError("Input descriptor must be an object")
    digest = _hash(item.get("sha256"))
    if type(item.get("size_bytes")) is not int or not 0 < item["size_bytes"] <= MAX_INPUT_BYTES:
        raise ProvenanceError("Input size is outside the bounded retention limit")
    if item.get("store_key") != store_key(digest):
        raise ProvenanceError("Input path is not its canonical content-addressed key")
    validate_source_url(item.get("source_url"))
    if not isinstance(item.get("cutout"), dict):
        raise ProvenanceError("Input cutout parameters must be an explicit object")


def _store_path(store_dir: Path, digest: str) -> Path:
    root = Path(store_dir).resolve()
    path = root / store_key(digest)
    if not path.resolve().is_relative_to(root):
        raise ProvenanceError("Content-store path escapes its root (possibly a symlink)")
    return path


def _verify_bytes(content: bytes, descriptor: dict[str, Any]) -> None:
    if len(content) != descriptor["size_bytes"] or content_hash(content) != descriptor["sha256"]:
        raise ProvenanceError(f"Pinned input hash/size mismatch: {descriptor['sha256']}; no substitution allowed")


def _publish_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".provenance-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def store_input(content: bytes, store_dir: Path, *, source_url: str,
                cutout: dict[str, Any], retrieved_at: str | None = None) -> dict[str, Any]:
    """Retain exact bytes. Same-hash corrupt existing files fail, never repair silently."""
    descriptor = {"sha256": content_hash(content), "size_bytes": len(content),
                  "source_url": source_url, "cutout": cutout,
                  "store_key": store_key(content_hash(content)),
                  "retrieved_at": retrieved_at}
    canonical_json(descriptor)
    _descriptor(descriptor)
    path = _store_path(store_dir, descriptor["sha256"])
    if path.exists():
        _verify_bytes(path.read_bytes(), descriptor)
    else:
        _publish_bytes(path, content)
    return descriptor


def _source_file_hashes(repo_root: Path) -> dict[str, str]:
    """Source-only check: no git commands, caches, tests or secrets."""
    root = Path(repo_root).resolve()
    paths = set()
    for folder in ("backend/core", "backend/services", "backend/models", "backend/routers", "backend/app"):
        paths.update((root / folder).rglob("*.py"))
    for name in ("backend/requirements.txt", "scripts/build_golden_cache.py",
                 "scripts/replay_analysis.py", "scripts/stage_phase4.py",
                 "scripts/curate_phase4_replay.py", "scripts/bundle_analysis.py",
                 "backend/core/staged_astrometry.json", "data/catalog-exposure-index.json", "data/archive-spatial-index.json.gz", "Dockerfile"):
        if (root / name).is_file():
            paths.add(root / name)
    files = {}
    for path in sorted(paths):
        if not path.resolve().is_relative_to(root) or path.is_symlink():
            raise ProvenanceError("Source identity cannot follow links outside the source tree")
        files[path.relative_to(root).as_posix()] = content_hash(path.read_bytes())
    return files


def capture_code_identity(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Hash all relevant tracked AND untracked source files; exclude tests/secrets."""
    root = Path(repo_root).resolve()
    files = _source_file_hashes(root)
    def git(*args: str) -> str | None:
        try:
            return subprocess.run(["git", "-C", str(root), *args], check=True,
                                  capture_output=True, text=True, timeout=10).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None
    status = git("status", "--porcelain", "--untracked-files=all", "--", *files)
    return {"commit": git("rev-parse", "HEAD"),
            "dirty": None if status is None else bool(status),
            "source_digest": content_hash(canonical_json(files)), "files": files}


def bind_application_source(repo_root: Path = REPO_ROOT) -> None:
    """Freeze identity once after application imports; another factory cannot rebind it.

    This catches later edits and failed development reloads. It is not an
    attestation against files changing concurrently with the initial imports.
    Standalone replay/scripts retain their explicit disk-identity behavior.
    """
    global _APPLICATION_SOURCE
    if _APPLICATION_SOURCE is None:
        _APPLICATION_SOURCE = (Path(repo_root).resolve(), capture_code_identity(repo_root))
    else:
        assert_application_source_current()


def assert_application_source_current() -> None:
    """Reject source drift before expensive acquisition and again before publication."""
    if _APPLICATION_SOURCE is None:
        return
    root, identity = _APPLICATION_SOURCE
    try:
        current = _source_file_hashes(root)
    except (OSError, ProvenanceError) as exc:
        raise RuntimeSourceChanged(
            "Processing source changed or became unavailable. Restart the API server and retry."
        ) from exc
    if current != identity["files"]:
        raise RuntimeSourceChanged(
            "Processing source changed while this API server was running. Restart the API server and retry."
        )


def capture_environment() -> dict[str, Any]:
    versions = {}
    for package in DEPENDENCIES:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    from PIL import features
    from astropy.wcs import _wcs
    return {"python": platform.python_version(), "implementation": platform.python_implementation(),
            "platform": sys.platform, "machine": platform.machine(), "packages": versions,
            "native_libraries": {"webp": features.version("webp"),
                                 "wcslib": str(_wcs.WCSLIB_VERSION)}}


def native_method() -> dict[str, Any]:
    from core import flags
    from models.version import API_CONTRACT_VERSION
    from services import spectrophotometry as spectrum
    return {"name": "native_aperture", "version": 2,
            "api_version": API_CONTRACT_VERSION, "cache_schema_version": spectrum.SPECTRUM_CACHE_VERSION,
            "aperture_radius_arcsec": spectrum.APERTURE_RADIUS_ARCSEC,
            "annulus_inner_pixels": spectrum.ANNULUS_INNER_PIXELS,
            "annulus_outer_pixels": spectrum.ANNULUS_OUTER_PIXELS,
            "eligibility": "full_clean_aperture_inside_image; >=10_clean_annulus_pixels; supported_field_background; no_hard_bad_centre",
            "hard_bad_mask": int(flags.HARD_BAD_MASK),
            "photometry_exclude_mask": int(flags.PHOTOMETRY_EXCLUDE_MASK),
            "background_exclude_mask": int(flags.HARD_BAD_MASK | flags.ARTIFACT_WARNING_MASK | flags.BIT_SOURCE),
            "wavelength_calibration": spectrum.WAVELENGTH_CALIBRATION,
            "uncertainty": "native_variance_plus_approximate_background; covariance_not_calibrated",
            "verification_tolerance": dict(NUMERICAL_TOLERANCE)}


def make_record(*, kind: str, query: dict[str, Any], inputs: list[dict[str, Any]],
                exposures: list[dict[str, Any]], method: dict[str, Any],
                selection: dict[str, Any] | None = None, outputs: dict[str, Any] | None = None,
                code: dict[str, Any] | None = None, environment: dict[str, Any] | None = None,
                created_at: str | None = None, acquisition: dict[str, Any] | None = None) -> dict[str, Any]:
    assert_application_source_current()
    if code is None:
        code = _APPLICATION_SOURCE[1] if _APPLICATION_SOURCE is not None else capture_code_identity()
    # Copy through canonical JSON: neither caller mutation nor numpy scalars can
    # invisibly change a record after its fingerprint has been assigned.
    timestamps = {item["sha256"]: item.get("retrieved_at") for item in inputs}
    identity = {"kind": kind, "query": query,
                "inputs": sorted([{key: value for key, value in item.items() if key != "retrieved_at"} for item in inputs],
                                 key=lambda item: item["sha256"]),
                "exposures": exposures, "method": method, "selection": selection or {},
                "outputs": outputs or {}, "code": code,
                "environment": environment if environment is not None else capture_environment()}
    identity = json.loads(canonical_json(identity))
    result = {"schema_version": SCHEMA_VERSION, "analysis_id": fingerprint(identity),
              "identity": identity, "created_at": created_at or utc_now(), "retrieved_at": timestamps}
    if acquisition is not None:
        result["acquisition"] = json.loads(canonical_json(acquisition))
    validate_record(result)
    return result


def validate_record(record: dict[str, Any]) -> dict[str, Any]:
    canonical_json(record)
    if not isinstance(record, dict) or record.get("schema_version") != SCHEMA_VERSION:
        raise ProvenanceError("Unsupported analysis record version")
    identity = record.get("identity")
    if not isinstance(identity, dict) or record.get("analysis_id") != fingerprint(identity):
        raise ProvenanceError("Scientific record fingerprint mismatch")
    if identity.get("kind") not in ("spectrum", "image"):
        raise ProvenanceError("Unsupported analysis kind")
    for key in ("query", "method", "selection", "outputs", "code", "environment"):
        if not isinstance(identity.get(key), dict):
            raise ProvenanceError(f"Missing record object: {key}")
    inputs, exposures = identity.get("inputs"), identity.get("exposures")
    if not isinstance(inputs, list) or not inputs or len(inputs) > 10000:
        raise ProvenanceError("An analysis requires a bounded, nonempty input index")
    hashes = set()
    for item in inputs:
        _descriptor(item)
        if item["sha256"] in hashes:
            raise ProvenanceError("Duplicate input hash; deduplicate the input index")
        hashes.add(item["sha256"])
    if sum(item["size_bytes"] for item in inputs) > MAX_TOTAL_BYTES:
        raise ProvenanceError("Record exceeds total input size limit")
    if not isinstance(exposures, list) or not exposures or len(exposures) > 10000:
        raise ProvenanceError("An analysis requires a bounded, nonempty exposure index")
    for exposure in exposures:
        if not isinstance(exposure, dict) or exposure.get("input_sha256") not in hashes:
            raise ProvenanceError("Exposure references an absent input")
        if type(exposure.get("detector")) is not int or not 1 <= exposure["detector"] <= 6:
            raise ProvenanceError("Exposure detector must be 1..6")
        if not isinstance(exposure.get("epoch_id"), str) or not exposure["epoch_id"]:
            raise ProvenanceError("Exposure requires its recorded epoch ID")
        position = exposure.get("extraction", {})
        if (not isinstance(position, dict)
                or type(position.get("ra")) not in (int, float)
                or type(position.get("dec")) not in (int, float)
                or not 0 <= position["ra"] < 360 or not -90 <= position["dec"] <= 90):
            raise ProvenanceError("Exposure requires finite ICRS extraction coordinates")
        if identity["kind"] == "spectrum" and "expected_channel" not in exposure:
            raise ProvenanceError("Spectrum exposure requires expected_channel (explicit null permitted)")
        channel = exposure.get("expected_channel")
        if channel is not None:
            if not isinstance(channel, dict):
                raise ProvenanceError("Expected channel must be an object or null")
            required = set(CHANNEL_FIELDS[:9])
            if not required.issubset(channel):
                raise ProvenanceError("Expected channel lacks required scientific fields")
            if channel["detector"] != exposure["detector"]:
                raise ProvenanceError("Channel detector differs from its exposure")
    return record


def write_record(path: Path, record: dict[str, Any]) -> None:
    validate_record(record)
    _publish_bytes(Path(path), canonical_json(record) + b"\n")


def read_record(path: Path) -> dict[str, Any]:
    if Path(path).stat().st_size > MAX_RECORD_BYTES:
        raise ProvenanceError("Analysis record exceeds size limit")
    def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ProvenanceError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    try:
        record = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique_pairs)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ProvenanceError("Invalid analysis JSON") from exc
    return validate_record(record)


def verify_inputs(record: dict[str, Any], store_dir: Path) -> dict[str, Path]:
    validate_record(record)
    result = {}
    for descriptor in record["identity"]["inputs"]:
        digest = descriptor["sha256"]
        path = _store_path(store_dir, digest)
        if not path.is_file():
            raise ProvenanceError(f"Missing pinned input {digest}; run acquire or provide the retained bundle")
        if path.stat().st_size != descriptor["size_bytes"]:
            raise ProvenanceError(f"Pinned input size mismatch: {digest}")
        _verify_bytes(path.read_bytes(), descriptor)
        result[digest] = path
    return result


def acquire_inputs(record: dict[str, Any], store_dir: Path, *, timeout_seconds: float = 120.0) -> dict[str, Path]:
    """Acquire missing exact bytes; changed inputs/corrupt retained bytes fail closed."""
    import httpx
    validate_record(record)
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ProvenanceError("Acquisition timeout must be finite and positive")
    deadline = time.monotonic() + timeout_seconds
    with httpx.Client(follow_redirects=False, trust_env=False) as client:
        for descriptor in record["identity"]["inputs"]:
            path = _store_path(store_dir, descriptor["sha256"])
            if path.exists():
                if path.stat().st_size != descriptor["size_bytes"]:
                    raise ProvenanceError("Retained input size mismatch; refusing silent repair")
                _verify_bytes(path.read_bytes(), descriptor)
                continue
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProvenanceError("Pinned input acquisition deadline exceeded")
            try:
                with client.stream("GET", descriptor["source_url"], timeout=min(remaining, 30.0)) as response:
                    response.raise_for_status()
                    if response.is_redirect:
                        raise ProvenanceError("Archive redirect refused; record the verified final URL explicitly")
                    chunks = []
                    size = 0
                    for chunk in response.iter_bytes():
                        if time.monotonic() >= deadline:
                            raise ProvenanceError("Pinned input acquisition deadline exceeded")
                        size += len(chunk)
                        if size > descriptor["size_bytes"]:
                            raise ProvenanceError("Archive input exceeds pinned size; no substitution allowed")
                        chunks.append(chunk)
                content = b"".join(chunks)
            except httpx.HTTPError as exc:
                raise ProvenanceError(f"Pinned archive input unavailable: {descriptor['sha256']}: {type(exc).__name__}") from exc
            _verify_bytes(content, descriptor)
            _publish_bytes(path, content)
    return verify_inputs(record, store_dir)


def verify_channels(expected: dict[str, Any] | None, actual: dict[str, Any] | None) -> list[str]:
    """Compare public science values; extra internal diagnostics do not hide failures."""
    if expected is None or actual is None:
        return [] if expected is actual else ["channel availability differs"]
    differences = []
    for key in CHANNEL_FIELDS:
        if key not in expected and key not in actual:
            continue
        if key not in expected or key not in actual:
            differences.append(f"{key}: field presence differs")
            continue
        before, after = expected[key], actual[key]
        if key in FLOAT_CHANNEL_FIELDS and before is not None and after is not None:
            equal = (type(before) in (int, float) and type(after) in (int, float)
                     and math.isfinite(before) and math.isfinite(after)
                     and math.isclose(before, after, rel_tol=NUMERICAL_TOLERANCE["rtol"],
                                      abs_tol=NUMERICAL_TOLERANCE["atol"]))
        else:
            equal = type(before) is type(after) and before == after
        if not equal:
            differences.append(f"{key}: expected {before!r}, got {after!r}")
    return differences
