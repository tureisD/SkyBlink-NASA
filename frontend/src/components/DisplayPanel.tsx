import type { ColormapId } from "../lib/colormaps";
import { COLORMAPS } from "../lib/colormaps";
import type { StretchId } from "../lib/display";
import { STRETCHES } from "../lib/display";
import type { OverlayKey } from "../hooks/useUrlState";

export interface DisplayPanelProps {
  colormap: ColormapId;
  stretch: StretchId;
  contrast: number;
  bias: number;
  overlays: OverlayKey[];
  /** True when the manifest provides `reference_overlays.gaia_sources_url`. */
  gaiaAvailable: boolean;
  gaiaCount: number;
  /** True when any epoch carries `lvf_geometry`. */
  lvfAvailable: boolean;
  /** Difference mode: LVF geometry is not applicable to signed residuals. */
  diffMode: boolean;
  /** Current client-side field of view, degrees. */
  fov: number;
  onColormap: (colormap: ColormapId) => void;
  onStretch: (stretch: StretchId) => void;
  onContrast: (value: number) => void;
  onBias: (value: number) => void;
  onOverlay: (overlay: OverlayKey, enabled: boolean) => void;
  onFov: (size: number) => void;
  onResetView: () => void;
  /** Share state for the Copy link action. */
  copied: boolean;
  onCopy: () => void;
  onTriage: () => void;
}

const OVERLAY_LABELS: Array<{ key: OverlayKey; label: string; hint: string }> =
  [
    {
      key: "reticle",
      label: "Proper-motion reticle",
      hint: "Reference epoch → 2025.8 vector",
    },
    {
      key: "box",
      label: "Native pixel box",
      hint: "6.15″ (2 grid pixels at 3.075″/px)",
    },
    {
      key: "scale",
      label: "Scale bar",
      hint: "Arcsecond scale bar, zoom-aware",
    },
    {
      key: "compass",
      label: "Compass",
      hint: "North up, east left (cdelt1 < 0)",
    },
  ];

const FOV_PRESETS = [0.05, 0.1, 0.15, 0.2];

