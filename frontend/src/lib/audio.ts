/**
 * Native Web Audio sonification (F6), no external dependency.
 *
 * Documented mapping:
 *   wavelength 0.75–5.0 µm  →  220–1760 Hz  (three octaves, linear in λ)
 *   channel gain            ∝  relative clean-channel flux
 *   hard-bad / null         →  muted (never represented as a tone)
 *   low-clean (clean <0.8)  →  distinctly attenuated (×0.25)
 *
 * The engine is a module-level singleton so the rAF blink loop can request an
 * epoch tick without React re-renders. Audio starts only after an explicit user
 * gesture; `prefers-reduced-motion` disables epoch ticks, not the user-initiated
 * spectrum sweep. This is accessibility/exploratory audio, not a detection.
 */

import type { SpectrumChannel, SpectrumResponse } from "./types";

export const AUDIO_WAVELENGTH_MIN_UM = 0.75;
export const AUDIO_WAVELENGTH_MAX_UM = 5.0;
export const AUDIO_PITCH_MIN_HZ = 220;
export const AUDIO_PITCH_MAX_HZ = 1760;
export const AUDIO_CHANNEL_MS = 110;
const AUDIO_TONE_MS = 95;
const AUDIO_GAIN_MAX = 0.11;

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/** Linear-in-wavelength mapping onto a three-octave pitch range. */
export function wavelengthToHz(wavelengthUm: number): number {
  const t = clamp(
    (wavelengthUm - AUDIO_WAVELENGTH_MIN_UM) /
      (AUDIO_WAVELENGTH_MAX_UM - AUDIO_WAVELENGTH_MIN_UM),
    0,
    1,
  );
  return AUDIO_PITCH_MIN_HZ * 2 ** (t * 3);
}

export interface SweepInfo {
  epochId: string;
  channels: number;
  muted: number;
  attenuated: number;
  durationMs: number;
}

type AudioContextCtor = typeof AudioContext;

function audioContextCtor(): AudioContextCtor | null {
  if (typeof window === "undefined") return null;
  const candidate =
    window.AudioContext ??
    (window as unknown as { webkitAudioContext?: AudioContextCtor })
      .webkitAudioContext;
  return candidate ?? null;
}

function channelIsMuted(channel: SpectrumChannel): boolean {
  return (
    channel.is_flagged_bad ||
    channel.flux_ujy === null ||
    !Number.isFinite(channel.flux_ujy)
  );
}

function channelGainScale(channel: SpectrumChannel): number {
  const lowClean =
    !channel.is_used_in_photometry || channel.clean_fraction < 0.8;
  return lowClean ? 0.25 : 1;
}

export class SpectrumAudioEngine {
  private context: AudioContext | null = null;
  private master: GainNode | null = null;
  private spectrum: SpectrumResponse | null = null;
  private volume = 0.55;
  private muted = false;
  private enabled = false;
  private tickEnabled = false;
  private live = new Set<AudioScheduledSourceNode>();
  private cleanupTimers = new Set<number>();

  isEnabled(): boolean {
    return this.enabled;
  }

  getVolume(): number {
    return this.volume;
  }

  isMuted(): boolean {
    return this.muted;
  }

  isTickEnabled(): boolean {
    return this.tickEnabled;
  }

  hasSpectrum(): boolean {
    return this.spectrum !== null;
  }

  /** Must be called from a user gesture (click) for reliable autoplay policy. */
  async enable(): Promise<boolean> {
    const Ctor = audioContextCtor();
    if (!Ctor) return false;
    try {
      if (!this.context) {
        this.context = new Ctor();
        this.master = this.context.createGain();
        this.master.gain.value = this.muted ? 0 : this.volume;
        this.master.connect(this.context.destination);
      }
      if (this.context.state === "suspended") {
        await this.context.resume();
      }
      this.enabled = this.context.state === "running";
      return this.enabled;
    } catch {
      this.enabled = false;
      return false;
    }
  }

  disable(): void {
    this.stopAll();
    this.enabled = false;
    if (this.context && this.context.state === "running") {
      void this.context.suspend().catch(() => undefined);
    }
  }

  setVolume(value: number): void {
    this.volume = clamp(value, 0, 1);
    if (this.master && this.context) {
      this.master.gain.setTargetAtTime(
        this.muted ? 0 : this.volume,
        this.context.currentTime,
        0.02,
      );
    }
  }

  setMuted(value: boolean): void {
    this.muted = value;
    if (this.master && this.context) {
      this.master.gain.setTargetAtTime(
        this.muted ? 0 : this.volume,
        this.context.currentTime,
        0.02,
      );
    }
  }

  setSpectrum(spectrum: SpectrumResponse | null): void {
    if (spectrum === null) this.stopAll();
    this.spectrum = spectrum;
  }

  setTickEnabled(value: boolean): void {
    this.tickEnabled = value;
  }

