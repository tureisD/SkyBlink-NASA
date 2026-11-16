/**
 * Client-side mirror of the frozen O1 API contract (`AGENTS.md` §3,
 * `backend/models/**`, with optional additions through contract 1.4.0).
 *
 * These types are intentionally hand-written rather than generated so the
 * frontend keeps compiling if the backend adds optional fields. They are
 * read-only: the browser never mutates a manifest and never re-normalizes
 * frames (LAW 8).
 */

export type TargetId =
  | "wise_0855"
  | "barnards_star"
  | "eps_indi_b"
  | "rw_aurigae"
  | "r_draconis";

export type FlagStatus = "NOMINAL" | "CAUTION" | "ALERT";

export type Confidence = "high" | "low";

export interface SkyQueryInfo {
  ra: number;
  dec: number;
  size_deg: number;
  target_id: string | null;
}

export interface Target {
  id: string;
  name: string;
  category: string;
  ra_ref: number;
  dec_ref: number;
  ref_epoch: string;
  ra_epoch2025: number;
  dec_epoch2025: number;
  /** μ_α cos δ, milliarcseconds per year. */
  pm_ra_mas_yr: number;
  pm_dec_mas_yr: number;
  recommended_bands: number[];
  story_headline: string;
  story_body: string;
}

export interface WcsInfo {
  crval1: number;
  crval2: number;
  crpix1: number;
  crpix2: number;
  cdelt1: number;
  cdelt2: number;
  width: number;
  height: number;
  pixel_scale_arcsec: number;
  native_pixel_scale_arcsec: number;
}

export interface FlagSummary {
  status: FlagStatus;
  source_bit_set: boolean;
  artifact_pixel_fraction: number;
  active_warning_flags: string[];
  human_explanation: string;
}

/**
 * Optional per-epoch display-intensity telemetry sidecar (contract 1.1.0). It is
 * separate from `frames`: display WebPs remain 8-bit previews.
 */
export interface TelemetryAsset {
  url: string;
  format: "float16_uint32_le_gzip";
  width: number;
  height: number;
  byte_size: number;
  flux_band: "thermal" | "all";
  /** Absent on legacy products: quantity/normalization are then unknown. */
  quantity?: "normalized_display_intensity" | null;
  normalization_applied?: boolean | null;
}

/** Actual contributing observation times; never inferred from epoch IDs. */
export interface ObservationRange {
  mjd_min: number;
  mjd_max: number;
  date_start_iso: string;
  date_end_iso: string;
  time_scale?: "utc" | null;
}

export interface MeasurementAvailability {
  total_channels: number;
  finite_channels: number;
  usable_channels: number;
  reasons: string[];
}

export interface AnalysisProvenance {
  data_access?: "archive" | "saved" | null;
  discovery_mode?: "live" | "known" | "indexed" | null;
  discovery_status?: "complete" | "partial" | "unknown" | null;
  missing_collections?: string[] | null;
  analysis_id?: string | null;
  analysis_record_url?: string | null;
  processing_version?: string | null;
}

/** Per-detector LVF dispersion geometry (contract 1.1.0). */
export interface LVFGeometry {
  detector: number;
  pa_deg: number;
  grad_um_per_arcsec: number;
}

/** Objective difference-frame candidate; never a confidence score. */
export interface DetectedCandidate {
  id: string;
  ra: number;
  dec: number;
  x_px: number;
  y_px: number;
  kind: "dipole" | "variable";
  snr: number;
  delta_flux_mjy_sr: number | null;
  is_artifact_clean: boolean;
  label: string;
}

/**
 * Frame keys are strings in JSON. API asset paths are absolute-resolved
 * against the site root by the browser.
 */
export interface Epoch {
  epoch_id: string;
  label: string;
  collection: string;
  release: string;
  mjd_mean: number;
  date_iso: string;
  frames: Record<string, string>;
  flag_summary: FlagSummary;
  telemetry?: TelemetryAsset | null;
  lvf_geometry?: LVFGeometry[] | null;
  candidates?: DetectedCandidate[] | null;
  core_inpainted?: boolean;
  observation_range?: ObservationRange | null;
}

export interface FluxNormalization {
  method: string;
  scope: string;
  reference_epoch: string | null;
  applied: boolean;
  status: string;
  clamped: boolean;
  raw_stats_location: string;
}

