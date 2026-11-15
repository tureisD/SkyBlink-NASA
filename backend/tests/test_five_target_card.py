"""Historical display smoke checks; explicitly not scientific acceptance."""

from __future__ import annotations

from scripts.run_five_target_card import TARGET_IDS, run_card


def test_five_target_card_has_no_failures() -> None:
    report = run_card()
    assert report["scientific_acceptance"] == "not_evaluated"
    assert set(report["targets"]) == set(TARGET_IDS)
    assert report["summary"]["fail"] == 0
    for target_id, target in report["targets"].items():
        assert target["status"] in {"pass", "partial"}, target_id
        assert target["checks_total"] > 0
        assert target["checks_passed"] > 0
        assert target["epochs"], target_id
        assert all(check["scientific_acceptance"] is False for check in target["checks"])
