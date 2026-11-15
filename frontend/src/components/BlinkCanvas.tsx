import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import type { ColormapId } from "../lib/colormaps";
import { colormapLut } from "../lib/colormaps";
import type { StretchId } from "../lib/display";
import type { DecodedFrame } from "../lib/frames";
import {
  buildFlagOverlay,
  decodeFrame,
  flagStrengthAt,
  lumaAt,
  percentileClip,
} from "../lib/frames";
import type { GaiaSource } from "../lib/gaia";
import { GAIA_PM_VECTOR_YEARS } from "../lib/gaia";
import { spectrumAudio } from "../lib/audio";
import { findLvfGeometry, lvfGradientStops } from "../lib/lvf";
import type { LvfHighlight } from "../lib/lvf";
import {
  formatSigned,
  parallaxGridPixels,
  parallaxPeakToPeakArcsec,
  parallaxPeakToPeakGridPixels,
  parallaxSemiAmplitudeArcsec,
  trialShiftGridPixels,
} from "../lib/trial";
import {
  formatFlagHex,
  formatFlagNames,
  formatMjy,
  sampleTelemetry,
  telemetryStore,
} from "../lib/telemetry";
import type { TelemetryEntry } from "../lib/telemetry";
import type { Epoch, LVFGeometry, SkyResponse } from "../lib/types";
import { bandMeta } from "../lib/types";
import { observationDateLabel, telemetryDescription } from "../lib/semantics";
import type { OverlayKey, PlaybackMode } from "../hooks/useUrlState";
import type { GaiaCatalogState } from "../hooks/useGaiaSources";
import {
  angularSeparationArcsec,
  formatDec,
  formatRa,
  pixelToWorld,
  worldToPixel,
} from "../lib/wcs";

const MAX_FPS = 8;
const MIN_ZOOM = 1;
const MAX_ZOOM = 12;
const BG = "#08090b";
const HUD_BG = "rgba(10, 12, 16, 0.82)";
const HUD_BORDER = "rgba(255, 255, 255, 0.1)";
const HUD_TEXT = "#f4f6f8";
const HUD_MUTED = "#9aa1ac";
const HUD_CYAN = "#38bdf8";
const RETICLE_HALO = "rgba(0, 0, 0, 0.78)";
const FONT_MONO = '11px ui-monospace, "SF Mono", Menlo, Consolas, monospace';
const FONT_SANS =
  '11px -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, sans-serif';

export interface BlinkCanvasProps {
  camera?: { zoom: number; panX: number; panY: number };
  onCameraChange?: (camera: {
    zoom: number;
    panX: number;
    panY: number;
  }) => void;
  manifest: SkyResponse;
  band: string;
  epoch: string;
  /** Field of view in degrees: client-side crop of the 240×240 output grid. */
  sizeDeg: number;
  /** Selected adjacent difference pair, when `diff` is true. */
  diffKey?: string | null;
  mode: PlaybackMode;
  fps: number;
  diff: boolean;
  pingpong: boolean;
  colormap: ColormapId;
  stretch: StretchId;
  contrast: number;
  bias: number;
  overlays: OverlayKey[];
  reducedMotion: boolean;
  /** Optional Gaia G≤16 pin catalog; drawn only when the `gaia` overlay is on. */
  gaia: GaiaCatalogState;
  /** Trial-motion sandbox: shift epochs by μ × ΔMJD. */
  track: boolean;
  /** Trial μ_α* (mas/yr), display/URL state. */
  trialPmRa: number;
  /** Trial μ_δ (mas/yr), display/URL state. */
  trialPmDec: number;
  /** Parallax reflex overlay (2 AU baseline). */
  parallax: boolean;
  /** Test/assumed distance for the parallax overlay, AU. */
  parallaxAu: number;
  /** SpectrumDrawer hover → LVF strip highlight. */
  lvfHighlight: LvfHighlight | null;
}

export interface BlinkCanvasHandle {
  /** Reset zoom and pan without touching React state. */
  resetView: () => void;
  /** Epoch currently painted by the rAF loop (null for difference frames). */
  getActiveEpochId: () => string | null;
  /** Index currently painted by the rAF loop (0 for difference frames). */
  getActiveIndex: () => number;
}

interface DecodeState {
  status: "loading" | "ready" | "error";
  loaded: number;
  total: number;
  errors: string[];
}

interface RenderState {
  band: string;
  diff: boolean;
  diffUrl: string | null;
  diffKey: string | null;
  epochs: Epoch[];
  playing: boolean;
  fps: number;
  pingpong: boolean;
  colormap: ColormapId;
  stretch: StretchId;
  contrast: number;
  bias: number;
  overlays: Set<OverlayKey>;
  sizeDeg: number;
  track: boolean;
  trialPmRa: number;
  trialPmDec: number;
  parallax: boolean;
  parallaxAu: number;
  lvfHighlight: LvfHighlight | null;
}

interface ViewState {
  zoom: number;
  panX: number;
  panY: number;
  cssWidth: number;
  cssHeight: number;
  dpr: number;
  scale: number;
  baseScale: number;
  ox: number;
  oy: number;
  srcW: number;
  srcH: number;
  cropX0: number;
  cropY0: number;
  cropPx: number;
  imgW: number;
  imgH: number;
  ready: boolean;
}

interface HoverState {
  x: number;
  y: number;
  inside: boolean;
}

interface FrameInfo {
  frame: DecodedFrame;
  epoch: Epoch | null;
  index: number;
  isDiff: boolean;
}

