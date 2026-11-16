/** Presentation of recorded facts only; missing metadata stays unknown. */
import type { AnalysisProvenance, ObservationRange, SpectrumChannel, SpectrumResponse, Target, TelemetryAsset } from "./types";

export function discoveryNotice(provenance: AnalysisProvenance): string | null {
  if (provenance.discovery_mode === "indexed") {
    return "Images downloaded online using a limited spatial index. Coverage and newer observations outside the index are unknown.";
  }
  if (provenance.discovery_mode === "known") {
    return "Using a previously verified exposure list; no new archive search. Newer observations may exist.";
  }
  if (provenance.discovery_status !== "partial") return null;
  const missing = provenance.missing_collections?.length
    ? ` Missing collections: ${provenance.missing_collections.join(", ")}.`
    : "";
  return "Archive search incomplete; showing retrieved observations. Coverage/latest-epoch inventory is not complete." + missing;
}

export function coordinateEpochLabel(target: Target | null): string {
  return target ? "query coordinate epoch 2025.8" : "coordinate epoch unspecified";
}

export function observationDateLabel(epoch: {
  observation_range?: ObservationRange | null;
  date_iso?: string;
}): string {
  const range = epoch.observation_range;
  if (range?.date_start_iso && range.date_end_iso) {
    return range.date_start_iso === range.date_end_iso
      ? range.date_start_iso
      : `${range.date_start_iso} to ${range.date_end_iso}`;
  }
  return epoch.date_iso ? `Mean ${epoch.date_iso}; range unavailable` : "Observation dates unavailable";
}

export function telemetryDescription(asset: TelemetryAsset, displayedBand: string) {
  const knownQuantity = asset.quantity === "normalized_display_intensity";
  const quantity = knownQuantity && asset.normalization_applied === true
    ? "Normalized display intensity"
    : "Display intensity";
  const normalization = asset.normalization_applied === true
    ? "server normalization applied"
    : asset.normalization_applied === false
      ? "server normalization not applied"
      : "normalization metadata unavailable";
  const plane = `${asset.flux_band} plane`;
  const mismatch = asset.flux_band === displayedBand
    ? ""
    : `; displayed image: ${displayedBand}`;
  return {
    label: `${quantity} (${asset.flux_band})`,
    detail: `${plane}${mismatch}; ${knownQuantity ? "" : "quantity metadata unavailable; "}${normalization}; not calibrated source flux`,
  };
}

/**
 * Honor recorded eligibility; new archive partial-aperture/annulus exclusions
 * arrive as false. Do not retroactively reinterpret saved legacy flags.
 */
export function channelStats(spectrum: SpectrumResponse | null) {
  let total = 0;
  let finite = 0;
  let nullFlux = 0;
  let hardBad = 0;
  const usableFluxes: number[] = [];
  for (const epoch of spectrum?.epochs ?? []) {
    for (const channel of epoch.channels) {
      total += 1;
      if (channel.is_flagged_bad) hardBad += 1;
      if (channel.flux_ujy === null || !Number.isFinite(channel.flux_ujy)) {
        nullFlux += 1;
        continue;
      }
      finite += 1;
      if (channel.is_used_in_photometry && !channel.is_flagged_bad) {
        usableFluxes.push(channel.flux_ujy);
      }
    }
  }
  usableFluxes.sort((a, b) => a - b);
  const count = usableFluxes.length;
  const middle = Math.floor(count / 2);
  const medianFlux = !count ? null : count % 2
    ? usableFluxes[middle]
    : (usableFluxes[middle - 1] + usableFluxes[middle]) / 2;
  return { total, finite, usable: count, nullFlux, hardBad, medianFlux, excludedFinite: finite - count };
}

