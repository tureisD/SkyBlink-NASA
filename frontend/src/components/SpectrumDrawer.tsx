import { useCallback, useLayoutEffect, useMemo, useState } from "react";
import type { LiveSource } from "../lib/api";
import { findLvfGeometry } from "../lib/lvf";
import type { LvfHighlight } from "../lib/lvf";
import type {
  SpectrumChannel,
  SpectrumResponse,
  SkyResponse,
} from "../lib/types";
import { useSpectrum } from "../hooks/useSpectrum";
import { SpectrumPlot, spectrumEpochColor } from "./SpectrumPlot";
import {
  channelStats,
  channelStatus,
  measurementReasonLabel,
  discoveryNotice,
  observationDateLabel,
  measurementNumber,
  spectrumTableSamples,
} from "../lib/semantics";
import type { SampleQuality, SampleSort } from "../lib/semantics";
import { resolveAssetUrl } from "../lib/api";

export interface SpectrumDrawerProps {
  manifest: SkyResponse;
  discoveryOverride: "inherit" | "known";
  onKnownRecovery: () => void;
  onInheritDiscovery: () => void;
  skySource: LiveSource | null;
  onClose: () => void;
  /** Sync a hovered spectrum channel to the canvas LVF overlay. */
  onLvfHover?: (highlight: LvfHighlight | null) => void;
}

