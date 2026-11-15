"""Isolated ranking/protocol inputs; never observations or packaged products."""
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from services import live_selection as selection
from services.irsa_client import ArtifactRecord, IRSANoData, IrsaClient


def record(name, region=None):
    return ArtifactRecord(f"unit-ranking-{name}", 60000, 60001, 3, "SPHEREx-D3", name,
                          "DR1", "spherex_dr1", s_region=region)


REGION = "POLYGON ICRS 359 -1 1 -1 1 1 359 1 359 -1"
DISTANT = "POLYGON ICRS 10 -1 12 -1 12 1 10 1 10 -1"


def test_polygon_metadata_survives_sia_parsing_without_claiming_local_wavelength():
    actual = IrsaClient._record_from_sia2_row({"access_url": "https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/unit.fits",
        "energy_bandpassname": "SPHEREx-D3", "t_min": 60000, "s_region": REGION,
        "em_min": 1e-6, "em_max": 2e-6}, "spherex_dr1")
    assert actual.s_region == REGION
    assert not hasattr(actual, "wavelength_um")


def test_rank_searches_beyond_independent_evenly_spaced_sample():
    old = record("old", REGION)
    sampled = record("sampled", DISTANT)
    hidden = record("outside-old-sample", REGION)
    epochs = [SimpleNamespace(epoch_id="e1", records=[old]),
              SimpleNamespace(epoch_id="e2", records=[sampled, hidden])]
    ranked = selection.ranked_candidate_pairs(epochs, {("e1", 3): [old], ("e2", 3): [sampled]}, max_pairs=1)
    assert ranked[0]["first"] == old and ranked[0]["second"] == hidden
    assert ranked[0]["corner_chord_distance"] == 0


def test_corner_order_preserves_detector_orientation_and_handles_ra_wrap():
    original = record("original", REGION)
    same = record("same", "POLYGON ICRS -1 -1 1 -1 1 1 -1 1 -1 -1")
    rotated = record("rotated", "POLYGON ICRS 1 1 359 1 359 -1 1 -1 1 1")
    epochs = [SimpleNamespace(epoch_id="e1", records=[original]),
              SimpleNamespace(epoch_id="e2", records=[rotated, same])]
    ranked = selection.ranked_candidate_pairs(epochs, {})
    assert ranked[0]["second"] == same
    assert ranked[0]["corner_chord_distance"] < 1e-14
    assert ranked[1]["corner_chord_distance"] > .01


def test_missing_or_invalid_footprints_use_balanced_fallback_only():
    old = record("old", "POLYGON ICRS nan 1")
    new = record("new")
    epochs = [SimpleNamespace(epoch_id="e1", records=[old]), SimpleNamespace(epoch_id="e2", records=[new])]
    ranked = selection.ranked_candidate_pairs(epochs, {("e1", 3): [old], ("e2", 3): [new]})
    assert [(item["first"], item["second"]) for item in ranked] == [(old, new)]
    assert ranked[0]["corner_chord_distance"] is None
    assert ranked[0]["method"] == "balanced_time_sample_without_footprints"


def test_identical_geometry_never_overrides_measured_wavelength_rejection(monkeypatch):
    old = record("old", REGION)
    new = replace(record("new", REGION), mjd_lower=60200, mjd_upper=60201)
    epochs = [SimpleNamespace(epoch_id="e1", records=[old]), SimpleNamespace(epoch_id="e2", records=[new])]
    candidates = {("e1", 3): [old], ("e2", 3): [new]}
    assert selection.ranked_candidate_pairs(epochs, candidates)[0]["corner_chord_distance"] == 0
    monkeypatch.setattr(selection, "spectral_signature", lambda content, *args:
                        np.array([[1.5 if content == b"protocol-a" else 1.7]*9, [.02]*9]))
    with pytest.raises(IRSANoData, match="No spectrally comparable"):
        selection.select_pair(epochs, candidates, {old: b"protocol-a", new: b"protocol-b"},
                              0, 0, .2, lambda: None)


def test_ranking_deadline_stops_before_large_inventory_work():
    old,new=record("old",REGION),record("new",REGION)
    epochs=[SimpleNamespace(epoch_id="e1",records=[old]),SimpleNamespace(epoch_id="e2",records=[new])]
    def expired():
        raise TimeoutError("isolated ranking deadline")
    with pytest.raises(TimeoutError,match="ranking deadline"):
        selection.ranked_candidate_pairs(epochs,{},check_deadline=expired)


def test_ranking_ties_do_not_depend_on_discovery_row_order():
    left=[record(f"left-{index}",REGION) for index in range(12)]
    right=[record(f"right-{index}",REGION) for index in range(12)]
    def ranking(a,b):
        epochs=[SimpleNamespace(epoch_id="e1",records=a),SimpleNamespace(epoch_id="e2",records=b)]
        return [(item["first"].uri,item["second"].uri) for item in selection.ranked_candidate_pairs(epochs,{})]
    assert ranking(left,right)==ranking(left[::-1],right[::-1])


def test_missing_footprints_keep_reserved_acquisition_chance():
    left=[record(f"left-{index}",REGION) for index in range(6)]
    right=[record(f"right-{index}",REGION) for index in range(6)]
    missing=record("missing-polygon")
    epochs=[SimpleNamespace(epoch_id="e1",records=left),SimpleNamespace(epoch_id="e2",records=right+[missing])]
    candidates={("e1",3):left[:1],("e2",3):[missing]}
    ranked=selection.ranked_candidate_pairs(epochs,candidates,max_pairs=4)
    assert len(ranked)==4
    assert any(item["second"]==missing for item in ranked)
