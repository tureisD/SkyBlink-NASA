import type { UrlState } from "../hooks/useUrlState";
import { MAX_FPS, MIN_FPS } from "../hooks/useUrlState";
import { BANDS } from "../lib/types";
export interface TimelineEpoch {
  id: string;
  label: string;
  date: string;
  status: "NOMINAL" | "CAUTION" | "ALERT";
}

export interface TimelineDockProps {
  state: UrlState;
  /** Band/frame keys that actually exist in the current mode. */
  availableBands: string[];
  epochs: TimelineEpoch[];
  canDiff: boolean;
  diffPairs: Array<{ key: string; label: string }>;
  activeDiffKey: string | null;
  onDiffPair: (key: string) => void;
  reducedMotion: boolean;
  pingpong: boolean;
  spectrumOpen: boolean;
  onPlay: () => void;
  onPause: () => void;
  onStep: (direction: -1 | 1) => void;
  onBand: (band: string) => void;
  onEpoch: (epoch: string) => void;
  onDiff: (diff: boolean) => void;
  onFps: (fps: number) => void;
  onPingpong: (pingpong: boolean) => void;
  onSpectrum: () => void;
  /** Index currently painted by the canvas rAF loop (blink playhead). */
  getActiveIndex?: () => number;
}

export function TimelineDock(p: TimelineDockProps) {
  const { state, epochs } = p;
  const paired =
    state.task === "compare" && state.comparisonLayout === "side-by-side";
  const multiple =
    epochs.length > 1 && new Set(epochs.map((e) => e.id)).size > 1;
  return (
    <section className="timeline-dock" aria-label="Observation controls">
      <div className="transport-row">
        <button
          className="btn"
          disabled={!multiple || state.diff || paired}
          aria-keyshortcuts="ArrowLeft"
          onClick={() => p.onStep(-1)}
        >
          Previous
        </button>
        <button
          className="btn btn--accent"
          disabled={!multiple || state.diff || p.reducedMotion}
          aria-keyshortcuts="Space"
          onClick={state.mode === "blink" ? p.onPause : p.onPlay}
        >
          {state.mode === "blink"
            ? "Pause"
            : paired
              ? "Switch to blink"
              : "Play blink"}
        </button>
        <button
          className="btn"
          disabled={!multiple || state.diff || paired}
          aria-keyshortcuts="ArrowRight"
          onClick={() => p.onStep(1)}
        >
          Next
        </button>
        <button className="btn" onClick={p.onSpectrum}>
          Spectrum
        </button>
      </div>
      <div className="observation-selectors">
        <label>
          Image bands
          <select
            aria-label="Image bands"
            value={state.bands}
            onChange={(e) => p.onBand(e.target.value)}
          >
            {p.availableBands.map((key) => (
              <option key={key} value={key}>
                {key === "all"
                  ? "Available bands combined"
                  : key === "thermal"
                    ? "Thermal: available B5/B6"
                    : (BANDS.find((b) => b.key === key)?.label ?? key)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Observation date
          <select
            aria-label="Observation date"
            value={state.epoch === "all" ? (epochs[0]?.id ?? "") : state.epoch}
            disabled={state.diff || state.mode === "blink" || paired}
            onChange={(e) => p.onEpoch(e.target.value)}
          >
            {epochs.map((e) => (
              <option key={e.id} value={e.id}>
                {e.date}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="supporting-copy">
        {p.reducedMotion
          ? "Reduced motion: playback disabled. Use manual steps or side by side."
          : !multiple
            ? "One observation available in this selection. Temporal comparison requires two."
            : "Playback is optional. Manual steps and side by side avoid flashing."}
      </p>
      {state.task === "compare" && (
        <div className="comparison-options">
          <label>
            <input
              type="checkbox"
              checked={state.diff}
              disabled={!p.canDiff}
              onChange={(e) => p.onDiff(e.target.checked)}
            />{" "}
            Difference (B minus A)
          </label>
          {state.diff && (
            <label>
              Recorded difference pair
              <select
                value={p.activeDiffKey ?? ""}
                onChange={(e) => p.onDiffPair(e.target.value)}
              >
                {p.diffPairs.map((pair) => (
                  <option key={pair.key} value={pair.key}>
                    {pair.label}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label>
            Playback rate
            <select
              value={state.fps}
              onChange={(e) => p.onFps(Number(e.target.value))}
            >
              {Array.from(
                { length: MAX_FPS - MIN_FPS + 1 },
                (_, i) => i + MIN_FPS,
              ).map((fps) => (
                <option key={fps} value={fps}>
                  {fps} frames / second
                </option>
              ))}
            </select>
          </label>
          <label>
            <input
              type="checkbox"
              checked={p.pingpong}
              onChange={(e) => p.onPingpong(e.target.checked)}
            />{" "}
            Reverse at end
          </label>
          {state.diff && (
            <p>
              Signed residual display: blue is negative, neutral is zero, red is
              positive with the cool-warm map. Historical saved differences
              remain unvalidated.
            </p>
          )}
        </div>
      )}
    </section>
  );
}
