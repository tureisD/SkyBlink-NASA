/**
 * Gaia DR3 G≤16 pin catalog (`reference_overlays.gaia_sources_url`).
 *
 * The contract only defines the URL string; this module accepts the documented
 * catalog shape and a small set of equivalent field names. Pins without a finite G
 * magnitude are dropped: the UI must not claim G≤16 for an unknown magnitude.
 */

export const GAIA_MAX_G = 16;
/** Illustrative on-canvas vector length for catalog proper motions. */
export const GAIA_PM_VECTOR_YEARS = 10;

export interface GaiaSource {
  source_id: string;
  ra: number;
  dec: number;
  /** Gaia G magnitude; always finite and ≤ 16 by the time it reaches the UI. */
  g_mag: number;
  /** μ_α* (mas/yr); null when the catalog row has no proper motion. */
  pmra: number | null;
  /** μ_δ (mas/yr); null when the catalog row has no proper motion. */
  pmdec: number | null;
  label: string;
}

export interface GaiaCatalog {
  sources: GaiaSource[];
  isSimulatedFallback: boolean;
  attribution: string | null;
}

function finiteOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function pickNumber(record: Record<string, unknown>, keys: string[]): number | null {
  for (const key of keys) {
    const value = finiteOrNull(record[key]);
    if (value !== null) return value;
  }
  return null;
}

function pickString(record: Record<string, unknown>, keys: string[]): string | null {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string" && value.trim() !== "") return value.trim();
  }
  return null;
}

/**
 * Parse the Gaia catalog. Unknown rows are skipped rather than guessed; null
 * proper motion keeps the pin and suppresses only its vector.
 */
export function parseGaiaCatalog(value: unknown): GaiaCatalog {
  const root =
    typeof value === "object" && value !== null
      ? (value as Record<string, unknown>)
      : {};
  if (root.is_simulated_fallback !== false) {
    throw new Error("Gaia catalog must identify real observations; synthetic or unknown provenance is not supported.");
  }
  const rawSources = Array.isArray(value)
    ? value
    : Array.isArray(root.sources)
      ? root.sources
      : [];

  const sources: GaiaSource[] = [];
  for (const entry of rawSources) {
    if (typeof entry !== "object" || entry === null) continue;
    const record = entry as Record<string, unknown>;
    const ra = pickNumber(record, ["ra", "ra_deg", "ra_icrs"]);
    const dec = pickNumber(record, ["dec", "dec_deg", "dec_icrs"]);
    const gMag = pickNumber(record, ["g_mag", "phot_g_mean_mag", "gmag"]);
    if (ra === null || dec === null || gMag === null) continue;
    if (ra < 0 || ra >= 360 || dec < -90 || dec > 90) continue;
    if (gMag > GAIA_MAX_G) continue;

    const pmra = pickNumber(record, ["pmra", "pmra_mas_yr", "pm_ra_mas_yr"]);
    const pmdec = pickNumber(record, ["pmdec", "pmdec_mas_yr", "pm_dec_mas_yr"]);
    const sourceId =
      pickString(record, ["source_id", "id", "designation"]) ?? `gaia-${sources.length}`;
    sources.push({
      source_id: sourceId,
      ra,
      dec,
      g_mag: gMag,
      pmra,
      pmdec,
      label: pickString(record, ["label", "name"]) ?? sourceId,
    });
  }

  sources.sort((a, b) => a.g_mag - b.g_mag);
  const isSimulatedFallback = false;
  const attribution = pickString(root, ["attribution", "citation"]);
  return { sources, isSimulatedFallback, attribution };
}
