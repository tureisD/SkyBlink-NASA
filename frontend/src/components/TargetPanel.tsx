import { ArtifactShield } from "./ArtifactShield";
import type { OverlayKey } from "../hooks/useUrlState";
import type { SkyResponse } from "../lib/types";
import { coordinateEpochLabel } from "../lib/semantics";
import { resolveAssetUrl } from "../lib/api";
import {
  angularSeparationArcsec,
  formatArcsec,
  formatDec,
  formatRa,
} from "../lib/wcs";

export interface TargetPanelProps {
  manifest: SkyResponse;
  /** "all" while blinking, else the pinned epoch id. */
  pinnedEpoch: string;
  diff: boolean;
  overlays: OverlayKey[];
  onOverlay: (key: OverlayKey, enabled: boolean) => void;
  /** Opens the coordinate resolver / benchmark picker. */
  onSearch: () => void;
}

interface Metric {
  key: string;
  label: string;
  value: string;
  unit?: string;
}

/** Compact a recommended-band list: [1,2,3,4,6] → "B1–B4 · B6". */
function formatBands(bands: number[]): string {
  const sorted = [...new Set(bands)].sort((a, b) => a - b);
  if (sorted.length === 0) return "—";
  const ranges: string[] = [];
  let start = sorted[0];
  let previous = sorted[0];
  for (let index = 1; index <= sorted.length; index += 1) {
    const value = sorted[index];
    if (value === previous + 1) {
      previous = value;
      continue;
    }
    ranges.push(
      start === previous ? `B${start}` : `B${start}–B${previous}`,
    );
    start = value;
    previous = value;
  }
  return ranges.join(" · ");
}

function SearchIcon() {
  return (
    <svg viewBox="0 0 12 12" width="10" height="10" aria-hidden="true">
      <circle
        cx="5"
        cy="5"
        r="3.3"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.2"
      />
      <path
        d="M7.5 7.5 10.4 10.4"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
    </svg>
  );
}

/**
 * Unified, high-density telemetry rail: target header, two-column metric grid,
 * compact Artifact Shield, and static copy moved into collapsed drawers.
 * No stacked cards.
 */
