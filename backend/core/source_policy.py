"""Keep corrected online astrometry separate from historical saved products."""
from core.target_profiles import corrected_targets
from core.targets import TARGETS


def source_targets(source: str):
    return TARGETS if source == "saved" else corrected_targets()


def source_target(target_id: str | None, source: str):
    return next((target for target in source_targets(source) if target.id == target_id), None)