function csvCell(value: string | number | boolean | null): string {
  if (value === null) return "";
  const text = String(value);
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function downloadCsv(
  spectrum: SpectrumResponse,
  targetId: string | null,
  source: "archive" | "saved" | "unrecorded",
) {
  const header = [
    "epoch_id",
    "label",
    "collection",
    "release",
    "detector",
    "wavelength_um",
    "bandwidth_um",
    "flux_ujy",
    "flux_err_ujy",
    "flags",
    "is_flagged_bad",
    "clean_fraction",
    "is_used_in_photometry",
    "spectrum_source",
    "discovery_mode",
    "discovery_status",
    "missing_collections",
    "is_simulated_fallback",
    "date_start_iso",
    "date_end_iso",
    "input_id",
    "extraction_ra",
    "extraction_dec",
    "measurement_reasons",
    "analysis_id",
    "processing_version",
  ];
  const rows: string[] = [header.join(",")];
  for (const epoch of spectrum.epochs) {
    for (const channel of epoch.channels) {
      rows.push(
        [
          epoch.epoch_id,
          observationDateLabel(epoch),
          epoch.collection,
          epoch.release,
          channel.detector,
          channel.wavelength_um,
          channel.bandwidth_um,
          channel.flux_ujy,
          channel.flux_err_ujy,
          channel.flags,
          channel.is_flagged_bad,
          channel.clean_fraction,
          channel.is_used_in_photometry,
          source,
          spectrum.provenance.discovery_mode ?? "unrecorded",
          spectrum.provenance.discovery_status ?? "unknown",
          spectrum.provenance.missing_collections?.join("; ") ?? null,
          spectrum.provenance.is_simulated_fallback,
          epoch.observation_range?.date_start_iso ?? null,
          epoch.observation_range?.date_end_iso ?? null,
          channel.input_id ?? null,
          channel.extraction_ra ?? null,
          channel.extraction_dec ?? null,
          channel.measurement_reasons?.join("; ") ?? null,
          spectrum.provenance.analysis_id ?? null,
          spectrum.provenance.processing_version ?? null,
        ]
          .map(csvCell)
          .join(","),
      );
    }
  }
  const blob = new Blob([`\ufeff${rows.join("\r\n")}`], {
    type: "text/csv;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `skyblink_spectrum_${targetId ?? "field"}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function formatFlux(value: number | null): string {
  return measurementNumber(value);
}

function formatError(value: number | null): string {
  return measurementNumber(value);
}

function ChannelRows({
  epochId,
  channels,
  selected,
  onSelect,
}: {
  epochId: string;
  channels: SpectrumChannel[];
  selected: SpectrumChannel | null;
  onSelect: (channel: SpectrumChannel, epochId: string) => void;
}) {
  return (
    <>
      {channels.map((channel) => {
        const rowClass = channel.is_flagged_bad
          ? "spec-row--bad"
          : !channel.is_used_in_photometry
            ? "spec-row--caution"
            : undefined;
        return (
          <tr
            key={`${epochId}-${channel.detector}-${channel.wavelength_um}`}
            className={`${rowClass ?? ""} ${selected === channel ? "spec-row--selected" : ""}`}
          >
            <td>
              <button
                type="button"
                className="btn"
                onClick={() => onSelect(channel, epochId)}
                aria-pressed={selected === channel}
                aria-label={`Inspect ${epochId} detector ${channel.detector} at ${channel.wavelength_um.toFixed(3)} micrometers`}
              >
                Inspect
              </button>
            </td>
            <td className="mono">{epochId}</td>
            <td className="mono">{channel.detector}</td>
            <td className="mono">{channel.wavelength_um.toFixed(3)}</td>
            <td className="mono">{channel.bandwidth_um.toFixed(3)}</td>
            <td className="mono">{formatFlux(channel.flux_ujy)}</td>
            <td className="mono">{formatError(channel.flux_err_ujy)}</td>
            <td className="mono">{channel.flags}</td>
            <td>{channel.is_flagged_bad ? "yes" : "no"}</td>
            <td className="mono">
              {(channel.clean_fraction * 100).toFixed(0)}%
            </td>
            <td>{channel.is_used_in_photometry ? "yes" : "no"}</td>
            <td>
              {channel.measurement_reasons?.length
                ? channel.measurement_reasons.join(", ")
                : "Not recorded"}
            </td>
          </tr>
        );
      })}
    </>
  );
}

/** Real API spectra with channel quality, CSV export, and a data table. */
export function SpectrumDrawer({
  manifest,
  discoveryOverride,
  onKnownRecovery,
  onInheritDiscovery,
  skySource,
  onClose,
  onLvfHover,
}: SpectrumDrawerProps) {
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
  const state = useSpectrum(query, skySource, true);
  const spectrum = state.spectrum;
  const measurements = useMemo(() => channelStats(spectrum), [spectrum]);
  const targetName = manifest.target?.name ?? "Sky field";
  const [lvfHover, setLvfHover] = useState<LvfHighlight | null>(null);
  const [showReferences, setShowReferences] = useState(false);
  const [selected, setSelected] = useState<{
    channel: SpectrumChannel;
    epochId: string;
  } | null>(null);
  const [quality, setQuality] = useState<SampleQuality>("all");
  const [tableEpoch, setTableEpoch] = useState("all");
  const [tableSort, setTableSort] = useState<SampleSort>("recorded");
  const [copyStatus, setCopyStatus] = useState("");
  const samples = useMemo(
    () =>
      spectrum?.epochs.flatMap((epoch) =>
        epoch.channels.map((channel) => ({ channel, epochId: epoch.epoch_id })),
      ) ?? [],
    [spectrum],
  );
  const shownSamples = useMemo(
    () => spectrumTableSamples(samples, quality, tableEpoch, tableSort),
    [samples, quality, tableEpoch, tableSort],
  );
  const selectedIndex = samples.findIndex(
    (sample) =>
      sample.channel === selected?.channel &&
      sample.epochId === selected?.epochId,
  );
  // Reset before paint: a passive reset can erase the first keyboard selection
  // made immediately after the new spectrum becomes interactive.
  useLayoutEffect(() => {
    setSelected(null);
    setShowReferences(false);
    setQuality("all");
    setTableEpoch("all");
    setTableSort("recorded");
    setCopyStatus("");
  }, [spectrum]);

  const channelCount = useMemo(
    () =>
      spectrum
        ? spectrum.epochs.reduce(
            (total, epoch) => total + epoch.channels.length,
            0,
          )
        : 0,
    [spectrum],
  );
  const lowClean = useMemo(
    () =>
      spectrum
        ? spectrum.epochs.some((epoch) =>
            epoch.channels.some(
              (channel) =>
                !channel.is_flagged_bad && channel.clean_fraction < 1,
            ),
          )
        : false,
    [spectrum],
  );
  const lvfGeometry = lvfHover
    ? findLvfGeometry(manifest.epochs, lvfHover.epochId, lvfHover.detector)
    : null;
  const lvfAvailable = manifest.epochs.some(
    (epoch) => (epoch.lvf_geometry?.length ?? 0) > 0,
  );

  const handleChannelHover = useCallback(
    (channel: SpectrumChannel | null, epochId: string) => {
      if (!channel) {
        setLvfHover(null);
        onLvfHover?.(null);
        return;
      }
      const next: LvfHighlight = {
        detector: channel.detector,
        wavelengthUm: channel.wavelength_um,
        epochId,
      };
      setLvfHover(next);
      onLvfHover?.(next);
    },
    [onLvfHover],
  );
  const selectChannel = (channel: SpectrumChannel | null, epochId: string) => {
    setCopyStatus("");
    setSelected(channel ? { channel, epochId } : null);
    handleChannelHover(channel, epochId);
  };
  const copySample = async () => {
    if (!selected || !spectrum) return;
    const c = selected.channel;
    const text = [
      `Epoch: ${selected.epochId}`,
      `Detector: ${c.detector}`,
      `Wavelength (µm): ${c.wavelength_um}`,
      `Bandwidth (µm): ${c.bandwidth_um}`,
      `Flux (µJy): ${c.flux_ujy ?? "unavailable"}`,
      `Approximate error (µJy): ${c.flux_err_ujy ?? "unavailable"}`,
      `Status: ${channelStatus(c)}`,
      `Extraction ICRS (deg): ${c.extraction_ra != null && c.extraction_dec != null ? `${c.extraction_ra}, ${c.extraction_dec}` : "not recorded"}`,
      `Input: ${c.input_id ?? "not recorded"}`,
      `Reasons: ${c.measurement_reasons ? c.measurement_reasons.join(", ") || "none listed" : "not recorded"}`,
      `Analysis: ${spectrum.provenance.analysis_id ?? "not recorded"}`,
      `Access: ${spectrum.provenance.data_access ?? "not recorded"}`,
      `Discovery mode: ${spectrum.provenance.discovery_mode ?? "not recorded"}`,
    ].join("\n");
    try {
      await navigator.clipboard.writeText(text);
      setCopyStatus("Sample metadata copied.");
    } catch {
      setCopyStatus(
        "Clipboard unavailable. Select the text below or export the CSV.",
      );
    }
  };

  return (
    <div className="spectrum-drawer">
      <header className="drawer-head">
        <div>
          <p className="drawer-kicker">
            Spectrum · fixed{" "}
            {spectrum ? spectrum.aperture_radius_arcsec.toFixed(1) : "12.3"}″
            aperture
          </p>
          <h2 id="spectrum-title">{targetName} spectrum</h2>
          <p className="drawer-sub">
            <span className="mono">
              {query.ra.toFixed(6)}°, {query.dec.toFixed(6)}°
            </span>
            {query.target ? <span> · {query.target}</span> : null}
          </p>
        </div>
        <button
          type="button"
          className="icon-btn"
          onClick={onClose}
          aria-label="Close spectrum"
        >
          ✕
        </button>
      </header>

      {discoveryOverride === "known" && (
        <section
          className="spectrum-recovery-note"
          aria-label="Spectrum discovery mode"
        >
          <p>
            Spectrum uses known exposures with fresh downloads. The image keeps
            its own discovery mode. This is a limited verified exposure list,
            not a new archive search.
          </p>
          <button className="btn" onClick={onInheritDiscovery}>
            Use image discovery mode for spectrum
          </button>
        </section>
      )}

      {state.status === "loading" ? (
        <div className="drawer-status" role="status">
          <span className="spinner" aria-hidden="true" />
          Retrieving recorded spectrum measurements…
          <button type="button" className="btn" onClick={state.cancel}>
            Cancel spectrum request
          </button>
        </div>
      ) : null}

      {state.status === "cancelled" ? (
        <div className="drawer-status" role="status">
          Spectrum request cancelled.{" "}
          <button type="button" className="btn" onClick={state.reload}>
            Retry spectrum
          </button>
        </div>
      ) : null}

      {state.status === "error" ? (
        <div className="drawer-error" role="alert">
          <h3>Spectrum request failed</h3>
          <p>{state.error}</p>
          <details>
            <summary>Request details</summary>
            <p>{state.technicalError}</p>
          </details>
          <button
            type="button"
            className="btn btn--accent"
            onClick={state.reload}
          >
            Retry spectrum
          </button>
          {state.canRecoverKnown &&
            skySource === "archive" &&
            query.target &&
            query.discovery === "live" && (
              <section className="spectrum-recovery-note">
                <p>
                  Download a previously verified exposure list afresh for this
                  catalog center. The image stays unchanged; newer observations
                  may exist and eligible measurements are not guaranteed.
                </p>
                <button className="btn" onClick={onKnownRecovery}>
                  Fetch known spectrum online
                </button>
              </section>
            )}
        </div>
      ) : null}

      {spectrum ? (
        <>
          <div className="spectrum-meta">
            {spectrum.provenance.discovery_mode === "known" && (
              <p>
                Catalog-centered measurements from the previously verified
                exposure list, downloaded afresh. Sampling may be sparse; no new
                archive search was performed. To inspect another position, use
                coordinate Search to start fresh discovery.
              </p>
            )}
            {discoveryNotice(spectrum.provenance) ? (
              <p
                role="status"
                data-discovery-status={
                  spectrum.provenance.discovery_mode === "known"
                    ? "known"
                    : (spectrum.provenance.discovery_status ?? "unknown")
                }
              >
                {discoveryNotice(spectrum.provenance)}
              </p>
            ) : null}
            <span className="badge badge--real">
              {spectrum.provenance.release} · {spectrum.provenance.source}
            </span>
            <span
              className="source-tag source-tag--api"
              title="Loaded from /api/v1/spectrum"
            >
              {spectrum.provenance.data_access === "saved"
                ? "SAVED SPECTRUM"
                : spectrum.provenance.data_access === "archive"
                  ? spectrum.provenance.discovery_mode === "known"
                    ? "KNOWN EXPOSURES / FRESH DOWNLOADS"
                    : "ARCHIVE SPECTRUM"
                  : "ACCESS UNRECORDED"}
            </span>
            <span>
              Extraction:{" "}
              {spectrum.confidence === "high"
                ? "precomputed target spectrum"
                : "best-effort aperture — not a discovery probability"}
            </span>
            <span>
              ZODI{" "}
              {spectrum.provenance.zodi_subtracted
                ? "subtracted"
                : "not subtracted"}{" "}
              · background{" "}
              {spectrum.provenance.background_subtracted
                ? "subtracted"
                : "not subtracted"}
            </span>
          </div>

          <div className="spectrum-legend" aria-label="Epoch legend">
            {spectrum.epochs.map((epoch, index) => (
              <span key={epoch.epoch_id} className="legend-item">
                <span
                  className="legend-swatch"
                  style={{ background: spectrumEpochColor(index) }}
                  aria-hidden="true"
                />
                <span className="mono">{epoch.epoch_id}</span>
                <span>
                  {observationDateLabel(epoch).replace(
                    "Observation dates unavailable",
                    "Dates unrecorded",
                  )}
                </span>
                <span className="legend-release mono">
                  {epoch.collection} · {epoch.release}
                </span>
              </span>
            ))}
          </div>

          <div className="spectrum-counts" role="status">
            <strong>
              Fetched {measurements.total} samples; {measurements.usable}{" "}
              recorded eligible
            </strong>
            {" · "}
            {measurements.excludedFinite} finite excluded{" · "}
            {measurements.nullFlux} unavailable{" · "}
            {measurements.total} total samples
          </div>
          {measurements.usable === 0 ? (
            <div
              className="spectrum-banner"
              role="status"
              data-no-eligible="true"
            >
              <strong>No usable flux measurements.</strong>{" "}
              {measurements.finite === 0
                ? "All recorded flux values are unavailable; no flux plot is drawn."
                : "Finite values below are excluded exploratory sums, not eligible measurements."}{" "}
              Inspect the recorded reasons and metadata below. Missing flux is
              not zero or a nondetection limit.
            </div>
          ) : null}
          <p className="control-hint">
            Eligibility does not establish source isolation, calibrated total
            flux or astrophysical variability.
          </p>
          <details className="spectrum-method-details">
            <summary>Measurement rules and per-observation reasons</summary>
            <p className="control-hint">
              Wavelength lookup: {spectrum.wavelength_calibration}
            </p>
            <p className="control-hint">
              Current archive extractions require the full center-selected
              aperture inside the image, all selected aperture pixels clean,
              supported field background, at least 10 clean local-annulus
              pixels, and a center without hard-bad flags. Finite
              partial-aperture or insufficient-annulus sums remain exploratory
              and are excluded from eligible summaries. Saved datasets retain
              their historical eligibility flags; they are not revalidated by
              this display.
            </p>
            {spectrum.epochs.map((epoch) => (
              <p
                className="control-hint"
                key={`availability-${epoch.epoch_id}`}
              >
                {epoch.epoch_id}:{" "}
                {epoch.measurement_availability
                  ? `${epoch.measurement_availability.usable_channels}/${epoch.measurement_availability.total_channels} eligible; ${epoch.measurement_availability.finite_channels} finite. Recorded reasons: ${epoch.measurement_availability.reasons.length ? epoch.measurement_availability.reasons.join(", ") : "none listed"}.`
                  : "Measurement reason metadata unavailable; per-channel flags and eligibility remain available."}
              </p>
            ))}
          </details>

          {measurements.finite > 0 ? (
            <>
              <div className="spectrum-controls">
                <label>
                  <input
                    type="checkbox"
                    checked={showReferences}
                    onChange={(event) =>
                      setShowReferences(event.target.checked)
                    }
                  />{" "}
                  Show molecular reference wavelengths
                </label>
              </div>
              {showReferences ? (
                <p className="control-hint" role="status">
                  Reference wavelengths only, not detected molecules or evidence
                  of absorption in these samples.
                </p>
              ) : null}
              <div className="spectrum-plot-wrap">
                <SpectrumPlot
                  spectrum={spectrum}
                  onChannelHover={handleChannelHover}
                  showReferences={showReferences}
                  selectedChannel={selected?.channel ?? null}
                  selectedEpochId={selected?.epochId}
                  onChannelSelect={selectChannel}
                />
              </div>
              {showReferences ? (
                <p className="control-hint">
                  Reference key:{" "}
                  {spectrum.molecular_features
                    .map(
                      (feature, index) =>
                        `${index + 1}: ${feature.label} at ${feature.wavelength_um.toFixed(2)} µm`,
                    )
                    .join(" · ")}
                  . Numbered markers are used on narrow plots.
                </p>
              ) : null}
              <div className="spectrum-hover-status">
                {lvfHover ? (
                  <div className="lvf-hover" role="status" aria-live="polite">
                    <span className="lvf-hover-title mono">
                      LVF D{lvfHover.detector} · λ{" "}
                      {lvfHover.wavelengthUm.toFixed(2)} µm
                    </span>
                    {lvfGeometry ? (
                      <span className="lvf-hover-meta mono">
                        PA {lvfGeometry.pa_deg.toFixed(0)}° ·{" "}
                        {lvfGeometry.grad_um_per_arcsec.toFixed(3)} µm/″ ·
                        highlighted on the canvas
                      </span>
                    ) : (
                      <span className="lvf-hover-meta mono">
                        no LVF geometry for this epoch — canvas overlay hidden
                      </span>
                    )}
                  </div>
                ) : lvfAvailable ? (
                  <p className="control-hint">
                    Select or hover a spectrum point to highlight its detector's
                    LVF strip on the canvas (orientation and µm/arcsec are
                    manifest geometry).
                  </p>
                ) : (
                  <p className="control-hint">
                    This manifest does not provide LVF geometry; the canvas
                    overlay is hidden rather than assumed.
                  </p>
                )}
              </div>
              <p className="control-hint">
                Points are discrete samples, never a fitted spectrum. Open amber
                diamonds: excluded from photometry. Red ✕: hard-bad center.
                Signed flux and both approximate error limits are shown;
                negative flux after background subtraction is not clipped to
                zero. Tap a point, use arrow keys on the plot, or inspect any
                row below.
              </p>
            </>
          ) : (
            <p className="drawer-status">
              {channelCount
                ? "Recorded channels and reasons remain available in the table and metadata export."
                : "No channels were returned for this spectrum."}
            </p>
          )}

          {channelCount > 0 ? (
            <section
              className="spectrum-selection"
              aria-label="Selected spectrum sample"
            >
              <div className="spectrum-controls">
                <button
                  type="button"
                  className="btn"
                  disabled={selectedIndex <= 0}
                  onClick={() => {
                    const s = samples[selectedIndex - 1];
                    selectChannel(s.channel, s.epochId);
                  }}
                >
                  Previous sample
                </button>
                <button
                  type="button"
                  className="btn"
                  disabled={selectedIndex >= samples.length - 1}
                  onClick={() => {
                    const s = samples[selectedIndex + 1];
                    selectChannel(s.channel, s.epochId);
                  }}
                >
                  {selected ? "Next sample" : "Inspect first sample"}
                </button>
                {selected ? (
                  <button
                    type="button"
                    className="btn"
                    onClick={() => selectChannel(null, "")}
                  >
                    Clear selection
                  </button>
                ) : null}
                {selected ? (
                  <button type="button" className="btn" onClick={copySample}>
                    Copy sample metadata
                  </button>
                ) : null}
              </div>
              <p className="spectrum-copy-status" role="status">
                {copyStatus}
              </p>
              {selected ? (
                <div aria-live="polite" aria-atomic="true">
                  <h3>
                    {selected.epochId} · detector {selected.channel.detector} ·{" "}
                    {selected.channel.wavelength_um.toFixed(3)} µm
                  </h3>
                  <p>
                    <strong>{channelStatus(selected.channel)}</strong>
                    {" · "}
                    {formatFlux(selected.channel.flux_ujy)} µJy
                    {selected.channel.flux_err_ujy === null
                      ? " · uncertainty unavailable"
                      : ` ± ${formatError(selected.channel.flux_err_ujy)} µJy (approximate)`}
                  </p>
                  <p>
                    {selected.channel.measurement_reasons?.length
                      ? selected.channel.measurement_reasons
                          .map(measurementReasonLabel)
                          .join("; ")
                      : "Measurement reason metadata not recorded."}
                  </p>
                  <dl>
                    <dt>Bandwidth</dt>
                    <dd>{selected.channel.bandwidth_um.toFixed(4)} µm</dd>
                    <dt>Clean aperture pixels</dt>
                    <dd>
                      {(selected.channel.clean_fraction * 100).toFixed(1)}%
                    </dd>
                    <dt>Flags at extraction center</dt>
                    <dd>
                      {selected.channel.flags} · hard bad:{" "}
                      {selected.channel.is_flagged_bad ? "yes" : "no"}
                    </dd>
                    <dt>Extraction position (ICRS)</dt>
                    <dd>
                      {selected.channel.extraction_ra != null &&
                      selected.channel.extraction_dec != null
                        ? `${selected.channel.extraction_ra.toFixed(7)}°, ${selected.channel.extraction_dec.toFixed(7)}°`
                        : "Not recorded"}
                    </dd>
                    <dt>Input identifier</dt>
                    <dd className="mono">
                      {selected.channel.input_id ??
                        "Not recorded (legacy metadata)"}
                    </dd>
                    <dt>Method</dt>
                    <dd>
                      {selected.channel.photometry_method ?? "Not recorded"}
                    </dd>
                  </dl>
                  {spectrum.provenance.analysis_record_url ? (
                    <a
                      href={resolveAssetUrl(
                        spectrum.provenance.analysis_record_url,
                      )}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Inspect source inputs and processing record
                    </a>
                  ) : null}
                </div>
              ) : (
                <p>
                  Select a sample to retain its value, uncertainty, eligibility
                  and source information. The table includes unavailable
                  measurements.
                </p>
              )}
            </section>
          ) : null}

          {lowClean ? (
            <p className="spectrum-banner spectrum-banner--soft">
              Some channels have <code>clean_fraction &lt; 1</code>; finite
              values are exploratory partial sums, not calibrated totals. New
              archive extractions exclude them from measurement eligibility;
              saved flags retain their historical meaning.
            </p>
          ) : null}

          <div className="spectrum-actions">
            <button
              type="button"
              className="btn btn--accent"
              onClick={() =>
                downloadCsv(
                  spectrum,
                  spectrum.target_id,
                  spectrum.provenance.data_access ?? "unrecorded",
                )
              }
            >
              {measurements.finite
                ? "Export measurements CSV"
                : "Export channel metadata CSV"}
            </button>
            <span className="control-hint">
              {channelCount} channels · {spectrum.epochs.length} epoch
              {spectrum.epochs.length === 1 ? "" : "s"}
            </span>
          </div>

          <details className="spec-table-wrap" open={measurements.usable === 0}>
            <summary>Data table ({channelCount} channels)</summary>
            <div className="spectrum-table-controls">
              <label>
                Measurement status
                <select
                  aria-label="Measurement status"
                  value={quality}
                  onChange={(event) =>
                    setQuality(event.target.value as SampleQuality)
                  }
                >
                  <option value="all">All recorded samples</option>
                  <option value="eligible">Recorded eligible</option>
                  <option value="excluded">Finite excluded</option>
                  <option value="unavailable">Unavailable flux</option>
                </select>
              </label>
              <label>
                Table epoch
                <select
                  aria-label="Table epoch"
                  value={tableEpoch}
                  onChange={(event) => setTableEpoch(event.target.value)}
                >
                  <option value="all">All epochs</option>
                  {spectrum.epochs.map((epoch) => (
                    <option key={epoch.epoch_id} value={epoch.epoch_id}>
                      {epoch.epoch_id}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Sort samples
                <select
                  aria-label="Sort samples"
                  value={tableSort}
                  onChange={(event) =>
                    setTableSort(event.target.value as SampleSort)
                  }
                >
                  <option value="recorded">Recorded order</option>
                  <option value="wavelength">Wavelength, increasing</option>
                  <option value="flux-up">Flux, increasing</option>
                  <option value="flux-down">Flux, decreasing</option>
                </select>
              </label>
              <button
                type="button"
                className="btn"
                onClick={() => {
                  setQuality("all");
                  setTableEpoch("all");
                  setTableSort("recorded");
                }}
              >
                Reset table
              </button>
            </div>
            <p className="control-hint" data-table-count="true" role="status">
              Showing {shownSamples.length} of {channelCount} recorded samples.
              Table filters do not change the plot or CSV export; exports
              include all samples. Unavailable flux sorts last.
            </p>
            {shownSamples.length === 0 ? (
              <p className="spectrum-banner">
                No recorded samples match these table filters.
              </p>
            ) : null}
            <div className="spec-table-scroll">
              <table className="spec-table">
                <caption>
                  Recorded channels matching the table filters. Null flux means
                  a measurement is unavailable, including missing clean pixels
                  or unsupported background; missing channels are omitted, not
                  marked bad.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Inspect</th>
                    <th scope="col">Epoch</th>
                    <th scope="col">Det</th>
                    <th scope="col">λ (µm)</th>
                    <th scope="col">Δλ (µm)</th>
                    <th scope="col">Flux (µJy)</th>
                    <th scope="col">Error (µJy)</th>
                    <th scope="col">Flags</th>
                    <th scope="col">Hard bad</th>
                    <th scope="col">Clean</th>
                    <th scope="col">Used</th>
                    <th scope="col">Recorded reasons</th>
                  </tr>
                </thead>
                <tbody>
                  {shownSamples.map((sample, index) => (
                    <ChannelRows
                      key={`${sample.epochId}-${sample.channel.detector}-${sample.channel.wavelength_um}-${index}`}
                      epochId={sample.epochId}
                      channels={[sample.channel]}
                      selected={
                        selected?.epochId === sample.epochId
                          ? selected.channel
                          : null
                      }
                      onSelect={selectChannel}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          </details>

          <p className="citation">
            {spectrum.provenance.source} · {spectrum.provenance.citation} ·{" "}
            {spectrum.provenance.generated_at}
          </p>
          <p className="citation">
            Processing version:{" "}
            {spectrum.provenance.processing_version ??
              "unavailable (legacy metadata)"}
            {" · "}Analysis:{" "}
            {spectrum.provenance.analysis_record_url ? (
              <a
                href={resolveAssetUrl(spectrum.provenance.analysis_record_url)}
                target="_blank"
                rel="noreferrer"
              >
                {spectrum.provenance.analysis_id ??
                  "recorded inputs and method"}
              </a>
            ) : (
              (spectrum.provenance.analysis_id ??
              "unavailable (legacy metadata)")
            )}
          </p>
        </>
      ) : null}
    </div>
  );
}
