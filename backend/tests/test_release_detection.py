"""Focused B10 tests: DR1/QR3 release detection and labelling.

DR1 supersedes QR2 and is used together with QR3.  The API vocabulary is
``DR1``/``QR3``/``DR1+QR3`` (plus historical ``QR2``/``QR2+QR3`` for the
revision-2 golden cache); these tests pin the detection and label helpers.
"""

from __future__ import annotations

import pytest

from scripts.build_golden_cache import _record_release_and_collection
from services.irsa_client import (
    DEFAULT_SIA_COLLECTIONS,
    ArtifactRecord,
    _detect_release,
)
from services.spherex_pipeline import (
    EpochBucket,
    _top_level_provenance,
    epoch_collection_release,
    source_label,
)


def _record(band: int, release: str, collection: str) -> ArtifactRecord:
    return ArtifactRecord(
        uri=(
            "https://irsa.ipac.caltech.edu/ibe/data/spherex/"
            f"{release.lower()}/level2/example_{band}.fits"
        ),
        mjd_lower=61000.0,
        mjd_upper=None,
        band=band,
        band_name=f"SPHEREx-D{band}",
        planeid=f"plane-{band}",
        release=release,
        collection=collection,
    )


def _epoch(*records: ArtifactRecord) -> EpochBucket:
    return EpochBucket(
        epoch_id="2025_E1",
        index=1,
        year=2025,
        semester=1,
        label="Survey Epoch 1 (2025)",
        records=tuple(records),
        mjd_start=min(record.mjd_lower for record in records),
        mjd_end=max(record.mjd_mid for record in records),
    )


@pytest.mark.parametrize(
    ("uri", "expected"),
    [
        (
            "https://irsa.ipac.caltech.edu/ibe/data/spherex/"
            "dr1/level2/2025W19_1B/l2b-v27-2026-197/3/example.fits",
            ("DR1", "spherex_dr1"),
        ),
        (
            "https://irsa.ipac.caltech.edu/ibe/data/spherex/"
            "qr3/level2/example.fits",
            ("QR3", "spherex_qr3"),
        ),
        (
            "https://irsa.ipac.caltech.edu/ibe/data/spherex/"
            "qr2/level2/example.fits",
            ("QR2", "spherex_qr2"),
        ),
        ("/DR1/LEVEL2/EXAMPLE.FITS", ("DR1", "spherex_dr1")),
        ("https://example.test/unknown/example.fits", ("unknown", "spherex")),
    ],
)
def test_detect_release_from_uri(uri: str, expected: tuple[str, str]) -> None:
    assert _detect_release(uri) == expected


@pytest.mark.parametrize(
    ("hint", "expected"),
    [
        ("spherex_dr1", ("DR1", "spherex_dr1")),
        ("spherex_dr1_deep", ("DR1", "spherex_dr1")),
        ("spherex_qr3", ("QR3", "spherex_qr3")),
        ("spherex_qr3_deep", ("QR3", "spherex_qr3")),
        ("spherex_qr2", ("QR2", "spherex_qr2")),
    ],
)
def test_detect_release_from_collection_hint(
    hint: str, expected: tuple[str, str]
) -> None:
    assert _detect_release("", hint) == expected


def test_detect_release_prefers_uri_over_collection_hint() -> None:
    assert _detect_release("/ibe/data/spherex/dr1/level2/x.fits", "spherex_qr2") == (
        "DR1",
        "spherex_dr1",
    )


def test_sia2_default_collections_are_dr1_qr3_with_optional_deep() -> None:
    # Wide collections first so DEEP duplicates never win deduplication.
    assert DEFAULT_SIA_COLLECTIONS == (
        "spherex_dr1",
        "spherex_qr3",
        "spherex_dr1_deep",
        "spherex_qr3_deep",
    )
    assert "spherex_qr2" not in DEFAULT_SIA_COLLECTIONS


def test_build_cache_release_helper_accepts_dr1_and_keeps_qr_compatibility() -> None:
    assert _record_release_and_collection({"release": "DR1"}) == (
        "DR1",
        "spherex_dr1",
    )
    assert _record_release_and_collection({"release": "QR3"}) == (
        "QR3",
        "spherex_qr3",
    )
    assert _record_release_and_collection({"release": "QR2"}) == (
        "QR2",
        "spherex_qr2",
    )
    assert _record_release_and_collection({}) == ("unknown", "spherex")
    assert _record_release_and_collection({"release": "DP1"}) == (
        "unknown",
        "spherex",
    )


def test_source_label_handles_dr1_and_mixed_dr1_qr3() -> None:
    assert source_label("DR1") == "NASA/IPAC IRSA SPHEREx DR1"
    assert source_label("DR1+QR3") == "NASA/IPAC IRSA SPHEREx DR1/QR3"
    assert source_label("QR3") == "NASA/IPAC IRSA SPHEREx QR3"
    assert source_label("QR2") == "NASA/IPAC IRSA SPHEREx QR2"
    assert source_label("QR2+QR3") == "NASA/IPAC IRSA SPHEREx QR3/QR2"


def test_epoch_collection_release_labels_dr1_and_mixed_pairs() -> None:
    dr1_epoch = _epoch(_record(1, "DR1", "spherex_dr1"))
    assert epoch_collection_release(dr1_epoch) == ("spherex_dr1", "DR1")

    dr1_qr3_epoch = _epoch(
        _record(1, "DR1", "spherex_dr1"),
        _record(2, "QR3", "spherex_qr3"),
    )
    assert epoch_collection_release(dr1_qr3_epoch) == ("mixed", "DR1+QR3")

    qr2_qr3_epoch = _epoch(
        _record(1, "QR2", "spherex_qr2"),
        _record(2, "QR3", "spherex_qr3"),
    )
    assert epoch_collection_release(qr2_qr3_epoch) == ("mixed", "QR2+QR3")


def test_top_level_provenance_accepts_dr1_and_mixed_dr1_qr3() -> None:
    normalization = {
        "method": "static_source_p99_5",
        "reference_epoch": "2025_E1",
        "applied": True,
        "status": "ok",
        "clamped": False,
    }

    dr1_only = _top_level_provenance(
        [{"release": "DR1"}, {"release": "DR1"}], normalization
    )
    assert dr1_only["collection"] == "spherex_dr1"
    assert dr1_only["release"] == "DR1"
    assert dr1_only["source"] == "NASA/IPAC IRSA SPHEREx DR1"

    mixed = _top_level_provenance(
        [{"release": "DR1"}, {"release": "QR3"}], normalization
    )
    assert mixed["collection"] == "mixed"
    assert mixed["release"] == "DR1+QR3"
    assert mixed["source"] == "NASA/IPAC IRSA SPHEREx DR1/QR3"

    historical = _top_level_provenance(
        [{"release": "QR2"}, {"release": "QR3"}], normalization
    )
    assert historical["collection"] == "mixed"
    assert historical["release"] == "QR2+QR3"

    historical_epoch_labels = _top_level_provenance(
        [{"release": "QR2+QR3"}, {"release": "QR3"}], normalization
    )
    assert historical_epoch_labels["collection"] == "mixed"
    assert historical_epoch_labels["release"] == "QR2+QR3"
