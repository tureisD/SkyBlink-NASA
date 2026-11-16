"""Fail-closed product policy using real cached observations and rejected inputs."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app, create_app
from core.config import settings
from core.targets import TARGETS, get_target
from services import golden_cache
from services.irsa_client import IrsaClient

ROOT = Path(__file__).resolve().parents[2]


def test_five_real_targets_and_assets_work_without_network(monkeypatch):
    def offline(*args, **kwargs):
        raise AssertionError("Catalog data must be served offline")
    monkeypatch.setattr(IrsaClient, "query_artifacts", offline)
    with TestClient(app) as client:
        for target in TARGETS:
            query = {"source": "saved", "target_id": target.id, "ra": target.ra_epoch2025, "dec": target.dec_epoch2025}
            sky = client.get("/api/v1/sky", params=query)
            spectrum = client.get("/api/v1/spectrum", params=query)
            assert sky.status_code == spectrum.status_code == 200
            for result in (sky.json(), spectrum.json()):
                assert result["provenance"]["is_simulated_fallback"] is False
                assert result["epochs"]
            for epoch in sky.json()["epochs"]:
                for url in epoch["frames"].values():
                    asset = client.get(url)
                    assert asset.status_code == 200
                    assert asset.headers["content-type"] == "image/webp"


def test_retired_namespace_files_cannot_be_served_even_if_reintroduced(tmp_path, monkeypatch):
    from routers import assets
    from fastapi.staticfiles import StaticFiles
    isolated = replace(settings, golden_cache_dir=tmp_path / "golden", cache_dir=tmp_path / "cache")
    monkeypatch.setattr(assets, "settings", isolated)
    names = ["mock", "unknown", *(f"fallback_{target.id}" for target in TARGETS)]
    for base in (isolated.golden_cache_dir, isolated.live_cache_dir):
        for name in names:
            directory = base / name
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "manifest.json").write_text('{"is_simulated_fallback":true}')
    static_dir = tmp_path / "dist"
    (static_dir / "mock").mkdir(parents=True)
    (static_dir / "mock" / "manifest.json").write_text("{}")
    (static_dir / "mock" / "2025_E1_ALL.webp").write_bytes(b"rejected fixture")
    static_app = create_app()
    static_app.mount("/", StaticFiles(directory=static_dir, html=True))
    with TestClient(static_app) as client:
        for name in names:
            assert client.get(f"/api/v1/assets/{name}/manifest.json").status_code == 404
        for url in ("/mock", "/mock/manifest.json", "/mock/2025_E1_ALL.webp"):
            assert client.get(url).status_code == 404
            assert client.head(url).status_code == 404


@pytest.mark.parametrize("marker", [True, None, "false", 0])
def test_golden_loaders_require_explicit_real_provenance(marker):
    target = get_target("wise_0855")
    directory = ROOT / "golden_cache" / target.id
    manifest = json.loads((directory / "manifest.json").read_text())
    spectrum = json.loads((directory / "spectrum.json").read_text())
    assert golden_cache._validate_manifest(target, manifest, directory)
    assert golden_cache._validate_golden_spectrum(target, spectrum)
    for payload in (manifest, spectrum):
        if marker is None:
            payload["provenance"].pop("is_simulated_fallback")
        else:
            payload["provenance"]["is_simulated_fallback"] = marker
    assert not golden_cache._validate_manifest(target, manifest, directory)
    assert not golden_cache._validate_golden_spectrum(target, spectrum)


@pytest.mark.parametrize("kind", ["sky", "spectrum"])
@pytest.mark.parametrize("marker", [True, None])
def test_live_cache_loaders_reject_simulated_or_unknown_provenance(tmp_path, monkeypatch, kind, marker):
    from datetime import datetime, timezone
    from services import spherex_pipeline as sky, spectrophotometry as spectra

    target = get_target("wise_0855")
    directory = ROOT / "golden_cache" / target.id
    filename = "manifest.json" if kind == "sky" else "spectrum.json"
    payload = json.loads((directory / filename).read_text())
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    payload["max_visits_per_band"] = 3
    payload["max_epochs"] = None
    path = tmp_path / filename
    if kind == "sky":
        payload["version"] = sky.CACHE_VERSION
        for epoch in payload["epochs"]:
            if epoch.get("telemetry"):
                epoch["telemetry"]["url"] = Path(epoch["telemetry"]["url"]).name
        monkeypatch.setattr(sky, "_manifest_path", lambda key: path)
        monkeypatch.setattr(sky, "_asset_dir", lambda key: directory)
        load = lambda: sky._load_cached_manifest(target.id, target.ra_epoch2025, target.dec_epoch2025, 0.2, 3, None)
    else:
        payload["version"] = spectra.SPECTRUM_CACHE_VERSION
        monkeypatch.setattr(spectra, "_spectrum_path", lambda key: path)
        load = lambda: spectra._load_cached_spectrum(target.id, target.ra_epoch2025, target.dec_epoch2025, 3, payload["confidence"])
    path.write_text(json.dumps(payload))
    assert load() is not None  # Prove the baseline cache is otherwise usable.
    if marker is None:
        payload["provenance"].pop("is_simulated_fallback")
    else:
        payload["provenance"]["is_simulated_fallback"] = marker
    path.write_text(json.dumps(payload))
    assert load() is None


def test_real_only_guard_detects_modified_and_unapproved_assets(tmp_path):
    from scripts.verify_real_data import TARGETS as approved_targets, digest, verify
    files = []
    for target in approved_targets:
        path = tmp_path / "golden_cache" / target / "manifest.json"
        path.parent.mkdir(parents=True)
        source = ROOT / "golden_cache" / target / "manifest.json"
        path.write_bytes(source.read_bytes())
        files.append({"path": path.relative_to(tmp_path).as_posix(), "sha256": digest(path), "approved_runtime_observation": True})
    metadata = tmp_path / "data/catalog-exposure-index.json"
    metadata.parent.mkdir()
    metadata.write_bytes((ROOT / "data/catalog-exposure-index.json").read_bytes())
    files.append({"path": "data/catalog-exposure-index.json", "sha256": digest(metadata), "approved_runtime_metadata": True})
    spatial = tmp_path / "data/archive-spatial-index.json.gz"
    spatial.write_bytes((ROOT / "data/archive-spatial-index.json.gz").read_bytes())
    files.append({"path": "data/archive-spatial-index.json.gz", "sha256": digest(spatial), "approved_runtime_metadata": True})
    inventory = tmp_path / "inventory.json"
    inventory.write_text(json.dumps({"files": files}))
    assert verify(tmp_path, inventory) == []
    changed = tmp_path / files[0]["path"]
    changed.write_bytes(changed.read_bytes() + b"\n")
    unwanted = tmp_path / "golden_cache" / "fallback_wise_0855" / "manifest.json"
    unwanted.parent.mkdir()
    unwanted.write_text("{}")
    errors = verify(tmp_path, inventory)
    assert any("Changed approved asset" in error for error in errors)
    assert any("Unapproved golden asset" in error for error in errors)
    metadata.write_bytes(metadata.read_bytes() + b"\n")
    (metadata.parent / "unapproved.json").write_text("{}")
    errors = verify(tmp_path, inventory)
    assert any("changed approved runtime metadata" in error for error in errors)
    assert any("Unapproved runtime metadata/data file" in error for error in errors)
