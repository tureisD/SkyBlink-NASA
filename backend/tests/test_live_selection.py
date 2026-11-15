"""Algorithm boundary inputs, isolated from observed and packaged products."""
from types import SimpleNamespace

import numpy as np
import pytest

from services.irsa_client import ArtifactRecord, IRSANoData, IRSAUnavailable
from services import live_selection as selection


def signature(wavelength=4.65, width=.04):
    return np.array([[wavelength] * 9, [width] * 9])


def record(name, band=6):
    return ArtifactRecord(f"unit-{name}", 60000, None, band, f"SPHEREx-D{band}", name, "DR1", "spherex_dr1")


def test_compatibility_requires_entire_sample_grid_and_positive_bandwidth():
    first = signature()
    assert selection.compatible(first, signature(4.659))
    assert not selection.compatible(first, signature(4.661))
    edge = signature()
    edge[0, 8] += .02
    assert not selection.compatible(first, edge)  # Center alone is insufficient.
    for invalid in (np.nan, np.inf, 0, -1):
        bad = signature()
        bad[1, 0] = invalid
        assert not selection.compatible(first, bad)
    assert not selection.compatible(first, signature(4.656, .02))  # Narrower width controls.


def test_selection_chooses_latest_compatible_pair_and_common_bands(monkeypatch):
    epochs = [SimpleNamespace(epoch_id=f"e{index}") for index in (1, 2, 3)]
    a, b, c, missing = record("a"), record("b"), record("c"), record("missing", 1)
    candidates = {("e1", 6): [a], ("e2", 6): [b], ("e3", 6): [c], ("e3", 1): [missing]}
    contents = {a: b"a", b: b"b", c: b"c", missing: b"missing"}
    values = {b"a": signature(4.3), b"b": signature(4.65), b"c": signature(4.655), b"missing": signature(1)}
    monkeypatch.setattr(selection, "spectral_signature", lambda content, *args: values[content])
    monkeypatch.setattr(selection, "dense_spectral_signature", lambda content, *args: values[content])
    selected_epochs, chosen = selection.select_pair(epochs, candidates, contents, 0, 0, .05, lambda: None)
    assert [epoch.epoch_id for epoch in selected_epochs] == ["e2", "e3"]
    assert chosen == {("e2", 6): [b], ("e3", 6): [c]}


def test_multiple_incompatible_epochs_are_not_presented_as_a_single_epoch(monkeypatch):
    epochs = [SimpleNamespace(epoch_id=f"e{index}") for index in (1, 2)]
    a, b = record("a"), record("b")
    monkeypatch.setattr(selection, "spectral_signature", lambda content, *args: signature(4.3 if content == b"a" else 4.8))
    with pytest.raises(IRSANoData) as error:
        selection.select_pair(epochs, {("e1", 6): [a], ("e2", 6): [b]}, {a: b"a", b: b"b"}, 0, 0, .2, lambda: None)
    assert error.value.detail["reason"] == "NO_COMPARABLE_EPOCHS"
    assert error.value.detail["candidate_epochs"] == ["e1", "e2"]


def test_malformed_spectral_wcs_is_upstream_failure_not_absent_coverage(monkeypatch):
    def malformed(*args):
        raise ValueError("missing spectral axis")

    monkeypatch.setattr(selection, "spectral_signature", malformed)
    artifact = record("malformed")
    with pytest.raises(IRSAUnavailable, match="invalid spectral WCS"):
        selection.select_pair([], {}, {artifact: b"invalid-test-input"}, 0, 0, .05, lambda: None)


def test_equal_centers_with_different_bandwidths_are_not_comparable():
    assert not selection.compatible(signature(width=.04),signature(width=.03))
    assert selection.compatible(signature(width=.04),signature(width=.032))


def test_dense_grid_rejects_mismatch_between_coarse_samples(monkeypatch):
    epochs = [SimpleNamespace(epoch_id=f"e{index}") for index in (1,2)]
    a,b = record("dense-a"),record("dense-b")
    monkeypatch.setattr(selection,"spectral_signature",lambda *args:signature())
    dense_b = signature()
    dense_b[0,1] += .02
    monkeypatch.setattr(selection,"dense_spectral_signature",lambda content,*args:signature() if content == b"a" else dense_b)
    with pytest.raises(IRSANoData):
        selection.select_pair(epochs,{("e1",6):[a],("e2",6):[b]},{a:b"a",b:b"b"},0,0,.2,lambda:None)


def test_composite_selection_keeps_common_bands_within_thirty_days():
    from dataclasses import replace
    epochs = [SimpleNamespace(epoch_id=f"e{index}") for index in (1,2)]
    selected = {}
    for index,epoch in enumerate(epochs):
        for band,offset in ((1,0),(2,20),(3,60)):
            selected[(epoch.epoch_id,band)] = [replace(record(f"{epoch.epoch_id}-{band}",band),mjd_lower=60000+200*index+offset)]
    result = selection.compact_selection(epochs,selected)
    assert set(result) == {("e1",1),("e1",2),("e2",1),("e2",2)}


def test_unusable_best_spectral_candidate_does_not_hide_next_usable_pair(monkeypatch):
    epochs = [SimpleNamespace(epoch_id=f"e{index}") for index in (1,2)]
    a,b,c = record("bad-background"),record("usable-alternative"),record("later")
    monkeypatch.setattr(selection,"spectral_signature",lambda *args:signature())
    monkeypatch.setattr(selection,"dense_spectral_signature",lambda *args:signature())
    _,chosen = selection.select_pair(epochs,{("e1",6):[a,b],("e2",6):[c]},
                                    {a:b"a",b:b"b",c:b"c"},0,0,.2,lambda:None,
                                    lambda candidate:candidate != a)
    assert chosen == {("e1",6):[b],("e2",6):[c]}


def test_best_pair_does_not_spend_budget_validating_worse_pairs(monkeypatch):
    epochs = [SimpleNamespace(epoch_id=f"e{index}") for index in (1, 2)]
    a, b, c = record("best"), record("worse"), record("later")
    values = {b"a": signature(4.65), b"b": signature(4.655), b"c": signature(4.65)}
    dense_calls = []
    monkeypatch.setattr(selection, "spectral_signature", lambda content, *args: values[content])
    def dense(content, *args):
        dense_calls.append(content)
        return values[content]
    monkeypatch.setattr(selection, "dense_spectral_signature", dense)
    _, chosen = selection.select_pair(epochs, {("e1", 6): [b, a], ("e2", 6): [c]},
                                      {a: b"a", b: b"b", c: b"c"}, 0, 0, .2, lambda: None)
    assert chosen == {("e1", 6): [a], ("e2", 6): [c]}
    assert b"b" not in dense_calls


@pytest.mark.parametrize("size,side",[(.05,58),(.2,234)])
def test_field_mask_uses_exact_contract_pixel_centers(size,side):
    expected = np.zeros((240,240),dtype=bool)
    lower,upper = (91,149) if size == .05 else (3,237)
    expected[lower:upper,lower:upper] = True
    assert np.array_equal(selection.field_pixel_mask(size),expected)
    assert int(expected.sum()) == side**2
