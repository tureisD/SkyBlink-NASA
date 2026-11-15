/**
 * LVF (linear variable filter) geometry helpers (contract 1.1.0).
 *
 * `epochs[].lvf_geometry` gives one entry per detector: a position angle and a
 * wavelength gradient in µm per arcsecond. The UI draws a schematic gradient
 * strip for each detector; it does not invent detector footprints. Missing
 * geometry is hidden, never guessed.
 */

import type { Epoch, LVFGeometry } from "./types";

export interface LvfHighlight {
  detector: number;
  wavelengthUm: number;
  epochId: string;
}

/** First geometry entry for a detector, preferring the requested epoch. */
export function findLvfGeometry(
  epochs: Epoch[],
  epochId: string | null | undefined,
  detector: number,
): LVFGeometry | null {
  if (epochId) {
    const epoch = epochs.find((entry) => entry.epoch_id === epochId);
    const match = epoch?.lvf_geometry?.find((entry) => entry.detector === detector);
    if (match) return match;
  }
  for (const epoch of epochs) {
    const match = epoch.lvf_geometry?.find((entry) => entry.detector === detector);
    if (match) return match;
  }
  return null;
}

/** Epochs that actually carry usable LVF geometry. */
export function epochsWithLvf(epochs: Epoch[]): Epoch[] {
  return epochs.filter((epoch) => (epoch.lvf_geometry?.length ?? 0) > 0);
}

/** Wavelength gradient colour ramp used for the translucent strips. */
export function lvfGradientStops(): Array<{ offset: number; color: string }> {
  return [
    { offset: 0, color: "#3b82f6" },
    { offset: 0.35, color: "#8b5cf6" },
    { offset: 0.7, color: "#f59e0b" },
    { offset: 1, color: "#f97316" },
  ];
}
