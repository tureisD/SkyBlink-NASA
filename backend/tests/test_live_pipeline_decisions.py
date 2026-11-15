"""Live orchestration decisions with isolated protocol/render-stage doubles.

Real saved metadata supplies epoch labels and payload shape. These tests do
not claim the stage doubles are measured sky data and never write products.
"""
from copy import deepcopy
import gzip
import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
import numpy as np
import pytest

from app.main import app
from services import spherex_pipeline as pipeline
from services.irsa_client import ArtifactRecord, IRSANoData

ROOT = Path(__file__).resolve().parents[2]


def setup_discovery(monkeypatch, tmp_path, count, incomplete=False, fetch_sizes=None):
    golden = json.loads((ROOT / "golden_cache/wise_0855/manifest.json").read_text())
    epochs = golden["epochs"][:count]
    records = [ArtifactRecord(epoch["band_stats"]["6"]["artifact_uris"][0], epoch["mjd_mean"], None,
                              6, "SPHEREx-D6", epoch["epoch_id"], "DR1", "spherex_dr1") for epoch in epochs]
    class Client:
        def __init__(self, *args, **kwargs):
            self.deadline_at = kwargs.get("deadline_at")
        def query_artifacts(self, *args, **kwargs):
            assert kwargs["fallback"] is True
            return records
        def fetch_cutouts(self, chosen, *args, **kwargs):
            if fetch_sizes is not None:
                fetch_sizes.append(kwargs.get("size_deg", args[2] if len(args) > 2 else None))
            # The failed observation is stable even when acquisition order changes.
            return {record: b"isolated-stage-double" for record in chosen if not incomplete or record != records[-1]}
    monkeypatch.setattr(pipeline, "IrsaClient", Client)
    monkeypatch.setattr(pipeline, "_load_cached_manifest", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "_asset_dir", lambda key: tmp_path)
    monkeypatch.setattr(pipeline, "_write_manifest", lambda payload: None)
    # This test isolates orchestration with non-observation stage doubles.
    # Real scientific lineage/replay is tested on downloaded FITS separately.
    monkeypatch.setattr(pipeline, "record_images", lambda *args, **kwargs: None)
    return golden, epochs


def setup_render(monkeypatch, golden, epochs):
    sidecar = ROOT / "golden_cache/wise_0855" / Path(epochs[0]["telemetry"]["url"]).name
    actual_flux = np.frombuffer(gzip.decompress(sidecar.read_bytes()), dtype="<f2", count=240*240).reshape(240, 240)
    monkeypatch.setattr(pipeline, "_coadd_band", lambda *args, **kwargs: SimpleNamespace(image_mjy_sr=actual_flux))
    monkeypatch.setattr(pipeline, "_normalization_candidates", lambda *args: {})
    monkeypatch.setattr(pipeline, "_compute_normalization", lambda *args: {})
    monkeypatch.setattr(pipeline, "_apply_normalization", lambda *args: None)
    monkeypatch.setattr(pipeline, "_build_epoch_payloads", lambda *args, **kwargs: deepcopy(epochs))
    monkeypatch.setattr(pipeline, "_build_differences", lambda *args, **kwargs: {})
    monkeypatch.setattr(pipeline, "_top_level_provenance", lambda *args: deepcopy(golden["provenance"]))


def test_genuine_single_archive_epoch_is_allowed_without_pair_matching(monkeypatch, tmp_path):
    fetch_sizes = []
    golden, epochs = setup_discovery(monkeypatch, tmp_path, 1, fetch_sizes=fetch_sizes)
    def forbidden(*args, **kwargs):
        raise AssertionError("One archive epoch must not invent a comparison partner")
    monkeypatch.setattr(pipeline, "select_pair", forbidden)
    setup_render(monkeypatch, golden, epochs)
    result = pipeline.build_manifest("single-test", 1, 2, cutout_size_deg=.05,
                                     live_mode=True, max_epochs=3, deadline_seconds=5)
    assert len(result["epochs"]) == 1
    assert result["differences"] == {}
    assert result["live_selection"]["method"] == "single_archive_epoch"
    assert fetch_sizes == pytest.approx([np.sqrt(2) * .05 + 2 * 6.15 / 3600])
    assert result["query"]["cutout_size_deg"] == .05


def test_complete_compatible_pair_survives_unused_failed_candidate(monkeypatch, tmp_path):
    golden, epochs = setup_discovery(monkeypatch, tmp_path, 3, incomplete=True)
    selected = []
    def compatible_pair(available_epochs, candidates, contents, *args):
        assert len(contents) == 2  # Third candidate's download failed.
        chosen_epochs = available_epochs[:2]
        selected.extend(epoch.epoch_id for epoch in chosen_epochs)
        chosen = {key: records for key, records in candidates.items()
                  if key[0] in selected and all(record in contents for record in records)}
        assert len(chosen) == 2
        return chosen_epochs, chosen
    monkeypatch.setattr(pipeline, "select_pair", compatible_pair)
    setup_render(monkeypatch, golden, epochs[:2])
    result = pipeline.build_manifest("complete-pair-test", 1, 2, cutout_size_deg=.05,
                                     live_mode=True, max_epochs=3, deadline_seconds=5)
    assert [epoch["epoch_id"] for epoch in result["epochs"]] == selected
    assert len(result["epochs"]) == 2
    assert result["provenance"]["is_simulated_fallback"] is False


