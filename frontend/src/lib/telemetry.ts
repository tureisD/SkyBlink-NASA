/**
 * Display-intensity sidecar decoder (`epochs[].telemetry`).
 *
 * A sidecar is a gzipped, little-endian plane pair:
 *   `width × height` float16 display intensity (MJy/sr after any server
 *   normalization), then `width × height` uint32 Table 16
 *   flags. The browser only reads it for the cursor loupe. Display frames stay
 *   8-bit WebP previews; nothing here re-normalizes flux (LAW 8).
 *
 * The cache is module-level and keyed by URL so a blink loop never refetches or
 * re-decodes a sidecar. No React state is touched from the animation loop.
 */

import type { TelemetryAsset } from "./types";

/** Table 16 flag definitions (mirrors `backend/core/flags.py`). */
export interface FlagDefinition {
  bit: number;
  /** Name used by the Explanatory Supplement / backend. */
  tableName: string;
  /** Name shown in the UI. `SOURCE` is surfaced as `BIT_SOURCE`. */
  displayName: string;
  category: "hard" | "warning" | "info" | "source";
  description: string;
}

export const FLAG_TABLE: readonly FlagDefinition[] = [
  {
    bit: 0,
    tableName: "TRANSIENT",
    displayName: "TRANSIENT",
    category: "warning",
    description: "Possible cosmic ray or transient; alert-level warning, not a detection.",
  },
  {
    bit: 1,
    tableName: "OVERFLOW",
    displayName: "OVERFLOW",
    category: "warning",
    description: "Saturated or overflow pixel.",
  },
  {
    bit: 2,
    tableName: "SUR_ERROR",
    displayName: "SUR_ERROR",
    category: "hard",
    description: "Surface-brightness error above tolerance; hard-bad for photometry.",
  },
  {
    bit: 6,
    tableName: "NONFUNC",
    displayName: "NONFUNC",
    category: "hard",
    description: "Non-functional detector pixel.",
  },
  {
    bit: 7,
    tableName: "DICHROIC",
    displayName: "DICHROIC",
    category: "warning",
    description: "Dichroic-edge pixel: low throughput, excluded from photometry.",
  },
  {
    bit: 9,
    tableName: "MISSING_DATA",
    displayName: "MISSING_DATA",
    category: "hard",
    description: "No valid data in this pixel.",
  },
  {
    bit: 10,
    tableName: "HOT",
    displayName: "HOT",
    category: "hard",
    description: "Hot detector pixel.",
  },
  {
    bit: 11,
    tableName: "COLD",
    displayName: "COLD",
    category: "hard",
    description: "Cold detector pixel.",
  },
  {
    bit: 12,
    tableName: "FULLSAMPLE",
    displayName: "FULLSAMPLE",
    category: "info",
    description: "Full-sample data present; informational only, never masked.",
  },
  {
    bit: 14,
    tableName: "PHANMISS",
    displayName: "PHANMISS",
    category: "hard",
    description: "Missing phantom (reference) sample.",
  },
  {
    bit: 15,
    tableName: "NONLINEAR",
    displayName: "NONLINEAR",
    category: "hard",
    description: "Pixel outside the linear detector regime.",
  },
  {
    bit: 17,
    tableName: "PERSIST",
    displayName: "PERSIST",
    category: "warning",
    description: "Persistence from a previous exposure.",
  },
  {
    bit: 19,
    tableName: "OUTLIER",
    displayName: "OUTLIER",
    category: "warning",
    description: "Pixel outlier relative to its neighbours.",
  },
  {
    bit: 20,
    tableName: "CROSSTALK",
    displayName: "CROSSTALK",
    category: "warning",
    description: "Signal coupled from another detector or readout.",
  },
  {
    bit: 21,
    tableName: "SOURCE",
    displayName: "BIT_SOURCE",
    category: "source",
    description:
      "Known catalog object (Bit 21). Never masked from the image; excluded only from background estimation.",
  },
  {
    bit: 22,
    tableName: "GHOST",
    displayName: "GHOST",
    category: "warning",
    description: "Optical ghost from a bright source.",
  },
  {
    bit: 23,
    tableName: "GHOST_FPA",
    displayName: "GHOST_FPA",
    category: "warning",
    description: "Focal-plane-array ghost (reserved warning bit).",
  },
  {
    bit: 24,
    tableName: "GHOST_EXT",
    displayName: "GHOST_EXT",
    category: "warning",
    description: "Extended optical ghost.",
  },
  {
    bit: 25,
    tableName: "STREAK",
    displayName: "STREAK",
    category: "warning",
    description: "Streak from a bright source.",
  },
  {
    bit: 26,
    tableName: "BLOOM",
    displayName: "BLOOM",
    category: "hard",
    description: "Bloom from an overflowing pixel.",
  },
  {
    bit: 27,
    tableName: "SNOWBALL",
    displayName: "SNOWBALL",
    category: "hard",
    description: "Snowball / cosmic-ray cluster.",
  },
  {
    bit: 28,
    tableName: "HALO",
    displayName: "HALO",
    category: "hard",
    description: "Halo around a bright source; hard-masked for photometry.",
  },
  {
    bit: 29,
    tableName: "SATELLITE_HALO",
    displayName: "SATELLITE_HALO",
    category: "hard",
    description: "Satellite-trail halo; hard-bad.",
  },
] as const;