  private note(
    frequencyHz: number,
    gainValue: number,
    startAt: number,
    durationSeconds: number,
    pan: number | null = null,
  ): void {
    const ctx = this.context;
    const master = this.master;
    if (!ctx || !master) return;
    const oscillator = ctx.createOscillator();
    const gain = ctx.createGain();
    oscillator.type = "sine";
    oscillator.frequency.setValueAtTime(frequencyHz, startAt);
    const peak = Math.max(0.0002, gainValue);
    gain.gain.setValueAtTime(0.0001, startAt);
    gain.gain.exponentialRampToValueAtTime(peak, startAt + 0.012);
    gain.gain.exponentialRampToValueAtTime(
      0.0001,
      startAt + durationSeconds,
    );
    oscillator.connect(gain);
    if (pan !== null && typeof ctx.createStereoPanner === "function") {
      const panner = ctx.createStereoPanner();
      panner.pan.setValueAtTime(clamp(pan, -1, 1), startAt);
      gain.connect(panner);
      panner.connect(master);
    } else {
      gain.connect(master);
    }
    oscillator.start(startAt);
    oscillator.stop(startAt + durationSeconds + 0.02);
    this.live.add(oscillator);
    oscillator.onended = () => {
      this.live.delete(oscillator);
    };
  }

  /**
   * Schedule one sweep of the active (or requested) spectrum epoch. Returns
   * after scheduling, not after playback; the UI shows the duration.
   */
  async sweep(epochId?: string): Promise<SweepInfo | null> {
    if (!this.enabled || !this.context || !this.master) return null;
    if (this.context.state === "suspended") {
      try {
        await this.context.resume();
      } catch {
        return null;
      }
    }
    const spectrum = this.spectrum;
    if (!spectrum || spectrum.epochs.length === 0) return null;
    const epoch =
      spectrum.epochs.find((entry) => entry.epoch_id === epochId) ??
      spectrum.epochs[0];
    const all = epoch.channels
      .slice()
      .sort((a, b) => a.wavelength_um - b.wavelength_um);
    const tonal = all.filter((channel) => !channelIsMuted(channel));
    if (tonal.length === 0) return null;
    const maxFlux = Math.max(
      ...tonal.map((channel) => Math.abs(channel.flux_ujy ?? 0)),
      1e-6,
    );

    this.stopAll();
    const ctx = this.context;
    const startBase = ctx.currentTime + 0.05;
    let attenuated = 0;
    tonal.forEach((channel, index) => {
      const flux = Math.abs(channel.flux_ujy ?? 0);
      const relative = clamp(flux / maxFlux, 0, 1);
      const scale = channelGainScale(channel);
      if (scale < 1) attenuated += 1;
      const gainValue = (0.018 + AUDIO_GAIN_MAX * relative) * scale;
      this.note(
        wavelengthToHz(channel.wavelength_um),
        Math.max(0.0006, gainValue),
        startBase + index * (AUDIO_CHANNEL_MS / 1000),
        AUDIO_TONE_MS / 1000,
      );
    });

    const durationMs = tonal.length * AUDIO_CHANNEL_MS + AUDIO_TONE_MS + 250;
    const timer = window.setTimeout(() => {
      this.cleanupTimers.delete(timer);
    }, durationMs);
    this.cleanupTimers.add(timer);

    return {
      epochId: epoch.epoch_id,
      channels: tonal.length,
      muted: all.length - tonal.length,
      attenuated,
      durationMs,
    };
  }

  /**
   * Short epoch tick. Gain follows the epoch's clean-channel mean flux relative
   * to the other epochs; stereo pan follows the caller's displayed centroid
   * displacement. No spectrum → no tick (never invent a value).
   */
  maybeTick(epochId: string, pan: number): void {
    if (!this.enabled || !this.tickEnabled) return;
    if (!this.spectrum || !this.context || !this.master) return;
    const epoch = this.spectrum.epochs.find((entry) => entry.epoch_id === epochId);
    if (!epoch) return;
    const means = this.spectrum.epochs.map((entry) => {
      const fluxes = entry.channels
        .filter(
          (channel) =>
            channel.flux_ujy !== null &&
            Number.isFinite(channel.flux_ujy) &&
            !channel.is_flagged_bad,
        )
        .map((channel) => Math.abs(channel.flux_ujy ?? 0));
      return fluxes.length > 0
        ? fluxes.reduce((total, value) => total + value, 0) / fluxes.length
        : null;
    });
    const finite = means.filter((value): value is number => value !== null);
    const mean = means[this.spectrum.epochs.indexOf(epoch)];
    if (mean === null || finite.length === 0) return;
    const lo = Math.min(...finite);
    const hi = Math.max(...finite);
    const normalized = hi > lo ? (mean - lo) / (hi - lo) : 0.5;
    this.note(
      720,
      0.025 + 0.07 * normalized,
      this.context.currentTime + 0.01,
      0.075,
      clamp(pan, -1, 1),
    );
    this.setTickPanNote(pan);
  }

  private lastTickPan = 0;

  private setTickPanNote(pan: number): void {
    this.lastTickPan = clamp(pan, -1, 1);
  }

  getLastTickPan(): number {
    return this.lastTickPan;
  }

  stopAll(): void {
    for (const node of this.live) {
      try {
        node.stop();
      } catch {
        // Already stopped.
      }
    }
    this.live.clear();
    for (const timer of this.cleanupTimers) window.clearTimeout(timer);
    this.cleanupTimers.clear();
  }
}

export const spectrumAudio = new SpectrumAudioEngine();