@pytest.mark.parametrize("incomplete", [False, True])
def test_unmatched_pair_can_display_one_real_epoch_without_claiming_comparison(monkeypatch, tmp_path, incomplete):
    golden, observed = setup_discovery(monkeypatch, tmp_path, 2, incomplete=incomplete)
    def incompatible(*args, **kwargs):
        raise IRSANoData("No compatible sample", detail={"reason": "NO_COMPARABLE_EPOCHS"})
    monkeypatch.setattr(pipeline, "select_pair", incompatible)
    setup_render(monkeypatch, golden, observed[:1] if incomplete else observed[-1:])
    result = pipeline.build_manifest("single-observation-test", 1, 2, cutout_size_deg=.05,
                                     live_mode=True, allow_single_epoch=True, deadline_seconds=5)
    assert len(result["epochs"]) == 1
    assert result["differences"] == {}
    assert result["provenance"]["comparison_status"] == "unmatched_single_epoch"
    expected = "PARTIAL_DOWNLOAD_NO_MATCHED_PAIR" if incomplete else "NO_MATCHED_PAIR_IN_BOUNDED_SAMPLE"
    assert result["provenance"]["comparison_reason"] == expected
    assert len(result["live_selection"]["candidate_epoch_ids"]) == 2


def test_strict_rebuild_still_rejects_unmatched_pair(monkeypatch, tmp_path):
    setup_discovery(monkeypatch, tmp_path, 2)
    def incompatible(*args, **kwargs):
        raise IRSANoData("No compatible sample", detail={"reason": "NO_COMPARABLE_EPOCHS"})
    monkeypatch.setattr(pipeline, "select_pair", incompatible)
    with pytest.raises(IRSANoData):
        pipeline.build_manifest("strict-test", 1, 2, cutout_size_deg=.05,
                                live_mode=True, allow_single_epoch=False, deadline_seconds=5)


def test_live_override_one_is_normalized_to_at_least_two_candidates(monkeypatch):
    seen = []
    def build(*args, **kwargs):
        seen.append(kwargs["max_epochs"])
        return {"captured": True}
    monkeypatch.setattr(pipeline, "_build_manifest", build)
    result = pipeline.build_manifest("minimum-test", 1, 2, cutout_size_deg=.05,
                                     live_mode=True, max_epochs=1, deadline_seconds=5)
    assert result == {"captured": True}
    assert seen == [2]


def test_comparison_round_rescues_failed_first_pair_then_stops(monkeypatch, tmp_path):
    golden, observed = setup_discovery(monkeypatch, tmp_path, 3)
    fetched = []
    original_fetch = pipeline.IrsaClient.fetch_cutouts
    def fetch(client, records, *args, **kwargs):
        fetched.append(list(records))
        assert kwargs["allow_partial"] is True
        assert kwargs["stage_deadline_at"] <= client.deadline_at
        return original_fetch(client, records, *args, **kwargs)
    monkeypatch.setattr(pipeline.IrsaClient, "fetch_cutouts", fetch)
    def proposals(epochs, *args, **kwargs):
        a,b,c = [epoch.records[0] for epoch in epochs]
        def proposal(first,second):
            return {"first":first,"second":second,"method":"isolated-protocol-order","corner_chord_distance":None}
        return [proposal(a,b),proposal(a,b),proposal(a,c),proposal(a,c),proposal(b,c)]
    monkeypatch.setattr(pipeline,"ranked_candidate_pairs",proposals)
    checks=[]
    def match(epochs,candidates,contents,*args):
        checks.append(len(contents))
        if len(checks)==1:
            raise IRSANoData("Isolated first-pair rejection")
        chosen_epochs=[epochs[0],epochs[2]]
        return chosen_epochs,{(epoch.epoch_id,6):[epoch.records[0]] for epoch in chosen_epochs}
    monkeypatch.setattr(pipeline,"select_pair",match)
    setup_render(monkeypatch,golden,[observed[0],observed[2]])
    result=pipeline.build_manifest("comparison-round-test",1,2,cutout_size_deg=.2,
                                   live_mode=True,allow_single_epoch=True,deadline_seconds=10)
    assert checks == [2,3]
    assert len(fetched)==2 and len(fetched[0])==2 and len(fetched[1])==1
    assert fetched[0][0].planeid != fetched[0][1].planeid
    assert result["provenance"]["comparison_status"] == "matched_visual"
    assert [entry["outcome"] for entry in result["live_selection"]["retrieval_rounds"]] == ["no_dense_usable_match","matched_visual"]