const FLAG_BY_BIT = new Map(FLAG_TABLE.map((flag) => [flag.bit, flag]));

/** Flag names set in a raw uint32 value, including unknown reserved bits. */
export function flagsFor(value: number): FlagDefinition[] {
  if (!Number.isFinite(value) || value === 0) return [];
  const flags: FlagDefinition[] = [];
  for (let bit = 0; bit < 32; bit += 1) {
    if ((value & (1 << bit)) === 0) continue;
    const known = FLAG_BY_BIT.get(bit);
    flags.push(
      known ?? {
        bit,
        tableName: `BIT_${bit}`,
        displayName: `BIT_${bit}`,
        category: "info",
        description: `Reserved or undocumented Table 16 bit ${bit}.`,
      },
    );
  }
  return flags;
}

/** Compact list for the cursor HUD, e.g. `BIT_SOURCE · HALO`. */
export function formatFlagNames(
  value: number,
  maxNames = 6,
): { text: string; full: string } {
  const flags = flagsFor(value);
  if (flags.length === 0) {
    return { text: "no Table 16 flags", full: "No Table 16 flag bits set." };
  }
  const shown = flags
    .slice(0, maxNames)
    .map((flag) => flag.displayName)
    .join(" · ");
  const suffix = flags.length > maxNames ? ` +${flags.length - maxNames}` : "";
  const full = flags
    .map((flag) => `${flag.displayName} (bit ${flag.bit}): ${flag.description}`)
    .join("\n");
  return { text: `${shown}${suffix}`, full };
}

export interface TelemetryData {
  url: string;
  width: number;
  height: number;
  fluxBand: "thermal" | "all";
  /** MJy/sr, raw server-side values (never re-normalized in the browser). */
  fluxMjySr: Float32Array;
  /** Table 16 uint32 flags. */
  flags: Uint32Array;
}

export type TelemetryEntry =
  | { status: "loading"; url: string; asset: TelemetryAsset }
  | { status: "ready"; url: string; asset: TelemetryAsset; data: TelemetryData }
  | { status: "error"; url: string; asset: TelemetryAsset; error: string };

export class TelemetryDecodeError extends Error {
  readonly url: string;

  constructor(url: string, message: string) {
    super(message);
    this.name = "TelemetryDecodeError";
    this.url = url;
  }
}

/** IEEE 754 binary16 → number (little-endian input value). */
export function decodeFloat16(value: number): number {
  const sign = (value & 0x8000) !== 0 ? -1 : 1;
  const exponent = (value >> 10) & 0x1f;
  const fraction = value & 0x3ff;
  if (exponent === 0) {
    return sign * 2 ** -14 * (fraction / 1024);
  }
  if (exponent === 0x1f) {
    return fraction === 0 ? sign * Infinity : NaN;
  }
  return sign * 2 ** (exponent - 15) * (1 + fraction / 1024);
}

async function gunzip(buffer: ArrayBuffer, url: string): Promise<ArrayBuffer> {
  if (typeof DecompressionStream !== "function") {
    throw new TelemetryDecodeError(
      url,
      "This browser does not expose DecompressionStream; physical telemetry cannot be decoded.",
    );
  }
  try {
    const stream = new Blob([buffer])
      .stream()
      .pipeThrough(new DecompressionStream("gzip"));
    return await new Response(stream).arrayBuffer();
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    throw new TelemetryDecodeError(url, `gzip decompression failed: ${detail}`);
  }
}

function isGzip(buffer: ArrayBuffer): boolean {
  const magic = new Uint8Array(buffer, 0, Math.min(2, buffer.byteLength));
  return magic.length === 2 && magic[0] === 0x1f && magic[1] === 0x8b;
}

/**
 * Decode the transport payload exactly once.
 *
 * The contract sidecar is gzip-compressed, but a static host may add
 * `Content-Encoding: gzip` for a `.gz` file; the browser then transparently
 * removes the gzip wrapper before `arrayBuffer()` sees it. In that case the
 * payload is already the expected raw plane pair: for the 240×240 contract grid
 * that is exactly 240 × 240 × 6 = 345,600 bytes (2-byte float16 + 4-byte
 * uint32 per pixel). Accepting the raw size here is deliberate and prevents a
 * second `DecompressionStream` pass that would fail on already-decoded bytes.
 * Both paths are honest: the bytes are the same sidecar, never synthesized.
 */
