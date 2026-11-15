import type { RecentField } from "../hooks/useRecentFields";
import { useRef, useState } from "react";
import type { FormEvent } from "react";
import { parseDec, parseRa } from "../lib/coordinates";
import { targetSeeds } from "../lib/targets";
import type { DataAccess, DiscoveryMode } from "../lib/api";

export interface SearchDialogProps {
  recent?: RecentField[];
  onRecent?: (field: RecentField) => void;
  onClearRecent?: () => void;
  /** Receives the exact validated decimal degrees; no catalog snapping. */
  onResolve: (ra: number, dec: number) => void;
  onClose: () => void;
  source: DataAccess;
  discovery: DiscoveryMode;
  onTarget: (id: string) => void;
}

/**
 * Coordinate entry available from the persistent workspace header.
 * Parsing happens locally so the dialog can show an inline error before any
 * network request. Numeric positions stay exact; named targets are selected
 * explicitly below and use source-specific catalog coordinates.
 */
export function SearchDialog({
  onResolve,
  onClose,
  source,
  discovery,
  onTarget,
  recent = [],
  onRecent,
  onClearRecent,
}: SearchDialogProps) {
  const [ra, setRa] = useState("");
  const [dec, setDec] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [invalid, setInvalid] = useState<"ra" | "dec" | null>(null);
  const raRef = useRef<HTMLInputElement | null>(null);
  const decRef = useRef<HTMLInputElement | null>(null);

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const parsedRa = parseRa(ra);
    if (!parsedRa.ok) {
      setError(parsedRa.error);
      setInvalid("ra");
      raRef.current?.focus();
      return;
    }
    const parsedDec = parseDec(dec);
    if (!parsedDec.ok) {
      setError(parsedDec.error);
      setInvalid("dec");
      decRef.current?.focus();
      return;
    }
    setError(null);
    setInvalid(null);
    onResolve(parsedRa.degrees, parsedDec.degrees);
  };

  return (
    <>
      <header className="drawer-head">
        <div>
          <p className="drawer-kicker">Coordinate resolver</p>
          <h2 id="search-title">Search coordinates</h2>
          <p className="drawer-sub">
            ICRS · RA 0–360° · Dec −90–90° · exact coordinate search
          </p>
        </div>
        <button
          type="button"
          className="icon-btn"
          onClick={onClose}
          aria-label="Close coordinate search"
        >
          ✕
        </button>
      </header>

      {recent.length > 0 && (
        <section
          className="recent-fields"
          aria-label="Recent successful fields"
        >
          <details>
            <summary>Recently explored ({recent.length})</summary>
            <div className="section-heading">
              <button className="btn btn--quiet" onClick={onClearRecent}>
                Clear history
              </button>
            </div>
            <p className="supporting-copy">
              Query history stays in this browser. Opening an archive field
              makes a new request.
            </p>
            <div className="recent-field-list">
              {recent.map((field) => (
                <button
                  className="btn"
                  key={`${field.source}:${field.discovery}:${field.spectrumDiscovery}:${field.ra}:${field.dec}:${field.size}`}
                  onClick={() => onRecent?.(field)}
                >
                  <strong>{field.name}</strong>
                  <span>
                    {field.source === "archive"
                      ? field.discovery === "known"
                        ? "Known exposures / fresh downloads"
                        : "Online archive / fresh search"
                      : "Saved observations"}{" "}
                    · {field.size}° field
                    {field.spectrumDiscovery === "known"
                      ? " / spectrum: known exposures"
                      : ""}
                  </span>
                </button>
              ))}
            </div>
          </details>
        </section>
      )}
      {discovery === "known" && (
        <p className="supporting-copy">
          Coordinate submission switches to a fresh archive search.
          Known-exposure recovery is available only for named catalog targets.
        </p>
      )}
      <form className="search-form" onSubmit={submit} noValidate>
        <div className="search-grid">
          <div className="search-field">
            <label htmlFor="search-ra">RA (ICRS)</label>
            <input
              ref={raRef}
              id="search-ra"
              className="search-input"
              value={ra}
              onChange={(event) => {
                setRa(event.target.value);
                if (invalid === "ra") {
                  setInvalid(null);
                  setError(null);
                }
              }}
              placeholder="08h55m10.831s"
              autoComplete="off"
              spellCheck={false}
              aria-invalid={invalid === "ra"}
              aria-describedby={
                invalid === "ra" ? "search-hint search-error" : "search-hint"
              }
            />
          </div>
          <div className="search-field">
            <label htmlFor="search-dec">Dec (ICRS)</label>
            <input
              ref={decRef}
              id="search-dec"
              className="search-input"
              value={dec}
              onChange={(event) => {
                setDec(event.target.value);
                if (invalid === "dec") {
                  setInvalid(null);
                  setError(null);
                }
              }}
              placeholder="−7d14m42.53s"
              autoComplete="off"
              spellCheck={false}
              aria-invalid={invalid === "dec"}
              aria-describedby={
                invalid === "dec" ? "search-hint search-error" : "search-hint"
              }
            />
          </div>
        </div>

        {error ? (
          <p className="search-error" id="search-error" role="alert">
            {error}
          </p>
        ) : null}

        <p className="search-hint" id="search-hint">
          Decimal degrees (<code>133.79513</code>, <code>−7.24515</code>) or
          sexagesimal (<code>08h55m10.831s</code>, <code>−7d14m42.53s</code>,{" "}
          <code>08 55 10.831</code>, <code>−07:14:42.53</code>). RA sexagesimal
          is hours.
        </p>

        <div className="search-actions">
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn--accent">
            Resolve &amp; load
          </button>
        </div>

        <div className="search-benchmarks">
          <p className="search-benchmarks-label">
            Named catalog targets ·{" "}
            {source === "saved"
              ? "saved positions"
              : "corrected archive positions"}
          </p>
          <div className="search-benchmark-row">
            {Object.values(targetSeeds(source)).map((seed) => (
              <button
                key={seed.id}
                type="button"
                className="btn btn--sm"
                title={`${seed.name} · ${seed.refEpoch} reference coordinates`}
                onClick={() => onTarget(seed.id)}
              >
                {seed.shortName} · {seed.refEpoch}
              </button>
            ))}
          </div>
        </div>
      </form>
    </>
  );
}