@pytest.mark.parametrize("retry_succeeds", [True, False])
def test_exhausted_small_inventory_retries_only_missing_partner_once(monkeypatch, tmp_path, retry_succeeds):
    golden, observed = setup_discovery(monkeypatch, tmp_path, 2)
    fetched = []
    windows = []
    def fetch(client, records, *args, **kwargs):
        fetched.append(list(records))
        assert kwargs["stage_deadline_at"] <= client.deadline_at
        windows.append(kwargs["stage_deadline_at"] - pipeline.time.monotonic())
        if len(fetched) == 1:
            return {records[0]: b"isolated-stage-double"}
        return {record: b"isolated-stage-double" for record in records} if retry_succeeds else {}
    monkeypatch.setattr(pipeline.IrsaClient, "fetch_cutouts", fetch)
    def match(epochs, candidates, contents, *args):
        if len(contents) < 2:
            raise IRSANoData("Isolated incomplete pair")
        return epochs, candidates
    monkeypatch.setattr(pipeline, "select_pair", match)
    setup_render(monkeypatch, golden, observed if retry_succeeds else observed[:1])
    result = pipeline.build_manifest("completion-test", 1, 2, cutout_size_deg=.2,
                                     live_mode=True, allow_single_epoch=True, deadline_seconds=120)
    assert len(fetched) == 2
    assert len(fetched[0]) == 2 and len(fetched[1]) == 1
    assert fetched[1][0] == fetched[0][1]  # Successful first input was not fetched again.
    assert windows == pytest.approx([18, 30], abs=1)
    assert result["live_selection"]["retrieval_rounds"][-1]["phase"] == "complete_incomplete_pairs"
    assert result["live_selection"]["missing_candidate_cutouts"] == (0 if retry_succeeds else 1)
    assert result["provenance"]["comparison_status"] == ("matched_visual" if retry_succeeds else "unmatched_single_epoch")
    # Historical first failure remains recorded; successful retry clears only
    # final missing status, not the history of the failed attempt.
    assert len(result["live_selection"]["retrieval_rounds"][0]["missing_uris"]) == 1
    assert len(result["live_selection"]["retrieval_rounds"][-1]["missing_uris"]) == (0 if retry_succeeds else 1)


def test_completion_does_not_retry_complete_scientifically_rejected_pair(monkeypatch, tmp_path):
    golden, observed = setup_discovery(monkeypatch, tmp_path, 2)
    fetched = []
    original = pipeline.IrsaClient.fetch_cutouts
    def fetch(client, records, *args, **kwargs):
        fetched.append(list(records))
        return original(client, records, *args, **kwargs)
    monkeypatch.setattr(pipeline.IrsaClient, "fetch_cutouts", fetch)
    def reject(*args, **kwargs):
        raise IRSANoData("Isolated scientific incompatibility")
    monkeypatch.setattr(pipeline, "select_pair", reject)
    setup_render(monkeypatch, golden, observed[-1:])
    result = pipeline.build_manifest("complete-rejected-test", 1, 2, cutout_size_deg=.2,
                                     live_mode=True, allow_single_epoch=True, deadline_seconds=10)
    assert len(fetched) == 1
    assert result["provenance"]["comparison_reason"] == "NO_MATCHED_PAIR_IN_BOUNDED_SAMPLE"


@pytest.mark.parametrize("after_first_check", [185.0, 190.0])
def test_completion_obeys_remaining_search_budget(monkeypatch, tmp_path, after_first_check):
    golden, observed = setup_discovery(monkeypatch, tmp_path, 2)
    clock = [100.0]
    # Replace only this module's clock, leaving thread/singleflight clocks alone.
    monkeypatch.setattr(pipeline, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    calls = []
    def fetch(client, records, *args, **kwargs):
        calls.append((list(records), kwargs["stage_deadline_at"]))
        if len(calls) == 1:
            return {records[0]: b"isolated-stage-double"}
        return {record: b"isolated-stage-double" for record in records}
    monkeypatch.setattr(pipeline.IrsaClient, "fetch_cutouts", fetch)
    def match(epochs, candidates, contents, *args):
        if len(contents) < 2:
            clock[0] = after_first_check
            raise IRSANoData("Isolated incomplete pair after bounded processing")
        return epochs, candidates
    monkeypatch.setattr(pipeline, "select_pair", match)
    expired = after_first_check == 190.0
    setup_render(monkeypatch, golden, observed[:1] if expired else observed)
    # Start100, total deadline220, comparison deadline190 (75% of120s).
    result = pipeline._build_manifest("completion-budget-test", 1, 2, cutout_size_deg=.2,
                                      live_mode=True, allow_single_epoch=True, deadline_seconds=120)
    assert calls[0][1] == 118.0
    if expired:
        assert len(calls) == 1  # No completion fetch after the search deadline.
        assert result["provenance"]["comparison_reason"] == "COMPARISON_SEARCH_BUDGET_REACHED"
        assert result["live_selection"]["missing_candidate_cutouts"] == 1
    else:
        assert len(calls) == 2
        assert calls[1][1] == 190.0  # Only5s remain, not a fresh30s budget.
        assert calls[1][1] - clock[0] == 5.0
        assert result["provenance"]["comparison_status"] == "matched_visual"
