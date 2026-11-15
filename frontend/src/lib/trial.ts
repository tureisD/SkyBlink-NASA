/**
 * Trial-motion and parallax sandbox math (F6).
 *
 * The WCS is the frozen 240 × 240 north-up TAN grid whose reference point is
 * the catalog target's 2025.8 coordinate (AGENTS.md §3.4). A trial proper
 * motion therefore means:
 *
 *   Δt      = (mjd_mean − MJD_2025_8) / 365.25 years
 *   Δx_FITS = (μ_α* · Δt) / cdelt1
 *   Δy_FITS = (μ_δ  · Δt) / cdelt2
 *
 * `μ_α*` is already μ_α cos δ (contract convention), so no additional cos δ
 * factor is applied. Display y is inverted relative to FITS y.
 *
 * These helpers are display-only. They never alter frames, flux, variance, or
 * normalization (LAW 8); they only shift the rendered crop.
 */

import type { WcsInfo } from "./types";

/** Decimal year 2025.8 expressed as a mean MJD (2025-10-20). */
export const MJD_2025_8 = 60968.0;

const MAS_PER_DEG = 3.6e6;
const ARCSEC_PER_AU_AT_1PC = 206264.80624709636;

export interface TrialShift {
  /** Target displacement in grid pixels (display x grows to the right). */
  dxPx: number;
  /** Target displacement in grid pixels (display y grows downward). */
  dyPx: number;
  /** Epoch MJD minus the 2025.8 anchor, in years. */
  dtYears: number;
}

export function epochDeltaYears(mjdMean: number): number {
  if (!Number.isFinite(mjdMean)) return 0;
  return (mjdMean - MJD_2025_8) / 365.25;
}

/** Apparent target displacement for a trial vector at one epoch. */
export function trialShiftGridPixels(
  wcs: WcsInfo,
  mjdMean: number,
  pmRaMasYr: number,
  pmDecMasYr: number,
): TrialShift {
  const dtYears = epochDeltaYears(mjdMean);
  if (
    !Number.isFinite(dtYears) ||
    !Number.isFinite(pmRaMasYr) ||
    !Number.isFinite(pmDecMasYr) ||
    wcs.cdelt1 === 0 ||
    wcs.cdelt2 === 0
  ) {
    return { dxPx: 0, dyPx: 0, dtYears };
  }
  const dxPx = ((pmRaMasYr / MAS_PER_DEG) * dtYears) / wcs.cdelt1;
  const dyFits = ((pmDecMasYr / MAS_PER_DEG) * dtYears) / wcs.cdelt2;
  return { dxPx, dyPx: -dyFits, dtYears };
}

/**
 * Annual parallax semi-amplitude ϖ in arcseconds for a distance in AU.
 * ϖ = 1 / d[pc] = 206265 / d[AU].
 */
export function parallaxSemiAmplitudeArcsec(distanceAu: number): number {
  if (!Number.isFinite(distanceAu) || distanceAu <= 0) return 0;
  return ARCSEC_PER_AU_AT_1PC / distanceAu;
}

/** Six-month peak-to-peak reflex shift, 2ϖ (2 AU baseline). */
export function parallaxPeakToPeakArcsec(distanceAu: number): number {
  return 2 * parallaxSemiAmplitudeArcsec(distanceAu);
}

/** ϖ expressed in grid pixels (3.075″/px for the contract WCS). */
export function parallaxGridPixels(wcs: WcsInfo, distanceAu: number): number {
  if (wcs.pixel_scale_arcsec <= 0) return 0;
  return parallaxSemiAmplitudeArcsec(distanceAu) / wcs.pixel_scale_arcsec;
}

/** 2ϖ expressed in grid pixels. */
export function parallaxPeakToPeakGridPixels(
  wcs: WcsInfo,
  distanceAu: number,
): number {
  return 2 * parallaxGridPixels(wcs, distanceAu);
}

/**
 * Catalog distances documented in ROADMAP.md Appendix A. These are display
 * context only; the API does not carry a distance field. Unknown targets have
 * no preset and the sandbox stays on the explicit test distance.
 */
export const CATALOG_DISTANCE_PC: Readonly<Record<string, number>> = {
  wise_0855: 2.28,
  barnards_star: 1.83,
  eps_indi_b: 3.63,
  rw_aurigae: 156,
};

export function catalogDistanceAu(targetId: string | null): number | null {
  if (!targetId) return null;
  const pc = CATALOG_DISTANCE_PC[targetId];
  return pc ? pc * ARCSEC_PER_AU_AT_1PC : null;
}

/** Test distance used by the default sandbox state. */
export const TEST_DISTANCE_AU = 400;

export function formatSigned(value: number, digits = 1): string {
  if (!Number.isFinite(value)) return "—";
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${Math.abs(value).toFixed(digits)}`;
}

export function formatSignedYears(value: number, digits = 3): string {
  return `${formatSigned(value, digits)} yr`;
}