/** Signed domain includes both error endpoints. Missing errors are not displayed as zero. */
export function spectrumDomain(channels: SpectrumChannel[]): [number, number] {
  let lower = 0, upper = 0;
  for (const channel of channels) {
    if (channel.flux_ujy === null || !Number.isFinite(channel.flux_ujy)) continue;
    const error = channel.flux_err_ujy !== null && Number.isFinite(channel.flux_err_ujy) && channel.flux_err_ujy >= 0 ? channel.flux_err_ujy : 0;
    lower = Math.min(lower, channel.flux_ujy - error);
    upper = Math.max(upper, channel.flux_ujy + error);
  }
  if (lower === upper) return [-1, 1];
  const padding = (upper - lower) * 0.08;
  return [lower - padding, upper + padding];
}

export function channelStatus(channel: SpectrumChannel): string {
  if (channel.flux_ujy === null || !Number.isFinite(channel.flux_ujy)) return "No flux measurement";
  if (channel.is_flagged_bad) return "Excluded: hard-bad center";
  return channel.is_used_in_photometry ? "Recorded eligible" : "Excluded exploratory sum";
}

/** Readable signed numbers; never round a small finite measurement to a false zero. */
export function measurementNumber(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "—";
  if (value !== 0 && (Math.abs(value) < .01 || Math.abs(value) >= 1e6)) return value.toExponential(3);
  return new Intl.NumberFormat("en", { maximumSignificantDigits: 5, useGrouping: false }).format(value);
}

export type SampleQuality = "all" | "eligible" | "excluded" | "unavailable";
export type SampleSort = "recorded" | "wavelength" | "flux-up" | "flux-down";
export interface SpectrumSample { channel: SpectrumChannel; epochId: string }

/** Table-only view. Original arrays, plot, eligibility and exports are unchanged. */
export function spectrumTableSamples(samples: SpectrumSample[], quality: SampleQuality, epoch: string, sort: SampleSort): SpectrumSample[] {
  const result = samples.filter(({ channel, epochId }) => {
    if (epoch !== "all" && epoch !== epochId) return false;
    const finite = channel.flux_ujy !== null && Number.isFinite(channel.flux_ujy);
    const eligible = finite && channel.is_used_in_photometry && !channel.is_flagged_bad;
    return quality === "all" || (quality === "eligible" && eligible)
      || (quality === "excluded" && finite && !eligible) || (quality === "unavailable" && !finite);
  });
  if (sort === "wavelength") result.sort((a, b) => a.channel.wavelength_um - b.channel.wavelength_um);
  if (sort === "flux-up" || sort === "flux-down") result.sort((a, b) => {
    const av = a.channel.flux_ujy, bv = b.channel.flux_ujy;
    if (av === null || !Number.isFinite(av)) return bv === null || !Number.isFinite(bv) ? 0 : 1;
    if (bv === null || !Number.isFinite(bv)) return -1;
    return (av - bv) * (sort === "flux-up" ? 1 : -1);
  });
  return result;
}

export function measurementReasonLabel(reason: string): string {
  const labels: Record<string, string> = {
    incomplete_aperture: "Some aperture pixels are unavailable or excluded",
    partial_aperture: "Only part of the aperture contributes",
    insufficient_annulus: "Too few clean pixels to measure the local background",
    insufficient_local_annulus: "Too few clean pixels to measure the local background",
    unsupported_background: "The background estimate is not supported",
    aperture_outside_native_image: "The aperture extends outside the recorded image",
    insufficient_clean_aperture: "Too little clean aperture area remains",
    partial_clean_aperture: "Some aperture pixels are excluded",
    hard_bad_extraction_centre: "The extraction center has a hard-bad flag",
    no_clean_aperture_pixels: "No clean aperture pixels remain",
    field_background_fallback: "Local background support is insufficient; a field estimate was used",
    hard_bad_center: "The extraction center has a hard-bad flag",
    no_clean_pixels: "No clean aperture pixels remain",
  };
  return labels[reason.toLowerCase()] ?? reason.toLowerCase().replaceAll("_", " ");
}