export function DisplayPanel({
  colormap,
  stretch,
  contrast,
  bias,
  overlays,
  gaiaAvailable,
  gaiaCount,
  lvfAvailable,
  diffMode,
  fov,
  onColormap,
  onStretch,
  onContrast,
  onBias,
  onOverlay,
  onFov,
  onResetView,
  copied,
  onCopy,
  onTriage,
}: DisplayPanelProps) {
  const customFov = !FOV_PRESETS.some((value) => Math.abs(value - fov) < 0.001);
  const stretchMeta = STRETCHES.find((entry) => entry.id === stretch);
  const gaiaEnabled = overlays.includes("gaia");

  return (
    <div className="display-panel" aria-label="Display controls">
      <section className="control-section" aria-labelledby="colormap-heading">
        <div className="control-head">
          <h2 className="control-name" id="colormap-heading">
            Colormap
          </h2>
          <span className="control-value">
            {COLORMAPS.find((entry) => entry.id === colormap)?.short}
          </span>
        </div>
        <div
          className="swatch-list"
          role="group"
          aria-labelledby="colormap-heading"
        >
          {COLORMAPS.map((entry) => (
            <button
              key={entry.id}
              type="button"
              className={colormap === entry.id ? "swatch is-active" : "swatch"}
              aria-pressed={colormap === entry.id}
              onClick={() => onColormap(entry.id)}
              title={
                entry.diverging
                  ? `${entry.label} — designed for difference frames (dark zero point)`
                  : entry.label
              }
            >
              <span
                className="swatch-bar"
                style={{ background: entry.css }}
                aria-hidden="true"
              />
              <span className="swatch-name">{entry.short}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="control-section" aria-labelledby="stretch-heading">
        <div className="control-head">
          <h2 className="control-name" id="stretch-heading">
            Stretch
          </h2>
        </div>
        <div
          className="segmented"
          role="group"
          aria-labelledby="stretch-heading"
        >
          {STRETCHES.map((entry) => (
            <button
              key={entry.id}
              type="button"
              className={stretch === entry.id ? "is-active" : undefined}
              aria-pressed={stretch === entry.id}
              onClick={() => onStretch(entry.id)}
              title={entry.description}
            >
              {entry.label}
            </button>
          ))}
        </div>
        <p className="control-hint">{stretchMeta?.description}</p>
      </section>

      <section className="control-section" aria-labelledby="transfer-heading">
        <div className="control-head">
          <h2 className="control-name" id="transfer-heading">
            Transfer
          </h2>
          <span className="control-value">display-only</span>
        </div>

        <div className="slider">
          <label className="slider-name" htmlFor="contrast">
            Contrast
          </label>
          <span className="slider-value">{contrast.toFixed(2)}×</span>
          <input
            id="contrast"
            className="range"
            type="range"
            min={0.4}
            max={2.6}
            step={0.01}
            value={contrast}
            onChange={(event) => onContrast(Number(event.target.value))}
          />
        </div>

        <div className="slider">
          <label className="slider-name" htmlFor="bias">
            Bias
          </label>
          <span className="slider-value">
            {bias >= 0 ? "+" : ""}
            {bias.toFixed(2)}
          </span>
          <input
            id="bias"
            className="range"
            type="range"
            min={-0.3}
            max={0.3}
            step={0.01}
            value={bias}
            onChange={(event) => onBias(Number(event.target.value))}
          />
        </div>
      </section>

      <section className="control-section" aria-labelledby="overlay-heading">
        <div className="control-head">
          <h2 className="control-name" id="overlay-heading">
            Overlays
          </h2>
        </div>
        {OVERLAY_LABELS.map((entry) => {
          const enabled = overlays.includes(entry.key);
          return (
            <button
              key={entry.key}
              type="button"
              role="switch"
              aria-checked={enabled}
              className="switch-row"
              title={entry.hint}
              onClick={() => onOverlay(entry.key, !enabled)}
            >
              <span>{entry.label}</span>
              <span className="switch" aria-hidden="true" />
            </button>
          );
        })}
        {gaiaAvailable ? (
          <button
            type="button"
            role="switch"
            aria-checked={gaiaEnabled}
            className="switch-row"
            title={`Gaia DR3 G ≤ 16: ${gaiaCount} pins. Vectors show 10-year catalog proper motion, not an epoch displacement; sub-pixel vectors are 5 px direction ticks.`}
            onClick={() => onOverlay("gaia", !gaiaEnabled)}
          >
            <span>Gaia G≤16 pins</span>
            <span className="switch" aria-hidden="true" />
          </button>
        ) : null}
        {gaiaAvailable && gaiaEnabled ? (
          <p className="control-hint">
            {gaiaCount} pin{gaiaCount === 1 ? "" : "s"} · PM ×10 yr (sub-px = 5
            px ticks)
            {" · Gaia DR3"}
          </p>
        ) : null}
        <button
          type="button"
          role="switch"
          aria-checked={overlays.includes("lvf")}
          className="switch-row"
          disabled={!lvfAvailable || diffMode}
          title={
            !lvfAvailable
              ? "No epoch in this manifest provides lvf_geometry; the overlay is hidden."
              : diffMode
                ? "Difference frames are fixed-frame; LVF geometry applies to epoch frames."
                : "Show six translucent schematic LVF gradient strips from epochs[].lvf_geometry (PA + µm/arcsec). No detector footprint is implied."
          }
          onClick={() => onOverlay("lvf", !overlays.includes("lvf"))}
        >
          <span>LVF dispersion overlay</span>
          <span className="switch" aria-hidden="true" />
        </button>
        {!lvfAvailable ? (
          <p className="control-hint">
            LVF geometry is not provided in this manifest. The overlay is hidden
            rather than assumed.
          </p>
        ) : null}
      </section>

      <section className="control-section" aria-labelledby="field-heading">
        <div className="control-head">
          <h2 className="control-name" id="field-heading">
            Field of view
          </h2>
          <span className="control-value">{fov.toFixed(2)}°</span>
        </div>
        <div
          className="field-presets"
          role="group"
          aria-label="Field of view presets"
        >
          {FOV_PRESETS.map((value) => (
            <button
              key={value}
              type="button"
              className={
                Math.abs(value - fov) < 0.001
                  ? "field-chip is-active"
                  : "field-chip"
              }
              aria-pressed={Math.abs(value - fov) < 0.001}
              onClick={() => onFov(value)}
            >
              {value.toFixed(2)}°
            </button>
          ))}
          {customFov ? (
            <button type="button" className="field-chip is-active" aria-pressed>
              {fov.toFixed(2)}°
            </button>
          ) : null}
        </div>
        <p className="control-hint">
          Client-side crop of the 240 × 240 output grid; the manifest WCS is
          unchanged.
        </p>
        <button
          type="button"
          className="btn btn--block btn--sm"
          style={{ marginTop: 8 }}
          onClick={onResetView}
        >
          Reset zoom &amp; pan
        </button>
      </section>

      <section
        className="control-section display-actions"
        aria-labelledby="actions-heading"
      >
        <div className="control-head">
          <h2 className="control-name" id="actions-heading">
            Share &amp; export
          </h2>
          <span className="control-value">session</span>
        </div>
        <div className="action-grid">
          <button
            type="button"
            className="btn btn--sm"
            onClick={onTriage}
            title="Export the selected observations, measurement availability and limits"
            aria-haspopup="dialog"
          >
            Evidence report
          </button>
          <button
            type="button"
            className={copied ? "btn btn--sm btn--accent" : "btn btn--sm"}
            onClick={onCopy}
            title="Copy a shareable URL that restores this view"
            aria-live="polite"
          >
            {copied ? "COPIED" : "Copy link"}
          </button>
        </div>
        <p className="control-hint">
          The report writes PNG + Markdown. Shared links restore view settings
          paused and check a recorded analysis identity when available.
        </p>
      </section>
    </div>
  );
}
