import { useEffect, useLayoutEffect, useMemo, useState } from "react";
import type { LiveSource } from "../lib/api";
import {
  AUDIO_PITCH_MAX_HZ,
  AUDIO_PITCH_MIN_HZ,
  AUDIO_WAVELENGTH_MAX_UM,
  AUDIO_WAVELENGTH_MIN_UM,
  spectrumAudio,
} from "../lib/audio";
import { useSpectrum } from "../hooks/useSpectrum";
import type { SkyResponse } from "../lib/types";

export interface AudioPanelProps {
  manifest: SkyResponse;
  discoveryOverride: "inherit" | "known";
  skySource: LiveSource | null;
  reducedMotion: boolean;
}

/**
 * Web Audio sonification panel. Audio is created only after the explicit
 * "Enable audio" click. The spectrum sweep is user-initiated; epoch ticks are
 * optional and disabled when `prefers-reduced-motion` is set. Exploratory
 * accessibility audio — never a detection.
 */
export function AudioPanel({
  manifest,
  discoveryOverride,
  skySource,
  reducedMotion,
}: AudioPanelProps) {
  const [armed, setArmed] = useState(() => spectrumAudio.isEnabled());
  const [enabled, setEnabled] = useState(() => spectrumAudio.isEnabled());
  const [volume, setVolume] = useState(() => spectrumAudio.getVolume());
  const [muted, setMuted] = useState(() => spectrumAudio.isMuted());
  const [tickEnabled, setTickEnabled] = useState(() =>
    spectrumAudio.isTickEnabled(),
  );
  const [status, setStatus] = useState(() =>
    spectrumAudio.isEnabled()
      ? "Audio running — choose a sweep or epoch ticks."
      : "Audio off — audio starts only after an explicit click.",
  );

  const query = useMemo(
    () => ({
      ra: manifest.query.ra,
      dec: manifest.query.dec,
      target: manifest.query.target_id,
      discovery:
        discoveryOverride === "known"
          ? ("known" as const)
          : (manifest.provenance.discovery_mode ?? "live"),
    }),
    [
      manifest.query.ra,
      manifest.query.dec,
      manifest.query.target_id,
      manifest.provenance.discovery_mode,
      discoveryOverride,
    ],
  );
  const spectrumState = useSpectrum(query, skySource, armed);

  useLayoutEffect(() => {
    spectrumAudio.setSpectrum(spectrumState.spectrum);
    if (!spectrumState.spectrum) return;
    if (enabled) {
      setStatus(
        `Spectrum ready · ${spectrumState.spectrum.epochs.reduce(
          (total, epoch) => total + epoch.channels.length,
          0,
        )} channels. Sweep or enable epoch ticks.`,
      );
    }
  }, [spectrumState.spectrum, enabled]);

  useEffect(() => {
    if (!reducedMotion) return;
    spectrumAudio.setTickEnabled(false);
    setTickEnabled(false);
  }, [reducedMotion]);

  const handleEnable = async () => {
    const ok = await spectrumAudio.enable();
    setArmed(true);
    setEnabled(ok);
    setStatus(
      ok
        ? "Audio running — loading the spectrum; then sweep or enable epoch ticks."
        : "Web Audio is unavailable in this browser.",
    );
  };

  const handleSweep = async () => {
    const info = await spectrumAudio.sweep();
    if (!info) {
      setStatus(
        "Sweep unavailable — enable audio and wait for spectrum channels.",
      );
      return;
    }
    setStatus(
      `Sweep ${info.epochId}: ${info.channels} channels · ${info.muted} muted · ${info.attenuated} attenuated · ${(info.durationMs / 1000).toFixed(1)} s`,
    );
  };

  const handleStop = () => {
    spectrumAudio.stopAll();
    setStatus("Audio stopped. No automatic playback.");
  };

  const toggleTick = () => {
    if (reducedMotion) return;
    const next = !tickEnabled;
    spectrumAudio.setTickEnabled(next);
    setTickEnabled(next);
    setStatus(
      next
        ? "Epoch ticks on — gain follows relative flux; pan follows catalog motion."
        : "Epoch ticks off.",
    );
  };

  const channelCount = spectrumState.spectrum
    ? spectrumState.spectrum.epochs.reduce(
        (total, epoch) => total + epoch.channels.length,
        0,
      )
    : 0;

  return (
    <details className="rail-section audio-panel">
      <summary>
        <span>Audio sonification</span>
        <span
          className={`audio-badge ${enabled ? "audio-badge--on" : ""}`}
          data-audio-enabled={enabled ? "1" : "0"}
        >
          {enabled ? "ON" : "OFF"}
        </span>
      </summary>
      <div className="audio-body">
        <p className="control-hint">
          Exploratory accessibility audio — not a detection. Native Web Audio;
          no external dependency.
        </p>
        <div className="audio-actions">
          {!enabled ? (
            <button
              type="button"
              className="btn btn--accent btn--sm"
              onClick={handleEnable}
            >
              Enable audio
            </button>
          ) : (
            <>
              <button
                type="button"
                className="btn btn--accent btn--sm"
                onClick={handleSweep}
                disabled={!spectrumState.spectrum || channelCount === 0}
              >
                Sweep spectrum
              </button>
              <button
                type="button"
                className="btn btn--sm"
                onClick={handleStop}
              >
                Stop
              </button>
            </>
          )}
        </div>

        <div className="slider audio-slider">
          <label className="slider-name" htmlFor="audio-volume">
            Volume
          </label>
          <span className="slider-value">{Math.round(volume * 100)}%</span>
          <input
            id="audio-volume"
            className="range"
            type="range"
            min={0}
            max={1}
            step={0.01}
            value={volume}
            onChange={(event) => {
              const next = Number(event.target.value);
              setVolume(next);
              spectrumAudio.setVolume(next);
            }}
          />
        </div>

        <button
          type="button"
          role="switch"
          aria-checked={muted}
          className="switch-row"
          onClick={() => {
            const next = !muted;
            setMuted(next);
            spectrumAudio.setMuted(next);
          }}
        >
          <span>Mute</span>
          <span className="switch" aria-hidden="true" />
        </button>

        <button
          type="button"
          role="switch"
          aria-checked={tickEnabled}
          className="switch-row"
          disabled={!enabled || reducedMotion || !spectrumState.spectrum}
          onClick={toggleTick}
          title={
            reducedMotion
              ? "prefers-reduced-motion: epoch ticks are disabled."
              : "Play a short tick on each visible epoch change; gain follows relative flux."
          }
        >
          <span>Blink epoch ticks</span>
          <span className="switch" aria-hidden="true" />
        </button>
        {reducedMotion ? (
          <p className="control-hint">
            prefers-reduced-motion is set: epoch ticks are disabled. A manual
            spectrum sweep is still available after a click.
          </p>
        ) : null}

        <div className="audio-status mono" role="status" aria-live="polite">
          {spectrumState.status === "loading"
            ? "Loading spectrum channels…"
            : spectrumState.status === "error"
              ? spectrumState.error
              : status}
        </div>

        <dl className="audio-map">
          <div>
            <dt>Pitch</dt>
            <dd>
              λ {AUDIO_WAVELENGTH_MIN_UM.toFixed(2)}–
              {AUDIO_WAVELENGTH_MAX_UM.toFixed(2)} µm → {AUDIO_PITCH_MIN_HZ}–
              {AUDIO_PITCH_MAX_HZ} Hz (3 octaves)
            </dd>
          </div>
          <div>
            <dt>Gain</dt>
            <dd>∝ relative clean-channel flux</dd>
          </div>
          <div>
            <dt>Flags</dt>
            <dd>hard-bad/null muted · low-clean ×0.25</dd>
          </div>
          <div>
            <dt>Epoch tick</dt>
            <dd>
              gain ∝ relative mean flux · pan ∝ candidate centroid, else catalog
              motion
            </dd>
          </div>
        </dl>
      </div>
    </details>
  );
}