export interface SkyProvenance extends AnalysisProvenance {
  comparison_status?: "matched_visual" | "single_epoch" | "unmatched_single_epoch" | "legacy_unvalidated" | null;
  comparison_reason?: string | null;
  source: string;
  collection: string;
  release: string;
  zodi_subtracted: boolean;
  background_subtracted: boolean;
  flux_normalization: FluxNormalization;
  is_simulated_fallback: boolean;
  generated_at: string;
  citation: string;
}

/** `GET /api/v1/sky` response body. */
export interface SkyResponse {
  query: SkyQueryInfo;
  target: Target | null;
  wcs: WcsInfo;
  epochs: Epoch[];
  /** Keyed `{later}_minus_{earlier}` → band key → asset URL. */
  differences: Record<string, Record<string, string>>;
  reference_overlays: Record<string, string>;
  provenance: SkyProvenance;
}

export interface SpectrumChannel {
  detector: number;
  wavelength_um: number;
  bandwidth_um: number;
  flux_ujy: number | null;
  flux_err_ujy: number | null;
  flags: number;
  is_flagged_bad: boolean;
  clean_fraction: number;
  is_used_in_photometry: boolean;
  /** Contract 1.1.0 additive fields (optional on older payloads). */
  photometry_method?: "aperture_12.3" | "crowded_diff_6.8";
  aperture_mode?: "standard_12.3" | "crowded_diff_6.8";
  aperture_radius_arcsec?: number;
  input_id?: string | null;
  extraction_ra?: number | null;
  extraction_dec?: number | null;
  measurement_reasons?: string[];
}

export interface SpectrumEpoch {
  epoch_id: string;
  label: string;
  collection: string;
  release: string;
  channels: SpectrumChannel[];
  observation_range?: ObservationRange | null;
  measurement_availability?: MeasurementAvailability | null;
}

export interface MolecularFeature {
  label: string;
  wavelength_um: number;
  band: number;
}

export interface SpectrumProvenance extends AnalysisProvenance {
  source: string;
  collection: string;
  release: string;
  zodi_subtracted: boolean;
  background_subtracted: boolean;
  is_simulated_fallback: boolean;
  generated_at: string;
  citation: string;
}

/** `GET /api/v1/spectrum` response body (used by the F3 drawer). */
export interface SpectrumResponse {
  target_id: string | null;
  ra: number;
  dec: number;
  aperture_radius_arcsec: number;
  wavelength_calibration: string;
  confidence: Confidence;
  epochs: SpectrumEpoch[];
  molecular_features: MolecularFeature[];
  provenance: SpectrumProvenance;
}

/** Band display metadata documented in `ROADMAP.md` §3.2. */
export const BANDS: ReadonlyArray<{
  key: string;
  label: string;
  short: string;
  wavelength: string;
  minUm: number;
  maxUm: number;
  color: string;
}> = [
  { key: "1", label: "Band 1", short: "B1", wavelength: "0.75–1.09 µm", minUm: 0.75, maxUm: 1.09, color: "#38bdf8" },
  { key: "2", label: "Band 2", short: "B2", wavelength: "1.10–1.62 µm", minUm: 1.1, maxUm: 1.62, color: "#34d399" },
  { key: "3", label: "Band 3", short: "B3", wavelength: "1.63–2.41 µm", minUm: 1.63, maxUm: 2.41, color: "#a3e635" },
  { key: "4", label: "Band 4", short: "B4", wavelength: "2.42–3.82 µm", minUm: 2.42, maxUm: 3.82, color: "#fbbf24" },
  { key: "5", label: "Band 5", short: "B5", wavelength: "3.83–4.41 µm", minUm: 3.83, maxUm: 4.41, color: "#fb923c" },
  { key: "6", label: "Band 6", short: "B6", wavelength: "4.42–5.00 µm", minUm: 4.42, maxUm: 5.0, color: "#f43f5e" },
];

export const BAND_KEYS = ["1", "2", "3", "4", "5", "6"] as const;

export type BandKey = (typeof BAND_KEYS)[number] | "all" | "thermal";

export const FRAME_KEY_LABELS: Record<string, string> = {
  all: "All bands",
  thermal: "Thermal",
};

export function bandMeta(key: string): {
  label: string;
  short: string;
  wavelength: string;
  color: string;
} {
  const band = BANDS.find((entry) => entry.key === key);
  if (band) return band;
  if (key === "thermal") {
    return { label: "Thermal", short: "B5+B6", wavelength: "3.83–5.00 µm", color: "#fb923c" };
  }
  if (key === "all") {
    return { label: "All bands", short: "B1–B6", wavelength: "0.75–5.00 µm", color: "#38bdf8" };
  }
  return { label: `Band ${key}`, short: key, wavelength: "", color: "#94a3b8" };
}
