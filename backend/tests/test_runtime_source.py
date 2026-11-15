"""Source drift uses isolated source trees; no observations or real source edits."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services import provenance


@pytest.fixture
def bound_source(tmp_path, monkeypatch):
    monkeypatch.setattr(provenance, "_APPLICATION_SOURCE", None)
    source = tmp_path / "backend/services/extract.py"
    source.parent.mkdir(parents=True)
    source.write_text("VERSION = 12\n")
    provenance.bind_application_source(tmp_path)
    return tmp_path, source


@pytest.mark.parametrize("change", ["edit", "delete", "add", "astrometry"])
def test_source_drift_rejected_without_rebinding(bound_source, change):
    root, source = bound_source
    provenance.assert_application_source_current()
    if change == "edit":
        source.write_text("VERSION = 13\n")
    elif change == "delete":
        source.unlink()
    elif change == "add":
        source.with_name("new_method.py").write_text("NEW = True\n")
    else:
        profile = root / "backend/core/staged_astrometry.json"
        profile.parent.mkdir(parents=True)
        profile.write_text("{}")
    with pytest.raises(provenance.RuntimeSourceChanged, match="Restart"):
        provenance.assert_application_source_current()
    with pytest.raises(provenance.RuntimeSourceChanged):
        provenance.bind_application_source(root)


def test_cache_docs_tests_and_timestamps_do_not_cause_drift(bound_source):
    root, source = bound_source
    for name in ("backend/.cache/data.fits", "backend/tests/test_sample.py", "docs/note.md"):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"not processing source")
    source.touch()
    provenance.assert_application_source_current()


def test_midbuild_drift_blocks_record_before_validation(bound_source):
    _, source = bound_source
    source.write_text("CHANGED = True\n")
    with pytest.raises(provenance.RuntimeSourceChanged):
        provenance.make_record(kind="image", query={}, inputs=[], exposures=[], method={})


@pytest.mark.parametrize("endpoint", ["sky", "spectrum"])
def test_api_source_drift_fails_before_archive_work(bound_source, monkeypatch, endpoint):
    from app.main import app
    from routers import sky, spectrum
    _, source = bound_source
    source.write_text("CHANGED = True\n")

    def forbidden(*args, **kwargs):
        pytest.fail("A stale process must not start archive acquisition")

    monkeypatch.setattr(sky, "build_manifest", forbidden)
    monkeypatch.setattr(spectrum, "build_spectrum", forbidden)
    response = TestClient(app).get(f"/api/v1/{endpoint}", params={"ra": 10, "dec": 20, "source": "archive"})
    assert response.status_code == 503
    assert response.json()["error"]["detail"]["reason"] == "PROCESSING_SOURCE_CHANGED"
    assert "Restart" in response.json()["error"]["message"]


def test_unbound_standalone_capture_uses_current_source(tmp_path, monkeypatch):
    monkeypatch.setattr(provenance, "_APPLICATION_SOURCE", None)
    folder = tmp_path / "backend/services"
    folder.mkdir(parents=True)
    file = folder / "source.py"
    file.write_text("VERSION = 1")
    first = provenance.capture_code_identity(tmp_path)
    file.write_text("VERSION = 2")
    provenance.assert_application_source_current()
    second = provenance.capture_code_identity(tmp_path)
    assert first["source_digest"] != second["source_digest"]
