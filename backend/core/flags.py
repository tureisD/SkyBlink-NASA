"""SPHEREx Level 2 image pixel flags (Explanatory Supplement Table 16).

Policy summary (``AGENTS.md`` §4.2, ``ROADMAP.md`` §6.4):

* ``HARD_BAD_MASK`` pixels are set to ``NaN`` before background estimation,
  reprojection, coadds, and display.
* ``ARTIFACT_WARNING_MASK`` pixels are **not** masked from the displayed image;
  they are surfaced through the flag summary / artifact overlay.
* ``BIT_SOURCE`` (known catalog object) and ``BIT_FULLSAMPLE`` (informational)
  are never used as a bad-pixel mask.  ``BIT_SOURCE`` is excluded only while
  estimating the local sky background.
* ``PHOTOMETRY_EXCLUDE_MASK`` is the conservative mask for photometry and
  coadds: hard-bad plus warning pixels (including DICHROIC).  It never
  contains ``BIT_SOURCE``.

Never use a blanket "any flag set" test as a bad-pixel mask: it would erase
every cataloged source, including the demo targets.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

# ---------------------------------------------------------------------------
# Table 16 — Image pixel flags used in spectral images at Level 2
# ---------------------------------------------------------------------------
# name -> bit index
FLAG_BITS: dict[str, int] = {
    "TRANSIENT": 0,
    "OVERFLOW": 1,
    "SUR_ERROR": 2,
    "NONFUNC": 6,
    "DICHROIC": 7,
    "MISSING_DATA": 9,
    "HOT": 10,
    "COLD": 11,
    "FULLSAMPLE": 12,
    "PHANMISS": 14,
    "NONLINEAR": 15,
    "PERSIST": 17,
    "OUTLIER": 19,
    "CROSSTALK": 20,
    "SOURCE": 21,
    "GHOST": 22,
    "GHOST_FPA": 23,
    "GHOST_EXT": 24,
    "STREAK": 25,
    "BLOOM": 26,
    "SNOWBALL": 27,
    "HALO": 28,
    "SATELLITE_HALO": 29,
}

FLAG_VALUES: dict[str, int] = {name: 1 << bit for name, bit in FLAG_BITS.items()}


def _mask(*names: str) -> int:
    value = 0
    for name in names:
        value |= FLAG_VALUES[name]
    return value


#: Hard data defects.  These pixels become ``NaN``.
HARD_BAD_MASK = _mask(
    "SUR_ERROR",
    "NONFUNC",
    "MISSING_DATA",
    "HOT",
    "COLD",
    "PHANMISS",
    "NONLINEAR",
    "BLOOM",
    "SNOWBALL",
    "HALO",
    "SATELLITE_HALO",
)

#: Artifact warnings.  Kept in the displayed image; described in the shield.
#: ``GHOST_FPA`` (bit 23) is currently unused but included for forward
#: compatibility with the supplement.
ARTIFACT_WARNING_MASK = _mask(
    "TRANSIENT",
    "OVERFLOW",
    "DICHROIC",
    "PERSIST",
    "OUTLIER",
    "CROSSTALK",
    "GHOST",
    "GHOST_FPA",
    "GHOST_EXT",
    "STREAK",
)

#: Known catalog source.  Never mask this from an image.
BIT_SOURCE = FLAG_VALUES["SOURCE"]

#: Informational: pixel contains full-sample data.  Never mask.
BIT_FULLSAMPLE = FLAG_VALUES["FULLSAMPLE"]

#: Bits that must never participate in a bad-pixel mask.
NEVER_MASK = BIT_SOURCE | BIT_FULLSAMPLE

#: Conservative photometry/coadd mask (O1 decision §1).
#: DICHROIC is low-throughput and not usefully calibratable; HALO remains
#: hard.  ``BIT_SOURCE`` is deliberately absent.
PHOTOMETRY_EXCLUDE_MASK = HARD_BAD_MASK | ARTIFACT_WARNING_MASK

#: Mask used only for estimating the local sky background (§4.5).
BACKGROUND_EXCLUDE_MASK = HARD_BAD_MASK | ARTIFACT_WARNING_MASK | BIT_SOURCE

#: Display mask.  The O1 decision keeps HALO hard by default; a target may
#: switch to ``HARD_BAD_MASK & ~HALO`` only after the S2 display-only gate.
DISPLAY_BAD_MASK = HARD_BAD_MASK

HALO_BIT = FLAG_VALUES["HALO"]

#: Display mask when the O1 HALO display-only gate is active: HALO is shown,
#: everything else hard-bad stays NaN.  Photometry continues to use
#: ``PHOTOMETRY_EXCLUDE_MASK`` (HALO remains hard for `is_flagged_bad`).
HALO_DISPLAY_BAD_MASK = HARD_BAD_MASK & ~HALO_BIT

#: Warning flags that force ``ALERT`` in the flag summary (O1 decision §2).
ALERT_WARNING_NAMES: frozenset[str] = frozenset(
    {
        "TRANSIENT",
        "OVERFLOW",
        "PERSIST",
        "CROSSTALK",
        "GHOST",
        "GHOST_FPA",
        "GHOST_EXT",
        "STREAK",
    }
)

#: Warning flags that force ``CAUTION`` in the flag summary (O1 decision §2).
CAUTION_WARNING_NAMES: frozenset[str] = frozenset({"DICHROIC", "OUTLIER"})

#: Fraction of finite frame pixels with a warning bit above which the epoch
#: is reported as ``CAUTION`` (O1 decision §2).
ARTIFACT_CAUTION_FRACTION = 0.01


def names_for(value: int) -> list[str]:
    """Return the sorted flag names set in ``value``.

    Unknown bits are ignored; the caller can still inspect the raw integer.
    """
    value = int(value)
    return [
        name
        for name, bit in sorted(FLAG_BITS.items(), key=lambda item: item[1])
        if value & (1 << bit)
    ]


def union_names(values: Iterable[int]) -> list[str]:
    """Sorted union of flag names across an iterable of raw flag integers."""
    union = 0
    for value in values:
        union |= int(value)
    return names_for(union)


def has_source_bit(value: int) -> bool:
    return (int(value) & BIT_SOURCE) != 0


def is_hard_bad(value: int) -> bool:
    return (int(value) & HARD_BAD_MASK) != 0


def is_warning(value: int) -> bool:
    return (int(value) & ARTIFACT_WARNING_MASK) != 0


def is_photometry_clean(value: int) -> bool:
    """True when the pixel is in neither the hard nor the warning mask."""
    return (int(value) & PHOTOMETRY_EXCLUDE_MASK) == 0


def flag_status(
    warning_names: Sequence[str],
    artifact_pixel_fraction: float,
    *,
    halo_display_mode: bool = False,
) -> str:
    """Return ``NOMINAL``, ``CAUTION`` or ``ALERT`` for a flag summary.

    ``warning_names`` is the union of warning flags in the target aperture
    across the bands that contribute to the epoch.  ``ALERT`` follows the O1
    aggregation rule; ``HALO`` alone never escalates to ``ALERT``.
    """
    names = set(warning_names)
    if names & ALERT_WARNING_NAMES:
        return "ALERT"
    if names & CAUTION_WARNING_NAMES:
        return "CAUTION"
    if artifact_pixel_fraction > ARTIFACT_CAUTION_FRACTION:
        return "CAUTION"
    if halo_display_mode and "HALO" in names:
        return "CAUTION"
    return "NOMINAL"


def describe_mask(mask: int) -> str:
    """Human-readable list of the flag names contained in ``mask``."""
    names = names_for(mask)
    return ", ".join(names) if names else "none"


# Module-level sanity checks: catch accidental overlap between the masks that
# must stay disjoint.  BIT_SOURCE must never enter a bad-pixel mask.
assert HARD_BAD_MASK & ARTIFACT_WARNING_MASK == 0
assert HARD_BAD_MASK & BIT_SOURCE == 0
assert ARTIFACT_WARNING_MASK & BIT_SOURCE == 0
assert PHOTOMETRY_EXCLUDE_MASK & NEVER_MASK == 0
assert BACKGROUND_EXCLUDE_MASK & BIT_FULLSAMPLE == 0
