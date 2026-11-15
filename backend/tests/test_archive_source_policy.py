"""Source routing boundaries; failures are protocol doubles, never observations."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from core.source_policy import source_target
from core.cachekeys import is_live_asset_key
from routers import sky, spectrum
from services.irsa_client import IRSAUnavailable


@pytest.mark.parametrize("endpoint,module,builder,saved_loader", [
    ("sky", sky, "build_manifest", "load_golden_manifest"),
    ("spectrum", spectrum, "build_spectrum", "load_golden_spectrum"),
])
def test_default_catalog_request_uses_corrected_archive_never_saved(monkeypatch, endpoint, module, builder, saved_loader):
    target = source_target("wise_0855", "archive")
    calls = []
    def unavailable(key, ra, dec, **kwargs):
        calls.append((key, ra, dec, kwargs))
        raise IRSAUnavailable("Controlled upstream outage")
    def forbidden(*args, **kwargs):
        raise AssertionError("Archive requests must never load saved products")
    monkeypatch.setattr(module, builder, unavailable)
    monkeypatch.setattr(module, saved_loader, forbidden)
    with TestClient(app) as client:
        response = client.get(f"/api/v1/{endpoint}", params={"target_id": target.id,
                              "ra": target.ra_epoch2025, "dec": target.dec_epoch2025})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "UPSTREAM_UNAVAILABLE"
    assert len(calls) == 1
    key, ra, dec, options = calls[0]
    assert is_live_asset_key(key)
    assert (ra, dec) == (target.ra_epoch2025, target.dec_epoch2025)
    assert options["force_refresh"] is True
    assert options["live_mode"] is True
    assert options["deadline_seconds"] == 120


@pytest.mark.parametrize("endpoint", ["sky", "spectrum"])
def test_saved_mode_requires_named_target(endpoint):
    with TestClient(app) as client:
        response = client.get(f"/api/v1/{endpoint}", params={"ra": 1, "dec": 2, "source": "saved"})
    assert response.status_code == 422


def test_catalog_modes_keep_historical_and_corrected_coordinates_separate():
    with TestClient(app) as client:
        archive = client.get("/api/v1/targets").json()["targets"]
        saved = client.get("/api/v1/targets", params={"source": "saved"}).json()["targets"]
        invalid = client.get("/api/v1/targets", params={"source": "arbitrary"})
    new = next(target for target in archive if target["id"] == "wise_0855")
    old = next(target for target in saved if target["id"] == "wise_0855")
    assert new["ra_epoch2025"] == pytest.approx(133.76021647484097, abs=1e-10)
    assert old["ra_epoch2025"] == 133.75921
    assert invalid.status_code == 422