interface Geometry {
  cssWidth: number;
  cssHeight: number;
  scale: number;
  ox: number;
  oy: number;
  srcW: number;
  srcH: number;
  cropX0: number;
  cropY0: number;
  cropPx: number;
  imgW: number;
  imgH: number;
  /** Display-only co-moving shift applied to the image and fixed-sky pins. */
  shiftX: number;
  shiftY: number;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function setText(element: HTMLElement | null, text: string): void {
  if (element && element.textContent !== text) element.textContent = text;
}

function roundedRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number,
): void {
  const r = Math.min(radius, width / 2, height / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + width - r, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + r);
  ctx.lineTo(x + width, y + height - r);
  ctx.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
  ctx.lineTo(x + r, y + height);
  ctx.quadraticCurveTo(x, y + height, x, y + height - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

/** HUD-consistent chip label drawn on the canvas (no bare text over pixels). */
function drawLabel(
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  options: {
    align?: "left" | "center" | "right";
    color?: string;
    font?: string;
    bg?: string;
  } = {},
): void {
  ctx.font = options.font ?? FONT_MONO;
  const padX = 5;
  const height = 17;
  const width = ctx.measureText(text).width;
  const align = options.align ?? "left";
  const left =
    align === "center"
      ? x - width / 2 - padX
      : align === "right"
        ? x - width - padX * 2
        : x;
  const top = y - height / 2;
  roundedRect(ctx, left, top, width + padX * 2, height, 4);
  ctx.fillStyle = options.bg ?? HUD_BG;
  ctx.fill();
  ctx.strokeStyle = HUD_BORDER;
  ctx.lineWidth = 1;
  ctx.stroke();
  ctx.textBaseline = "middle";
  ctx.fillStyle = options.color ?? HUD_TEXT;
  ctx.fillText(text, left + padX, y + 0.5);
  ctx.textBaseline = "alphabetic";
}

/** Double-stroke hairline: dark halo first, accent second. */
function strokeWithHalo(
  ctx: CanvasRenderingContext2D,
  draw: () => void,
  color = HUD_CYAN,
  width = 1,
): void {
  ctx.save();
  ctx.strokeStyle = RETICLE_HALO;
  ctx.lineWidth = width + 2;
  draw();
  ctx.stroke();
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  draw();
  ctx.stroke();
  ctx.restore();
}

function screenPoint(g: Geometry, x: number, y: number) {
  return {
    x: g.ox + (x - g.cropX0) * g.scale,
    y: g.oy + (y - g.cropY0) * g.scale,
  };
}

function insideCrop(g: Geometry, x: number, y: number): boolean {
  return (
    x >= g.cropX0 &&
    y >= g.cropY0 &&
    x < g.cropX0 + g.cropPx &&
    y < g.cropY0 + g.cropPx
  );
}

function drawReticle(
  ctx: CanvasRenderingContext2D,
  manifest: SkyResponse,
  g: Geometry,
  track: boolean,
): void {
  const target = manifest.target;
  if (!target) return;
  const wcs = manifest.wcs;
  const ref = worldToPixel(wcs, target.ra_ref, target.dec_ref);
  const cur = worldToPixel(wcs, target.ra_epoch2025, target.dec_epoch2025);
  const refScreen = screenPoint(g, ref.x, ref.y);
  const curScreen = screenPoint(g, cur.x, cur.y);
  const separation = angularSeparationArcsec(
    { ra: target.ra_ref, dec: target.dec_ref },
    { ra: target.ra_epoch2025, dec: target.dec_epoch2025 },
  );
  const vectorPx = Math.hypot(
    refScreen.x - curScreen.x,
    refScreen.y - curScreen.y,
  );
  const refVisible = insideCrop(g, ref.x, ref.y);
  const curVisible = insideCrop(g, cur.x, cur.y);
  const midVisible = insideCrop(g, (ref.x + cur.x) / 2, (ref.y + cur.y) / 2);

  ctx.save();
  ctx.beginPath();
  ctx.rect(g.ox, g.oy, g.imgW, g.imgH);
  ctx.clip();

  // In co-moving mode the trial vector locks the target at the crosshair; the
  // historical reference vector would imply a sky-fixed frame, so it is hidden.
  if (!track && vectorPx > 3) {
    strokeWithHalo(
      ctx,
      () => {
        ctx.setLineDash([5, 4]);
        ctx.beginPath();
        ctx.moveTo(refScreen.x, refScreen.y);
        ctx.lineTo(curScreen.x, curScreen.y);
      },
      HUD_CYAN,
      1,
    );
    ctx.setLineDash([]);

    if (curVisible) {
      // Arrowhead at the 2025.8 end, haloed for contrast over bright stars.
      const angle = Math.atan2(
        curScreen.y - refScreen.y,
        curScreen.x - refScreen.x,
      );
      const triangle = (head: number) => {
        ctx.beginPath();
        ctx.moveTo(curScreen.x, curScreen.y);
        ctx.lineTo(
          curScreen.x - head * Math.cos(angle - 0.4),
          curScreen.y - head * Math.sin(angle - 0.4),
        );
        ctx.lineTo(
          curScreen.x - head * Math.cos(angle + 0.4),
          curScreen.y - head * Math.sin(angle + 0.4),
        );
        ctx.closePath();
      };
      ctx.fillStyle = RETICLE_HALO;
      triangle(9);
      ctx.fill();
      ctx.fillStyle = HUD_CYAN;
      triangle(5.5);
      ctx.fill();
    }
  }

  if (!track && refVisible) {
    // Reference-epoch marker.
    strokeWithHalo(
      ctx,
      () => {
        ctx.setLineDash([3, 3]);
        ctx.beginPath();
        ctx.arc(refScreen.x, refScreen.y, 6, 0, Math.PI * 2);
      },
      "rgba(244, 246, 248, 0.9)",
      1,
    );
    ctx.setLineDash([]);
    strokeWithHalo(
      ctx,
      () => {
        ctx.beginPath();
        ctx.moveTo(refScreen.x - 3, refScreen.y);
        ctx.lineTo(refScreen.x + 3, refScreen.y);
        ctx.moveTo(refScreen.x, refScreen.y - 3);
        ctx.lineTo(refScreen.x, refScreen.y + 3);
      },
      "rgba(244, 246, 248, 0.9)",
      1,
    );
  }

  if (curVisible) {
    // 2025.8 marker (frame centre / aperture centre).
    strokeWithHalo(ctx, () => {
      ctx.beginPath();
      ctx.arc(curScreen.x, curScreen.y, 8, 0, Math.PI * 2);
    });
    strokeWithHalo(ctx, () => {
      ctx.beginPath();
      ctx.moveTo(curScreen.x - 12, curScreen.y);
      ctx.lineTo(curScreen.x - 9, curScreen.y);
      ctx.moveTo(curScreen.x + 9, curScreen.y);
      ctx.lineTo(curScreen.x + 12, curScreen.y);
      ctx.moveTo(curScreen.x, curScreen.y - 12);
      ctx.lineTo(curScreen.x, curScreen.y - 9);
      ctx.moveTo(curScreen.x, curScreen.y + 9);
      ctx.lineTo(curScreen.x, curScreen.y + 12);
    });
  }
  ctx.restore();

  if (track && curVisible) {
    drawLabel(ctx, "TRIAL LOCK", curScreen.x + 14, curScreen.y + 18, {
      align: curScreen.x < g.cssWidth - 100 ? "left" : "right",
      color: HUD_CYAN,
    });
  } else if (refVisible) {
    drawLabel(
      ctx,
      `${target.ref_epoch} ref`,
      refScreen.x - 10,
      refScreen.y - 20,
      { align: "right", color: "#d5dae2" },
    );
  }
  if (!track && curVisible) {
    drawLabel(ctx, "2025.8", curScreen.x + 14, curScreen.y + 18, {
      align: curScreen.x < g.cssWidth - 90 ? "left" : "right",
      color: HUD_CYAN,
    });
  }
  if (!track && separation > 0.5 && midVisible) {
    drawLabel(
      ctx,
      `PM ${separation >= 100 ? separation.toFixed(0) : separation.toFixed(1)}″`,
      (refScreen.x + curScreen.x) / 2,
      (refScreen.y + curScreen.y) / 2 - 30,
      { align: "center", color: HUD_CYAN },
    );
  }
}

function drawPixelBox(
  ctx: CanvasRenderingContext2D,
  manifest: SkyResponse,
  g: Geometry,
): void {
  const target = manifest.target;
  const wcs = manifest.wcs;
  const center = target
    ? worldToPixel(wcs, target.ra_epoch2025, target.dec_epoch2025)
    : { x: wcs.width / 2, y: wcs.height / 2 };
  if (!insideCrop(g, center.x, center.y)) return;
  const box = 2 * g.scale; // 2 grid pixels = 6.15″ at 3.075″/px
  const x0 = g.ox + (center.x - 1 - g.cropX0) * g.scale;
  const y0 = g.oy + (center.y - 1 - g.cropY0) * g.scale;
  ctx.save();
  strokeWithHalo(
    ctx,
    () => {
      ctx.setLineDash([3, 3]);
      ctx.strokeRect(x0, y0, box, box);
    },
    HUD_CYAN,
    1,
  );
  ctx.setLineDash([]);
  const labelX = x0 + box + 6;
  drawLabel(
    ctx,
    "6.15″ native px",
    labelX < g.cssWidth - 100 ? labelX : x0 - 6,
    y0 - 11,
    {
      align: labelX < g.cssWidth - 100 ? "left" : "right",
      color: HUD_CYAN,
    },
  );
  ctx.restore();
}

function drawScaleBar(
  ctx: CanvasRenderingContext2D,
  manifest: SkyResponse,
  g: Geometry,
): void {
  const wcs = manifest.wcs;
  const arcsecPerCssPx = wcs.pixel_scale_arcsec / g.scale;
  const candidates = [10, 15, 30, 60, 120, 300, 600];
  let chosen = candidates[0];
  for (const candidate of candidates) {
    if (candidate / arcsecPerCssPx <= 150) chosen = candidate;
  }
  const barPx = chosen / arcsecPerCssPx;
  const x = 16;
  const y = g.cssHeight - 26;
  strokeWithHalo(
    ctx,
    () => {
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x + barPx, y);
      ctx.moveTo(x, y - 4);
      ctx.lineTo(x, y + 4);
      ctx.moveTo(x + barPx, y - 4);
      ctx.lineTo(x + barPx, y + 4);
    },
    "rgba(244, 246, 248, 0.9)",
    1,
  );
  drawLabel(ctx, `${chosen}″`, x + barPx / 2, y - 14, {
    align: "center",
    color: "#e6e8ec",
  });
}

function drawCompass(
  ctx: CanvasRenderingContext2D,
  manifest: SkyResponse,
  g: Geometry,
): void {
  const wcs = manifest.wcs;
  const northUp = wcs.cdelt2 > 0;
  const eastLeft = wcs.cdelt1 < 0;
  const cx = g.cssWidth - 38;
  const cy = 132;
  const arm = 13;
  strokeWithHalo(
    ctx,
    () => {
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx, northUp ? cy - arm : cy + arm);
      ctx.moveTo(cx, cy);
      ctx.lineTo(eastLeft ? cx - arm : cx + arm, cy);
    },
    "rgba(244, 246, 248, 0.85)",
    1,
  );
  strokeWithHalo(ctx, () => {
    ctx.beginPath();
    ctx.arc(cx, cy, 1.6, 0, Math.PI * 2);
  });
  drawLabel(ctx, "N", cx, northUp ? cy - arm - 9 : cy + arm + 9, {
    align: "center",
    color: "#e6e8ec",
  });
  drawLabel(ctx, "E", eastLeft ? cx - arm - 9 : cx + arm + 9, cy, {
    align: "center",
    color: "#e6e8ec",
  });
}

/**
 * Gaia G≤16 pins with 10-year catalog proper-motion vectors.
 *
 * Gaia catalogs are display references, not
 * detections. A null PM keeps the pin and suppresses the vector. All text
 * stays in HUD chips.
 */
