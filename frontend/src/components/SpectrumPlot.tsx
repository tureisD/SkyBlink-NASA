import { useEffect, useMemo, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import type { SpectrumChannel, SpectrumResponse } from "../lib/types";
import { BANDS } from "../lib/types";
import { observationDateLabel, spectrumDomain, measurementNumber } from "../lib/semantics";

const HEIGHT = 350;
const MARGIN = { left: 80, right: 18, top: 38, bottom: 52 };
const PLOT_H = HEIGHT - MARGIN.top - MARGIN.bottom;
const X_MIN = 0.7;
const X_MAX = 5.1;
const HOVER_RADIUS = 15;
const EPOCH_COLORS = ["var(--chart-series-1, #b8dacc)", "var(--chart-series-2, #eac995)", "var(--chart-series-3, #a4c6ee)", "var(--chart-series-4, #d2b5e2)", "var(--chart-series-5, #e6aaa3)"];

const TOOLTIP_H = 116;

export function spectrumEpochColor(index: number): string {
  return EPOCH_COLORS[index % EPOCH_COLORS.length];
}

interface SeriesPoint {
  channel: SpectrumChannel;
  x: number;
  y: number;
  yTop: number;
  yBottom: number;
}

interface PlottedPoint extends SeriesPoint {
  epochId: string;
  color: string;
  key: string;
}

interface TooltipLine {
  text: string;
  color?: string;
}

function tooltipLines(point: PlottedPoint): TooltipLine[] {
  const channel = point.channel;
  const flux = channel.flux_ujy ?? 0;
  const error = channel.flux_err_ujy ?? 0;
  const clean = (channel.clean_fraction * 100).toFixed(0);
  const status = channel.is_flagged_bad
    ? "hard-bad"
    : !channel.is_used_in_photometry
      ? "excluded"
      : channel.clean_fraction < 1
        ? "used · low clean"
        : "used";
  return [
    {
      text: `${point.epochId} · D${channel.detector} · ${channel.wavelength_um.toFixed(3)} µm`,
      color: point.color,
    },
    { text: `${measurementNumber(flux)} µJy · ${channel.flux_err_ujy === null ? "error unavailable" : `± ${measurementNumber(error)}`}` },
    { text: `clean ${clean}% · ${status}` },
    { text: `flags ${channel.flags} · Δλ ${channel.bandwidth_um.toFixed(3)} µm` },
  ];
}

function SpectrumTooltip({ point, width }: { point: PlottedPoint; width: number }) {
  const lines = tooltipLines(point);
  const tooltipWidth = Math.min(320, width - 8);
  let x = point.x + 12;
  let y = point.y - TOOLTIP_H - 10;
  if (x + tooltipWidth > width - 4) x = point.x - tooltipWidth - 12;
  x = Math.max(4, Math.min(x, width - tooltipWidth - 4));
  if (y < 4) y = point.y + 14;
  if (y + TOOLTIP_H > HEIGHT - 4) y = HEIGHT - TOOLTIP_H - 4;

  return (
    <g className="spectrum-tooltip" pointerEvents="none" transform={`translate(${x} ${y})`}>
      <rect
        width={tooltipWidth}
        height={TOOLTIP_H}
        rx={4}
        fill="var(--chart-bg, #171c20)"
        stroke="var(--chart-muted, #b0b7b5)"
        strokeWidth={1}
      />
      <rect x={9} y={9} width={2} height={TOOLTIP_H - 18} fill={point.color} rx={1} />
      {lines.map((line, index) => (
        <text
          key={line.text}
          x={18}
          y={25 + index * 25}
          fill={line.color ?? "var(--chart-text, #eeeae0)"}
          fontSize={13}
          fontFamily="var(--font-body, sans-serif)"
        >
          {line.text}
        </text>
      ))}
    </g>
  );
}

export interface SpectrumPlotProps {
  spectrum: SpectrumResponse;
  showReferences?: boolean;
  selectedChannel?: SpectrumChannel | null;
  selectedEpochId?: string;
  onChannelSelect?: (channel: SpectrumChannel | null, epochId: string) => void;
  /** Hovered channel and its epoch; used to sync the LVF canvas overlay. */
  onChannelHover?: (
    channel: SpectrumChannel | null,
    epochId: string,
  ) => void;
}

/**
 * Accessible SVG spectrum. All values come from the manifest; no smoothing,
 * template fitting, or invented confidence is applied.
 *
 * Hover uses nearest-point detection on the SVG rather than per-marker
 * pointerenter/leave. This avoids flicker between the tiny marker, its error
 * bar, and the browser's native SVG tooltip, and it keeps the LVF callback from
 * firing on every sub-pixel movement.
 */
export function SpectrumPlot({ spectrum, onChannelHover, showReferences = false, selectedChannel, selectedEpochId, onChannelSelect }: SpectrumPlotProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [width, setWidth] = useState(780);
  useEffect(() => {
    const element = svgRef.current;
    if (!element) return;
    const resize = () => setWidth(Math.max(220, Math.round(element.getBoundingClientRect().width)));
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const WIDTH = width;
  const PLOT_W = WIDTH - MARGIN.left - MARGIN.right;
  const xScale = (wavelength: number) => MARGIN.left + ((wavelength - X_MIN) / (X_MAX - X_MIN)) * PLOT_W;
  const [hovered, setHovered] = useState<PlottedPoint | null>(null);
  const hoveredKeyRef = useRef<string | null>(null);

  const series = useMemo(() => {
    return spectrum.epochs.map((epoch, index) => {
      const channels = epoch.channels
        .filter(
          (channel) =>
            typeof channel.flux_ujy === "number" &&
            Number.isFinite(channel.flux_ujy) &&
            channel.flux_ujy !== null,
        )
        .slice()
        .sort((a, b) => a.wavelength_um - b.wavelength_um);
      return {
        epoch,
        color: EPOCH_COLORS[index % EPOCH_COLORS.length],
        channels,
      };
    });
  }, [spectrum]);

  const [yMin, yMax] = useMemo(() => spectrumDomain(series.flatMap(item => item.channels)), [series]);

  const plotted = useMemo<PlottedPoint[]>(() => {
    return series.flatMap((item) =>
      item.channels.map((channel) => {
        const flux = channel.flux_ujy ?? 0;
        const error = channel.flux_err_ujy ?? 0;
        const x = xScale(channel.wavelength_um);
        const y = MARGIN.top + PLOT_H - ((flux - yMin) / (yMax - yMin)) * PLOT_H;
        const yTop = MARGIN.top + PLOT_H - ((flux + error - yMin) / (yMax - yMin)) * PLOT_H;
        const yBottom =
          MARGIN.top + PLOT_H - ((flux - error - yMin) / (yMax - yMin)) * PLOT_H;
        return {
          channel,
          x,
          y,
          yTop,
          yBottom,
          epochId: item.epoch.epoch_id,
          color: item.color,
          key: `${item.epoch.epoch_id}-${channel.detector}-${channel.wavelength_um}`,
        };
      }),
    );
  }, [series, yMax, yMin, PLOT_W]);

  // Clear the hover when the plotted spectrum changes (target / epoch / data).
  useEffect(() => {
    hoveredKeyRef.current = null;
    setHovered(null);
  }, [spectrum, width]);

  const yTicks = [...Array.from({ length: 6 }, (_, index) => yMin + ((yMax - yMin) * index) / 5)
    .filter(tick => Math.abs(tick) > (yMax - yMin) * .07), 0].sort((a, b) => a - b);
  const xTicks = [1, 2, 3, 4, 5];

  const ariaSummary = series
    .map(
      (item) =>
        `${observationDateLabel(item.epoch)}; ID ${item.epoch.epoch_id} (${item.epoch.collection}/${item.epoch.release}): ${item.channels.length} channels`,
    )
    .join("; ");

  const clearHover = () => {
    if (hoveredKeyRef.current === null) return;
    hoveredKeyRef.current = null;
    setHovered(null);
    onChannelHover?.(selectedChannel ?? null, selectedEpochId ?? "");
  };

  const handlePointerMove = (event: ReactPointerEvent<SVGSVGElement>) => {
    const svg = event.currentTarget;
    const ctm = svg.getScreenCTM();
    if (!ctm) return;
    // The SVG is letterboxed by preserveAspectRatio when max-height clamps it.
    // Map the pointer through the actual screen CTM, not the container box.
    const screenPoint = svg.createSVGPoint();
    screenPoint.x = event.clientX;
    screenPoint.y = event.clientY;
    const localPoint = screenPoint.matrixTransform(ctm.inverse());
    const x = localPoint.x;
    const y = localPoint.y;
    let nearest: PlottedPoint | null = null;
    let best = Math.pow(Math.max(HOVER_RADIUS, 24 / Math.max(Math.abs(ctm.a), .1)), 2);
    for (const point of plotted) {
      const dx = point.x - x;
      const dy = point.y - y;
      const distance = dx * dx + dy * dy;
      if (distance < best) {
        best = distance;
        nearest = point;
      }
    }
    if (event.type === "pointerdown") onChannelSelect?.(nearest?.channel ?? null, nearest?.epochId ?? "");
    if ((nearest?.key ?? null) === hoveredKeyRef.current) return;
    hoveredKeyRef.current = nearest?.key ?? null;
    setHovered(nearest);
    onChannelHover?.(nearest?.channel ?? null, nearest?.epochId ?? "");
  };

  return (
    <svg
      ref={svgRef}
      className="spectrum-plot"
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      role="group"
      tabIndex={0}
      data-domain-min={yMin}
      data-domain-max={yMax}
      aria-label={`Signed flux versus wavelength. ${ariaSummary}. Arrow keys select samples. A full data table follows.`}
      onKeyDown={event => {
        if (!plotted.length) return;
        const current = plotted.findIndex(p => p.channel === selectedChannel && p.epochId === selectedEpochId);
        let index: number | null = null;
        if (event.key === "ArrowRight" || event.key === "ArrowDown") index = (current + 1) % plotted.length;
        if (event.key === "ArrowLeft" || event.key === "ArrowUp") index = (Math.max(current, 0) - 1 + plotted.length) % plotted.length;
        if (event.key === "Home") index = 0;
        if (event.key === "End") index = plotted.length - 1;
        if (index !== null) { event.preventDefault(); onChannelSelect?.(plotted[index].channel, plotted[index].epochId); }
      }}
      onPointerDown={handlePointerMove}
      onPointerMove={handlePointerMove}
      onPointerLeave={clearHover}
      onPointerCancel={clearHover}
    >
      <rect x={0} y={0} width={WIDTH} height={HEIGHT} fill="var(--chart-bg, #171c20)" rx={8} />

      {/* Detector-band zones */}
      {BANDS.map((band, index) => {
        const x1 = xScale(Math.max(X_MIN, band.minUm));
        const x2 = xScale(Math.min(X_MAX, band.maxUm));
        return (
          <g key={band.key}>
            <rect
              x={x1}
              y={MARGIN.top}
              width={Math.max(0, x2 - x1)}
              height={PLOT_H}
              fill={band.color}
              opacity={0.055}
            />
            <text
              x={(x1 + x2) / 2}
              y={WIDTH < 400 ? 15 + (index % 2) * 16 : 22}
              textAnchor="middle"
              fill={band.color}
              fontSize={13}
              fontFamily="var(--font-body, sans-serif)"
            >
              {band.short}
            </text>
          </g>
        );
      })}

      {/* Y grid + labels */}
      {yTicks.map((tick) => {
        const y = MARGIN.top + PLOT_H - ((tick - yMin) / (yMax - yMin)) * PLOT_H;
        return (
          <g key={tick}>
            <line
              x1={MARGIN.left}
              x2={WIDTH - MARGIN.right}
              y1={y}
              y2={y}
              stroke="var(--chart-grid, #41494d)"
              strokeWidth={1}
              strokeDasharray={tick === 0 ? undefined : "2 4"}
            />
            <text
              x={MARGIN.left - 8}
              y={y + 3}
              textAnchor="end"
              fill="var(--chart-text, #eeeae0)"
              fontSize={13}
              fontFamily="var(--font-body, sans-serif)"
            >
              {Math.abs(tick) >= 10000 ? tick.toExponential(1) : new Intl.NumberFormat("en", { maximumSignificantDigits: 3 }).format(tick)}
            </text>
          </g>
        );
      })}

      <line data-zero-line="true" x1={MARGIN.left} x2={WIDTH - MARGIN.right}
        y1={MARGIN.top + PLOT_H + yMin / (yMax - yMin) * PLOT_H}
        y2={MARGIN.top + PLOT_H + yMin / (yMax - yMin) * PLOT_H} stroke="#d6dbe5" strokeOpacity={.7} />

      {/* X ticks + labels */}
      {xTicks.map((tick) => (
        <g key={tick}>
          <line
            x1={xScale(tick)}
            x2={xScale(tick)}
            y1={MARGIN.top}
            y2={MARGIN.top + PLOT_H}
            stroke="var(--chart-grid, #41494d)"
            strokeWidth={1}
            strokeDasharray="2 4"
          />
          <text
            x={xScale(tick)}
            y={MARGIN.top + PLOT_H + 16}
            textAnchor="middle"
            fill="var(--chart-text, #eeeae0)"
            fontSize={13}
            fontFamily="var(--font-body, sans-serif)"
          >
            {tick.toFixed(1)}
          </text>
        </g>
      ))}

      {/* Molecular features */}
      {showReferences && spectrum.molecular_features.map((feature, index) => {
        const x = xScale(feature.wavelength_um);
        const row = index % 3;
        const labelY = 54 + row * 18;
        return (
          <g key={`${feature.label}-${feature.wavelength_um}`} data-molecular-reference="true">
            <line
              x1={x}
              x2={x}
              y1={labelY + 3}
              y2={MARGIN.top + PLOT_H}
              stroke="rgba(251, 191, 36, 0.34)"
              strokeWidth={1}
              strokeDasharray="3 4"
            />
            <text
              x={Math.min(x + 2, WIDTH - MARGIN.right)}
              y={labelY}
              textAnchor={x > WIDTH - 120 ? "end" : "start"}
              fill="#fcd34d"
              fontSize={13}
              fontFamily="var(--font-body, sans-serif)"
            >
              {WIDTH < 500 ? index + 1 : feature.label}
            </text>
          </g>
        );
      })}

      {/* Persistent crosshair is tied to an actual selected sample. */}
      {plotted.filter(point => point.channel === selectedChannel && point.epochId === selectedEpochId).map(point => (
        <g key={`crosshair-${point.key}`} data-selected-crosshair="true" pointerEvents="none" stroke="var(--chart-accent, #bce9df)" strokeWidth={1} strokeDasharray="4 4" opacity={.65}>
          <line x1={MARGIN.left} x2={WIDTH - MARGIN.right} y1={point.y} y2={point.y} />
          <line x1={point.x} x2={point.x} y1={MARGIN.top} y2={MARGIN.top + PLOT_H} />
        </g>
      ))}

      {/* Epoch series */}
      {series.map((item) => {
        const points = plotted.filter((point) => point.epochId === item.epoch.epoch_id);
        return (
          <g key={item.epoch.epoch_id}>
            {points.map((point) => {
              const channel = point.channel;
              const lowClean = !channel.is_used_in_photometry;
              const bad = channel.is_flagged_bad;
              return (
                <g
                  key={point.key}
                  data-detector={channel.detector}
                  data-wavelength={channel.wavelength_um}
                  data-epoch={item.epoch.epoch_id}
                  data-spectrum-point="true"
                  data-flux={channel.flux_ujy}
                  data-error-lower={channel.flux_err_ujy === null ? undefined : channel.flux_ujy! - channel.flux_err_ujy}
                  data-selected={channel === selectedChannel && item.epoch.epoch_id === selectedEpochId}
                  pointerEvents="none"
                >
                  {channel.flux_err_ujy !== null ? (
                    <g
                      stroke={lowClean ? "var(--chart-warning, #eac995)" : item.color}
                      strokeWidth={1}
                      strokeOpacity={lowClean ? 0.6 : 0.45}
                      strokeDasharray={lowClean ? "2 2" : undefined}
                    >
                      <line
                        x1={point.x}
                        x2={point.x}
                        y1={point.yTop}
                        y2={point.yBottom}
                        vectorEffect="non-scaling-stroke"
                      />
                      <line
                        x1={point.x - 3}
                        x2={point.x + 3}
                        y1={point.yTop}
                        y2={point.yTop}
                        vectorEffect="non-scaling-stroke"
                      />
                      <line
                        x1={point.x - 3}
                        x2={point.x + 3}
                        y1={point.yBottom}
                        y2={point.yBottom}
                        vectorEffect="non-scaling-stroke"
                      />
                    </g>
                  ) : null}
                  {channel === selectedChannel && item.epoch.epoch_id === selectedEpochId ? <circle cx={point.x} cy={point.y} r={7} fill="none" stroke="var(--chart-accent, #bce9df)" strokeWidth={1.6} /> : null}
                  {bad ? (
                    <g stroke="var(--chart-danger, #ed9a98)" strokeWidth={1.6}>
                      <line x1={point.x - 4} x2={point.x + 4} y1={point.y - 4} y2={point.y + 4} />
                      <line x1={point.x - 4} x2={point.x + 4} y1={point.y + 4} y2={point.y - 4} />
                    </g>
                  ) : channel.is_used_in_photometry && !lowClean ? (
                    <circle
                      cx={point.x}
                      cy={point.y}
                      r={3}
                      fill={item.color}
                      stroke="var(--chart-bg, #171c20)"
                      strokeWidth={0.8}
                    />
                  ) : (
                    <rect
                      x={point.x - 3}
                      y={point.y - 3}
                      width={6}
                      height={6}
                      transform={`rotate(45 ${point.x} ${point.y})`}
                      fill="var(--chart-bg, #171c20)"
                      stroke="var(--chart-warning, #eac995)"
                      strokeWidth={1.4}
                    />
                  )}
                </g>
              );
            })}
          </g>
        );
      })}

      {/* Hover guide + custom tooltip. Both are pointer-events: none. */}
      {hovered ? (
        <>
          <line
            x1={hovered.x}
            x2={hovered.x}
            y1={MARGIN.top}
            y2={MARGIN.top + PLOT_H}
            stroke={hovered.color}
            strokeOpacity={0.3}
            strokeWidth={1}
            strokeDasharray="3 3"
            pointerEvents="none"
          />
          <circle
            cx={hovered.x}
            cy={hovered.y}
            r={5}
            fill="none"
            stroke={hovered.color}
            strokeWidth={1.4}
            pointerEvents="none"
          />
          <SpectrumTooltip point={hovered} width={WIDTH} />
        </>
      ) : null}

      {/* Axis labels */}
      <text
        x={MARGIN.left + PLOT_W / 2}
        y={HEIGHT - 8}
        textAnchor="middle"
        fill="var(--chart-muted, #b0b7b5)"
        fontSize={13}
        fontFamily="var(--font-body, sans-serif)"
      >
        Wavelength (µm)
      </text>
      <text
        x={14}
        y={MARGIN.top + PLOT_H / 2}
        textAnchor="middle"
        fill="var(--chart-muted, #b0b7b5)"
        fontSize={13}
        fontFamily="var(--font-body, sans-serif)"
        transform={`rotate(-90 14 ${MARGIN.top + PLOT_H / 2})`}
      >
        Flux (µJy)
      </text>
    </svg>
  );
}
