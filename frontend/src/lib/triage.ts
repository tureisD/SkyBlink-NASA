/**
 * Dynamic-channel triage card export (F6).
 *
 * Produces a 4-panel PNG (Epoch A, Epoch B, difference, spectrum) plus a
 * Markdown report. Everything is derived from the loaded manifest, spectrum
 * response, and Gaia catalog; missing data is written as "not available" and
 * never substituted with an invented cross-match or metric.
 *
 * The spectrum panel/report always states the true channel count, e.g.
 * "24-channel SPHEREx spectrum" — never a fixed "102-band" claim.
 */

import type { GaiaCatalogState } from "../hooks/useGaiaSources";
import { BANDS } from "./types";
import type {
  Epoch,
  SkyResponse,
  SpectrumChannel,
  SpectrumResponse,
} from "./types";
import { angularSeparationArcsec, formatDec, formatRa } from "./wcs";
import { channelStats, coordinateEpochLabel, observationDateLabel, telemetryDescription, spectrumDomain } from "./semantics";
import { resolveAssetUrl } from "./api";
import { analysisIdentityNotice } from "./share";

export interface TriageSelection {
  band: string;
  epochs: Epoch[];
  diffKey: string | null;
  diffUrl: string | null;
}

export interface TriageCardInput extends TriageSelection {
  manifest: SkyResponse;
  spectrum: SpectrumResponse | null;
  /** Full response order before selecting A/B, including empty epochs. */
  spectrumEpochOrder?: readonly string[];
  gaia: GaiaCatalogState;
  shareUrl: string;
}

export interface TriageCardResult {
  pngBlob: Blob;
  pngUrl: string;
  markdown: string;
  filenameBase: string;
  channelCount: number;
}

const WIDTH = 1600;
const HEIGHT = 1180;
const PANEL_W = 760;
const PANEL_H = 470;
const PANEL_A = { x: 24, y: 104 };
const PANEL_B = { x: 816, y: 104 };
const PANEL_C = { x: 24, y: 606 };
const PANEL_D = { x: 816, y: 606 };

const COLORS = {
  bg: "#08090b",
  panel: "#0e1015",
  panelInset: "#0a0c0f",
  hairline: "rgba(255, 255, 255, 0.10)",
  hairlineSoft: "rgba(255, 255, 255, 0.06)",
  text: "#e6e8ec",
  bright: "#f4f6f8",
  muted: "#9aa1ac",
  dim: "#7b8390",
  accent: "#38bdf8",
  amber: "#fbbf24",
  red: "#f87171",
  nominal: "#34d399",
  mono: 'ui-monospace, "SF Mono", Menlo, Consolas, monospace',
  sans: '-apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, sans-serif',
};

