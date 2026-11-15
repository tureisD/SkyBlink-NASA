"""HALO (bit 28) display-only decision and flag-summary helpers.

The O1 decision (§9) evaluates the gate once per target:

* ``halo_fraction > 0.05`` in any band/epoch, or
* ``halo_aperture_fraction > 0`` for the target.

When triggered, displayed frames use
``HARD_BAD_MASK & ~(1 << 28)`` (HALO is shown), the flag overlay and
``active_warning_flags`` include ``HALO``, and the status is at least
``CAUTION``.  HALO remains in ``PHOTOMETRY_EXCLUDE_MASK`` and in the hard mask
used by ``is_flagged_bad`` at a spectrum extraction center.

A target/golden manifest may carry an explicit decision
(``halo_display_mode``, ``data_quality.halo_display_mode``,
``halo.display_mode`` or ``halo_decision.display_mode``); otherwise the gate is
evaluated from the per-epoch ``band_stats``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

HALO_GATE_FRACTION = 0.05
HALO_APERTURE_GATE_FRACTION = 0.0


@dataclass(frozen=True)
class HaloDecision:
    """Resolved HALO display policy for one target/manifest."""

    display_mode: bool
    triggered: bool
    max_halo_fraction: float
    max_halo_aperture_fraction: float
    evidence: tuple[str, ...]
    source: str = "gate"

    def to_dict(self) -> dict[str, Any]:
        return {
            "display_mode": bool(self.display_mode),
            "triggered": bool(self.triggered),
            "max_halo_fraction": float(self.max_halo_fraction),
            "max_halo_aperture_fraction": float(self.max_halo_aperture_fraction),
            "evidence": list(self.evidence),
            "source": self.source,
        }


def _get_nested(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _float_or_zero(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if number == number else 0.0  # NaN -> 0.0


def _explicit_decision(manifest: dict[str, Any]) -> bool | None:
    for path in (
        ("halo_display_mode",),
        ("data_quality", "halo_display_mode"),
        ("halo", "display_mode"),
        ("halo_decision", "display_mode"),
    ):
        value = _get_nested(manifest, path)
        if isinstance(value, bool):
            return value
    return None


def resolve_halo_decision(
    manifest: dict[str, Any],
    *,
    evaluate_gate: bool = True,
) -> HaloDecision:
    """Return the HALO display policy for a sky/golden manifest."""
    explicit = _explicit_decision(manifest)
    max_halo_fraction = 0.0
    max_halo_aperture_fraction = 0.0
    evidence: list[str] = []

    if evaluate_gate:
        for epoch in manifest.get("epochs", []) or []:
            epoch_id = str(epoch.get("epoch_id", "?"))
            for band, stats in (epoch.get("band_stats") or {}).items():
                if not isinstance(stats, dict):
                    continue
                halo_fraction = _float_or_zero(stats.get("halo_fraction"))
                halo_aperture_fraction = _float_or_zero(
                    stats.get("halo_aperture_fraction")
                )
                max_halo_fraction = max(max_halo_fraction, halo_fraction)
                max_halo_aperture_fraction = max(
                    max_halo_aperture_fraction, halo_aperture_fraction
                )
                if (
                    halo_fraction > HALO_GATE_FRACTION
                    or halo_aperture_fraction > HALO_APERTURE_GATE_FRACTION
                ):
                    evidence.append(
                        f"{epoch_id} D{band}: "
                        f"halo_fraction={halo_fraction:.4f}, "
                        f"halo_aperture_fraction={halo_aperture_fraction:.4f}"
                    )

    triggered = bool(evidence)
    if explicit is not None:
        display_mode = explicit
        source = "manifest"
    else:
        display_mode = triggered
        source = "gate"

    return HaloDecision(
        display_mode=bool(display_mode),
        triggered=triggered,
        max_halo_fraction=float(max_halo_fraction),
        max_halo_aperture_fraction=float(max_halo_aperture_fraction),
        evidence=tuple(evidence),
        source=source,
    )


def apply_halo_to_summary(
    summary: dict[str, Any],
    decision: HaloDecision | None,
) -> dict[str, Any]:
    """Return a flag-summary copy with HALO surfaced when display mode is on."""
    result = dict(summary)
    if decision is None or not decision.display_mode:
        return result

    flags = sorted(set(result.get("active_warning_flags", []) or []) | {"HALO"})
    result["active_warning_flags"] = flags
    status = str(result.get("status", "NOMINAL"))
    if status == "NOMINAL":
        result["status"] = "CAUTION"
    explanation = str(result.get("human_explanation", "")).strip()
    if "HALO" not in explanation:
        explanation = (
            f"{explanation} HALO is shown in display-only mode and remains "
            "excluded from photometry."
        ).strip()
    result["human_explanation"] = explanation
    return result
