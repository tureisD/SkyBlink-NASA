"""Catalog of the five official demo targets.

Reference coordinates, proper motions, and the propagated 2025.8 positions
follow ``ROADMAP.md`` Appendix A and ``docs/decisions/o1-contract-decisions.md`` §10.
The stored ``ra_epoch2025``/``dec_epoch2025`` values are the contract values
used for every IRSA query (LAW 5); :func:`propagated_coordinates` recomputes
them with Astropy for verification and reticle work.

WISE 0855's reference epoch is 2010.0 (WISE discovery), not J2000.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.time import Time
from erfa import ErfaWarning

from models import Target

#: Decimal year used by the API contract for the propagated catalog positions.
EPOCH_2025_8 = 2025.8

_ARCSEC_PER_DEG = 3600.0


@dataclass(frozen=True)
class TargetRecord:
    """Internal target record; serialized to :class:`models.Target` on output."""

    id: str
    name: str
    category: str
    ra_ref: float
    dec_ref: float
    ref_epoch: str
    ra_epoch2025: float
    dec_epoch2025: float
    pm_ra_mas_yr: float
    pm_dec_mas_yr: float
    recommended_bands: tuple[int, ...]
    story_headline: str
    story_body: str
    reference_time_value: float | None = None
    reference_time_format: str | None = None
    reference_time_scale: str | None = None
    astrometry_citation: str | None = None

    def to_contract(self) -> Target:
        """Return the frozen Pydantic contract model (extra fields rejected)."""
        return Target(
            id=self.id,
            name=self.name,
            category=self.category,
            ra_ref=self.ra_ref,
            dec_ref=self.dec_ref,
            ref_epoch=self.ref_epoch,
            ra_epoch2025=self.ra_epoch2025,
            dec_epoch2025=self.dec_epoch2025,
            pm_ra_mas_yr=self.pm_ra_mas_yr,
            pm_dec_mas_yr=self.pm_dec_mas_yr,
            recommended_bands=list(self.recommended_bands),
            story_headline=self.story_headline,
            story_body=self.story_body,
        )


TARGETS: tuple[TargetRecord, ...] = (
    TargetRecord(
        id="wise_0855",
        name="WISE 0855",
        category="Y4 Sub-Brown Dwarf (~250 K)",
        ra_ref=133.79513,
        dec_ref=-7.24515,
        ref_epoch="2010.0",
        ra_epoch2025=133.75921,
        dec_epoch2025=-7.24216,
        pm_ra_mas_yr=-8118.0,
        pm_dec_mas_yr=680.0,
        recommended_bands=(5, 6),
        story_headline="Coldest Known Object Outside the Solar System",
        story_body=(
            "This ~250 K brown dwarf is brightest at longer infrared wavelengths; "
            "the saved field does not establish uncontaminated target photometry. "
            "The coordinate audit found a roughly 3.6 arcsecond reference-epoch "
            "discrepancy. The saved query position is retained pending a coordinated "
            "coordinate correction and real-data cache rebuild."
        ),
    ),
    TargetRecord(
        id="barnards_star",
        name="Barnard's Star",
        category="M4V Red Dwarf (1.83 pc)",
        ra_ref=269.4521,
        dec_ref=4.6934,
        ref_epoch="J2000",
        ra_epoch2025=269.4463,
        dec_epoch2025=4.7676,
        pm_ra_mas_yr=-801.6,
        pm_dec_mas_yr=10362.4,
        recommended_bands=(1, 2, 3, 4, 5, 6),
        story_headline="The Fastest Proper Motion in the Sky",
        story_body=(
            "Barnard's Star moves about 10.4 arcsec per year, roughly 5.2 "
            "arcsec per six-month survey epoch. Comparing epochs reveals a "
            "clear dipole where the star has moved against the static field."
        ),
    ),
    TargetRecord(
        id="eps_indi_b",
        name="Epsilon Indi B",
        category="T1 + T6 Brown Dwarf Binary (3.63 pc)",
        ra_ref=331.04415,
        dec_ref=-56.78284,
        ref_epoch="J2000",
        ra_epoch2025=331.0962,
        dec_epoch2025=-56.8005,
        pm_ra_mas_yr=3982.0,
        pm_dec_mas_yr=-2466.8,
        recommended_bands=(4, 5, 6),
        story_headline="A Brown Dwarf Pair Blended in One Native Pixel",
        story_body=(
            "Epsilon Indi Ba and Bb are only about 0.6 arcsec apart and are "
            "blended in a single 6.15-arcsec SPHEREx native pixel. Their "
            "composite near-infrared spectrum carries methane and water "
            "absorption; Epsilon Indi A is about 6.7 arcmin away."
        ),
    ),
    TargetRecord(
        id="rw_aurigae",
        name="RW Aurigae",
        category="Classical T Tauri Binary (~156 pc)",
        ra_ref=76.95607,
        dec_ref=30.40133,
        ref_epoch="J2000",
        ra_epoch2025=76.9561,
        dec_epoch2025=30.4011,
        pm_ra_mas_yr=2.6,
        pm_dec_mas_yr=-27.4,
        recommended_bands=(1, 2, 3, 4, 5, 6),
        story_headline="A Young Disk That Dims and Recovers",
        story_body=(
            "RW Aurigae is a classical T Tauri binary whose inner disk can "
            "occult the star. Its near-infrared brightness and spectral shape "
            "change between epochs because of variable dust extinction and "
            "disk structure."
        ),
    ),
    TargetRecord(
        id="r_draconis",
        name="R Draconis",
        category="Mira AGB Variable (P ~ 245.6 d)",
        ra_ref=248.1676,
        dec_ref=66.7550,
        ref_epoch="J2000",
        ra_epoch2025=248.1674,
        dec_epoch2025=66.7548,
        pm_ra_mas_yr=-13.7,
        pm_dec_mas_yr=-31.0,
        recommended_bands=(1, 2, 3, 4, 5, 6),
        story_headline="A Pulsating Mira Near the North Ecliptic Pole",
        story_body=(
            "R Draconis pulsates with a period of about 245.6 days and can "
            "vary strongly between survey epochs. Its position near the North "
            "Ecliptic Pole gives SPHEREx repeated coverage. The saved spectrum "
            "has no accepted photometry; inspect the HALO/overflow flags. "
            "Stored proper motion differs from Gaia DR3 and awaits correction "
            "with the cache rebuild; this view does not validate variability."
        ),
    ),
)

TARGET_BY_ID: dict[str, TargetRecord] = {target.id: target for target in TARGETS}

BAND_NAMES: dict[int, str] = {band: f"SPHEREx-D{band}" for band in range(1, 7)}


def get_target(target_id: str) -> TargetRecord | None:
    """Look up a catalog target by its contract ID."""
    return TARGET_BY_ID.get(target_id)


def _reference_time(epoch: str) -> Time:
    """Parse ``J2000`` or a decimal year such as ``2010.0`` into a Time."""
    text = str(epoch).strip()
    if text.upper() in {"J2000", "J2000.0"}:
        return Time(2000.0, format="jyear", scale="tt")
    return Time(float(text), format="decimalyear", scale="tt")


def propagated_coordinates(
    target: TargetRecord,
    decimal_year: float = EPOCH_2025_8,
    *, obstime: Time | None = None,
) -> SkyCoord:
    """Propagate the catalog position with ``SkyCoord.apply_space_motion``.

    The returned coordinate is in ICRS.  This is the production propagation
    path required by ``ROADMAP.md`` §4.1; the stored contract values remain
    authoritative for API/query centering.
    """
    reference = SkyCoord(
        ra=target.ra_ref * u.deg,
        dec=target.dec_ref * u.deg,
        pm_ra_cosdec=target.pm_ra_mas_yr * u.mas / u.yr,
        pm_dec=target.pm_dec_mas_yr * u.mas / u.yr,
        obstime=(Time(target.reference_time_value, format=target.reference_time_format,
                      scale=target.reference_time_scale)
                 if target.reference_time_value is not None else _reference_time(target.ref_epoch)),
        frame="icrs",
    )
    with warnings.catch_warnings():
        # Proper motion without a parallax triggers an ERFA "distance
        # overridden" warning; the propagated direction is still valid.
        warnings.simplefilter("ignore", ErfaWarning)
        return reference.apply_space_motion(
            new_obstime=obstime if obstime is not None else Time(decimal_year, format="decimalyear", scale="tt")
        )

def angular_separation_arcsec(
    ra1: float,
    dec1: float,
    ra2: float,
    dec2: float,
) -> float:
    """Angular separation between two ICRS positions, in arcseconds."""
    first = SkyCoord(ra=ra1 * u.deg, dec=dec1 * u.deg, frame="icrs")
    second = SkyCoord(ra=ra2 * u.deg, dec=dec2 * u.deg, frame="icrs")
    return float(first.separation(second).to_value(u.arcsec))


def match_target(
    ra: float,
    dec: float,
    tolerance_arcsec: float = 1.0,
) -> TargetRecord | None:
    """Return the catalog target within ``tolerance_arcsec`` of a position.

    Matching uses the target's 2025.8 coordinates, per the frozen contract.
    """
    best: tuple[float, TargetRecord] | None = None
    for target in TARGETS:
        separation = angular_separation_arcsec(
            ra,
            dec,
            target.ra_epoch2025,
            target.dec_epoch2025,
        )
        if separation <= tolerance_arcsec and (best is None or separation < best[0]):
            best = (separation, target)
    return best[1] if best is not None else None
