"""Recorded real metadata and isolated transport faults; no observation generation."""
from copy import deepcopy
import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from core.cachekeys import live_asset_key
from core.config import Settings
from core.source_policy import source_target
from services import spherex_pipeline, spectrophotometry
from services.irsa_client import IRSAIncompleteDiscovery, IRSAUnavailable
from services.known_exposures import INDEX_PATH, KnownExposureClient


@pytest.fixture
def indexed(tmp_path):
    index = json.loads(INDEX_PATH.read_text())
    path = tmp_path / "index.json"
    path.write_text(json.dumps(index))
    client = KnownExposureClient(Settings(cache_dir=tmp_path / "cache"), target_id="rw_aurigae", index_path=path)
    query = index["targets"]["rw_aurigae"]["query"]
    return client, path, index, query


def test_known_inventory_is_partial_and_retains_real_metadata(indexed, monkeypatch):
    client, path, index, query = indexed
    monkeypatch.setattr(client, "_new_client", lambda: pytest.fail("Known inventory must not invent a network metadata query"))
    records = client.query_artifacts(**query, allow_partial=True)
    assert len(records) == len(index["targets"]["rw_aurigae"]["records"])
    assert all(record.s_region and record.mjd_upper >= record.mjd_lower for record in records)
    assert client.discovery_metadata["status"] == "partial"
    assert client.discovery_metadata["responses"] == []
    assert client.discovery_metadata["index_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert client.use_cache is False
    with pytest.raises(IRSAIncompleteDiscovery):
        client.query_artifacts(**query)


@pytest.mark.parametrize("change", ["unsafe_url", "wrong_coordinates", "invalid_time", "wrong_release", "empty", "duplicate"])
def test_invalid_index_fails_before_download(indexed, change):
    client, path, index, query = indexed
    entry = index["targets"]["rw_aurigae"]
    if change == "unsafe_url":
        entry["records"][0]["uri"] = "https://untrusted.example/observation.fits"
    elif change == "wrong_coordinates":
        entry["query"]["ra"] += 1
        query = {"ra": source_target("rw_aurigae", "archive").ra_epoch2025, "dec": query["dec"]}
    elif change == "invalid_time":
        entry["records"][0]["mjd_upper"] = -1
    elif change == "wrong_release":
        entry["records"][0]["release"] = "QR2"
    elif change == "empty":
        entry["records"] = []
    else:
        entry["records"].append(deepcopy(entry["records"][0]))
    path.write_text(json.dumps(index))
    with pytest.raises(IRSAUnavailable):
        client.query_artifacts(**query, allow_partial=True)


def test_known_download_never_uses_existing_input_cache(indexed, monkeypatch):
    client, _, _, query = indexed
    record = client.query_artifacts(**query, allow_partial=True)[0]
    # Deliberately invalid protocol cache sentinel, not a synthetic FITS observation.
    path = client._cutout_cache_path(record, query["ra"], query["dec"], .2)
    path.write_bytes(b"SIMPLE cached protocol sentinel")
    def fresh_request(*args, **kwargs):
        raise IRSAUnavailable("fresh network attempted")
    monkeypatch.setattr(client, "_request", fresh_request)
    with pytest.raises(IRSAUnavailable, match="fresh network attempted"):
        client.fetch_cutout(record, query["ra"], query["dec"], .2, client=object())
    assert client.acquisition_metadata[-1]["from_cache"] is False


def test_modes_have_distinct_asset_keys_and_singleflight_keys(monkeypatch):
    assert live_asset_key(10, 20, .2) != live_asset_key(10, 20, .2, discovery_mode="known")
    assert spectrophotometry.spectrum_asset_key(10, 20) != spectrophotometry.spectrum_asset_key(10, 20, discovery_mode="known")
    monkeypatch.setattr(spherex_pipeline, "run_once", lambda key, *args, **kwargs: key)
    live = spherex_pipeline.build_manifest("same", 10, 20, cutout_size_deg=.2)
    known = spherex_pipeline.build_manifest("same", 10, 20, cutout_size_deg=.2, discovery_mode="known")
    assert live != known
    monkeypatch.setattr(spectrophotometry, "run_once", lambda key, *args, **kwargs: key)
    args = {"confidence": "low", "max_visits_per_band": 1}
    assert spectrophotometry.build_spectrum("same", 10, 20, **args) != spectrophotometry.build_spectrum("same", 10, 20, discovery_mode="known", **args)


@pytest.mark.parametrize("endpoint", ["sky", "spectrum"])
@pytest.mark.parametrize("extra", [{}, {"target_id": "rw_aurigae", "source": "saved"}])
def test_known_query_requires_explicit_archive_catalog(endpoint, extra):
    result = TestClient(app).get(f"/api/v1/{endpoint}", params={"ra": 10, "dec": 20, "discovery": "known", **extra})
    assert result.status_code == 422
    assert result.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("endpoint", ["sky", "spectrum"])
def test_routes_forward_explicit_known_mode_and_never_switch_default(monkeypatch, endpoint):
    from routers import sky, spectrum
    target = source_target("rw_aurigae", "archive")
    seen = []
    def unavailable(*args, **kwargs):
        seen.append(kwargs["discovery_mode"])
        raise IRSAUnavailable("isolated acquisition failure")
    monkeypatch.setattr(sky, "build_manifest", unavailable)
    monkeypatch.setattr(spectrum, "build_spectrum", unavailable)
    q = {"ra": target.ra_epoch2025, "dec": target.dec_epoch2025, "target_id": target.id, "source": "archive"}
    client = TestClient(app)
    assert client.get(f"/api/v1/{endpoint}", params=q).status_code == 503
    assert client.get(f"/api/v1/{endpoint}", params=dict(q, discovery="known")).status_code == 503
    assert seen == ["live", "known"]
