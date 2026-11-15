/**
 * Plain-language meanings for SPHEREx Table 16 warning flags.
 *
 * These are data-quality descriptions, not probabilities or discovery claims.
 * Only ARTIFACT_WARNING_MASK names are listed; hard-bad flags are NaN in the
 * displayed frames and are not surfaced as image warnings.
 */

export const WARNING_FLAG_INFO: Record<string, string> = {
  TRANSIENT:
    "Possible cosmic ray or transient. Alert-level warning; it is not a confirmed detection.",
  OVERFLOW: "Saturated or overflow pixel.",
  DICHROIC:
    "Dichroic-edge pixel with low throughput. Excluded from photometry, but kept in the displayed image.",
  PERSIST: "Persistence from a previous exposure.",
  OUTLIER: "Pixel outlier relative to its neighbours.",
  CROSSTALK: "Signal coupled from another detector or readout.",
  GHOST: "Optical ghost from a bright source.",
  GHOST_FPA: "Focal-plane-array ghost (reserved warning bit).",
  GHOST_EXT: "Extended optical ghost.",
  STREAK: "Streak from a bright source.",
  HALO: "Halo around a bright source; hard-masked by default.",
};

export function flagDescription(name: string): string {
  return WARNING_FLAG_INFO[name] ?? "Warning flag reported by the manifest.";
}

export const STATUS_RANK: Record<string, number> = {
  NOMINAL: 0,
  CAUTION: 1,
  ALERT: 2,
};

export function worstStatus(statuses: string[]): "NOMINAL" | "CAUTION" | "ALERT" {
  let worst = "NOMINAL";
  for (const status of statuses) {
    if ((STATUS_RANK[status] ?? 0) > (STATUS_RANK[worst] ?? 0)) {
      worst = status;
    }
  }
  return worst as "NOMINAL" | "CAUTION" | "ALERT";
}
