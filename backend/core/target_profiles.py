"""Explicit reviewed staging astrometry; production remains a coherent old set."""
from dataclasses import replace
import json
from pathlib import Path

from core.targets import TARGETS, TargetRecord, propagated_coordinates

PROFILE = Path(__file__).with_name("staged_astrometry.json")


def corrected_targets() -> tuple[TargetRecord, ...]:
    records = {item["target_id"]: item for item in json.loads(PROFILE.read_text(encoding="utf-8"))["targets"]}
    corrected = []
    for old in TARGETS:
        entry = records[old.id]
        epoch = entry["reference_time"]
        target = replace(
            old, ra_ref=entry["reference_ra_deg"], dec_ref=entry["reference_dec_deg"],
            ref_epoch=entry["display_reference_epoch"],
            pm_ra_mas_yr=entry["pm_ra_cosdec_mas_yr"], pm_dec_mas_yr=entry["pm_dec_mas_yr"],
            reference_time_value=epoch["value"], reference_time_format=epoch["format"],
            reference_time_scale=epoch["scale"], astrometry_citation=entry["citation"],
            story_body=("Staged corrected catalog astrometry. Real measurements remain approximate; "
                        "this profile alone does not establish uncontaminated photometry or variability. " + entry["caveat"]),
        )
        position = propagated_coordinates(target)
        corrected.append(replace(target, ra_epoch2025=float(position.ra.deg), dec_epoch2025=float(position.dec.deg)))
    return tuple(corrected)
