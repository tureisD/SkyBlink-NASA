/**
 * Frame decoding and per-frame statistics.
 *
 * Frames are pre-decoded into ImageBitmaps + raw pixel buffers exactly once
 * per URL (LAW 6). The raw luminance buffer feeds client-side LUTs and the
 * cursor readout; the RGBA alpha buffer of the flag overlay feeds the flag
 * indicator. Nothing here changes the flux: all display transforms are
 * monotonic, per-pixel and applied after the server-side normalization.
 */

export interface DecodedFrame {
  url: string;
  width: number;
  height: number;
  bitmap: ImageBitmap;
  /** 8-bit display luminance (mean of RGB) for the LUT + readout. */
  luma: Uint8ClampedArray;
  /** Alpha channel of the source, when the overlay uses transparency. */
  alpha: Uint8ClampedArray;
  /**
   * True when the image actually uses transparency. The current server's
   * flag overlay is an opaque white-on-black mask.
   */
  hasAlpha: boolean;
}

export class FrameDecodeError extends Error {
  readonly url: string;

  constructor(url: string, cause: unknown) {
    const detail = cause instanceof Error ? cause.message : String(cause);
    super(`Could not decode ${url}: ${detail}`);
    this.name = "FrameDecodeError";
    this.url = url;
  }
}

function makeCanvas(width: number, height: number): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  return canvas;
}

/** Decode one WebP frame into an ImageBitmap and extract its pixel buffers. */
export async function decodeFrame(url: string): Promise<DecodedFrame> {
  if (typeof createImageBitmap !== "function") {
    throw new FrameDecodeError(
      url,
      "createImageBitmap is unavailable in this browser",
    );
  }
  let bitmap: ImageBitmap;
  try {
    const response = await fetch(url, { cache: "force-cache" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} ${response.statusText}`);
    }
    const blob = await response.blob();
    bitmap = await createImageBitmap(blob);
  } catch (error) {
    throw new FrameDecodeError(url, error);
  }

  const width = bitmap.width;
  const height = bitmap.height;
  const canvas = makeCanvas(width, height);
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) {
    bitmap.close();
    throw new FrameDecodeError(url, "2D canvas context unavailable");
  }
  ctx.drawImage(bitmap, 0, 0);
  const rgba = ctx.getImageData(0, 0, width, height).data;
  const luma = new Uint8ClampedArray(width * height);
  const alpha = new Uint8ClampedArray(width * height);
  let hasAlpha = false;
  for (let i = 0; i < width * height; i += 1) {
    const o = i * 4;
    luma[i] = Math.round((rgba[o] * 299 + rgba[o + 1] * 587 + rgba[o + 2] * 114) / 1000);
    alpha[i] = rgba[o + 3];
    if (rgba[o + 3] < 250) hasAlpha = true;
  }
  return { url, width, height, bitmap, luma, alpha, hasAlpha };
}

/**
 * Convert a flag-overlay frame into a translucent amber layer.
 *
 * The contract does not fix an overlay colour or alpha. Reading alpha when
 * present and luminance otherwise supports transparent overlays and opaque
 * masks without covering the science image.
 */
export function buildFlagOverlay(frame: DecodedFrame): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = frame.width;
  canvas.height = frame.height;
  const ctx = canvas.getContext("2d");
  if (!ctx) return canvas;
  const imageData = ctx.createImageData(frame.width, frame.height);
  const data = imageData.data;
  for (let i = 0; i < frame.width * frame.height; i += 1) {
    const strength = frame.hasAlpha ? frame.alpha[i] : frame.luma[i];
    if (strength < 12) continue;
    const offset = i * 4;
    data[offset] = 251; // #fbbf24 amber, consistent with the warning UI token
    data[offset + 1] = 191;
    data[offset + 2] = 36;
    data[offset + 3] = Math.min(150, Math.round(strength * 0.55));
  }
  ctx.putImageData(imageData, 0, 0);
  return canvas;
}

/** Histogram-derived percentile clip in [0, 1], used by the zscale stretch. */
export function percentileClip(
  luma: Uint8ClampedArray,
  lowFraction = 0.005,
  highFraction = 0.995,
): { lo: number; hi: number } {
  const histogram = new Uint32Array(256);
  for (let i = 0; i < luma.length; i += 1) histogram[luma[i]] += 1;
  const total = luma.length;
  const lowTarget = total * lowFraction;
  const highTarget = total * highFraction;
  let cumulative = 0;
  let lo = 0;
  let hi = 255;
  for (let v = 0; v < 256; v += 1) {
    cumulative += histogram[v];
    if (cumulative >= lowTarget) {
      lo = v;
      break;
    }
  }
  cumulative = 0;
  for (let v = 0; v < 256; v += 1) {
    cumulative += histogram[v];
    if (cumulative >= highTarget) {
      hi = v;
      break;
    }
  }
  if (hi <= lo) hi = Math.min(255, lo + 1);
  return { lo: lo / 255, hi: hi / 255 };
}

/** Mean 8-bit value of a frame; used for the readout, never for normalization. */
export function lumaAt(frame: DecodedFrame, x: number, y: number): number | null {
  const ix = Math.floor(x);
  const iy = Math.floor(y);
  if (ix < 0 || iy < 0 || ix >= frame.width || iy >= frame.height) return null;
  return frame.luma[iy * frame.width + ix];
}

/** Flag strength: alpha for transparent overlays, luminance for opaque masks. */
export function flagStrengthAt(frame: DecodedFrame, x: number, y: number): number {
  const ix = Math.floor(x);
  const iy = Math.floor(y);
  if (ix < 0 || iy < 0 || ix >= frame.width || iy >= frame.height) return 0;
  const index = iy * frame.width + ix;
  return frame.hasAlpha ? frame.alpha[index] : frame.luma[index];
}