export function TargetPanel({
  manifest,
  pinnedEpoch,
  diff,
  overlays,
  onOverlay,
  onSearch,
}: TargetPanelProps) {
  const target = manifest.target;
  const provenance = manifest.provenance;
  const wcs = manifest.wcs;
  const epochs = manifest.epochs;
  const separation = target
    ? angularSeparationArcsec(
        { ra: target.ra_ref, dec: target.dec_ref },
        { ra: target.ra_epoch2025, dec: target.dec_epoch2025 },
      )
    : null;

  const ra = manifest.query.ra;
  const dec = manifest.query.dec;
  const grid = `${wcs.width} × ${wcs.height}`;
  const scale = `${wcs.pixel_scale_arcsec.toFixed(2)}″ / px`;
  const normalization = provenance.flux_normalization.applied
    ? "applied"
    : provenance.flux_normalization.status;

  const metrics: Metric[] = target
    ? [
        { key: "ref", label: "Ref epoch", value: target.ref_epoch },
        { key: "prop", label: "Propagated", value: "2025.8" },
        {
          key: "pmra",
          label: "μ α cos δ",
          value: target.pm_ra_mas_yr.toFixed(1),
          unit: "mas/yr",
        },
        {
          key: "pmdec",
          label: "μ δ",
          value: target.pm_dec_mas_yr.toFixed(1),
          unit: "mas/yr",
        },
        {
          key: "sep",
          label: "Separation",
          value: separation !== null ? formatArcsec(separation) : "—",
        },
        {
          key: "bands",
          label: "Rec. bands",
          value: formatBands(target.recommended_bands),
        },
        { key: "grid", label: "Grid", value: grid },
        { key: "scale", label: "Scale", value: scale },
      ]
    : [
        { key: "ra", label: "Query RA", value: `${ra.toFixed(4)}°` },
        { key: "dec", label: "Query Dec", value: `${dec.toFixed(4)}°` },
        { key: "fov", label: "Field", value: `${manifest.query.size_deg.toFixed(2)}°` },
        { key: "grid", label: "Grid", value: grid },
        { key: "scale", label: "Scale", value: scale },
        { key: "release", label: "Release", value: provenance.release },
        { key: "epochs", label: "Epochs", value: String(epochs.length) },
        { key: "norm", label: "Normalization", value: normalization },
      ];

  return (
    <section className="rail-group" aria-label="Target telemetry">
      <header className="rail-head">
        <div className="rail-head-row">
          <p className="rail-kicker">
            {target ? "Catalog target" : "Arbitrary field"}
          </p>
          <button
            type="button"
            className="rail-search"
            onClick={onSearch}
            aria-label="Search coordinates"
            aria-haspopup="dialog"
            title="Search RA/Dec and resolve the five benchmark targets"
          >
            <SearchIcon />
            <span>Search coordinates</span>
          </button>
        </div>
        <h1 className="rail-title">{target?.name ?? "Sky field"}</h1>
        <p className="rail-category">
          {target?.category ?? "No catalog target record attached to this query"}
        </p>
        <div className="rail-coords" title={`ICRS; ${coordinateEpochLabel(target)}`}>
          <span>RA&nbsp;&nbsp;{formatRa(ra)}</span>
          <span>DEC {formatDec(dec)}</span>
          <span className="rail-coords-sub">
            {ra.toFixed(6)}°, {dec.toFixed(6)}°
          </span>
        </div>
      </header>

      <dl className="metric-grid" aria-label="Key target metrics">
        {metrics.map((metric) => (
          <div className="metric" key={metric.key}>
            <dt className="metric-k">{metric.label}</dt>
            <dd className="metric-v">
              {metric.value}
              {metric.unit ? <span> {metric.unit}</span> : null}
            </dd>
          </div>
        ))}
      </dl>

      <ArtifactShield
        manifest={manifest}
        pinnedEpoch={pinnedEpoch}
        diff={diff}
        overlays={overlays}
        onOverlay={onOverlay}
      />

      <details className="rail-drawer">
        <summary>Target story</summary>
        <div className="rail-drawer-body">
          {target ? (
            <>
              <p className="story-headline">{target.story_headline}</p>
              <p>{target.story_body}</p>
              <p className="story-note">
                Queries are centred on the propagated 2025.8 coordinates; the
                dashed cyan vector runs from the stored reference-epoch position
                to 2025.8.
              </p>
            </>
          ) : (
            <p>
              An arbitrary sky position. No catalog target record is attached,
              so the proper-motion reticle is hidden and the native pixel box
              marks the field centre. Spectra for arbitrary clicks are
              best-effort (low confidence) and labelled as such.
            </p>
          )}
        </div>
      </details>

      <details className="rail-drawer">
        <summary>Limitations &amp; provenance</summary>
        <div className="rail-drawer-body">
          <ul className="note-list">
            <li>
              Native SPHEREx pixels are 6.15″; close sources are blended.
            </li>
            <li>
              Blink playback uses hard cuts at 4 FPS by default (8 FPS cap).
              Pause or enable reduced motion if you are photosensitive.
            </li>
            <li>
              Low surface brightness and sparse epochs. Missing bands and
              epochs are disabled, never interpolated.
            </li>
            <li>
              Detector artifacts are surfaced in the Artifact Shield and flag
              overlay; they are never hidden or labelled as detections.
            </li>
            <li>
              Display frames are 8-bit WebP previews. When an epoch provides a
              <code> telemetry</code> sidecar, the cursor reads display intensity
              and decoded Table 16 flags. The readout names its actual plane and
              recorded normalization; this can differ from the displayed band.
              Legacy normalization metadata may be unavailable. These values
              are not calibrated source flux. The browser never re-normalizes them.
            </li>
            <li>
              Gaia pins are catalog references (G ≤ 16), not SPHEREx
              detections. Their vectors show 10 years of catalog proper motion,
              not the epoch separation; sub-pixel vectors are drawn as 5 px
              direction ticks.
            </li>
            <li>
              Difference frames are precomputed server-side from un-normalized,
              ZODI- and background-subtracted frames.
            </li>
            <li>
              No confidence scores or discovery probabilities are invented;
              simulated observation products are rejected.
            </li>
            <li>
              Measurements are approximate; follow-up observations confirm discoveries.
            </li>
            <li>
              {normalization === "applied"
                ? "Frames arrive pre-normalized across epochs (server-side static-source scaling). The browser never re-scales flux."
                : "Flux normalization was not applied in this response. The browser never re-scales flux."}
            </li>
          </ul>

          <dl className="prov-list">
            <div>
              <dt>Data access</dt>
              <dd>{provenance.data_access ?? "Not recorded"}</dd>
            </div>
            <div>
              <dt>Discovery mode</dt>
              <dd>{provenance.discovery_mode ?? "Not recorded"}</dd>
            </div>
            <div>
              <dt>Archive discovery</dt>
              <dd>{provenance.discovery_status ?? "unknown"}{provenance.missing_collections?.length ? `; missing: ${provenance.missing_collections.join(", ")}` : ""}</dd>
            </div>
            <div>
              <dt>Comparison</dt>
              <dd>{provenance.comparison_status ?? "Not recorded"}{provenance.comparison_reason ? `: ${provenance.comparison_reason}` : ""}</dd>
            </div>
            <div>
              <dt>Source</dt>
              <dd>{provenance.source}</dd>
            </div>
            <div>
              <dt>Collection</dt>
              <dd>{provenance.collection}</dd>
            </div>
            <div>
              <dt>Release</dt>
              <dd>{provenance.release}</dd>
            </div>
            <div>
              <dt>ZODI</dt>
              <dd>{provenance.zodi_subtracted ? "subtracted" : "not subtracted"}</dd>
            </div>
            <div>
              <dt>Background</dt>
              <dd>
                {provenance.background_subtracted
                  ? "subtracted"
                  : "not subtracted"}
              </dd>
            </div>
            <div>
              <dt>Normalization</dt>
              <dd>
                {provenance.flux_normalization.method} ·{" "}
                {provenance.flux_normalization.status}
              </dd>
            </div>
            <div>
              <dt>Generated</dt>
              <dd>{provenance.generated_at}</dd>
            </div>
            <div>
              <dt>Processing version</dt>
              <dd>{provenance.processing_version ?? "Unavailable (legacy metadata)"}</dd>
            </div>
            <div>
              <dt>Analysis record</dt>
              <dd>{provenance.analysis_record_url ? (
                <a href={resolveAssetUrl(provenance.analysis_record_url)} target="_blank" rel="noreferrer">
                  {provenance.analysis_id ?? "Recorded inputs and method"}
                </a>
              ) : provenance.analysis_id ?? "Unavailable (legacy metadata)"}</dd>
            </div>
          </dl>
          <p className="citation">{provenance.citation}</p>
        </div>
      </details>
    </section>
  );
}
