"""Contract 1.1.0 telemetry sidecar and LVF geometry verification (S4).

B8 writes ``telemetry_{epoch_id}.bin.gz`` next to the live frames; the golden
builder must copy them, rewrite ``epochs[].telemetry.url`` to the contract asset
URL, and verify the frozen codec: gzip of a little-endian 240 x 240 float16
MJy/sr plane followed by a 240 x 240 uint32 Table 16 flag plane.

These tests build real sidecar bytes with the frozen layout so they do not
depend on the backend implementation being importable.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from scripts.build_golden_cache import (
    _golden_epochs,
    _local_telemetry_filenames,
    _verify_telemetry_assets,
)

WIDTH = 240
HEIGHT = 240
DECODED_BYTES = WIDTH * HEIGHT * 6


def _sidecar_bytes(
    *,
    fill: float = 1.0,
    flags: int = 1 << 21,
    width: int = WIDTH,
    height: int = HEIGHT,
) -> bytes:
    image = np.full((height, width), fill, dtype="<f2")
    flag_plane = np.full((height, width), flags, dtype="<u4")
    raw = image.tobytes(order="C") + flag_plane.tobytes(order="C")
    assert len(raw) == DECODED_BYTES
    return gzip.compress(raw, compresslevel=6, mtime=0)


def _manifest(
    target_id: str,
    *,
    filename: str = "telemetry_2025_E1.bin.gz",
    content: bytes,
    flux_band: str = "all",
    lvf_geometry: list[dict] | None = None,
    url: str | None = None,
) -> dict:
    return {
        "target_id": target_id,
        "epochs": [
            {
                "epoch_id": "2025_E1",
                "telemetry": {
                    "url": url or f"/api/v1/assets/{target_id}/{filename}",
                    "format": "float16_uint32_le_gzip",
                    "width": WIDTH,
                    "height": HEIGHT,
                    "byte_size": len(content),
                    "flux_band": flux_band,
                },
                "lvf_geometry": lvf_geometry
                if lvf_geometry is not None
                else [
                    {"detector": band, "pa_deg": 31.5, "grad_um_per_arcsec": 0.047}
                    for band in range(1, 7)
                ],
            }
        ],
        "assets": {
            "telemetry": {
                "count": 1,
                "total_bytes": len(content),
                "sha256": {filename: hashlib.sha256(content).hexdigest()},
            }
        },
    }


def test_valid_sidecar_and_lvf_geometry(tmp_path: Path) -> None:
    content = _sidecar_bytes()
    (tmp_path / "telemetry_2025_E1.bin.gz").write_bytes(content)
    manifest = _manifest("barnards_star", content=content)
    summary = _verify_telemetry_assets("barnards_star", tmp_path, manifest)
    assert summary["available"] is True
    assert summary["count"] == 1
    assert summary["total_bytes"] == len(content)
    assert summary["decoded_bytes"] == DECODED_BYTES
    assert summary["expected_flux_band"] == "all"
    epoch = summary["by_epoch"]["2025_E1"]
    assert epoch["file"] == "telemetry_2025_E1.bin.gz"
    assert epoch["finite_fraction"] == pytest.approx(1.0)
    assert epoch["flags_or"] & (1 << 21)


def test_wise_0855_requires_thermal_flux_band(tmp_path: Path) -> None:
    content = _sidecar_bytes()
    (tmp_path / "telemetry_2025_E1.bin.gz").write_bytes(content)
    manifest = _manifest("wise_0855", content=content, flux_band="thermal")
    summary = _verify_telemetry_assets("wise_0855", tmp_path, manifest)
    assert summary["expected_flux_band"] == "thermal"

    wrong = _manifest("wise_0855", content=content, flux_band="all")
    with pytest.raises(ValueError, match="flux_band"):
        _verify_telemetry_assets("wise_0855", tmp_path, wrong)


def test_telemetry_rejections(tmp_path: Path) -> None:
    content = _sidecar_bytes()
    path = tmp_path / "telemetry_2025_E1.bin.gz"
    path.write_bytes(content)

    # Declared size mismatch.
    manifest = _manifest("rw_aurigae", content=content)
    manifest["epochs"][0]["telemetry"]["byte_size"] = len(content) + 1
    with pytest.raises(ValueError, match="byte_size"):
        _verify_telemetry_assets("rw_aurigae", tmp_path, manifest)

    # Hash mismatch.
    manifest = _manifest("rw_aurigae", content=content)
    manifest["assets"]["telemetry"]["sha256"]["telemetry_2025_E1.bin.gz"] = "0" * 64
    with pytest.raises(ValueError, match="SHA-256"):
        _verify_telemetry_assets("rw_aurigae", tmp_path, manifest)

    # Not gzip.
    path.write_bytes(b"not gzip")
    manifest = _manifest("rw_aurigae", content=b"not gzip")
    with pytest.raises(ValueError, match="gzip"):
        _verify_telemetry_assets("rw_aurigae", tmp_path, manifest)

    # Wrong decoded size.
    short = gzip.compress(b"\x00" * 100, mtime=0)
    path.write_bytes(short)
    manifest = _manifest("rw_aurigae", content=short)
    with pytest.raises(ValueError, match="decodes to"):
        _verify_telemetry_assets("rw_aurigae", tmp_path, manifest)

    # Invalid LVF detector.
    content = _sidecar_bytes()
    path.write_bytes(content)
    manifest = _manifest(
        "rw_aurigae",
        content=content,
        lvf_geometry=[{"detector": 7, "pa_deg": 10.0, "grad_um_per_arcsec": 0.04}],
    )
    with pytest.raises(ValueError, match="LVF detector"):
        _verify_telemetry_assets("rw_aurigae", tmp_path, manifest)

    # Non-finite LVF gradient.
    manifest = _manifest(
        "rw_aurigae",
        content=content,
        lvf_geometry=[{"detector": 1, "pa_deg": 10.0, "grad_um_per_arcsec": 0.0}],
    )
    with pytest.raises(ValueError, match="LVF geometry"):
        _verify_telemetry_assets("rw_aurigae", tmp_path, manifest)


def test_golden_epochs_rewrite_telemetry_urls() -> None:
    manifest = {
        "epochs": [
            {
                "epoch_id": "2025_E1",
                "telemetry": {
                    "url": "telemetry_2025_E1.bin.gz",
                    "format": "float16_uint32_le_gzip",
                    "width": WIDTH,
                    "height": HEIGHT,
                    "byte_size": 90000,
                    "flux_band": "all",
                },
                "lvf_geometry": None,
            },
            {"epoch_id": "2025_E2", "telemetry": None},
        ]
    }
    epochs = _golden_epochs(manifest, "barnards_star")
    assert epochs[0]["telemetry"]["url"] == (
        "/api/v1/assets/barnards_star/telemetry_2025_E1.bin.gz"
    )
    # The source manifest must not be mutated.
    assert manifest["epochs"][0]["telemetry"]["url"] == "telemetry_2025_E1.bin.gz"
    assert epochs[1]["telemetry"] is None
    assert _local_telemetry_filenames(
        {"epochs": epochs}, "barnards_star"
    ) == ["telemetry_2025_E1.bin.gz"]

    # A foreign absolute URL is never accepted as a golden asset.
    bad = {
        "epochs": [
            {
                "epoch_id": "2025_E1",
                "telemetry": {
                    "url": "https://example.org/telemetry.bin.gz",
                    "format": "float16_uint32_le_gzip",
                    "width": WIDTH,
                    "height": HEIGHT,
                    "byte_size": 1,
                    "flux_band": "all",
                },
            }
        ]
    }
    with pytest.raises(ValueError, match="not a local"):
        _golden_epochs(bad, "barnards_star")


def test_committed_golden_telemetry_when_present() -> None:
    """Stage 2 caches must carry one sidecar per epoch (skipped pre-B8)."""
    repo_root = Path(__file__).resolve().parents[2]
    for target_id in (
        "wise_0855",
        "barnards_star",
        "eps_indi_b",
        "rw_aurigae",
        "r_draconis",
    ):
        manifest = json.loads(
            (repo_root / "golden_cache" / target_id / "manifest.json").read_text(
                encoding="utf-8"
            )
        )
        blocks = [
            epoch.get("telemetry")
            for epoch in manifest["epochs"]
            if isinstance(epoch.get("telemetry"), dict)
        ]
        if not blocks:
            continue
        assert len(blocks) == len(manifest["epochs"])
        for block in blocks:
            assert block["format"] == "float16_uint32_le_gzip"
            assert block["url"].startswith(
                f"/api/v1/assets/{target_id}/telemetry_"
            )
            assert block["flux_band"] == (
                "thermal" if target_id == "wise_0855" else "all"
            )
