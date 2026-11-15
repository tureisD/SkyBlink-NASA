import { useMemo } from "react";
import type { SkyResponse } from "../lib/types";
import {
  catalogDistanceAu,
  formatSigned,
  formatSignedYears,
  parallaxGridPixels,
  parallaxPeakToPeakArcsec,
  parallaxPeakToPeakGridPixels,
  parallaxSemiAmplitudeArcsec,
  TEST_DISTANCE_AU,
  trialShiftGridPixels,
} from "../lib/trial";

export interface TrialMotionPanelProps {
  manifest: SkyResponse;
  band: string;
  diff: boolean;
  track: boolean;
  pmRa: number;
  pmDec: number;
  catalogPmRa: number;
  catalogPmDec: number;
  parallax: boolean;
  distanceAu: number;
  onTrack: (track: boolean) => void;
  onPm: (axis: "ra" | "dec", value: number) => void;
  onParallax: (enabled: boolean) => void;
  onDistance: (au: number) => void;
  onReset: () => void;
}

function distanceLabel(au: number): string {
  if (au >= 1e6) return `${(au / 1e6).toFixed(2)} M AU`;
  if (au >= 1e3) return `${(au / 1e3).toFixed(1)}k AU`;
  return `${au.toFixed(0)} AU`;
}

/**
 * Trial-motion / parallax sandbox. This is explicitly a visualization: locking
 * a trial vector is not a detection. All shifts are display-only and never
 * change the frames or their server-side normalization.
 */
