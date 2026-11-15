import type { OverlayKey } from "../hooks/useUrlState";
import { flagDescription, worstStatus } from "../lib/flags";
import type { SkyResponse } from "../lib/types";

export interface ArtifactShieldProps {
  manifest: SkyResponse;
  /** "all" while blinking, else the pinned epoch id. */
  pinnedEpoch: string;
  diff: boolean;
  overlays: OverlayKey[];
  onOverlay: (key: OverlayKey, enabled: boolean) => void;
}

/**
 * Data-quality shield. Renders the manifest's flag summary honestly: status
 * and active warning flags are target-aperture based; the artifact fraction
 * and the overlay are frame-wide (AGENTS.md §3.4, 2026-11-09 clarification).
 */
export function ArtifactShield({
  manifest,
  pinnedEpoch,
  diff,
  overlays,
  onOverlay,
}: ArtifactShieldProps) {
  const epochs = manifest.epochs;
  if (epochs.length === 0) {
    return (
      <section className="rail-section shield" aria-labelledby="shield-heading">
        <header className="section-head">
          <h2 id="shield-heading">Artifact shield</h2>
        </header>
        <p className="shield-body control-hint">
          No epochs were returned, so no flag summary exists.
        </p>
      </section>
    );
  }

  const pinned =
    pinnedEpoch !== "all"
      ? epochs.find((epoch) => epoch.epoch_id === pinnedEpoch) ?? null
      : null;
  const worst = epochs.reduce((current, epoch) => {
    const order = ["NOMINAL", "CAUTION", "ALERT"];
    return order.indexOf(epoch.flag_summary.status) >
      order.indexOf(current.flag_summary.status)
      ? epoch
      : current;
  }, epochs[0]);
  const focus = pinned ?? worst;
  const summary = focus.flag_summary;
  const status = summary.status;
  const scope = pinned
    ? `Pinned epoch ${focus.epoch_id}`
    : `Worst of ${epochs.length} epochs`;
  const warningFlags = summary.active_warning_flags;
  const fraction = summary.artifact_pixel_fraction;
  const overlayOn = overlays.includes("flags");
  const overallWorst = worstStatus(epochs.map((epoch) => epoch.flag_summary.status));

  return (
    <details className="rail-section shield" open>
      <summary>
        <h2 className="shield-summary-label" id="shield-heading">
          Artifact Shield
        </h2>
        <span
          className={`shield-badge shield-badge--${status.toLowerCase()}`}
          aria-label={`Flag status ${status}`}
        >
          {status}
        </span>
      </summary>

      <div className="shield-body">
        <p className="shield-scope">
          <span>{scope}</span>
          <span>{overallWorst !== status ? `overall ${overallWorst}` : "all epochs"}</span>
        </p>

        <div className="shield-facts">
          <div className="shield-fact">
            <span>Aperture flags</span>
            <strong>{warningFlags.length > 0 ? warningFlags.length : "none"}</strong>
          </div>
          <div className="shield-fact">
            <span>Frame artifacts</span>
            <strong>{(fraction * 100).toFixed(1)}%</strong>
          </div>
          <div className="shield-fact">
            <span>Source · bit 21</span>
            <strong>{summary.source_bit_set ? "set" : "not set"}</strong>
          </div>
          <div className="shield-fact">
            <span>Flag overlay</span>
            <strong>{overlayOn ? "on" : "off"}</strong>
          </div>
        </div>

        <div className="flag-chips" aria-label="Active warning flags in the target aperture">
          {warningFlags.length === 0 ? (
            <span className="flag-chip flag-chip--none">No aperture warning flags</span>
          ) : (
            warningFlags.map((flag) => (
              <span className="flag-chip" key={flag} title={flagDescription(flag)}>
                {flag}
              </span>
            ))
          )}
        </div>

        <button
          type="button"
          role="switch"
          aria-checked={overlayOn}
          className="switch-row"
          disabled={diff}
          onClick={() => onOverlay("flags", !overlayOn)}
          title={
            diff
              ? "Difference frames carry no flag overlay in the 1.0.0 contract."
              : "Show the union of ARTIFACT_WARNING_MASK bits across bands"
          }
        >
          <span>Frame-wide warning overlay</span>
          <span className="switch" aria-hidden="true" />
        </button>

        <details className="shield-more">
          <summary>Why {status}? Aperture &amp; frame-wide details</summary>
          <p className="shield-explanation">{summary.human_explanation}</p>

          {status === "ALERT" ? (
            <p className="shield-alert-note">
              Alert-level warning bit inside the 12.3″ target aperture. A
              data-quality condition — not a detection, probability, or discovery.
            </p>
          ) : status === "CAUTION" ? (
            <p className="shield-caution-note">
              DICHROIC/OUTLIER warning pixels, or a frame-wide artifact fraction
              above 1%. Inspect the flag layer before using the photometry.
            </p>
          ) : null}

          {fraction > 0.1 ? (
            <p className="shield-alert-note">
              Most of this frame carries a warning bit. The display keeps those
              pixels visible by design; photometry excludes them.
            </p>
          ) : null}

          {warningFlags.length > 0 ? (
            <ul className="shield-flag-defs">
              {warningFlags.map((flag) => (
                <li key={flag}>
                  <strong>{flag}</strong> — {flagDescription(flag)}
                </li>
              ))}
            </ul>
          ) : null}

          {epochs.length > 1 ? (
            <div className="shield-epochs" aria-label="Flag status by epoch">
              {epochs.map((epoch) => (
                <span
                  key={epoch.epoch_id}
                  className={`epoch-status epoch-status--${epoch.flag_summary.status.toLowerCase()}${
                    pinned?.epoch_id === epoch.epoch_id ? " epoch-status--active" : ""
                  }`}
                  title={`${epoch.date_iso} · ${epoch.flag_summary.human_explanation}`}
                >
                  {epoch.epoch_id} · {epoch.flag_summary.status}
                </span>
              ))}
            </div>
          ) : null}

          <p className="shield-footnote">
            {diff
              ? "Difference frames carry no flag overlay in the 1.0.0 contract."
              : "Aperture 12.3″: status & flags. Frame-wide: fraction & overlay. Amber pixels are a warning-bit union, never hidden by default."}
          </p>
        </details>
      </div>
    </details>
  );
}
