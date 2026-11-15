"""Real reference overlays and Gaia DR3 pins in the golden cache (S4).

The W0 report replaced the synthetic cross-mission mocks with real SkyView
DSS2 Red / WISE cutouts and IRSA TAP Gaia DR3 pins.  These tests verify the
committed golden assets without touching the network:

* the 1.0.0 overlay keys survive and the 1.1.0 keys are present as contract
  asset URLs;
* every referenced file exists, is a 240 x 240 WebP (or valid JSON), and its
  SHA-256 matches the recorded provenance;
* WISE 0855 carries the extra 4.6 um reference field;
* the Gaia JSON is real, capped, brightest-first, and keeps null proper
  motions;
* the attribution bundle credits DSS2, WISE, and Gaia;
* nothing is labeled synthetic.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from scripts import reference_overlays as overlays
from scripts.build_golden_cache import _sha256_text_bytes, verify_target

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = REPO_ROOT / "golden_cache"
TARGET_IDS = (
    "wise_0855",
    "barnards_star",
    "eps_indi_b",
    "rw_aurigae",
    "r_draconis",
)
GRID = (240, 240)
REQUIRED_1_1_KEYS = {
    "optical_dss2_red",
    "mid_ir_wise_w1",
    "gaia_sources_url",
    "attribution",
}
REQUIRED_1_0_KEYS = {"optical_dss_gaia", "mid_ir_wise"}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest(target_id: str) -> dict:
    path = GOLDEN_DIR / target_id / "manifest.json"
    assert path.is_file(), f"missing golden manifest {path}"
    return _load_json(path)


def _reference_files(manifest: dict) -> dict[str, Path]:
    target_id = str(manifest["target_id"])
    directory = GOLDEN_DIR / target_id
    files = overlays.local_reference_filenames(manifest, target_id)
    assert files
    return {name: directory / name for name in files}


def test_all_five_manifests_have_real_overlay_maps() -> None:
    for target_id in TARGET_IDS:
        manifest = _manifest(target_id)
        mapping = manifest.get("reference_overlays") or {}
        assert REQUIRED_1_0_KEYS <= set(mapping), target_id
        assert REQUIRED_1_1_KEYS <= set(mapping), target_id
        for key, value in mapping.items():
            assert isinstance(value, str) and value, f"{target_id}:{key}"
            if key == "attribution":
                # Human-readable prose metadata; must credit every survey.
                assert isinstance(value, str) and value.strip()
                lowered = value.lower()
                for token in ("skyview", "wise", "gaia", "stsc"):
                    assert token in lowered, (target_id, key, token)
                continue
            # The API prefixes asset files; the manifest stores deployable URLs.
            assert value.startswith(f"/api/v1/assets/{target_id}/"), (
                target_id,
                key,
                value,
            )
        assert mapping["optical_dss_gaia"] == mapping["optical_dss2_red"]
        assert mapping["mid_ir_wise"] == mapping["mid_ir_wise_w1"]
        assert mapping["gaia_sources_url"].endswith("/gaia_dr3.json")
        assert mapping["attribution_json"].endswith("/ref_attribution.json")

        provenance = manifest.get("reference_overlay_provenance") or {}
        assert provenance.get("is_simulated_fallback") is False, target_id
        assert provenance.get("display_only") is True, target_id
        assert provenance.get("attribution_text"), target_id
        assert provenance.get("assets"), target_id


def test_overlay_webps_and_hashes_are_real_240_grid_assets() -> None:
    for target_id in TARGET_IDS:
        manifest = _manifest(target_id)
        provenance = manifest["reference_overlay_provenance"]
        recorded = provenance["assets"]
        files = _reference_files(manifest)
        assert set(files) == set(recorded), target_id

        for name, path in files.items():
            assert path.is_file(), f"{target_id}: missing {path}"
            content = path.read_bytes()
            entry = recorded[name]
            assert entry.get("is_simulated_fallback") is False, (target_id, name)
            expected = (
                _sha256_text_bytes(content)
                if name.endswith(".json")
                else hashlib.sha256(content).hexdigest()
            )
            assert entry.get("sha256") == expected, (target_id, name)
            if name.endswith(".json"):
                # The manifest records the canonical LF length for reference
                # JSON (see scripts/reference_overlays.py); a Windows
                # core.autocrlf checkout may materialize CRLF, so compare the
                # normalized length rather than the raw checkout length.
                canonical = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
                assert int(entry.get("bytes", 0)) == len(canonical), (
                    target_id,
                    name,
                )
            else:
                assert int(entry.get("bytes", 0)) == len(content), (
                    target_id,
                    name,
                )

            if name.endswith(".webp"):
                assert content.startswith(b"RIFF") and content[8:12] == b"WEBP"
                with Image.open(path) as image:
                    assert image.size == GRID, (target_id, name, image.size)
                pixels = np.asarray(Image.open(path), dtype=float)
                # A blank or single-valued overlay would be a fake-looking
                # uniform card; real survey fields have structure.
                assert float(pixels.std()) > 1.0, (target_id, name)

    assert "ref_wise_w2.webp" in _reference_files(_manifest("wise_0855"))
    for target_id in set(TARGET_IDS) - {"wise_0855"}:
        manifest = _manifest(target_id)
        assert "mid_ir_wise_w2" not in manifest["reference_overlays"]
        assert "ref_wise_w2.webp" not in _reference_files(manifest)


def test_overlay_provenance_records_the_real_services_and_retries() -> None:
    for target_id in TARGET_IDS:
        assets = _manifest(target_id)["reference_overlay_provenance"]["assets"]
        for name in ("ref_optical.webp", "ref_wise.webp"):
            entry = assets[name]
            assert entry["service_url"].startswith(
                "https://skyview.gsfc.nasa.gov/"
            )
            assert "Survey=" in entry["request_url"]
            assert entry["http_status"] == 200
            assert entry["attempts"], (target_id, name)
            assert entry["primary_attempts"], (target_id, name)
            for attempt in entry["attempts"]:
                assert "attempt" in attempt and "ok" in attempt
            if not entry["fallback_200_used"]:
                assert entry["primary_attempts"] == entry["attempts"]
            for attempt in entry["primary_attempts"]:
                if attempt.get("shape") == [1]:
                    assert attempt["ok"] is False
                    assert "blank 1-element FITS" in attempt.get("note", "")
            assert entry["golden_grid"].startswith("240x240 TAN")
            assert entry["finite_fraction"] >= 0.5
            assert entry["display"]["stretch_percentiles"] == [0.5, 99.5]
            assert entry["display"]["quality"] == 90
        assert "DSS2" in assets["ref_optical.webp"]["survey"]
        assert "WISE" in assets["ref_wise.webp"]["survey"]
        if "ref_wise_w2.webp" in assets:
            assert "4.6" in assets["ref_wise_w2.webp"]["survey"]

        # The 200x200 fallback, when it was needed, must be recorded honestly.
        for entry in assets.values():
            if entry.get("fallback_200_used"):
                assert entry["input_shape"] == [200, 200]
                assert entry["resampled_to_golden_grid"] is True


def test_gaia_dr3_json_is_real_capped_and_null_safe() -> None:
    for target_id in TARGET_IDS:
        manifest = _manifest(target_id)
        query_center = manifest["query"]
        path = GOLDEN_DIR / target_id / "gaia_dr3.json"
        payload = _load_json(path)
        assert payload["target_id"] == target_id
        assert payload["is_simulated_fallback"] is False
        assert payload["frame"] == "ICRS"
        assert "Gaia DR3" in payload["source"]
        assert "IRSA" in payload["attribution"]

        query = payload["query"]
        assert query["ra"] == pytest.approx(float(query_center["ra"]), abs=1e-6)
        assert query["dec"] == pytest.approx(float(query_center["dec"]), abs=1e-6)
        assert query["radius_deg"] == pytest.approx(0.2)
        assert query["g_limit"] <= 16.0
        assert 1 <= query["cap"] <= 500
        assert query["returned"] == len(payload["sources"])
        assert query["returned"] <= query["cap"]
        assert query["total_g_le_limit"] >= query["returned"]
        assert query["truncated"] is (
            query["total_g_le_limit"] > query["returned"]
        )

        previous_mag = -math.inf
        seen: set[str] = set()
        null_pm = 0
        for source in payload["sources"]:
            assert set(source) == {
                "source_id",
                "ra",
                "dec",
                "g_mag",
                "pmra",
                "pmdec",
                "label",
            }
            # JavaScript-safe: Gaia source IDs exceed 2**53.
            assert isinstance(source["source_id"], str) and source["source_id"]
            assert int(source["source_id"]) > 0
            assert source["source_id"] not in seen
            seen.add(source["source_id"])
            assert -360.0 <= float(source["ra"]) <= 360.0
            assert -90.0 <= float(source["dec"]) <= 90.0
            assert source["g_mag"] is not None
            assert float(source["g_mag"]) <= query["g_limit"] + 1e-3
            assert float(source["g_mag"]) >= previous_mag
            previous_mag = float(source["g_mag"])
            assert source["label"].startswith("G=")
            for pm_key in ("pmra", "pmdec"):
                value = source[pm_key]
                if value is not None:
                    assert math.isfinite(float(value))
            if source["pmra"] is None or source["pmdec"] is None:
                null_pm += 1
        assert null_pm == query["null_pm_count"]

        # Every pin must lie inside the queried 0.2-deg circle (small margin
        # for rounded coordinates).
        center_ra = float(query["ra"])
        center_dec = float(query["dec"])
        for source in payload["sources"]:
            delta_ra = (
                (float(source["ra"]) - center_ra)
                * math.cos(math.radians(center_dec))
            )
            delta_dec = float(source["dec"]) - center_dec
            assert math.hypot(delta_ra, delta_dec) <= 0.2 + 1e-4


def test_attribution_bundle_credits_every_survey() -> None:
    for target_id in TARGET_IDS:
        payload = _load_json(GOLDEN_DIR / target_id / "ref_attribution.json")
        assert payload["is_simulated_fallback"] is False
        assert payload["target_id"] == target_id
        text = payload["attribution_text"].lower()
        assert "skyview" in text
        assert "stsc" in text
        assert "wise" in text
        assert "gaia" in text
        assets = {credit["asset"] for credit in payload["credits"]}
        assert {"ref_optical.webp", "ref_wise.webp", "gaia_dr3.json"} <= assets


def test_golden_verify_summary_reports_reference_assets() -> None:
    for target_id in TARGET_IDS:
        manifest = _manifest(target_id)
        summary = verify_target(target_id, golden_dir=GOLDEN_DIR)
        reference = summary["reference_assets"]
        assert reference["is_simulated_fallback"] is False
        assert reference["count"] == len(
            overlays.local_reference_filenames(manifest, target_id)
        )
        assert reference["keys"] == sorted(manifest["reference_overlays"])
        gaia = _load_json(GOLDEN_DIR / target_id / "gaia_dr3.json")
        assert reference["gaia_returned"] == gaia["query"]["returned"]
        assert reference["gaia_total_g_le_limit"] == gaia["query"]["total_g_le_limit"]


def test_local_reference_filenames_ignores_external_urls() -> None:
    manifest = {
        "reference_overlays": {
            "a": "/api/v1/assets/wise_0855/ref_optical.webp",
            "b": "ref_wise.webp",
            "c": "https://example.org/external.webp",
            "d": "/some/other/path.webp",
            "e": "not a filename",
        }
    }
    assert overlays.local_reference_filenames(manifest, "wise_0855") == [
        "ref_optical.webp",
        "ref_wise.webp",
    ]


def test_reference_json_hashes_are_line_ending_stable() -> None:
    """The recorded hashes are the LF canonical form, not the checkout form.

    ``core.autocrlf=true`` materializes the committed JSON with CRLF on
    Windows; verification must normalize before hashing or a clean checkout
    fails on bytes that are semantically identical.  The worktree itself may
    already be CRLF, so normalize to LF first and derive both variants from it.
    """
    for target_id in TARGET_IDS:
        recorded = _manifest(target_id)["reference_overlay_provenance"]["assets"]
        for name in ("gaia_dr3.json", "ref_attribution.json"):
            content = (GOLDEN_DIR / target_id / name).read_bytes()
            lf = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            crlf = lf.replace(b"\n", b"\r\n")
            cr = lf.replace(b"\n", b"\r")

            assert _sha256_text_bytes(lf) == recorded[name]["sha256"]
            assert _sha256_text_bytes(crlf) == recorded[name]["sha256"]
            assert _sha256_text_bytes(cr) == recorded[name]["sha256"]
            if b"\n" in lf:
                # The raw CRLF bytes are not the canonical form.
                assert hashlib.sha256(crlf).hexdigest() != recorded[name]["sha256"]


def test_verify_target_accepts_a_crlf_json_checkout(tmp_path: Path) -> None:
    """End-to-end regression for the Windows autocrlf failure."""
    import shutil

    source = GOLDEN_DIR / "wise_0855"
    destination = tmp_path / "wise_0855"
    shutil.copytree(source, destination)
    for name in ("gaia_dr3.json", "ref_attribution.json"):
        path = destination / name
        # The source may already be CRLF; normalize to LF first so the
        # conversion cannot produce \r\r\n.
        lf = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        crlf = lf.replace(b"\n", b"\r\n")
        assert b"\r\r\n" not in crlf
        path.write_bytes(crlf)
        assert b"\r\n" in crlf
    summary = verify_target(
        "wise_0855", golden_dir=tmp_path, require_telemetry=True
    )
    assert summary["reference_assets"]["is_simulated_fallback"] is False
    assert summary["telemetry_assets"]["available"] is True
