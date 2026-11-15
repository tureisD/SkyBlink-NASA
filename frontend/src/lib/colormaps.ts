/**
 * Client-side colour lookup tables (LAW 6 / AGENTS.md §5.2).
 *
 * LUTs are applied in the browser, after the server-side flux normalization.
 * The browser never re-requests frames for contrast/colormap changes and never
 * re-normalizes the underlying flux (LAW 8).
 */

export type ColormapId = "gray" | "inferno" | "viridis" | "coolwarm";

export interface ColormapMeta {
  id: ColormapId;
  label: string;
  /** Compact label used by the four-column swatch grid. */
  short: string;
  diverging: boolean;
  /** CSS gradient used by the swatch button. */
  css: string;
}

export const COLORMAPS: ReadonlyArray<ColormapMeta> = [
  {
    id: "gray",
    label: "Grayscale",
    short: "Gray",
    diverging: false,
    css: "linear-gradient(90deg, #05070c 0%, #e2e8f0 100%)",
  },
  {
    id: "inferno",
    label: "Inferno",
    short: "Inferno",
    diverging: false,
    css: "linear-gradient(90deg, #000004 0%, #4a0c6b 30%, #a52c60 55%, #ed6925 78%, #fcffa4 100%)",
  },
  {
    id: "viridis",
    label: "Viridis",
    short: "Viridis",
    diverging: false,
    css: "linear-gradient(90deg, #440154 0%, #3e4989 30%, #26828e 55%, #35b779 78%, #fde725 100%)",
  },
  {
    id: "coolwarm",
    label: "Cool–warm",
    short: "Cool",
    diverging: true,
    css: "linear-gradient(90deg, #1d4ed8 0%, #0b1220 50%, #ef4444 100%)",
  },
];

type Anchor = readonly [number, number, number, number];

// Anchor tables sampled from the standard Matplotlib maps (t, r, g, b).
const GRAY_ANCHORS: readonly Anchor[] = [
  [0, 0, 0, 0],
  [1, 255, 255, 255],
];

const INFERNO_ANCHORS: readonly Anchor[] = [
  [0.0, 0, 0, 4],
  [0.1, 22, 11, 57],
  [0.2, 66, 10, 104],
  [0.3, 106, 23, 110],
  [0.4, 147, 38, 103],
  [0.5, 185, 50, 82],
  [0.6, 220, 71, 55],
  [0.7, 243, 106, 24],
  [0.8, 251, 150, 8],
  [0.9, 250, 201, 34],
  [1.0, 252, 255, 164],
];

const VIRIDIS_ANCHORS: readonly Anchor[] = [
  [0.0, 68, 1, 84],
  [0.1, 72, 33, 115],
  [0.2, 64, 67, 135],
  [0.3, 52, 94, 141],
  [0.4, 41, 120, 142],
  [0.5, 32, 143, 140],
  [0.6, 34, 167, 132],
  [0.7, 68, 190, 112],
  [0.8, 121, 209, 81],
  [0.9, 189, 223, 38],
  [1.0, 253, 231, 37],
];

/**
 * Diverging map tuned for difference frames: the zero point is near-black so
 * switching epochs/modes never produces a full-screen white flash
 * (LAW 7). Negative residuals are blue, positive residuals are warm.
 */
const COOLWARM_ANCHORS: readonly Anchor[] = [
  [0.0, 37, 99, 235],
  [0.2, 29, 78, 216],
  [0.4, 23, 37, 84],
  [0.5, 6, 8, 14],
  [0.6, 69, 26, 3],
  [0.8, 194, 65, 12],
  [1.0, 244, 63, 94],
];

const ANCHORS: Record<ColormapId, readonly Anchor[]> = {
  gray: GRAY_ANCHORS,
  inferno: INFERNO_ANCHORS,
  viridis: VIRIDIS_ANCHORS,
  coolwarm: COOLWARM_ANCHORS,
};

const lutCache = new Map<ColormapId, Uint8Array>();

function buildLut(anchors: readonly Anchor[]): Uint8Array {
  const lut = new Uint8Array(256 * 3);
  for (let i = 0; i < 256; i += 1) {
    const t = i / 255;
    let lower = anchors[0];
    let upper = anchors[anchors.length - 1];
    for (let a = 0; a < anchors.length - 1; a += 1) {
      const current = anchors[a];
      const next = anchors[a + 1];
      if (t >= current[0] && t <= next[0]) {
        lower = current;
        upper = next;
        break;
      }
    }
    const span = upper[0] - lower[0] || 1;
    const f = Math.min(1, Math.max(0, (t - lower[0]) / span));
    lut[i * 3] = Math.round(lower[1] + (upper[1] - lower[1]) * f);
    lut[i * 3 + 1] = Math.round(lower[2] + (upper[2] - lower[2]) * f);
    lut[i * 3 + 2] = Math.round(lower[3] + (upper[3] - lower[3]) * f);
  }
  return lut;
}

/** 256-entry RGB LUT, cached per colormap. */
export function colormapLut(id: ColormapId): Uint8Array {
  let lut = lutCache.get(id);
  if (!lut) {
    lut = buildLut(ANCHORS[id]);
    lutCache.set(id, lut);
  }
  return lut;
}