function drawGaiaPins(
  ctx: CanvasRenderingContext2D,
  sources: GaiaSource[],
  manifest: SkyResponse,
  g: Geometry,
  shiftX: number,
  shiftY: number,
): void {
  if (sources.length === 0) return;
  const wcs = manifest.wcs;
  ctx.save();
  ctx.beginPath();
  ctx.rect(g.ox, g.oy, g.imgW, g.imgH);
  ctx.clip();

  for (const source of sources) {
    const center = worldToPixel(wcs, source.ra, source.dec);
    if (!insideCrop(g, center.x, center.y)) continue;
    const base = screenPoint(g, center.x, center.y);
    const pin = { x: base.x + shiftX, y: base.y + shiftY };

    if (
      source.pmra !== null &&
      source.pmdec !== null &&
      (source.pmra !== 0 || source.pmdec !== 0)
    ) {
      const cosDec = Math.max(0.01, Math.cos((source.dec * Math.PI) / 180));
      const deltaRaDeg = (source.pmra * GAIA_PM_VECTOR_YEARS) / 3.6e6 / cosDec;
      const deltaDecDeg = (source.pmdec * GAIA_PM_VECTOR_YEARS) / 3.6e6;
      const endSource = worldToPixel(
        wcs,
        source.ra + deltaRaDeg,
        source.dec + deltaDecDeg,
      );
      const end = screenPoint(g, endSource.x, endSource.y);
      let dx = end.x + shiftX - pin.x;
      let dy = end.y + shiftY - pin.y;
      const length = Math.hypot(dx, dy);
      if (length > 0) {
        // Real 10-yr Gaia vectors are usually sub-pixel at this field of view.
        // Keep the direction visible as a 5 px tick; the DisplayPanel labels
        // that the tick is a direction cue, not a to-scale displacement.
        const drawnLength = Math.max(5, length);
        dx = (dx / length) * drawnLength;
        dy = (dy / length) * drawnLength;
        strokeWithHalo(
          ctx,
          () => {
            ctx.beginPath();
            ctx.moveTo(pin.x, pin.y);
            ctx.lineTo(pin.x + dx, pin.y + dy);
          },
          HUD_CYAN,
          1,
        );
        strokeWithHalo(
          ctx,
          () => {
            ctx.beginPath();
            ctx.arc(pin.x + dx, pin.y + dy, 1.5, 0, Math.PI * 2);
          },
          HUD_CYAN,
          1,
        );
      }
    }

    const radius = clamp(5.2 - (source.g_mag - 12) * 0.55, 2.4, 5.2);
    strokeWithHalo(
      ctx,
      () => {
        ctx.beginPath();
        ctx.arc(pin.x, pin.y, radius, 0, Math.PI * 2);
      },
      "rgba(230, 232, 236, 0.95)",
      1,
    );
    ctx.fillStyle = "rgba(230, 232, 236, 0.9)";
    ctx.beginPath();
    ctx.arc(pin.x, pin.y, 1, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

/**
 * Parallax reflex overlay (2 AU baseline). ϖ is the annual semi-amplitude and
 * 2ϖ is the six-month peak-to-peak shift. A sub-pixel ϖ is shown in a labelled
 * inset; the true on-sky size is never inflated without stating the factor.
 */
function drawParallax(
  ctx: CanvasRenderingContext2D,
  manifest: SkyResponse,
  g: Geometry,
  distanceAu: number,
): void {
  const wcs = manifest.wcs;
  const semiArcsec = parallaxSemiAmplitudeArcsec(distanceAu);
  const peakArcsec = parallaxPeakToPeakArcsec(distanceAu);
  if (!(semiArcsec > 0)) return;
  const semiGridPx = parallaxGridPixels(wcs, distanceAu);
  const semiScreenPx = semiGridPx * g.scale;
  const center = manifest.target
    ? worldToPixel(
        wcs,
        manifest.target.ra_epoch2025,
        manifest.target.dec_epoch2025,
      )
    : { x: wcs.width / 2, y: wcs.height / 2 };
  if (!insideCrop(g, center.x, center.y)) return;
  const anchor = screenPoint(g, center.x, center.y);

  ctx.save();
  ctx.beginPath();
  ctx.rect(g.ox, g.oy, g.imgW, g.imgH);
  ctx.clip();

  if (semiScreenPx >= 8) {
    strokeWithHalo(
      ctx,
      () => {
        ctx.setLineDash([4, 5]);
        ctx.beginPath();
        ctx.arc(anchor.x, anchor.y, semiScreenPx, 0, Math.PI * 2);
      },
      HUD_CYAN,
      1,
    );
    ctx.setLineDash([]);
    // The orbit centre is the barycentre; a tiny marker keeps it interpretable.
    strokeWithHalo(ctx, () => {
      ctx.beginPath();
      ctx.arc(anchor.x, anchor.y, 2, 0, Math.PI * 2);
    });
    const labelY = anchor.y - Math.min(semiScreenPx, g.imgH / 2 - 16);
    drawLabel(
      ctx,
      `PARALLAX ϖ ${semiArcsec.toFixed(1)}″ · 2ϖ ${peakArcsec.toFixed(1)}″`,
      anchor.x,
      clamp(labelY, g.oy + 18, g.oy + g.imgH - 18),
      { align: "center", color: HUD_CYAN },
    );
    // If the annual circle is larger than the field, show a true-scale radius
    // line to the edge so the overlay is still visible and interpretable.
    if (semiScreenPx > Math.min(g.imgW, g.imgH) / 2) {
      const reach = Math.min(semiScreenPx, g.imgW / 2 - 16);
      const endX = anchor.x + reach;
      strokeWithHalo(
        ctx,
        () => {
          ctx.setLineDash([4, 5]);
          ctx.beginPath();
          ctx.moveTo(anchor.x, anchor.y);
          ctx.lineTo(endX, anchor.y);
        },
        HUD_CYAN,
        1,
      );
      ctx.setLineDash([]);
      ctx.fillStyle = HUD_CYAN;
      ctx.beginPath();
      ctx.moveTo(endX, anchor.y);
      ctx.lineTo(endX - 7, anchor.y - 4);
      ctx.lineTo(endX - 7, anchor.y + 4);
      ctx.closePath();
      ctx.fill();
      drawLabel(
        ctx,
        `ϖ radius ${semiArcsec.toFixed(0)}″ · circle exceeds field`,
        endX - 4,
        anchor.y - 14,
        { align: "right", color: HUD_CYAN },
      );
    }
  } else {
    // Sub-pixel on-sky reflex: an astrometric inset with a stated magnification.
    const factor = 26 / Math.max(0.01, semiScreenPx);
    const boxWidth = 174;
    const boxHeight = 108;
    const boxX = g.ox + 12;
    const boxY = g.oy + g.imgH - boxHeight - 46;
    roundedRect(ctx, boxX, boxY, boxWidth, boxHeight, 4);
    ctx.fillStyle = HUD_BG;
    ctx.fill();
    ctx.strokeStyle = HUD_BORDER;
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.strokeStyle = "rgba(56, 189, 248, 0.35)";
    ctx.setLineDash([3, 4]);
    ctx.beginPath();
    ctx.arc(boxX + 46, boxY + 58, 26, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.strokeStyle = HUD_CYAN;
    ctx.beginPath();
    ctx.moveTo(boxX + 46 - 32, boxY + 58);
    ctx.lineTo(boxX + 46 + 32, boxY + 58);
    ctx.moveTo(boxX + 46, boxY + 58 - 32);
    ctx.lineTo(boxX + 46, boxY + 58 + 32);
    ctx.stroke();
    ctx.fillStyle = HUD_TEXT;
    ctx.beginPath();
    ctx.arc(boxX + 46, boxY + 58, 2, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = HUD_CYAN;
    ctx.font = '9px ui-monospace, "SF Mono", Menlo, Consolas, monospace';
    ctx.fillText(`INSET ×${factor.toFixed(0)}`, boxX + 82, boxY + 20);
    ctx.fillStyle = HUD_TEXT;
    ctx.font = '10px ui-monospace, "SF Mono", Menlo, Consolas, monospace';
    ctx.fillText(`ϖ ${semiArcsec.toFixed(3)}″`, boxX + 82, boxY + 38);
    ctx.fillText(`2ϖ ${peakArcsec.toFixed(3)}″`, boxX + 82, boxY + 53);
    ctx.fillStyle = HUD_MUTED;
    ctx.font = '8.5px ui-monospace, "SF Mono", Menlo, Consolas, monospace';
    ctx.fillText(
      `on-sky ${parallaxPeakToPeakGridPixels(wcs, distanceAu).toFixed(2)} px`,
      boxX + 82,
      boxY + 68,
    );
    ctx.fillText("schematic — not to scale", boxX + 82, boxY + 82);
    ctx.fillText("2 AU baseline", boxX + 12, boxY + 98);
  }
  ctx.restore();
}

/**
 * Six translucent LVF strips whose long axis follows each detector's position
 * angle. The gradient runs from short to long wavelength along the PA. The
 * active detector (from a SpectrumDrawer hover) is highlighted and its measured
 * gradient is labelled. No detector footprint is implied.
 */
function drawLvfOverlay(
  ctx: CanvasRenderingContext2D,
  manifest: SkyResponse,
  g: Geometry,
  geometries: LVFGeometry[],
  highlight: LvfHighlight | null,
  showAll: boolean,
): void {
  if (geometries.length === 0) return;
  const wcs = manifest.wcs;
  const center = manifest.target
    ? worldToPixel(
        wcs,
        manifest.target.ra_epoch2025,
        manifest.target.dec_epoch2025,
      )
    : { x: wcs.width / 2, y: wcs.height / 2 };
  if (!insideCrop(g, center.x, center.y)) return;
  const anchor = screenPoint(g, center.x, center.y);
  const length = Math.min(g.cssWidth, g.cssHeight) * 0.46;
  const half = length / 2;
  const stops = lvfGradientStops();

  ctx.save();
  ctx.beginPath();
  ctx.rect(g.ox, g.oy, g.imgW, g.imgH);
  ctx.clip();

  for (const geometry of geometries) {
    const active = highlight?.detector === geometry.detector;
    // With the global overlay off, only the hovered detector is drawn. This
    // keeps the SpectrumDrawer hover meaningful without silently enabling six
    // strips for the whole field.
    if (!showAll && !active) continue;
    const theta = (geometry.pa_deg * Math.PI) / 180;
    // PA 0 = north (screen up); PA 90 = east (screen left on this WCS).
    const dx = -Math.sin(theta);
    const dy = -Math.cos(theta);
    const x0 = anchor.x - dx * half;
    const y0 = anchor.y - dy * half;
    const x1 = anchor.x + dx * half;
    const y1 = anchor.y + dy * half;
    const gradient = ctx.createLinearGradient(x0, y0, x1, y1);
    for (const stop of stops) gradient.addColorStop(stop.offset, stop.color);

    ctx.save();
    ctx.globalAlpha = active ? 0.42 : 0.1;
    ctx.strokeStyle = gradient;
    ctx.lineWidth = active ? 22 : 12;
    ctx.lineCap = "butt";
    ctx.beginPath();
    ctx.moveTo(x0, y0);
    ctx.lineTo(x1, y1);
    ctx.stroke();
    ctx.restore();

    if (active) {
      ctx.save();
      ctx.globalAlpha = 0.9;
      ctx.strokeStyle = HUD_CYAN;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x0, y0);
      ctx.lineTo(x1, y1);
      ctx.stroke();
      ctx.restore();

      if (highlight) {
        const t = clamp((highlight.wavelengthUm - 0.75) / (5.0 - 0.75), 0, 1);
        const mx = x0 + (x1 - x0) * t;
        const my = y0 + (y1 - y0) * t;
        const px = -dy;
        const py = dx;
        strokeWithHalo(
          ctx,
          () => {
            ctx.beginPath();
            ctx.moveTo(mx - px * 7, my - py * 7);
            ctx.lineTo(mx + px * 7, my + py * 7);
          },
          HUD_TEXT,
          1,
        );
        ctx.fillStyle = HUD_CYAN;
        ctx.beginPath();
        ctx.arc(mx, my, 2.2, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    const labelX = x1 + dx * 10;
    const labelY = y1 + dy * 10;
    const labelInside = insideCrop(g, labelX, labelY);
    if (labelInside && (active || geometries.length <= 6)) {
      const label = active
        ? `D${geometry.detector} · PA ${geometry.pa_deg.toFixed(0)}° · ${geometry.grad_um_per_arcsec.toFixed(3)} µm/″${
            highlight ? ` · λ ${highlight.wavelengthUm.toFixed(2)} µm` : ""
          }`
        : `D${geometry.detector}`;
      drawLabel(ctx, label, labelX, labelY, {
        align: "center",
        color: active ? HUD_CYAN : HUD_MUTED,
        font: active
          ? '10px ui-monospace, "SF Mono", Menlo, Consolas, monospace'
          : '9px ui-monospace, "SF Mono", Menlo, Consolas, monospace',
      });
    }
  }
  ctx.restore();
}

function drawCrosshair(
  ctx: CanvasRenderingContext2D,
  hover: HoverState,
  g: Geometry,
): void {
  const xSrc = g.cropX0 + (hover.x - g.ox) / g.scale;
  const ySrc = g.cropY0 + (hover.y - g.oy) / g.scale;
  if (!insideCrop(g, xSrc, ySrc)) return;
  ctx.save();
  ctx.strokeStyle = "rgba(56, 189, 248, 0.5)";
  ctx.lineWidth = 1;
  ctx.setLineDash([3, 4]);
  ctx.beginPath();
  ctx.moveTo(hover.x, g.oy);
  ctx.lineTo(hover.x, g.oy + g.imgH);
  ctx.moveTo(g.ox, hover.y);
  ctx.lineTo(g.ox + g.imgW, hover.y);
  ctx.stroke();
  ctx.setLineDash([]);
  roundedRect(ctx, hover.x - 3, hover.y - 3, 6, 6, 1);
  ctx.strokeStyle = "rgba(56, 189, 248, 0.9)";
  ctx.stroke();
  ctx.restore();
}

function buildDisplayCanvas(
  offscreen: HTMLCanvasElement,
  frame: DecodedFrame,
  state: RenderState,
  stretchRange: { lo: number; hi: number },
): void {
  const ctx = offscreen.getContext("2d");
  if (!ctx) return;
  const width = frame.width;
  const height = frame.height;
  if (offscreen.width !== width || offscreen.height !== height) {
    offscreen.width = width;
    offscreen.height = height;
  }
  const imageData = ctx.createImageData(width, height);
  const data = imageData.data;
  const lut = colormapLut(state.colormap);
  const span = Math.max(1e-6, stretchRange.hi - stretchRange.lo);
  const count = width * height;
  const contrast = state.contrast;
  const bias = state.bias;

  for (let i = 0; i < count; i += 1) {
    const ref = frame.luma[i] / 255;
    let t: number;
    if (state.diff) {
      const signed = clamp((frame.luma[i] - 128) / 127.5, -1, 1);
      t = (clamp(signed * contrast + bias * 2, -1, 1) + 1) / 2;
    } else {
      switch (state.stretch) {
        case "log":
          t = Math.log10(1 + 999 * ref) / 3;
          break;
        case "asinh":
          t = Math.asinh(10 * ref) / Math.asinh(10);
          break;
        case "zscale":
          t = (ref - stretchRange.lo) / span;
          break;
        default:
          t = ref;
          break;
      }
      t = clamp((t + bias - 0.5) * contrast + 0.5, 0, 1);
    }
    const index = (t * 255) | 0;
    const offset = i * 4;
    data[offset] = lut[index * 3];
    data[offset + 1] = lut[index * 3 + 1];
    data[offset + 2] = lut[index * 3 + 2];
    data[offset + 3] = 255;
  }
  ctx.putImageData(imageData, 0, 0);
}

export const BlinkCanvas = forwardRef<BlinkCanvasHandle, BlinkCanvasProps>(
  function BlinkCanvas(props, ref) {
    const {
      manifest,
      band,
      epoch,
      sizeDeg,
      diffKey: selectedDiffKey,
      mode,
      fps,
      diff,
      pingpong,
      colormap,
      stretch,
      contrast,
      bias,
      overlays,
      reducedMotion,
      gaia,
      track,
      trialPmRa,
      trialPmDec,
      parallax,
      parallaxAu,
      lvfHighlight,
    } = props;

    const cameraRef = useRef(props.camera);
    const cameraChangeRef = useRef(props.onCameraChange);
    cameraRef.current = props.camera;
    cameraChangeRef.current = props.onCameraChange;
    const canvasRef = useRef<HTMLCanvasElement | null>(null);
    const ctxRef = useRef<CanvasRenderingContext2D | null>(null);
    const offscreenRef = useRef<HTMLCanvasElement | null>(null);
    const framesRef = useRef<Map<string, DecodedFrame>>(new Map());
    const sceneRef = useRef<SkyResponse>(manifest);
    const decodeRef = useRef<DecodeState>({
      status: "loading",
      loaded: 0,
      total: 0,
      errors: [],
    });
    const [decode, setDecode] = useState<DecodeState>(decodeRef.current);
    const [decodeAttempt, setDecodeAttempt] = useState(0);

    // HUD text is written directly from the rAF loop (LAW 6: no setState per tick).
    const epochLineRef = useRef<HTMLSpanElement | null>(null);
    const metaLineRef = useRef<HTMLSpanElement | null>(null);
    const raRef = useRef<HTMLSpanElement | null>(null);
    const decRef = useRef<HTMLSpanElement | null>(null);
    const fluxRef = useRef<HTMLSpanElement | null>(null);
    const fluxNoteRef = useRef<HTMLSpanElement | null>(null);
    const pixelRef = useRef<HTMLSpanElement | null>(null);
    const flagNamesRef = useRef<HTMLSpanElement | null>(null);
    const flagStatusRef = useRef<HTMLSpanElement | null>(null);
    const trackLineRef = useRef<HTMLSpanElement | null>(null);
    const parallaxLineRef = useRef<HTMLSpanElement | null>(null);
    const lvfLineRef = useRef<HTMLSpanElement | null>(null);
    const gaiaRef = useRef<GaiaCatalogState>(gaia);

    const epochsForBand = manifest.epochs.filter(
      (entry) => typeof entry.frames[band] === "string",
    );
    const epochsKey = epochsForBand.map((entry) => entry.epoch_id).join("|");

    const fallbackDiffKey = diff
      ? (Object.keys(manifest.differences).find(
          (key) => typeof manifest.differences[key]?.[band] === "string",
        ) ??
        Object.keys(manifest.differences)[0] ??
        null)
      : null;
    const diffKey = diff
      ? selectedDiffKey === undefined
        ? fallbackDiffKey
        : selectedDiffKey && manifest.differences[selectedDiffKey]
          ? selectedDiffKey
          : null
      : null;
    const diffUrl = diffKey
      ? (manifest.differences[diffKey]?.[band] ?? null)
      : null;

    const stateRef = useRef<RenderState>({
      band,
      diff,
      diffUrl,
      diffKey,
      epochs: epochsForBand,
      playing: mode === "blink" && !reducedMotion && !diff,
      fps,
      pingpong,
      colormap,
      stretch,
      contrast,
      bias,
      overlays: new Set(overlays),
      sizeDeg,
      track,
      trialPmRa,
      trialPmDec,
      parallax,
      parallaxAu,
      lvfHighlight,
    });
    const activeRef = useRef({
      index: 0,
      direction: 1,
      lastTick: 0,
      lastTickedIndex: -1,
    });
    const hoverRef = useRef<HoverState>({ x: 0, y: 0, inside: false });
    const viewRef = useRef<ViewState>({
      zoom: 1,
      panX: 0,
      panY: 0,
      cssWidth: 0,
      cssHeight: 0,
      dpr: 1,
      scale: 1,
      baseScale: 1,
      ox: 0,
      oy: 0,
      srcW: manifest.wcs.width,
      srcH: manifest.wcs.height,
      cropX0: 0,
      cropY0: 0,
      cropPx: manifest.wcs.width,
      imgW: manifest.wcs.width,
      imgH: manifest.wcs.height,
      ready: false,
    });
    const dragRef = useRef({
      active: false,
      startX: 0,
      startY: 0,
      startPanX: 0,
      startPanY: 0,
    });
    const cacheRef = useRef({ signature: "" });
    const stretchRefs = useRef(new Map<string, { lo: number; hi: number }>());
    const flagOverlaysRef = useRef(new Map<string, HTMLCanvasElement>());

    // --- Scene + decode state keep in sync without touching React on ticks.
    useEffect(() => {
      const previous = framesRef.current;
      sceneRef.current = manifest;
      framesRef.current = new Map();
      for (const frame of previous.values()) frame.bitmap.close();
      cacheRef.current.signature = "";
      stretchRefs.current.clear();
      flagOverlaysRef.current.clear();
      activeRef.current.index = 0;
    }, [manifest]);

    useEffect(() => {
      decodeRef.current = decode;
    }, [decode]);

    useEffect(() => {
      gaiaRef.current = gaia;
    }, [gaia]);

    // --- Mirror props into the animation-state ref (LAW 6).
    useEffect(() => {
      const state = stateRef.current;
      const playing = mode === "blink" && !reducedMotion && !diff;
      if (playing && !state.playing) {
        activeRef.current.lastTick = performance.now();
      }
      state.band = band;
      state.diff = diff;
      state.diffUrl = diffUrl;
      state.diffKey = diffKey;
      state.epochs = epochsForBand;
      state.playing = playing;
      state.fps = clamp(fps, 1, MAX_FPS);
      state.pingpong = pingpong;
      state.colormap = colormap;
      state.stretch = stretch;
      state.contrast = contrast;
      state.bias = bias;
      state.overlays = new Set(overlays);
      state.sizeDeg = sizeDeg;
      state.track = track;
      state.trialPmRa = trialPmRa;
      state.trialPmDec = trialPmDec;
      state.parallax = parallax;
      state.parallaxAu = parallaxAu;
      state.lvfHighlight = lvfHighlight;
    }, [
      band,
      diff,
      diffUrl,
      diffKey,
      epochsKey,
      mode,
      reducedMotion,
      fps,
      pingpong,
      colormap,
      stretch,
      contrast,
      bias,
      overlays,
      sizeDeg,
      track,
      trialPmRa,
      trialPmDec,
      parallax,
      parallaxAu,
      lvfHighlight,
    ]);

    // A new FOV changes the crop scale; return to a predictable framing.
    useEffect(() => {
      const view = viewRef.current;
      view.zoom = 1;
      view.panX = 0;
      view.panY = 0;
    }, [sizeDeg]);

    // --- Reset the ring when the selected sequence changes.
    useEffect(() => {
      const active = activeRef.current;
      if (diff) {
        active.index = 0;
      } else if (epoch !== "all") {
        const found = epochsForBand.findIndex(
          (entry) => entry.epoch_id === epoch,
        );
        active.index = found >= 0 ? found : 0;
      } else if (active.index >= epochsForBand.length) {
        active.index = 0;
      }
      active.direction = 1;
      active.lastTick = performance.now();
    }, [band, diff, epoch, epochsKey, epochsForBand.length]);

    // --- Pre-decode every frame in the manifest (once per manifest).
    useEffect(() => {
      let cancelled = false;
      const urls = new Set<string>();
      for (const entry of manifest.epochs) {
        for (const url of Object.values(entry.frames)) urls.add(url);
      }
      for (const pair of Object.values(manifest.differences)) {
        for (const url of Object.values(pair)) urls.add(url);
      }
      const list = [...urls];
      const decoded = new Map<string, DecodedFrame>();
      const errors: string[] = [];
      let next = 0;
      let loaded = 0;
      setDecode({
        status: "loading",
        loaded: 0,
        total: list.length,
        errors: [],
      });

      const worker = async (): Promise<void> => {
        while (!cancelled) {
          const index = next;
          next += 1;
          if (index >= list.length) return;
          const url = list[index];
          try {
            const frame = await decodeFrame(url);
            if (cancelled) {
              frame.bitmap.close();
              return;
            }
            decoded.set(url, frame);
          } catch (error) {
            errors.push(error instanceof Error ? error.message : String(error));
          }
          loaded += 1;
          if (!cancelled) {
            setDecode({
              status: "loading",
              loaded,
              total: list.length,
              errors: [...errors],
            });
          }
        }
      };

      void Promise.all([worker(), worker(), worker(), worker()]).then(() => {
        if (cancelled) {
          for (const frame of decoded.values()) frame.bitmap.close();
          return;
        }
        for (const frame of framesRef.current.values()) frame.bitmap.close();
        framesRef.current = decoded;
        cacheRef.current.signature = "";
        const nextState: DecodeState = {
          status: errors.length > 0 ? "error" : "ready",
          loaded: list.length,
          total: list.length,
          errors,
        };
        decodeRef.current = nextState;
        setDecode(nextState);
      });

      return () => {
        cancelled = true;
      };
    }, [manifest, decodeAttempt]);

    // --- Close bitmaps on unmount only.
    useEffect(() => {
      return () => {
        for (const frame of framesRef.current.values()) frame.bitmap.close();
        framesRef.current = new Map();
      };
    }, []);

    const resetView = useCallback(() => {
      const view = viewRef.current;
      view.zoom = 1;
      view.panX = 0;
      view.panY = 0;
      cameraChangeRef.current?.({ zoom: 1, panX: 0, panY: 0 });
    }, []);

    useImperativeHandle(
      ref,
      () => ({
        resetView,
        getActiveEpochId: () => {
          const state = stateRef.current;
          if (state.diff) return null;
          return state.epochs[activeRef.current.index]?.epoch_id ?? null;
        },
        getActiveIndex: () =>
          stateRef.current.diff ? 0 : activeRef.current.index,
      }),
      [resetView],
    );

    // --- Zoom around the cursor (native listener so preventDefault works).
    useEffect(() => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const onWheel = (event: WheelEvent) => {
        if (!event.ctrlKey && !event.metaKey) return;
        event.preventDefault();
        const view = viewRef.current;
        if (!view.ready) return;
        const rect = canvas.getBoundingClientRect();
        const mouseX = event.clientX - rect.left;
        const mouseY = event.clientY - rect.top;
        const worldX = view.cropX0 + (mouseX - view.ox) / view.scale;
        const worldY = view.cropY0 + (mouseY - view.oy) / view.scale;
        const factor = event.deltaY < 0 ? 1.18 : 1 / 1.18;
        const zoom = clamp(view.zoom * factor, MIN_ZOOM, MAX_ZOOM);
        const scale = view.baseScale * zoom;
        const imgW = view.cropPx * scale;
        const imgH = view.cropPx * scale;
        const baseOx = (view.cssWidth - imgW) / 2;
        const baseOy = (view.cssHeight - imgH) / 2;
        view.zoom = zoom;
        view.panX = mouseX - baseOx - (worldX - view.cropX0) * scale;
        view.panY = mouseY - baseOy - (worldY - view.cropY0) * scale;
        const next = { zoom, panX: view.panX / imgW, panY: view.panY / imgH };
        cameraRef.current = next;
        cameraChangeRef.current?.(next);
      };
      canvas.addEventListener("wheel", onWheel, { passive: false });
      return () => canvas.removeEventListener("wheel", onWheel);
    }, []);

    const onPointerDown = (event: ReactPointerEvent<HTMLCanvasElement>) => {
      if (event.pointerType === "touch") return;
      const canvas = canvasRef.current;
      if (!canvas) return;
      canvas.focus({ preventScroll: true });
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      const view = viewRef.current;
      dragRef.current = {
        active: true,
        startX: x,
        startY: y,
        startPanX: view.panX,
        startPanY: view.panY,
      };
      canvas.setPointerCapture(event.pointerId);
      canvas.style.cursor = "grabbing";
    };

    const onPointerMove = (event: ReactPointerEvent<HTMLCanvasElement>) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      hoverRef.current = { x, y, inside: true };
      const drag = dragRef.current;
      if (drag.active) {
        const view = viewRef.current;
        view.panX = drag.startPanX + (x - drag.startX);
        view.panY = drag.startPanY + (y - drag.startY);
        const next = {
          zoom: view.zoom,
          panX: view.panX / view.imgW,
          panY: view.panY / view.imgH,
        };
        cameraRef.current = next;
        cameraChangeRef.current?.(next);
      }
    };

    const endDrag = (event: ReactPointerEvent<HTMLCanvasElement>) => {
      const drag = dragRef.current;
      if (!drag.active) return;
      drag.active = false;
      const canvas = canvasRef.current;
      if (canvas) {
        if (canvas.hasPointerCapture(event.pointerId)) {
          canvas.releasePointerCapture(event.pointerId);
        }
        canvas.style.cursor = "grab";
      }
    };

    const onPointerLeave = () => {
      hoverRef.current = { x: 0, y: 0, inside: false };
    };

    // --- Persistent rAF loop: the only place that paints pixels (LAW 6).
    useEffect(() => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext("2d", { alpha: false });
      if (!ctx) return;
      ctxRef.current = ctx;

      let raf = 0;
      let mounted = true;

      const drawStatus = (
        width: number,
        height: number,
        message: string,
        detail?: string,
      ) => {
        ctx.fillStyle = BG;
        ctx.fillRect(0, 0, width, height);
        ctx.textAlign = "left";
        ctx.font = FONT_SANS;
        const messageWidth = ctx.measureText(message).width;
        let detailWidth = 0;
        if (detail) {
          ctx.font = FONT_MONO;
          detailWidth = ctx.measureText(detail).width;
        }
        const boxWidth = Math.max(messageWidth, detailWidth) + 24;
        const boxHeight = detail ? 44 : 28;
        const boxX = width / 2 - boxWidth / 2;
        const boxY = height / 2 - boxHeight / 2;
        roundedRect(ctx, boxX, boxY, boxWidth, boxHeight, 4);
        ctx.fillStyle = HUD_BG;
        ctx.fill();
        ctx.strokeStyle = HUD_BORDER;
        ctx.lineWidth = 1;
        ctx.stroke();
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = HUD_MUTED;
        ctx.font = FONT_SANS;
        ctx.fillText(message, width / 2, detail ? height / 2 - 7 : height / 2);
        if (detail) {
          ctx.font = FONT_MONO;
          ctx.fillStyle = "#6a7280";
          ctx.fillText(detail, width / 2, height / 2 + 11);
        }
        ctx.textAlign = "left";
        ctx.textBaseline = "alphabetic";
      };

      const render = (now: number) => {
        if (!mounted) return;
        const view = viewRef.current;
        const state = stateRef.current;
        const scene = sceneRef.current;
        const frames = framesRef.current;
        const cssWidth = canvas.clientWidth;
        const cssHeight = canvas.clientHeight;
        if (cssWidth <= 0 || cssHeight <= 0) return;

        const dpr = Math.min(2, window.devicePixelRatio || 1);
        if (
          view.cssWidth !== cssWidth ||
          view.cssHeight !== cssHeight ||
          view.dpr !== dpr
        ) {
          view.cssWidth = cssWidth;
          view.cssHeight = cssHeight;
          view.dpr = dpr;
          canvas.width = Math.round(cssWidth * dpr);
          canvas.height = Math.round(cssHeight * dpr);
        }
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.fillStyle = BG;
        ctx.fillRect(0, 0, cssWidth, cssHeight);

        const active = activeRef.current;
        const playing = state.playing && !state.diff && state.epochs.length > 1;
        if (!playing) {
          active.lastTick = now;
        } else {
          const interval = 1000 / clamp(state.fps, 1, MAX_FPS);
          if (active.lastTick === 0) active.lastTick = now;
          if (now - active.lastTick >= interval) {
            let next = active.index + active.direction;
            const count = state.epochs.length;
            if (state.pingpong) {
              if (next >= count) {
                active.direction = -1;
                next = Math.max(0, count - 2);
              } else if (next < 0) {
                active.direction = 1;
                next = Math.min(count - 1, 1);
              }
            } else {
              next = ((next % count) + count) % count;
            }
            active.index = next;
            active.lastTick = now - ((now - active.lastTick) % interval);
          }
        }

        let frameInfo: FrameInfo | null = null;
        if (state.diff) {
          if (state.diffUrl) {
            const frame = frames.get(state.diffUrl);
            if (frame) {
              frameInfo = { frame, epoch: null, index: 0, isDiff: true };
            }
          }
        } else if (state.epochs.length > 0) {
          const index = clamp(active.index, 0, state.epochs.length - 1);
          const entry = state.epochs[index];
          const url = entry.frames[state.band];
          const frame = url ? frames.get(url) : undefined;
          if (frame) {
            frameInfo = { frame, epoch: entry, index, isDiff: false };
          }
        }

        if (!frameInfo) {
          const decodeState = decodeRef.current;
          if (decodeState.status === "loading") {
            // The DOM status chip carries the spinner and frame counts.
            setText(epochLineRef.current, "PRE-DECODING IMAGEBITMAP RING");
            setText(
              metaLineRef.current,
              `${decodeState.loaded}/${decodeState.total} frames`,
            );
          } else if (state.diff && !state.diffUrl) {
            drawStatus(
              cssWidth,
              cssHeight,
              "No difference frame for this band.",
            );
            setText(
              epochLineRef.current,
              "DIFFERENCE · no frame for this band",
            );
            setText(metaLineRef.current, scene.provenance.release);
          } else if (decodeState.status === "error") {
            setText(epochLineRef.current, "FRAME UNAVAILABLE");
            setText(metaLineRef.current, "decode error — see status chip");
          } else {
            drawStatus(
              cssWidth,
              cssHeight,
              "This frame is not available.",
              "Check the manifest and retry.",
            );
            setText(epochLineRef.current, "FRAME UNAVAILABLE");
            setText(metaLineRef.current, scene.provenance.release);
          }
          setText(fluxRef.current, "Iν — frame unavailable");
          setText(fluxNoteRef.current, "waiting for the active frame");
          setText(pixelRef.current, "display —/255");
          setText(flagNamesRef.current, "no active frame");
          if (flagNamesRef.current) flagNamesRef.current.title = "";
          return;
        }

        const wcs = scene.wcs;
        const srcW = wcs.width;
        const srcH = wcs.height;
        const padding = clamp(Math.min(cssWidth, cssHeight) * 0.045, 12, 26);
        const side = Math.max(80, Math.min(cssWidth, cssHeight) - padding * 2);
        // Client-side crop of the full 240×240 output grid (AGENTS.md §3.4).
        // Catalog assets are size-independent; `size` only changes the view.
        const maxCrop = Math.max(1, Math.min(srcW, srcH));
        const cropPx = clamp(
          (state.sizeDeg * 3600) / wcs.pixel_scale_arcsec,
          Math.min(8, maxCrop),
          maxCrop,
        );
        const cropX0 = (srcW - cropPx) / 2;
        const cropY0 = (srcH - cropPx) / 2;
        const baseScale = side / cropPx;
        if (cameraRef.current) view.zoom = cameraRef.current.zoom;
        const scale = baseScale * view.zoom;
        const imgW = cropPx * scale;
        const imgH = cropPx * scale;
        if (cameraRef.current) {
          view.panX = cameraRef.current.panX * imgW;
          view.panY = cameraRef.current.panY * imgH;
        }
        const maxPanX = imgW * 0.45;
        const maxPanY = imgH * 0.45;
        view.panX = clamp(view.panX, -maxPanX, maxPanX);
        view.panY = clamp(view.panY, -maxPanY, maxPanY);
        const ox = (cssWidth - imgW) / 2 + view.panX;
        const oy = (cssHeight - imgH) / 2 + view.panY;
        view.baseScale = baseScale;
        view.scale = scale;
        view.ox = ox;
        view.oy = oy;
        view.srcW = srcW;
        view.srcH = srcH;
        view.cropX0 = cropX0;
        view.cropY0 = cropY0;
        view.cropPx = cropPx;
        view.imgW = imgW;
        view.imgH = imgH;
        view.ready = true;

        // Trial-motion co-moving shift: the image (and fixed-sky pins) move by
        // −μ × Δt, locking the trial vector at the crosshair. Display-only.
        const motion = frameInfo.epoch
          ? trialShiftGridPixels(
              wcs,
              frameInfo.epoch.mjd_mean,
              state.trialPmRa,
              state.trialPmDec,
            )
          : { dxPx: 0, dyPx: 0, dtYears: 0 };
        const trial =
          state.track && !state.diff
            ? motion
            : { dxPx: 0, dyPx: 0, dtYears: motion.dtYears };
        const shiftX = -trial.dxPx * scale;
        const shiftY = -trial.dyPx * scale;

        const stretchKey = `${state.band}|${state.diff ? "diff" : "frame"}`;
        let stretchRange = stretchRefs.current.get(stretchKey);
        if (!stretchRange) {
          stretchRange = percentileClip(frameInfo.frame.luma);
          stretchRefs.current.set(stretchKey, stretchRange);
        }

        const signature = [
          frameInfo.frame.url,
          state.colormap,
          state.stretch,
          state.contrast.toFixed(2),
          state.bias.toFixed(2),
          state.diff ? "diff" : "frame",
          stretchRange.lo.toFixed(4),
          stretchRange.hi.toFixed(4),
        ].join("|");

        if (signature !== cacheRef.current.signature || !offscreenRef.current) {
          if (!offscreenRef.current) {
            offscreenRef.current = document.createElement("canvas");
          }
          buildDisplayCanvas(
            offscreenRef.current,
            frameInfo.frame,
            state,
            stretchRange,
          );
          cacheRef.current.signature = signature;
        }

        const offscreen = offscreenRef.current;
        if (offscreen) {
          // Expand the source rect by the shift so a co-moving frame does not
          // expose a blank strip at the crop edge. The 240×240 grid has a few
          // pixels of margin at the default 0.2° crop.
          const extra =
            Math.ceil(
              Math.max(Math.abs(shiftX), Math.abs(shiftY)) /
                Math.max(scale, 1e-6),
            ) + 1;
          const ex = Math.min(extra, 6);
          const sx0 = Math.max(0, cropX0 - ex);
          const sy0 = Math.max(0, cropY0 - ex);
          const sx1 = Math.min(srcW, cropX0 + cropPx + ex);
          const sy1 = Math.min(srcH, cropY0 + cropPx + ex);
          const destX = ox + (sx0 - cropX0) * scale + shiftX;
          const destY = oy + (sy0 - cropY0) * scale + shiftY;
          const destW = (sx1 - sx0) * scale;
          const destH = (sy1 - sy0) * scale;

          ctx.save();
          ctx.beginPath();
          ctx.rect(ox, oy, imgW, imgH);
          ctx.clip();
          ctx.imageSmoothingEnabled = false;
          ctx.drawImage(
            offscreen,
            sx0,
            sy0,
            sx1 - sx0,
            sy1 - sy0,
            destX,
            destY,
            destW,
            destH,
          );

          // Flag overlay (union of warning bits, per epoch; never in diff mode).
          if (
            !state.diff &&
            state.overlays.has("flags") &&
            frameInfo.epoch?.frames.flag_overlay
          ) {
            const flagFrame = frames.get(frameInfo.epoch.frames.flag_overlay);
            if (flagFrame) {
              let overlay = flagOverlaysRef.current.get(flagFrame.url);
              if (!overlay) {
                overlay = buildFlagOverlay(flagFrame);
                flagOverlaysRef.current.set(flagFrame.url, overlay);
              }
              const fx = flagFrame.width / srcW;
              const fy = flagFrame.height / srcH;
              ctx.imageSmoothingEnabled = false;
              ctx.drawImage(
                overlay,
                sx0 * fx,
                sy0 * fy,
                (sx1 - sx0) * fx,
                (sy1 - sy0) * fy,
                destX,
                destY,
                destW,
                destH,
              );
            }
          }
          ctx.restore();
        }

        ctx.strokeStyle = "rgba(255, 255, 255, 0.14)";
        ctx.lineWidth = 1;
        ctx.strokeRect(ox - 0.5, oy - 0.5, imgW + 1, imgH + 1);

        const geometry: Geometry = {
          cssWidth,
          cssHeight,
          scale,
          ox,
          oy,
          srcW,
          srcH,
          cropX0,
          cropY0,
          cropPx,
          imgW,
          imgH,
          shiftX,
          shiftY,
        };

        if (state.overlays.has("gaia")) {
          drawGaiaPins(
            ctx,
            gaiaRef.current.sources,
            scene,
            geometry,
            shiftX,
            shiftY,
          );
        }
        if (state.overlays.has("reticle")) {
          drawReticle(ctx, scene, geometry, state.track && !state.diff);
        }
        if (state.overlays.has("box")) drawPixelBox(ctx, scene, geometry);
        if (state.overlays.has("scale")) drawScaleBar(ctx, scene, geometry);
        if (state.overlays.has("compass")) drawCompass(ctx, scene, geometry);
        if (state.parallax && !state.diff) {
          drawParallax(ctx, scene, geometry, state.parallaxAu);
        }

        const highlightEpoch = state.lvfHighlight
          ? (scene.epochs.find(
              (entry) =>
                entry.epoch_id === state.lvfHighlight?.epochId &&
                (entry.lvf_geometry?.length ?? 0) > 0,
            ) ?? null)
          : null;
        const lvfEpoch =
          highlightEpoch ??
          (frameInfo.epoch?.lvf_geometry &&
          frameInfo.epoch.lvf_geometry.length > 0
            ? frameInfo.epoch
            : null);
        const lvfGeometries = lvfEpoch?.lvf_geometry ?? null;
        const lvfOverlayOn = state.overlays.has("lvf");
        if (
          !state.diff &&
          (lvfOverlayOn || state.lvfHighlight !== null) &&
          lvfGeometries &&
          lvfGeometries.length > 0
        ) {
          drawLvfOverlay(
            ctx,
            scene,
            geometry,
            lvfGeometries,
            state.lvfHighlight,
            lvfOverlayOn,
          );
        }

        const hover = hoverRef.current;
        if (hover.inside) drawCrosshair(ctx, hover, geometry);

        // --- HUD text: written imperatively, never through React state.
        if (frameInfo.isDiff && state.diffKey) {
          setText(
            epochLineRef.current,
            `DIFFERENCE · ${state.diffKey.replace("_minus_", " − ")}`,
          );
          setText(metaLineRef.current, "SIGNED RESIDUAL · BLUE − / WARM +");
        } else if (frameInfo.epoch) {
          setText(
            epochLineRef.current,
            `EPOCH ${frameInfo.index + 1}/${state.epochs.length} · ${frameInfo.epoch.epoch_id}`,
          );
          setText(
            metaLineRef.current,
            `${observationDateLabel(frameInfo.epoch)} · ${frameInfo.epoch.release} · ${
              state.playing ? `${state.fps} FPS` : "PAUSED"
            }`,
          );
        }

        // --- Trial-motion / parallax / LVF HUD (imperative, no setState/tick).
        canvas.dataset.track = state.track ? "1" : "0";
        canvas.dataset.trackShift = `${(-trial.dxPx).toFixed(2)},${(-trial.dyPx).toFixed(2)}`;
        canvas.dataset.trackDt = trial.dtYears.toFixed(3);
        if (state.track) {
          setText(
            trackLineRef.current,
            state.diff
              ? "TRACK — difference frames are fixed-frame"
              : `TRACK μ ${formatSigned(state.trialPmRa, 0)}, ${formatSigned(
                  state.trialPmDec,
                  0,
                )} mas/yr · Δt ${formatSigned(trial.dtYears, 3)} yr · image shift ${formatSigned(
                  -trial.dxPx,
                  2,
                )}, ${formatSigned(-trial.dyPx, 2)} px`,
          );
        } else {
          setText(trackLineRef.current, "SKY-FIXED ICRS · no trial shift");
        }

        if (state.parallax) {
          const semiArcsec = parallaxSemiAmplitudeArcsec(state.parallaxAu);
          const peakArcsec = parallaxPeakToPeakArcsec(state.parallaxAu);
          const semiScreen = parallaxGridPixels(wcs, state.parallaxAu) * scale;
          const insetFactor = 26 / Math.max(0.01, semiScreen);
          setText(
            parallaxLineRef.current,
            semiScreen >= 8
              ? `PARALLAX ϖ ${semiArcsec.toFixed(2)}″ · 2ϖ ${peakArcsec.toFixed(2)}″ · true scale`
              : `PARALLAX INSET ×${Math.round(insetFactor)} · ϖ ${semiArcsec.toFixed(
                  3,
                )}″ · 2ϖ ${peakArcsec.toFixed(3)}″ (${parallaxPeakToPeakGridPixels(
                  wcs,
                  state.parallaxAu,
                ).toFixed(2)} grid px) · schematic`,
          );
        } else {
          setText(parallaxLineRef.current, "");
        }

        if (state.overlays.has("lvf")) {
          if (!lvfGeometries || lvfGeometries.length === 0) {
            setText(
              lvfLineRef.current,
              "LVF — geometry not provided for this epoch",
            );
          } else if (state.lvfHighlight) {
            const geometryHit = findLvfGeometry(
              scene.epochs,
              state.lvfHighlight.epochId,
              state.lvfHighlight.detector,
            );
            setText(
              lvfLineRef.current,
              geometryHit
                ? `LVF D${geometryHit.detector} · PA ${geometryHit.pa_deg.toFixed(
                    0,
                  )}° · ${geometryHit.grad_um_per_arcsec.toFixed(3)} µm/″ · λ ${state.lvfHighlight.wavelengthUm.toFixed(2)} µm`
                : `LVF D${state.lvfHighlight.detector} · λ ${state.lvfHighlight.wavelengthUm.toFixed(2)} µm · geometry missing`,
            );
          } else {
            setText(
              lvfLineRef.current,
              `LVF D1–D6 · schematic PA/gradient · ${lvfGeometries.length} detectors · hover a spectrum point`,
            );
          }
        }

        // Optional epoch tick (user-enabled; reduced motion disables it).
        if (
          !state.diff &&
          frameInfo.epoch &&
          active.index !== active.lastTickedIndex
        ) {
          const candidate =
            frameInfo.epoch.candidates?.find(
              (entry) => entry.is_artifact_clean,
            ) ??
            frameInfo.epoch.candidates?.[0] ??
            null;
          const pan = candidate
            ? clamp((candidate.x_px - srcW / 2) / 3, -1, 1)
            : clamp(-motion.dxPx / 3, -1, 1);
          spectrumAudio.maybeTick(frameInfo.epoch.epoch_id, pan);
          active.lastTickedIndex = active.index;
        }

        const centerWorld = pixelToWorld(wcs, srcW / 2, srcH / 2);
        let readout = centerWorld;
        let displayValue: number | null = null;

        const telemetryAsset = frameInfo.epoch?.telemetry ?? null;
        let telemetryEntry: TelemetryEntry | null = null;
        if (!state.diff && telemetryAsset) {
          // Lazy per active epoch: the rAF loop polls the mutable cache, so no
          // React state update happens on a blink tick.
          telemetryEntry = telemetryStore.ensure(telemetryAsset);
        }
        const telemetryMeaning = telemetryAsset
          ? telemetryDescription(telemetryAsset, state.band)
          : null;
        const intensityLabel = telemetryMeaning?.label ?? "Display intensity";

        let fluxText: string;
        let fluxNote: string;
        let flagText: string;
        let flagTitle = "";

        if (state.diff) {
          fluxText = "Display intensity — difference frame";
          fluxNote = "no telemetry sidecar for signed residuals";
          flagText = "no Table 16 flag plane in difference";
        } else if (!telemetryAsset) {
          fluxText = "Display intensity — no telemetry sidecar";
          fluxNote = "this epoch has display frames only";
          flagText = state.overlays.has("flags")
            ? "flag overlay on · names need a sidecar"
            : "flag overlay off";
        } else if (telemetryEntry?.status === "loading") {
          fluxText = `${intensityLabel} loading…`;
          fluxNote =
            telemetryMeaning?.detail ?? "Telemetry metadata unavailable";
          flagText = "decoding Table 16 flags…";
        } else if (telemetryEntry?.status === "error") {
          fluxText = `${intensityLabel} unavailable`;
          fluxNote = telemetryEntry.error;
          flagText = "telemetry decode unavailable";
        } else {
          fluxText = `${intensityLabel}: hover to sample`;
          fluxNote =
            telemetryMeaning?.detail ?? "Telemetry metadata unavailable";
          flagText = "hover to decode Table 16 flags";
        }

        if (hover.inside) {
          const xSrc = cropX0 + (hover.x - ox - shiftX) / scale;
          const ySrc = cropY0 + (hover.y - oy - shiftY) / scale;
          if (insideCrop(geometry, xSrc, ySrc)) {
            readout = pixelToWorld(wcs, xSrc, ySrc);
            displayValue = lumaAt(frameInfo.frame, xSrc, ySrc);
            if (telemetryAsset && telemetryEntry?.status === "ready") {
              const sample = sampleTelemetry(
                telemetryEntry.data,
                xSrc,
                ySrc,
                srcW,
                srcH,
              );
              if (sample) {
                fluxText = `${intensityLabel}: ${formatMjy(sample.fluxMjySr)} MJy/sr`;
                fluxNote =
                  telemetryMeaning?.detail ?? "Telemetry metadata unavailable";
                const names = formatFlagNames(sample.flags, 6);
                flagText = `${formatFlagHex(sample.flags)} · ${names.text}`;
                flagTitle = names.full;
                if (!Number.isFinite(sample.fluxMjySr)) {
                  fluxText = "Display intensity unavailable";
                  fluxNote =
                    "Flags may be incomplete at masked pixels. " + fluxNote;
                  flagText =
                    sample.flags === 0
                      ? `${formatFlagHex(sample.flags)} · no flags recorded; completeness unknown`
                      : flagText;
                  flagTitle =
                    "Flags may be incomplete at masked pixels. " + flagTitle;
                }
              } else {
                fluxText = `${intensityLabel} unavailable`;
                fluxNote = "sidecar grid does not match the manifest WCS";
                flagText = "Table 16 grid mismatch";
              }
            } else if (
              !state.diff &&
              state.overlays.has("flags") &&
              frameInfo.epoch?.frames.flag_overlay &&
              telemetryEntry?.status !== "ready"
            ) {
              // Fallback while the display-intensity sidecar is absent or loading:
              // the overlay still tells you whether a warning bit is present.
              const flagFrame = frames.get(frameInfo.epoch.frames.flag_overlay);
              if (flagFrame) {
                const strength = flagStrengthAt(flagFrame, xSrc, ySrc);
                flagText =
                  strength > 12
                    ? "warning flag pixel · names need telemetry"
                    : "no warning flag · names need telemetry";
              }
            }
          }
        }
        setText(raRef.current, `RA  ${formatRa(readout.ra)}`);
        setText(decRef.current, `DEC ${formatDec(readout.dec)}`);
        setText(fluxRef.current, fluxText);
        setText(fluxNoteRef.current, fluxNote);
        setText(pixelRef.current, `display ${displayValue ?? "—"}/255`);
        setText(flagNamesRef.current, flagText);
        if (flagNamesRef.current) flagNamesRef.current.title = flagTitle;

        const status = frameInfo.epoch?.flag_summary.status ?? "NOMINAL";
        const statusEl = flagStatusRef.current;
        if (statusEl) {
          setText(statusEl, frameInfo.isDiff ? "DIFFERENCE" : status);
          const nextStatus = frameInfo.isDiff ? "DIFF" : status;
          if (statusEl.dataset.status !== nextStatus) {
            statusEl.dataset.status = nextStatus;
          }
        }
      };

      const loop = (now: number) => {
        if (!mounted) return;
        render(now);
        raf = window.requestAnimationFrame(loop);
      };
      raf = window.requestAnimationFrame(loop);

      return () => {
        mounted = false;
        window.cancelAnimationFrame(raf);
        ctxRef.current = null;
      };
    }, []);

    const bandInfo = bandMeta(band);
    const gaiaEnabled = overlays.includes("gaia");
    const gaiaCount = gaia.sources.length;

    return (
      <div className="canvas-shell">
        <canvas
          ref={canvasRef}
          className="blink-canvas"
          tabIndex={0}
          role="img"
          aria-label={`Blink viewport for ${manifest.target?.name ?? "the query field"}. ${epochsForBand.length} epoch${
            epochsForBand.length === 1 ? "" : "s"
          } available; hover reads coordinates, display intensity and Table 16 flags when a telemetry sidecar exists. The named telemetry plane may differ from the image band; normalization metadata may be unknown. Mouse drag pans; Control plus wheel zooms. Touch scrolls the page. Use external zoom/reset controls and Search for keyboard coordinate entry. ${
            track
              ? "Trial-motion co-moving display is on; this is not a detection."
              : ""
          } ${parallax ? "Parallax reflex overlay is on." : ""}`}
          onKeyDown={(event) => {
            if (
              event.metaKey ||
              event.ctrlKey ||
              event.altKey ||
              !event.shiftKey ||
              !["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(
                event.key,
              )
            )
              return;
            event.preventDefault();
            event.stopPropagation();
            const c = cameraRef.current ?? { zoom: 1, panX: 0, panY: 0 };
            cameraChangeRef.current?.({
              ...c,
              panX: clamp(
                c.panX +
                  (event.key === "ArrowLeft"
                    ? -0.05
                    : event.key === "ArrowRight"
                      ? 0.05
                      : 0),
                -2,
                2,
              ),
              panY: clamp(
                c.panY +
                  (event.key === "ArrowUp"
                    ? -0.05
                    : event.key === "ArrowDown"
                      ? 0.05
                      : 0),
                -2,
                2,
              ),
            });
          }}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
          onPointerLeave={onPointerLeave}
          onDoubleClick={() => resetView()}
        />

        <div className="hud hud--tl">
          <div className={diff ? "hud-chip hud-chip--warn" : "hud-chip"}>
            <span className="hud-name">
              {manifest.target?.name ?? "Sky field"}
            </span>
            <span className="hud-line" ref={epochLineRef}>
              EPOCH —
            </span>
            <span className="hud-dim" ref={metaLineRef}>
              initialising ImageBitmap ring
            </span>
          </div>
          {track || parallax ? (
            <div
              className="hud-chip hud-chip--track"
              data-track={track ? "1" : "0"}
              data-parallax={parallax ? "1" : "0"}
            >
              {track ? (
                <span className="hud-warn-line">
                  TRIAL-MOTION VISUALIZATION — NOT A DETECTION
                </span>
              ) : null}
              <span ref={trackLineRef} className="hud-line">
                SKY-FIXED ICRS
              </span>
            </div>
          ) : null}
        </div>

        <div className="hud hud--tr">
          <div className="hud-chip hud-chip--row">
            <span className="hud-line">
              {bandInfo.short} · {bandInfo.wavelength}
            </span>
          </div>
          {overlays.includes("lvf") ? (
            <div className="hud-chip hud-chip--lvf" data-lvf="1">
              <span ref={lvfLineRef} className="hud-line">
                LVF geometry
              </span>
            </div>
          ) : null}
          {gaiaEnabled && gaia.status === "ready" ? (
            <div className="hud-chip hud-chip--row" data-gaia-count={gaiaCount}>
              <span className="hud-line">GAIA G≤16 · {gaiaCount}</span>
              <span className="hud-dim">
                DR3 · PM dir · {GAIA_PM_VECTOR_YEARS} yr
              </span>
            </div>
          ) : null}
          {gaiaEnabled && gaia.status === "loading" ? (
            <div className="hud-chip hud-chip--row">
              <span className="hud-dim">GAIA catalog loading…</span>
            </div>
          ) : null}
          {gaiaEnabled && gaia.status === "error" ? (
            <div className="hud-chip hud-warn">GAIA CATALOG UNAVAILABLE</div>
          ) : null}
        </div>

        <div className="hud hud--br">
          <div className="hud-chip">
            <span ref={raRef}>RA —</span>
            <span ref={decRef}>DEC —</span>
          </div>
          <div className="hud-chip hud-chip--row hud-chip--loupe">
            <span ref={fluxRef}>Display intensity — MJy/sr</span>
            <span className="hud-sep">·</span>
            <span className="hud-dim" ref={pixelRef}>
              display —/255
            </span>
          </div>
          {parallax ? (
            <div className="hud-chip hud-chip--parallax" data-parallax="1">
              <span ref={parallaxLineRef} className="hud-line">
                PARALLAX
              </span>
            </div>
          ) : null}
          <div className="hud-chip hud-chip--row hud-chip--flags">
            <span className="hud-dim">FLAGS</span>
            <span className="hud-flag-names" ref={flagNamesRef}>
              Table 16 — no telemetry
            </span>
            <span
              className="hud-status"
              data-status="NOMINAL"
              ref={flagStatusRef}
            >
              NOMINAL
            </span>
          </div>
          <div className="hud-chip hud-chip--row hud-chip--secondary hud-chip--telemetry-meaning">
            <span className="hud-dim" ref={fluxNoteRef}>
              display-intensity telemetry loads only for the active epoch
            </span>
          </div>
        </div>

        {decode.status === "loading" ? (
          <div className="canvas-status" role="status" aria-live="polite">
            <span className="spinner" aria-hidden="true" />
            <span>
              Pre-decoding frames {decode.loaded}/{decode.total} — ImageBitmap
              ring
            </span>
          </div>
        ) : null}
        {decode.status === "error" ? (
          <div className="canvas-status canvas-status--error" role="alert">
            <span>
              {decode.errors.length} frame
              {decode.errors.length === 1 ? "" : "s"} failed to decode. Loaded
              images remain available. Missing images are not absent sky flux.
            </span>
            <button
              className="btn"
              onClick={() => setDecodeAttempt((attempt) => attempt + 1)}
            >
              Retry image assets
            </button>
            <details>
              <summary>Asset error details</summary>
              <p>{decode.errors[0]}</p>
            </details>
          </div>
        ) : null}
      </div>
    );
  },
);