const EPOCH_COLORS = ["#b8dacc", "#eac995", "#a4c6ee", "#d2b5e2", "#e6aaa3"];
/** Canvas requires a resolved color rather than an unresolved CSS variable. */
function epochColor(index: number): string {
  const fallback = EPOCH_COLORS[index % EPOCH_COLORS.length];
  if (typeof document === "undefined") return fallback;
  const resolved = getComputedStyle(document.documentElement).getPropertyValue(`--chart-series-${index % EPOCH_COLORS.length + 1}`).trim();
  return /^(#[0-9a-f]{3,8}|rgba?\([^)]*\)|hsla?\([^)]*\))$/i.test(resolved) ? resolved : fallback;
}

/** Preserve plotted epoch colors when the report selects a subset of observations. */
export function spectrumEpochColorIndex(epochId: string, fallbackIndex: number, order?: readonly string[]): number {
  const original = order?.indexOf(epochId) ?? -1;
  return original >= 0 ? original : fallbackIndex;
}

/** Full-set epoch IDs belong to a discovery inventory, not a global time axis. */
export function selectSpectrumForReport(
  manifest: SkyResponse,
  spectrum: SpectrumResponse | null,
  selectedIds: ReadonlySet<string>,
): SpectrumResponse | null {
  if (!spectrum) return null;
  if (
    (manifest.provenance.discovery_mode ?? "live") !==
    (spectrum.provenance.discovery_mode ?? "live")
  ) return spectrum;
  return {
    ...spectrum,
    epochs: spectrum.epochs.filter(epoch => selectedIds.has(epoch.epoch_id)),
  };
}

function formatArcsec(value: number): string {
  if (!Number.isFinite(value)) return "—";
  if (Math.abs(value) >= 100) return `${value.toFixed(0)}″`;
  if (Math.abs(value) >= 10) return `${value.toFixed(1)}″`;
  return `${value.toFixed(2)}″`;
}

function activeFlagText(epoch: Epoch): string {
  const flags = epoch.flag_summary.active_warning_flags;
  return flags.length > 0 ? flags.join(", ") : "none";
}

function candidateText(epoch: Epoch): string {
  const candidates = epoch.candidates ?? [];
  if (candidates.length === 0) return "none in manifest";
  const first = candidates[0];
  const extra = candidates.length > 1 ? ` +${candidates.length - 1}` : "";
  const flux =
    first.delta_flux_mjy_sr === null
      ? "Δflux —"
      : `Δflux ${first.delta_flux_mjy_sr.toFixed(3)} MJy/sr`;
  return `${first.kind} · SNR ${first.snr.toFixed(1)} · ${flux}${extra}`;
}

function nearestGaia(
  manifest: SkyResponse,
  gaia: GaiaCatalogState,
): { available: boolean; text: string } {
  if (!manifest.reference_overlays.gaia_sources_url) {
    return { available: false, text: "not available (no gaia_sources_url in this manifest)" };
  }
  if (gaia.status === "loading") {
    return { available: true, text: "catalog configured but still loading" };
  }
  if (gaia.status === "error") {
    return { available: true, text: "catalog configured but could not be loaded" };
  }
  if (gaia.sources.length === 0) {
    return { available: true, text: "catalog loaded; no G≤16 sources returned" };
  }
  const center = { ra: manifest.query.ra, dec: manifest.query.dec };
  let best = gaia.sources[0];
  let bestSep = angularSeparationArcsec(center, { ra: best.ra, dec: best.dec });
  for (const source of gaia.sources.slice(1)) {
    const separation = angularSeparationArcsec(center, {
      ra: source.ra,
      dec: source.dec,
    });
    if (separation < bestSep) {
      best = source;
      bestSep = separation;
    }
  }
  const catalogKind = "Gaia DR3 G≤16 · ";
  const aperture =
    bestSep <= 12.3
      ? "inside the 12.3″ target aperture"
      : `nearest is ${formatArcsec(bestSep)} from the query centre`;
  return {
    available: true,
    text: `${catalogKind}${best.source_id} at ${formatArcsec(bestSep)} (G ${best.g_mag.toFixed(1)}); ${aperture}. Display reference only, not a detection.`,
  };
}

function wiseText(manifest: SkyResponse): string {
  const hasWise = Boolean(
    manifest.reference_overlays.mid_ir_wise_w1 ??
      manifest.reference_overlays.mid_ir_wise,
  );
  return hasWise
    ? "WISE W1 reference image present (display reference); no catalog cross-match data in this manifest."
    : "not available (no WISE reference image in this manifest).";
}

/**
 * Preserve the workspace's band and ordered A/B selection. A missing band,
 * observation or difference never causes a substitute to be exported.
 */
export function selectTriageEpochs(
  manifest: SkyResponse,
  preferredBand: string,
  preferredDiffKey: string | null,
  epochA: string | null = null,
  epochB: string | null = null,
): TriageSelection {
  if (preferredDiffKey) {
    const [later, earlier] = preferredDiffKey.split("_minus_");
    if (!later || !earlier || (epochA && epochA !== earlier) || (epochB && epochB !== later)) {
      throw new Error("The selected difference does not match workspace observations B minus A.");
    }
    epochA = earlier;
    epochB = later;
  }
  if (!epochA) epochA = manifest.epochs.find(epoch => typeof epoch.frames[preferredBand] === "string")?.epoch_id ?? null;
  const ids = [epochA, epochB].filter((id): id is string => Boolean(id));
  if (epochA && epochA === epochB) throw new Error("Choose distinct observations A and B before exporting a comparison.");
  const chosenEpochs = ids.map(id => {
    const epoch = manifest.epochs.find(value => value.epoch_id === id);
    if (!epoch) throw new Error(`Selected observation ${id} is unavailable; the report cannot substitute another observation.`);
    return epoch;
  });
  const candidateKey = epochA && epochB ? `${epochB}_minus_${epochA}` : null;
  const hasBothFrames = chosenEpochs.length === 2 && chosenEpochs.every(epoch => typeof epoch.frames[preferredBand] === "string");
  const diffUrl = candidateKey && hasBothFrames ? manifest.differences[candidateKey]?.[preferredBand] ?? null : null;
  return { band: preferredBand, epochs: chosenEpochs, diffKey: diffUrl ? candidateKey : null, diffUrl };
}

async function loadBitmap(url: string | null): Promise<ImageBitmap | null> {
  if (!url) return null;
  try {
    const response = await fetch(url);
    if (!response.ok) return null;
    const blob = await response.blob();
    return await createImageBitmap(blob);
  } catch {
    return null;
  }
}

function drawPanelShell(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  title: string,
  subtitle: string,
): void {
  ctx.fillStyle = COLORS.panel;
  ctx.fillRect(x, y, PANEL_W, PANEL_H);
  ctx.strokeStyle = COLORS.hairline;
  ctx.lineWidth = 1;
  ctx.strokeRect(x + 0.5, y + 0.5, PANEL_W - 1, PANEL_H - 1);
  ctx.fillStyle = COLORS.bright;
  ctx.font = `600 12px ${COLORS.mono}`;
  ctx.fillText(title.toUpperCase(), x + 12, y + 20);
  ctx.fillStyle = COLORS.dim;
  ctx.font = `10px ${COLORS.mono}`;
  ctx.fillText(subtitle, x + 12, y + 34);
}

function drawImageFit(
  ctx: CanvasRenderingContext2D,
  bitmap: ImageBitmap | null,
  x: number,
  y: number,
  width: number,
  height: number,
): void {
  ctx.fillStyle = COLORS.panelInset;
  ctx.fillRect(x, y, width, height);
  ctx.strokeStyle = COLORS.hairlineSoft;
  ctx.strokeRect(x + 0.5, y + 0.5, width - 1, height - 1);
  if (!bitmap) {
    ctx.fillStyle = COLORS.muted;
    ctx.font = `11px ${COLORS.mono}`;
    ctx.textAlign = "center";
    ctx.fillText("frame not available", x + width / 2, y + height / 2);
    ctx.textAlign = "left";
    return;
  }
  const scale = Math.min(width / bitmap.width, height / bitmap.height);
  const drawnW = bitmap.width * scale;
  const drawnH = bitmap.height * scale;
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(
    bitmap,
    x + (width - drawnW) / 2,
    y + (height - drawnH) / 2,
    drawnW,
    drawnH,
  );
}

function drawMetaLines(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  lines: Array<[string, string]>,
): void {
  let cursor = y;
  for (const [label, value] of lines) {
    ctx.fillStyle = COLORS.dim;
    ctx.font = `9px ${COLORS.mono}`;
    ctx.fillText(label.toUpperCase(), x, cursor);
    ctx.fillStyle = COLORS.text;
    ctx.font = `10px ${COLORS.mono}`;
    const wrapped = value.length > 38 ? `${value.slice(0, 37)}…` : value;
    ctx.fillText(wrapped, x, cursor + 12);
    cursor += 31;
    if (cursor > y + 390) break;
  }
  ctx.strokeStyle = COLORS.hairlineSoft;
  ctx.beginPath();
  ctx.moveTo(x - 8, y - 12);
  ctx.lineTo(x - 8, y + 380);
  ctx.stroke();
}

function drawImagePanel(
  ctx: CanvasRenderingContext2D,
  origin: { x: number; y: number },
  title: string,
  subtitle: string,
  bitmap: ImageBitmap | null,
  lines: Array<[string, string]>,
): void {
  drawPanelShell(ctx, origin.x, origin.y, title, subtitle);
  const imageSize = PANEL_H - 48;
  drawImageFit(
    ctx,
    bitmap,
    origin.x + 12,
    origin.y + 42,
    imageSize,
    imageSize,
  );
  const metaX = origin.x + 12 + imageSize + 18;
  drawMetaLines(ctx, metaX, origin.y + 64, lines);
}

function spectrumChannels(spectrum: SpectrumResponse | null, epochOrder?: readonly string[]): Array<{
  channel: SpectrumChannel;
  epochId: string;
  color: string;
}> {
  if (!spectrum) return [];
  const rows: Array<{
    channel: SpectrumChannel;
    epochId: string;
    color: string;
  }> = [];
  spectrum.epochs.forEach((epoch, index) => {
    const color = epochColor(spectrumEpochColorIndex(epoch.epoch_id, index, epochOrder));
    for (const channel of epoch.channels) {
      rows.push({ channel, epochId: epoch.epoch_id, color });
    }
  });
  return rows;
}

function drawSpectrumPanel(
  ctx: CanvasRenderingContext2D,
  origin: { x: number; y: number },
  spectrum: SpectrumResponse | null,
  epochOrder?: readonly string[],
): void {
  const stats = channelStats(spectrum);
  const title = spectrum
    ? `${stats.total}-channel SPHEREx spectrum`
    : "SPHEREx spectrum — not available";
  const discoveryLabel = spectrum?.provenance.discovery_mode === "known"
    ? "Known exposures / fresh downloads"
    : spectrum?.provenance.discovery_mode === "indexed"
      ? "Indexed archive / fresh downloads (limited coverage)"
    : spectrum?.provenance.data_access === "saved"
      ? "Saved spectrum"
      : spectrum?.provenance.discovery_mode === "live"
        ? "Live archive search"
        : "Discovery mode unrecorded";
  const subtitle = spectrum
    ? `${discoveryLabel} · ${spectrum.epochs.length} epoch${spectrum.epochs.length === 1 ? "" : "s"} · native flux µJy`
    : "Spectrum unavailable for this report; no samples invented";
  drawPanelShell(ctx, origin.x, origin.y, title, subtitle);
  const plot = {
    x: origin.x + 58,
    y: origin.y + 82,
    width: PANEL_W - 80,
    height: PANEL_H - 154,
  };

  if (!spectrum) {
    ctx.fillStyle = COLORS.muted;
    ctx.font = `11px ${COLORS.mono}`;
    ctx.fillText("No spectrum response — report says not available.", plot.x, plot.y + 30);
    return;
  }

  const rows = spectrumChannels(spectrum, epochOrder);
  if (stats.finite === 0) {
    ctx.fillStyle = COLORS.amber;
    ctx.font = `14px ${COLORS.sans}`;
    ctx.fillText("No usable flux measurements", plot.x, plot.y + 30);
    ctx.fillStyle = COLORS.muted;
    ctx.font = `11px ${COLORS.mono}`;
    ctx.fillText(`${stats.total} recorded samples; all flux values unavailable.`, plot.x, plot.y + 54);
    ctx.fillText("Observation and exclusion metadata remain in the report.", plot.x, plot.y + 76);
    return;
  }
  const xMin = 0.7;
  const xMax = 5.1;
  const [yMin, yMax] = spectrumDomain(rows.map(row => row.channel));
  const xScale = (value: number) =>
    plot.x + ((value - xMin) / (xMax - xMin)) * plot.width;
  const yScale = (value: number) =>
    plot.y + plot.height - ((value - yMin) / (yMax - yMin)) * plot.height;

  // Detector band zones.
  for (const band of BANDS) {
    const x1 = xScale(Math.max(xMin, band.minUm));
    const x2 = xScale(Math.min(xMax, band.maxUm));
    ctx.fillStyle = band.color;
    ctx.globalAlpha = 0.06;
    ctx.fillRect(x1, plot.y, Math.max(0, x2 - x1), plot.height);
    ctx.globalAlpha = 1;
    ctx.fillStyle = band.color;
    ctx.font = `9px ${COLORS.mono}`;
    ctx.fillText(band.short, (x1 + x2) / 2 - 6, plot.y - 7);
  }

  // Grid.
  ctx.strokeStyle = COLORS.hairlineSoft;
  ctx.fillStyle = COLORS.dim;
  ctx.font = `9px ${COLORS.mono}`;
  for (let index = 0; index <= 5; index += 1) {
    const tick = yMin + ((yMax - yMin) * index) / 5;
    const y = yScale(tick);
    ctx.beginPath();
    ctx.moveTo(plot.x, y);
    ctx.lineTo(plot.x + plot.width, y);
    ctx.stroke();
    ctx.fillText(
      tick >= 100 ? tick.toFixed(0) : tick.toFixed(1),
      plot.x - 42,
      y + 3,
    );
  }
  for (const tick of [1, 2, 3, 4, 5]) {
    const x = xScale(tick);
    ctx.beginPath();
    ctx.moveTo(x, plot.y);
    ctx.lineTo(x, plot.y + plot.height);
    ctx.stroke();
    ctx.fillText(`${tick.toFixed(0)}`, x - 3, plot.y + plot.height + 16);
  }

  // Channels.
  for (const { channel, color } of rows) {
    if (channel.flux_ujy === null || !Number.isFinite(channel.flux_ujy)) {
      continue;
    }
    const x = xScale(channel.wavelength_um);
    const y = yScale(channel.flux_ujy);
    if (channel.is_flagged_bad) {
      ctx.strokeStyle = COLORS.red;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(x - 4, y - 4);
      ctx.lineTo(x + 4, y + 4);
      ctx.moveTo(x + 4, y - 4);
      ctx.lineTo(x - 4, y + 4);
      ctx.stroke();
      continue;
    }
    const lowClean = !channel.is_used_in_photometry;
    const error = channel.flux_err_ujy;
    ctx.strokeStyle = lowClean ? COLORS.amber : color;
    ctx.lineWidth = 1;
    if (error !== null && Number.isFinite(error) && error >= 0) {
      ctx.beginPath();
      ctx.moveTo(x, yScale(channel.flux_ujy - error));
      ctx.lineTo(x, yScale(channel.flux_ujy + error));
      ctx.stroke();
    }
    if (lowClean) {
      ctx.strokeStyle = COLORS.amber;
      ctx.lineWidth = 1.2;
      ctx.strokeRect(x - 3, y - 3, 6, 6);
    } else {
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(x, y, 2.6, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  // Epoch legend.
  let legendX = plot.x;
  spectrum.epochs.forEach((epoch, index) => {
    const color = epochColor(spectrumEpochColorIndex(epoch.epoch_id, index, epochOrder));
    ctx.fillStyle = color;
    ctx.fillRect(legendX, plot.y - 34, 8, 8);
    ctx.fillStyle = COLORS.muted;
    ctx.font = `9px ${COLORS.mono}`;
    ctx.fillText(`${epoch.epoch_id} (${epoch.channels.length} ch)`, legendX + 12, plot.y - 27);
    legendX += 150;
  });

  ctx.fillStyle = COLORS.muted;
  ctx.font = `9px ${COLORS.mono}`;
  ctx.fillText("Wavelength (µm)", plot.x + plot.width / 2 - 40, plot.y + plot.height + 34);
  ctx.fillStyle = COLORS.amber;
  ctx.fillText(
    `${stats.usable} eligible · ${stats.excludedFinite} finite excluded (square/cross) · ${stats.nullFlux} null omitted`,
    plot.x,
    plot.y + plot.height + 50,
  );
}

function drawHeader(
  ctx: CanvasRenderingContext2D,
  input: TriageCardInput,
): void {
  const target = input.manifest.target;
  ctx.fillStyle = COLORS.panel;
  ctx.fillRect(0, 0, WIDTH, 92);
  ctx.strokeStyle = COLORS.hairline;
  ctx.beginPath();
  ctx.moveTo(0, 92.5);
  ctx.lineTo(WIDTH, 92.5);
  ctx.stroke();

  ctx.fillStyle = COLORS.bright;
  ctx.font = `600 22px ${COLORS.sans}`;
  ctx.fillText("SPHEREx SkyBlink · Dynamic-Channel Triage Card", 24, 34);

  ctx.fillStyle = COLORS.text;
  ctx.font = `12px ${COLORS.mono}`;
  ctx.fillText(
    `${target?.name ?? "Sky field"} · ${target?.category ?? "arbitrary ICRS position"}`,
    24,
    56,
  );
  ctx.fillStyle = COLORS.accent;
  ctx.font = `11px ${COLORS.mono}`;
  ctx.fillText(
    `ICRS ${formatRa(input.manifest.query.ra)} ${formatDec(input.manifest.query.dec)} · ${coordinateEpochLabel(input.manifest.target)}`,
    24,
    76,
  );

  const epochA = input.epochs[0];
  const epochB = input.epochs[1] ?? null;
  const baselineDays = epochB
    ? Math.abs(epochB.mjd_mean - epochA.mjd_mean)
    : 0;
  ctx.fillStyle = COLORS.muted;
  ctx.font = `10px ${COLORS.mono}`;
  ctx.textAlign = "right";
  ctx.fillText(
    epochB
      ? `${epochA.epoch_id} ${epochA.mjd_mean.toFixed(2)} → ${epochB.epoch_id} ${epochB.mjd_mean.toFixed(2)} · ${baselineDays.toFixed(1)} d baseline`
      : `${epochA.epoch_id} MJD ${epochA.mjd_mean.toFixed(2)} · single epoch`,
    WIDTH - 24,
    34,
  );
  ctx.fillText(
    `Band ${input.band} · ${input.diffKey ?? "no difference pair"}`,
    WIDTH - 24,
    52,
  );

  const badge = `REAL DATA · ${input.manifest.provenance.release}`;
  ctx.font = `600 10px ${COLORS.mono}`;
  const badgeWidth = ctx.measureText(badge).width + 18;
  const badgeX = WIDTH - 24 - badgeWidth;
  const badgeY = 64;
  ctx.fillStyle = "rgba(52, 211, 153, 0.08)";
  ctx.fillRect(badgeX, badgeY, badgeWidth, 18);
  ctx.strokeStyle = "rgba(52, 211, 153, 0.35)";
  ctx.strokeRect(badgeX + 0.5, badgeY + 0.5, badgeWidth - 1, 17);
  ctx.fillStyle = COLORS.nominal;
  ctx.textAlign = "center";
  ctx.fillText(badge, badgeX + badgeWidth / 2, badgeY + 13);
  ctx.textAlign = "left";
}

function drawFooter(
  ctx: CanvasRenderingContext2D,
  input: TriageCardInput,
  channelCount: number,
): void {
  ctx.fillStyle = COLORS.panel;
  ctx.fillRect(0, HEIGHT - 68, WIDTH, 68);
  ctx.strokeStyle = COLORS.hairline;
  ctx.beginPath();
  ctx.moveTo(0, HEIGHT - 68.5);
  ctx.lineTo(WIDTH, HEIGHT - 68.5);
  ctx.stroke();
  ctx.fillStyle = COLORS.amber;
  ctx.font = `600 10px ${COLORS.mono}`;
  ctx.fillText(
    `EXPLORATORY COMPARISON · no detection established · ${channelCount} recorded spectrum samples`,
    24,
    HEIGHT - 42,
  );
  ctx.fillStyle = COLORS.dim;
  ctx.font = `9px ${COLORS.mono}`;
  const url = input.shareUrl;
  const shownUrl = url.length > 150 ? `${url.slice(0, 149)}…` : url;
  ctx.fillText(`Generated ${new Date().toISOString()} · ${shownUrl}`, 24, HEIGHT - 22);
}

function buildMarkdown(
  input: TriageCardInput,
  channelCount: number,
): string {
  const target = input.manifest.target;
  const epochA = input.epochs[0];
  const epochB = input.epochs[1] ?? null;
  const baselineDays = epochB
    ? Math.abs(epochB.mjd_mean - epochA.mjd_mean)
    : 0;
  const baselineYears = baselineDays / 365.25;
  const stats = channelStats(input.spectrum);
  const gaia = nearestGaia(input.manifest, input.gaia);
  const lines: string[] = [];

  lines.push("# SPHEREx SkyBlink — Dynamic-Channel Triage Card", "");
  lines.push(`**Generated:** ${new Date().toISOString()}`, "");
  lines.push("## Target", "");
  lines.push(`- **Name:** ${target?.name ?? "Sky field"}`);
  lines.push(`- **Class:** ${target?.category ?? "arbitrary ICRS position"}`);
  lines.push(
    `- **ICRS (${coordinateEpochLabel(target)}):** ${formatRa(input.manifest.query.ra)} · ${formatDec(input.manifest.query.dec)} (${input.manifest.query.ra.toFixed(6)}°, ${input.manifest.query.dec.toFixed(6)}°)`,
  );
  if (target) {
    lines.push(
      `- **Proper motion:** μ_α* = ${target.pm_ra_mas_yr.toFixed(1)} mas/yr · μ_δ = ${target.pm_dec_mas_yr.toFixed(1)} mas/yr · reference ${target.ref_epoch}`,
    );
  } else {
    lines.push("- **Proper motion:** not available (arbitrary field, no target record)");
  }
  lines.push(`- **Data label:** real data · ${input.manifest.provenance.release}`);
  lines.push(`- **Sky data access:** ${input.manifest.provenance.data_access ?? "unrecorded"}`);
  lines.push(`- **Sky discovery mode:** ${input.manifest.provenance.discovery_mode ?? "unrecorded"}`);
  if (input.manifest.provenance.discovery_mode === "indexed") lines.push("- Limited spatial exposure index; images downloaded afresh. All-sky coverage and newer observations are unknown.");
  if (input.manifest.provenance.discovery_mode === "known") lines.push("- Previously verified exposure list; images downloaded afresh. No new archive coverage search.");
  lines.push(`- **Sky discovery status:** ${input.manifest.provenance.discovery_status ?? "unknown"}`);
  lines.push(`- **Sky missing collections:** ${input.manifest.provenance.missing_collections?.join(", ") || "not recorded"}`);
  if (input.manifest.provenance.discovery_mode !== "known" && input.manifest.provenance.discovery_status === "partial") lines.push("- Archive search incomplete; showing retrieved observations. Coverage/latest-epoch inventory is not complete.");
  lines.push(`- **Comparison status:** ${input.manifest.provenance.comparison_status ?? "unrecorded"}`);
  lines.push(`- **Comparison reason:** ${input.manifest.provenance.comparison_reason ?? "unrecorded"}`);
  lines.push(`- **Sky processing version:** ${input.manifest.provenance.processing_version ?? "unavailable (legacy metadata)"}`);
  lines.push(`- **Sky analysis ID:** ${input.manifest.provenance.analysis_id ?? "unavailable (legacy metadata)"}`);
  lines.push(`- **Sky analysis record:** ${input.manifest.provenance.analysis_record_url ? resolveAssetUrl(input.manifest.provenance.analysis_record_url) : "unavailable (legacy metadata)"}`);
  const expectedAnalysis = new URL(input.shareUrl, "https://skyblink.invalid").searchParams.get("analysis");
  if (expectedAnalysis) lines.push(`- **Shared expected analysis ID:** ${expectedAnalysis}`);
  const identityNotice = analysisIdentityNotice(expectedAnalysis, input.manifest.provenance.analysis_id);
  if (identityNotice) lines.push(`- **Identity limitation:** ${identityNotice}`);
  lines.push("");

  lines.push("## Epoch baseline", "");
  lines.push(`- **Band:** ${input.band}`);
  lines.push(`- **Epoch A:** ${epochA.epoch_id} · ${observationDateLabel(epochA)} · MJD ${epochA.mjd_mean.toFixed(2)} · ${epochA.collection}/${epochA.release}`);
  if (epochB) {
    lines.push(`- **Epoch B:** ${epochB.epoch_id} · ${observationDateLabel(epochB)} · MJD ${epochB.mjd_mean.toFixed(2)} · ${epochB.collection}/${epochB.release}`);
    lines.push(`- **Mean-date baseline:** ${baselineDays.toFixed(1)} d (${baselineYears.toFixed(3)} yr); individual observations can span the recorded ranges`);
  } else {
    lines.push("- **Epoch B:** not available (single-epoch set)");
  }
  if (input.diffKey) {
    lines.push(`- **Difference:** ${input.diffKey.replace("_minus_", " − ")}`);
  } else {
    lines.push("- **Difference:** not available");
  }
  for (const epoch of input.epochs) {
    const description = epoch.telemetry ? telemetryDescription(epoch.telemetry, input.band) : null;
    lines.push(`- **Telemetry ${epoch.epoch_id}:** ${description ? `${description.label}; ${description.detail}` : "unavailable"}`);
  }
  lines.push("");

  lines.push("## Measurements (manifest)", "");
  lines.push(`- **Flag summary A:** ${epochA.flag_summary.status} · aperture warnings: ${activeFlagText(epochA)} · frame artifacts ${(epochA.flag_summary.artifact_pixel_fraction * 100).toFixed(1)}% · Bit 21 ${epochA.flag_summary.source_bit_set ? "set" : "not set"}`);
  if (epochB) {
    lines.push(`- **Flag summary B:** ${epochB.flag_summary.status} · aperture warnings: ${activeFlagText(epochB)} · frame artifacts ${(epochB.flag_summary.artifact_pixel_fraction * 100).toFixed(1)}% · Bit 21 ${epochB.flag_summary.source_bit_set ? "set" : "not set"}`);
  }
  const candidates = input.epochs.flatMap((epoch) =>
    (epoch.candidates ?? []).map((candidate) => ({ epoch, candidate })),
  );
  if (candidates.length === 0) {
    lines.push("- **Centroid/flux metrics:** none in this manifest (no candidates array entries)");
  } else {
    lines.push("- **Centroid/flux metrics (candidates):**");
    for (const { epoch, candidate } of candidates) {
      lines.push(
        `  - ${epoch.epoch_id} · ${candidate.id} · ${candidate.kind} · x=${candidate.x_px.toFixed(2)} y=${candidate.y_px.toFixed(2)} px · SNR ${candidate.snr.toFixed(2)} · Δflux ${candidate.delta_flux_mjy_sr === null ? "—" : `${candidate.delta_flux_mjy_sr.toFixed(3)} MJy/sr`} · artifact-clean ${candidate.is_artifact_clean ? "yes" : "no"} · “${candidate.label}”`,
      );
    }
  }
  lines.push(
    `- **Spectrum:** ${input.spectrum ? `${channelCount} recorded samples; ${stats.finite} finite, ${stats.usable} eligible across ${input.spectrum.epochs.length} epoch${input.spectrum.epochs.length === 1 ? "" : "s"}` : "not available"}${stats.medianFlux !== null ? ` · median eligible-channel flux ${stats.medianFlux.toFixed(1)} µJy (not a total)` : ""}${stats.nullFlux > 0 || stats.hardBad > 0 ? ` · ${stats.nullFlux} null and ${stats.hardBad} hard-bad channels excluded from the summary (counts may overlap)` : ""}`,
  );
  if (input.spectrum) {
    const provenance = input.spectrum.provenance;
    lines.push(`- **Spectrum processing version:** ${provenance.processing_version ?? "unavailable (legacy metadata)"}`);
    lines.push(`- **Spectrum analysis ID:** ${provenance.analysis_id ?? "unavailable (legacy metadata)"}`);
    lines.push(`- **Spectrum analysis record:** ${provenance.analysis_record_url ? resolveAssetUrl(provenance.analysis_record_url) : "unavailable (legacy metadata)"}`);
    lines.push("- Native spectrum inputs are recorded separately; they are not assumed to match the displayed image pair.");
    lines.push("- Current archive eligibility requires the full center-selected aperture inside the image, all selected aperture pixels clean, supported field background, at least 10 clean local-annulus pixels, and no hard-bad center. Finite partial-aperture or insufficient-annulus sums remain exploratory and are excluded from eligible summaries. Saved products retain their historical recorded flags.");
    lines.push("- Eligibility is necessary quality screening; it does not certify source isolation, calibrated total flux or astrophysical variability.");
    for (const epoch of input.spectrum.epochs) {
      lines.push(`- **Spectrum ${epoch.epoch_id}:** ${observationDateLabel(epoch)}; recorded measurement reasons: ${epoch.measurement_availability ? epoch.measurement_availability.reasons.join(", ") || "none listed" : "unavailable (legacy metadata)"}`);
    }
  }
  lines.push(`- **Gaia:** ${gaia.text}`);
  lines.push(`- **WISE:** ${wiseText(input.manifest)}`);
  lines.push("");

  lines.push("## Panels", "");
  lines.push(`1. **Epoch A:** ${epochA.epoch_id} (${observationDateLabel(epochA)}, MJD ${epochA.mjd_mean.toFixed(2)})`);
  lines.push(`2. **Epoch B:** ${epochB ? `${epochB.epoch_id} (${observationDateLabel(epochB)}, MJD ${epochB.mjd_mean.toFixed(2)})` : "not available"}`);
  lines.push(`3. **Difference:** ${input.diffKey ? input.diffKey.replace("_minus_", " − ") : "not available"}`);
  lines.push(`4. **Spectrum:** ${input.spectrum ? `${channelCount}-channel SPHEREx spectrum` : "not available"}`);
  lines.push("");

  lines.push("## Shared view recipe", "");
  lines.push("The link restores documented selection and display settings, paused. Archive mode performs a new query and may return a different analysis fingerprint; this is not a pinned-input replay. Inspect the recorded analysis for exact input replay.", "");
  lines.push("```");
  lines.push(input.shareUrl);
  lines.push("```", "");

  lines.push("## Honesty notes", "");
  lines.push("- **Exploratory comparison; no detection established.** This report does not establish a detection, classification, or confirmation.");
  lines.push("- It contains no ML confidence score, probability, or discovery likelihood.");
  lines.push("- Missing bands/epochs/catalogs are written as “not available”; nothing is interpolated or fabricated.");
  lines.push("- Export panels use the selected observation IDs and band. The PNG uses original server previews at full frame; it does not apply the workspace camera, color/stretch settings, or trial-motion overlays. The share link preserves those view settings separately.");
  lines.push(input.spectrum && (input.manifest.provenance.discovery_mode ?? "live") !== (input.spectrum.provenance.discovery_mode ?? "live")
    ? "- Image and spectrum use different discovery modes. All returned spectrum epochs are retained; epoch IDs are not matched across these inventories. Read each spectrum observation date and its separate analysis fingerprint."
    : "- The spectrum is restricted to selected epoch IDs, but its native exposure samples are acquired and extracted independently of the displayed image pair. The native spectrum has its own analysis fingerprint.");
  lines.push("- Display frames are 8-bit WebP previews; Telemetry contains display intensity and Table 16 flags when provided. MJy/sr values may be server-normalized; they are not calibrated source flux. The telemetry plane can differ from the displayed band; absent quantity/normalization metadata remains unknown.");
  lines.push("- The browser never re-normalizes flux; the recorded normalization metadata states which server-side scaling was applied.");
  lines.push("");
  lines.push("## Attribution", "");
  lines.push(`- ${input.manifest.provenance.source}`);
  lines.push(`- ${input.manifest.provenance.citation}`);
  if (input.spectrum) {
    lines.push(`- Spectrum discovery mode: ${input.spectrum.provenance.discovery_mode ?? "unrecorded"}`);
    lines.push(`- Spectrum discovery status: ${input.spectrum.provenance.discovery_status ?? "unknown"}; missing collections: ${input.spectrum.provenance.missing_collections?.join(", ") || "not recorded"}`);
    lines.push(`- Spectrum: ${input.spectrum.provenance.source} · ${input.spectrum.provenance.citation}`);
  }
  lines.push("");
  return lines.join("\n");
}

export async function buildTriageCard(
  input: TriageCardInput,
): Promise<TriageCardResult> {
  if (
    input.manifest.provenance.is_simulated_fallback !== false ||
    (input.spectrum && input.spectrum.provenance.is_simulated_fallback !== false) ||
    input.gaia.isSimulatedFallback
  ) {
    throw new Error("Triage exports require real observations.");
  }
  if (input.epochs.length === 0) {
    throw new Error("No epochs are available for the triage card.");
  }
  const epochA = input.epochs[0];
  const epochB = input.epochs[1] ?? null;
  const frameA = typeof epochA.frames[input.band] === "string"
    ? epochA.frames[input.band]
    : null;
  const frameB =
    epochB && typeof epochB.frames[input.band] === "string"
      ? epochB.frames[input.band]
      : null;
  const [bitmapA, bitmapB, bitmapDiff] = await Promise.all([
    loadBitmap(frameA),
    loadBitmap(frameB),
    loadBitmap(input.diffUrl),
  ]);

  try {
    const canvas = document.createElement("canvas");
    canvas.width = WIDTH;
    canvas.height = HEIGHT;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Could not create the triage-card canvas.");
    ctx.fillStyle = COLORS.bg;
    ctx.fillRect(0, 0, WIDTH, HEIGHT);

    drawHeader(ctx, input);

    drawImagePanel(
      ctx,
      PANEL_A,
      `Epoch A · ${epochA.epoch_id}`,
      `${observationDateLabel(epochA)} · MJD ${epochA.mjd_mean.toFixed(2)}`,
      bitmapA,
      [
        ["Epoch", epochA.epoch_id],
        ["Dates", observationDateLabel(epochA)],
        ["MJD", epochA.mjd_mean.toFixed(2)],
        ["Release", `${epochA.collection} · ${epochA.release}`],
        ["Flags", `${epochA.flag_summary.status} · ${activeFlagText(epochA)}`],
        ["Frame artifacts", `${(epochA.flag_summary.artifact_pixel_fraction * 100).toFixed(1)}%`],
        ["Candidates", candidateText(epochA)],
        ["Core inpainted", epochA.core_inpainted ? "yes (display-only)" : "no"],
      ],
    );

    drawImagePanel(
      ctx,
      PANEL_B,
      epochB ? `Epoch B · ${epochB.epoch_id}` : "Epoch B · not available",
      epochB
        ? `${observationDateLabel(epochB)} · MJD ${epochB.mjd_mean.toFixed(2)}`
        : "single-epoch manifest; no second panel is invented",
      bitmapB,
      epochB
        ? [
            ["Epoch", epochB.epoch_id],
            ["Dates", observationDateLabel(epochB)],
            ["MJD", epochB.mjd_mean.toFixed(2)],
            ["Release", `${epochB.collection} · ${epochB.release}`],
            ["Flags", `${epochB.flag_summary.status} · ${activeFlagText(epochB)}`],
            ["Frame artifacts", `${(epochB.flag_summary.artifact_pixel_fraction * 100).toFixed(1)}%`],
            ["Candidates", candidateText(epochB)],
            ["Core inpainted", epochB.core_inpainted ? "yes (display-only)" : "no"],
          ]
        : [
            ["Epoch", "not available"],
            ["Baseline", "—"],
            ["Note", "no fabricated epoch"],
          ],
    );

    drawImagePanel(
      ctx,
      PANEL_C,
      input.diffKey
        ? `Difference · ${input.diffKey.replace("_minus_", " − ")}`
        : "Difference · not available",
      input.diffKey
        ? "server-computed signed residual · blue − / warm +"
        : "no adjacent difference pair for this selection",
      bitmapDiff,
      [
        ["Pair", input.diffKey?.replace("_minus_", " − ") ?? "not available"],
        ["Band", input.band],
        [
          "Baseline",
          epochB
            ? `${Math.abs(epochB.mjd_mean - epochA.mjd_mean).toFixed(1)} d`
            : "—",
        ],
        ["Interpretation", "triage display only"],
        ["Note", "no detection established"],
      ],
    );

    drawSpectrumPanel(ctx, PANEL_D, input.spectrum, input.spectrumEpochOrder);

    const stats = channelStats(input.spectrum);
    drawFooter(ctx, input, stats.total);

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/png"),
    );
    if (!blob) throw new Error("PNG encoding failed.");
    const markdown = buildMarkdown(input, stats.total);
    const targetId = input.manifest.query.target_id ?? "field";
    const filenameBase = `skyblink_triage_${targetId}_${epochA.epoch_id}${epochB ? `_${epochB.epoch_id}` : ""}`.replace(
      /[^A-Za-z0-9_-]+/g,
      "_",
    );
    return {
      pngBlob: blob,
      pngUrl: URL.createObjectURL(blob),
      markdown,
      filenameBase,
      channelCount: stats.total,
    };
  } finally {
    bitmapA?.close();
    bitmapB?.close();
    bitmapDiff?.close();
  }
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(textarea);
    return ok;
  }
}