async function decodePayload(
  buffer: ArrayBuffer,
  asset: TelemetryAsset,
): Promise<ArrayBuffer> {
  if (isGzip(buffer)) return gunzip(buffer, asset.url);
  const expected = asset.width * asset.height * 6;
  if (buffer.byteLength === expected) return buffer;
  throw new TelemetryDecodeError(
    asset.url,
    "Telemetry payload is neither gzip-compressed (missing 0x1f 0x8b magic) nor the expected decoded size.",
  );
}

function decodePlanePair(
  raw: ArrayBuffer,
  asset: TelemetryAsset,
): TelemetryData {
  const count = asset.width * asset.height;
  const fluxBytes = count * 2;
  const flagBytes = count * 4;
  const expected = fluxBytes + flagBytes;
  if (raw.byteLength !== expected) {
    throw new TelemetryDecodeError(
      asset.url,
      `Telemetry payload is ${raw.byteLength} bytes; expected ${expected} for ${asset.width}×${asset.height} float16 + uint32.`,
    );
  }

  const view = new DataView(raw);
  const fluxMjySr = new Float32Array(count);
  for (let index = 0; index < count; index += 1) {
    fluxMjySr[index] = decodeFloat16(view.getUint16(index * 2, true));
  }
  const flags = new Uint32Array(count);
  for (let index = 0; index < count; index += 1) {
    flags[index] = view.getUint32(fluxBytes + index * 4, true);
  }
  return {
    url: asset.url,
    width: asset.width,
    height: asset.height,
    fluxBand: asset.flux_band === "thermal" ? "thermal" : "all",
    fluxMjySr,
    flags,
  };
}

async function loadTelemetry(
  asset: TelemetryAsset,
  signal?: AbortSignal,
): Promise<TelemetryData> {
  if (asset.format !== "float16_uint32_le_gzip") {
    throw new TelemetryDecodeError(
      asset.url,
      `Unsupported telemetry format "${asset.format}".`,
    );
  }
  let response: Response;
  try {
    response = await fetch(asset.url, { cache: "force-cache", signal });
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    throw new TelemetryDecodeError(asset.url, `Telemetry request failed: ${detail}`);
  }
  if (!response.ok) {
    throw new TelemetryDecodeError(
      asset.url,
      `Telemetry request returned HTTP ${response.status} ${response.statusText}.`,
    );
  }
  const payload = await response.arrayBuffer();
  const raw = await decodePayload(payload, asset);
  return decodePlanePair(raw, asset);
}

/**
 * Module-level sidecar cache. Entries are mutable state machines so the rAF
 * loop can poll them without React re-renders.
 */
class TelemetryStore {
  private readonly entries = new Map<string, TelemetryEntry>();

  get(url: string): TelemetryEntry | undefined {
    return this.entries.get(url);
  }

  /** Return the cached entry, starting a lazy decode on first request. */
  ensure(asset: TelemetryAsset): TelemetryEntry {
    const existing = this.entries.get(asset.url);
    if (existing) return existing;
    const loading: TelemetryEntry = {
      status: "loading",
      url: asset.url,
      asset,
    };
    this.entries.set(asset.url, loading);
    void loadTelemetry(asset).then(
      (data) => {
        this.entries.set(asset.url, {
          status: "ready",
          url: asset.url,
          asset,
          data,
        });
      },
      (error: unknown) => {
        const message = error instanceof Error ? error.message : String(error);
        this.entries.set(asset.url, {
          status: "error",
          url: asset.url,
          asset,
          error: message,
        });
      },
    );
    return loading;
  }

  clear(): void {
    this.entries.clear();
  }
}

export const telemetryStore = new TelemetryStore();

export interface TelemetrySample {
  fluxMjySr: number;
  flags: number;
}

/**
 * Nearest-pixel sample in the sidecar grid. Returns null when the sidecar grid
 * does not match the manifest WCS (never guess a different registration).
 */
export function sampleTelemetry(
  data: TelemetryData,
  x: number,
  y: number,
  gridWidth: number,
  gridHeight: number,
): TelemetrySample | null {
  if (data.width !== gridWidth || data.height !== gridHeight) return null;
  const ix = Math.floor(x);
  const iy = Math.floor(y);
  if (ix < 0 || iy < 0 || ix >= data.width || iy >= data.height) return null;
  const index = iy * data.width + ix;
  return {
    fluxMjySr: data.fluxMjySr[index],
    flags: data.flags[index],
  };
}

/** `3.62` for the HUD; scientific notation only for extreme values. */
export function formatMjy(value: number): string {
  if (!Number.isFinite(value)) return "—";
  const magnitude = Math.abs(value);
  if (magnitude === 0) return "0.00";
  if (magnitude >= 1e5 || magnitude < 0.01) return value.toExponential(2);
  return value.toFixed(2);
}

export function formatFlagHex(value: number): string {
  return `0x${(value >>> 0).toString(16).padStart(6, "0")}`;
}
