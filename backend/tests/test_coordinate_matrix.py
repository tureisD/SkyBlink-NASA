"""Coordinate and FOV boundary contracts without asking IRSA for fake data."""
from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app.main import app
from routers import sky
from services.irsa_client import IRSANoData


@pytest.mark.parametrize("ra,dec", [(0.0, 0.0), (359.999999, -20.0), (0.000001, -20.0),
                                      (20.0, 89.9), (200.0, -89.9), (0.0, 90.0), (180.0, -90.0),
                                      (266.4051, -28.936175)])
@pytest.mark.parametrize("size,expected", [(.05, .05), (.2, .2), (.01, .05), (1.0, .2)])
def test_supported_coordinates_reach_live_pipeline_unchanged(monkeypatch, ra, dec, size, expected):
    calls = []
    def empty_archive(asset_key, center_ra, center_dec, *args, **kwargs):
        cutout_size = kwargs["cutout_size_deg"]
        calls.append((center_ra, center_dec, cutout_size))
        raise IRSANoData("Controlled empty archive response", collections_tried=["spherex_dr1", "spherex_qr3"])
    monkeypatch.setattr(sky, "build_manifest", empty_archive)
    with TestClient(app) as client:
        response = client.get("/api/v1/sky", params={"ra": ra, "dec": dec, "size": size})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NO_DATA"
    assert calls == [(ra, dec, expected)]


@pytest.mark.parametrize("ra,dec", [(-.01, 0), (360, 0), (0, -90.01), (0, 90.01),
                                      ("nan", 0), ("inf", 0), (0, "nan"), ("invalid", 0)])
def test_invalid_coordinates_are_rejected_before_discovery(monkeypatch, ra, dec):
    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid coordinates must not reach IRSA")
    monkeypatch.setattr(sky, "build_manifest", forbidden)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/sky", params={"ra": ra, "dec": dec})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_COORDINATES"
