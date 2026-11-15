/**
 * Local tangent-plane WCS helpers for the fixed 240×240 north-up grid.
 *
 * The contract (`AGENTS.md` §3.4, O1 decision §8) defines a plain TAN grid
 * with crpix at the image centre and no SIP/rotation. These are exact
 * gnomonic transforms, including the FITS default pole orientation used by
 * Astropy. They remain valid near the celestial poles and across RA zero.
 *
 * Coordinate conventions:
 *   - world: ICRS degrees.
 *   - source pixel: 0-based, top-left origin, north up (FITS row 1 is at the
 *     bottom, so y is flipped on display).
 */

import type { WcsInfo } from "./types";

const DEG2RAD = Math.PI / 180;

export interface PixelPoint {
  x: number;
  y: number;
}

export interface WorldPoint {
  ra: number;
  dec: number;
}

function wrapDeltaDegrees(delta: number): number {
  let wrapped = (((delta + 180) % 360) + 360) % 360 - 180;
  if (wrapped === -180) wrapped = 180;
  return wrapped;
}

function validWcs(wcs: WcsInfo): boolean {
  return [wcs.crval1, wcs.crval2, wcs.crpix1, wcs.crpix2,
    wcs.cdelt1, wcs.cdelt2, wcs.height].every(Number.isFinite) &&
    Math.abs(wcs.crval2) <= 90 && wcs.cdelt1 !== 0 && wcs.cdelt2 !== 0;
}

/** At +90°, FITS defaults LONPOLE to 0° instead of the usual 180°. */
function poleOrientation(wcs: WcsInfo): number {
  return wcs.crval2 === 90 ? -1 : 1;
}

/** World → 0-based source pixel (continuous, pixel centre at i + 0.5). */
export function worldToPixel(wcs: WcsInfo, ra: number, dec: number): PixelPoint {
  if (!validWcs(wcs) || !Number.isFinite(ra) || !Number.isFinite(dec) || Math.abs(dec) > 90) {
    return { x: NaN, y: NaN };
  }
  const deltaRa = wrapDeltaDegrees(ra - wcs.crval1) * DEG2RAD;
  const sinRef = Math.sin(wcs.crval2 * DEG2RAD);
  const cosRef = Math.abs(wcs.crval2) === 90 ? 0 : Math.cos(wcs.crval2 * DEG2RAD);
  const sinDec = Math.sin(dec * DEG2RAD);
  const cosDec = Math.abs(dec) === 90 ? 0 : Math.cos(dec * DEG2RAD);
  const cosDelta = Math.cos(deltaRa);
  const denominator = sinRef * sinDec + cosRef * cosDec * cosDelta;
  // The tangent horizon is singular; the back hemisphere is not representable.
  if (denominator <= 1e-15) return { x: NaN, y: NaN };
  const orientation = poleOrientation(wcs);
  const xi = orientation * cosDec * Math.sin(deltaRa) / denominator;
  const eta = orientation * (cosRef * sinDec - sinRef * cosDec * cosDelta) / denominator;
  const xFits = wcs.crpix1 + xi / DEG2RAD / wcs.cdelt1;
  const yFits = wcs.crpix2 + eta / DEG2RAD / wcs.cdelt2;
  return {
    x: xFits - 0.5,
    y: wcs.height - yFits + 0.5,
  };
}

/** 0-based source pixel (continuous) → world. */
export function pixelToWorld(wcs: WcsInfo, x: number, y: number): WorldPoint {
  if (!validWcs(wcs) || !Number.isFinite(x) || !Number.isFinite(y)) {
    return { ra: NaN, dec: NaN };
  }
  const xFits = x + 0.5;
  const yFits = wcs.height + 0.5 - y;
  const orientation = poleOrientation(wcs);
  const xi = orientation * (xFits - wcs.crpix1) * wcs.cdelt1 * DEG2RAD;
  const eta = orientation * (yFits - wcs.crpix2) * wcs.cdelt2 * DEG2RAD;
  const sinRef = Math.sin(wcs.crval2 * DEG2RAD);
  const cosRef = Math.abs(wcs.crval2) === 90 ? 0 : Math.cos(wcs.crval2 * DEG2RAD);
  const radial = cosRef - eta * sinRef;
  const ra = xi === 0 && eta === 0
    ? wcs.crval1
    : wcs.crval1 + Math.atan2(xi, radial) / DEG2RAD;
  const dec = Math.atan2(sinRef + eta * cosRef, Math.hypot(radial, xi)) / DEG2RAD;
  return { ra: ((ra % 360) + 360) % 360, dec };
}

/** Angular separation in arcseconds (haversine, adequate at this scale). */
export function angularSeparationArcsec(a: WorldPoint, b: WorldPoint): number {
  const dRa = wrapDeltaDegrees(a.ra - b.ra) * DEG2RAD;
  const dDec = (a.dec - b.dec) * DEG2RAD;
  const decA = a.dec * DEG2RAD;
  const decB = b.dec * DEG2RAD;
  const h =
    Math.sin(dDec / 2) ** 2 +
    Math.cos(decA) * Math.cos(decB) * Math.sin(dRa / 2) ** 2;
  const angle = 2 * Math.asin(Math.min(1, Math.sqrt(h)));
  return angle / DEG2RAD * 3600;
}

function pad(value: number, width: number): string {
  return Math.floor(value).toString().padStart(width, "0");
}

/** Right ascension as sexagesimal hours. */
export function formatRa(raDeg: number): string {
  const hours = ((raDeg % 360) + 360) % 360 / 15;
  let h = Math.floor(hours);
  let m = Math.floor((hours - h) * 60);
  let s = (hours - h - m / 60) * 3600;
  if (s >= 59.995) {
    s = 0;
    m += 1;
  }
  if (m >= 60) {
    m = 0;
    h = (h + 1) % 24;
  }
  return `${pad(h, 2)}h ${pad(m, 2)}m ${s.toFixed(2).padStart(5, "0")}s`;
}

/** Declination as sexagesimal degrees. */
export function formatDec(decDeg: number): string {
  const sign = decDeg < 0 ? "−" : "+";
  const value = Math.abs(decDeg);
  let d = Math.floor(value);
  let m = Math.floor((value - d) * 60);
  let s = (value - d - m / 60) * 3600;
  if (s >= 59.995) {
    s = 0;
    m += 1;
  }
  if (m >= 60) {
    m = 0;
    d += 1;
  }
  return `${sign}${pad(d, 2)}° ${pad(m, 2)}′ ${s.toFixed(1).padStart(4, "0")}″`;
}

export function formatArcsec(value: number): string {
  if (!Number.isFinite(value)) return "—";
  if (Math.abs(value) >= 100) return `${value.toFixed(0)}″`;
  if (Math.abs(value) >= 10) return `${value.toFixed(1)}″`;
  return `${value.toFixed(2)}″`;
}