export function TrialMotionPanel({
  manifest,
  band,
  diff,
  track,
  pmRa,
  pmDec,
  catalogPmRa,
  catalogPmDec,
  parallax,
  distanceAu,
  onTrack,
  onPm,
  onParallax,
  onDistance,
  onReset,
}: TrialMotionPanelProps) {
  const wcs = manifest.wcs;
  const epochs = manifest.epochs.filter(
    (entry) => typeof entry.frames[band] === "string",
  );
  const shifts = epochs.map((entry) => ({
    epoch: entry,
    ...trialShiftGridPixels(wcs, entry.mjd_mean, pmRa, pmDec),
  }));
  const maxShift = shifts.reduce(
    (current, entry) => Math.max(current, Math.hypot(entry.dxPx, entry.dyPx)),
    0,
  );
  const dtSpan = useMemo(() => {
    if (shifts.length < 2) return 0;
    const times = shifts.map((entry) => entry.dtYears);
    return Math.max(...times) - Math.min(...times);
  }, [shifts]);

  const semiArcsec = parallaxSemiAmplitudeArcsec(distanceAu);
  const peakArcsec = parallaxPeakToPeakArcsec(distanceAu);
  const semiPx = parallaxGridPixels(wcs, distanceAu);
  const peakPx = parallaxPeakToPeakGridPixels(wcs, distanceAu);
  const subPixel = peakPx < 1;
  const targetId = manifest.query.target_id ?? manifest.target?.id ?? null;
  const catalogAu = catalogDistanceAu(targetId);

  return (
    <section className="rail-section trial" aria-labelledby="trial-heading">
      <header className="section-head trial-head">
        <h2 id="trial-heading">Trial motion</h2>
        <span className="trial-tag">sandbox</span>
      </header>
      <div className="trial-body">
        <div
          className="segmented trial-mode"
          role="group"
          aria-label="Trial-motion reference frame"
        >
          <button
            type="button"
            className={track ? undefined : "is-active"}
            aria-pressed={!track}
            onClick={() => onTrack(false)}
            title="Sky-fixed ICRS: no trial shift; the catalog target moves across epochs."
          >
            Sky-fixed · ICRS
          </button>
          <button
            type="button"
            className={track ? "is-active" : undefined}
            aria-pressed={track}
            disabled={diff}
            onClick={() => onTrack(true)}
            title={
              diff
                ? "Difference frames are a single fixed-frame residual."
                : "Target co-moving: shift each epoch by the trial μ × ΔMJD."
            }
          >
            Target co-moving
          </button>
        </div>

        {track ? (
          <p className="trial-warning" role="note">
            Trial-Motion Visualization — not a detection. A visual lock is not a
            significance test.
          </p>
        ) : null}
        {diff ? (
          <p className="control-hint">
            Difference mode is fixed-frame; tracking applies only to epoch
            frames.
          </p>
        ) : null}

        <div className="trial-readout mono" aria-live="polite">
          <span>
            max |shift|{" "}
            <strong>
              {maxShift.toFixed(2)} px = {(maxShift * wcs.pixel_scale_arcsec).toFixed(1)}″
            </strong>
          </span>
          <span>
            Δt span{" "}
            <strong>{formatSignedYears(dtSpan, 2)}</strong> over {shifts.length}{" "}
            epoch{shifts.length === 1 ? "" : "s"}
          </span>
          <span>
            μ trial{" "}
            <strong>
              {formatSigned(pmRa, 0)}, {formatSigned(pmDec, 0)} mas/yr
            </strong>
          </span>
        </div>

        <div className="slider">
          <label className="slider-name" htmlFor="trial-pmra">
            μ α* trial
          </label>
          <span className="slider-value">
            {formatSigned(pmRa, 0)} mas/yr
          </span>
          <input
            id="trial-pmra"
            className="range"
            type="range"
            min={-12000}
            max={12000}
            step={10}
            value={Math.round(pmRa)}
            onChange={(event) => onPm("ra", Number(event.target.value))}
          />
        </div>
        <div className="slider">
          <label className="slider-name" htmlFor="trial-pmdec">
            μ δ trial
          </label>
          <span className="slider-value">
            {formatSigned(pmDec, 0)} mas/yr
          </span>
          <input
            id="trial-pmdec"
            className="range"
            type="range"
            min={-12000}
            max={12000}
            step={10}
            value={Math.round(pmDec)}
            onChange={(event) => onPm("dec", Number(event.target.value))}
          />
        </div>

        <div className="trial-actions">
          <button
            type="button"
            className="btn btn--sm"
            onClick={onReset}
            disabled={!manifest.target}
            title="Restore the catalog proper motion from the manifest target record"
          >
            Catalog PM
          </button>
          <span className="trial-note mono">
            {formatSigned(catalogPmRa, 1)}, {formatSigned(catalogPmDec, 1)}
          </span>
        </div>

        <div className="trial-divider" />

        <button
          type="button"
          role="switch"
          aria-checked={parallax}
          className="switch-row"
          onClick={() => onParallax(!parallax)}
          title="Show the annual parallax reflex circle and the six-month 2ϖ peak-to-peak scale."
        >
          <span>Parallax reflex (2 AU)</span>
          <span className="switch" aria-hidden="true" />
        </button>

        {parallax ? (
          <div className="parallax-block">
            <div className="parallax-row">
              <label className="parallax-label" htmlFor="parallax-distance">
                Distance
              </label>
              <input
                id="parallax-distance"
                className="num-input mono"
                type="number"
                min={0.1}
                max={1e9}
                step={10}
                value={Math.round(distanceAu)}
                onChange={(event) => {
                  const next = Number(event.target.value);
                  if (Number.isFinite(next) && next > 0) onDistance(next);
                }}
              />
              <span className="parallax-unit mono">AU</span>
            </div>
            <div className="parallax-presets">
              <button
                type="button"
                className={
                  Math.abs(distanceAu - TEST_DISTANCE_AU) < 0.5
                    ? "field-chip is-active"
                    : "field-chip"
                }
                onClick={() => onDistance(TEST_DISTANCE_AU)}
                title="The documented sandbox test distance"
              >
                400 AU test
              </button>
              {catalogAu ? (
                <button
                  type="button"
                  className={
                    Math.abs(distanceAu - catalogAu) < 1
                      ? "field-chip is-active"
                      : "field-chip"
                  }
                  onClick={() => onDistance(catalogAu)}
                  title="Catalog distance from ROADMAP Appendix A"
                >
                  Catalog · {distanceLabel(catalogAu)}
                </button>
              ) : null}
            </div>
            <div className="parallax-readout mono">
              <span>
                ϖ <strong>{semiArcsec.toFixed(2)}″</strong>
              </span>
              <span>
                2ϖ <strong>{peakArcsec.toFixed(2)}″</strong>
              </span>
              <span>
                {semiPx.toFixed(2)} px semiaxis · {peakPx.toFixed(2)} px p-p
              </span>
            </div>
            {subPixel ? (
              <p className="parallax-flag" role="note">
                Sub-pixel on-sky reflex ({peakPx.toFixed(2)} grid px at{" "}
                {wcs.pixel_scale_arcsec.toFixed(3)}″/px). The canvas shows a
                labelled astrometric inset; it never implies a 1-px on-sky
                motion.
              </p>
            ) : (
              <p className="control-hint">
                The dashed circle is the annual semi-amplitude ϖ drawn at true
                scale; 2ϖ is the six-month peak-to-peak reflex shift. A 2 AU
                baseline is used, not a detection claim.
              </p>
            )}
            <p className="control-hint">
              ϖ is the annual semi-amplitude; 2ϖ is the 6-month peak-to-peak
              reflex shift. The overlay is a geometric reference, not a parallax
              measurement.
            </p>
          </div>
        ) : null}
      </div>
    </section>
  );
}
