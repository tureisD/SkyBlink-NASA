import { useEffect, useMemo, useState } from "react";
import type { GaiaCatalogState } from "../hooks/useGaiaSources";
import { useSpectrum } from "../hooks/useSpectrum";
import type { LiveSource } from "../lib/api";
import {
  buildTriageCard,
  copyText,
  downloadBlob,
  selectTriageEpochs,
  selectSpectrumForReport,
} from "../lib/triage";
import type { TriageCardResult } from "../lib/triage";
import type { SkyResponse } from "../lib/types";

export interface TriageModalProps {
  manifest: SkyResponse;
  discoveryOverride: "inherit" | "known";
  band: string;
  diffKey: string | null;
  epochA?: string | null;
  epochB?: string | null;
  skySource: LiveSource | null;
  gaia: GaiaCatalogState;
  shareUrl: () => string;
  onClose: () => void;
}

/**
 * Generates and previews the dynamic-channel triage card. The PNG and Markdown
 * are produced from the loaded manifest + spectrum; missing data is reported as
 * "not available". The spectrum title always carries the real channel count.
 */
export function TriageModal({
  manifest,
  discoveryOverride,
  band,
  diffKey,
  epochA = null,
  epochB = null,
  skySource,
  gaia,
  shareUrl,
  onClose,
}: TriageModalProps) {
  const [result, setResult] = useState<TriageCardResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [attempt, setAttempt] = useState(0);
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
  const spectrumState = useSpectrum(query, skySource, true);

  useEffect(() => {
    setResult(null);
    setError(null);
    if (spectrumState.status === "loading" || spectrumState.status === "idle") {
      return;
    }
    let cancelled = false;
    let generated: TriageCardResult | null = null;
    // Selection errors belong to the visible report error state, not an
    // uncaught effect. Retrying regenerates from the current selection.
    void Promise.resolve()
      .then(() => {
        const selection = selectTriageEpochs(
          manifest,
          band,
          diffKey,
          epochA,
          epochB,
        );
        const selectedIds = new Set(
          selection.epochs.map((epoch) => epoch.epoch_id),
        );
        const selectedSpectrum = selectSpectrumForReport(
          manifest,
          spectrumState.spectrum,
          selectedIds,
        );
        return buildTriageCard({
          ...selection,
          manifest,
          spectrum: selectedSpectrum,
          spectrumEpochOrder: spectrumState.spectrum?.epochs.map(
            (epoch) => epoch.epoch_id,
          ),
          gaia,
          shareUrl: shareUrl(),
        });
      })
      .then((next) => {
        if (cancelled) URL.revokeObjectURL(next.pngUrl);
        else {
          generated = next;
          setResult(next);
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : String(cause));
        }
      });
    return () => {
      cancelled = true;
      if (generated) URL.revokeObjectURL(generated.pngUrl);
    };
  }, [
    manifest,
    discoveryOverride,
    band,
    diffKey,
    epochA,
    epochB,
    attempt,
    gaia,
    shareUrl,
    spectrumState.status,
    spectrumState.spectrum,
  ]);

  const handleCopy = async () => {
    if (!result) return;
    const ok = await copyText(result.markdown);
    setCopied(ok);
    if (ok) window.setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="triage" data-channel-count={result?.channelCount ?? ""}>
      <header className="drawer-head">
        <div>
          <p className="drawer-kicker">Dynamic-channel triage card</p>
          <h2 id="triage-title">4-panel PNG + Markdown report</h2>
          <p className="drawer-sub">
            Epoch A · Epoch B · difference · spectrum. Missing data is written
            as “not available”; nothing is invented.
          </p>
          <p className="control-hint">
            The PNG uses full-frame server previews for the selected
            observations and band. Camera, display adjustments, and trial
            overlays are restored by the share link, not painted into this
            report.
          </p>
        </div>
        <button
          type="button"
          className="icon-btn"
          onClick={onClose}
          aria-label="Close triage card"
        >
          ✕
        </button>
      </header>

      {!result && !error ? (
        <div className="drawer-status" role="status">
          <span className="spinner" aria-hidden="true" />
          Building the PNG and Markdown from the manifest
          {spectrumState.status === "loading" ? " and spectrum" : ""}…
          {spectrumState.status === "loading" ? (
            <button
              type="button"
              className="btn"
              onClick={spectrumState.cancel}
            >
              Continue without spectrum
            </button>
          ) : null}
        </div>
      ) : null}
      {spectrumState.status === "error" ||
      spectrumState.status === "cancelled" ? (
        <p role="status" className="control-hint">
          Spectrum unavailable in this report:{" "}
          {spectrumState.error ??
            "browser waiting was cancelled; already-started server work may continue"}
          .
          <button type="button" className="btn" onClick={spectrumState.reload}>
            Retry spectrum
          </button>
        </p>
      ) : null}

      {error ? (
        <div className="drawer-error" role="alert">
          <p>{error}</p>
          <button
            type="button"
            className="btn"
            onClick={() => setAttempt((value) => value + 1)}
          >
            Retry report
          </button>
          <p className="control-hint">
            The card was not generated. Close and retry once the manifest and
            spectrum endpoints are available.
          </p>
        </div>
      ) : null}

      {result ? (
        <>
          <div className="triage-meta mono">
            <span>1600 × 1180 px · 4 panels</span>
            <span>{result.channelCount}-channel SPHEREx spectrum</span>
            <span>Exploratory comparison; no detection established</span>
          </div>
          <div className="triage-preview">
            <img
              src={result.pngUrl}
              alt={`Evidence report for ${manifest.target?.name ?? "the sky field"}: selected observation panels, a difference when available, and ${result.channelCount} recorded spectrum samples. Unavailable panels are labeled.`}
            />
          </div>
          <div className="triage-actions">
            <button
              type="button"
              className="btn btn--accent btn--sm"
              onClick={() =>
                downloadBlob(result.pngBlob, `${result.filenameBase}.png`)
              }
            >
              Download PNG
            </button>
            <button
              type="button"
              className="btn btn--sm"
              onClick={() =>
                downloadBlob(
                  new Blob([result.markdown], {
                    type: "text/markdown;charset=utf-8",
                  }),
                  `${result.filenameBase}.md`,
                )
              }
            >
              Download Markdown
            </button>
            <button type="button" className="btn btn--sm" onClick={handleCopy}>
              {copied ? "COPIED" : "Copy Markdown"}
            </button>
          </div>
          <div className="triage-report-wrap">
            <div className="triage-report-head mono">
              Markdown report · {result.channelCount} samples · shared view
              recipe
            </div>
            <pre className="triage-report">{result.markdown}</pre>
          </div>
        </>
      ) : null}
    </div>
  );
}
