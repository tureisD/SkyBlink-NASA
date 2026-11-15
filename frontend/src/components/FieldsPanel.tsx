import type { ReactNode } from "react";
import type { DataAccess, DiscoveryMode } from "../lib/api";
import { SourceSelector } from "./SourceSelector";

interface FieldsPanelProps {
  source: DataAccess;
  discovery: DiscoveryMode;
  targetId: string | null;
  targetName: string;
  spectrumDiscovery: "inherit" | "known";
  ra: number;
  dec: number;
  size: number;
  children: ReactNode;
  onSource: (source: DataAccess, discovery?: DiscoveryMode) => void;
  onClose: () => void;
}

/** Task navigation and query settings; target selection lives in global Search. */
export function FieldsPanel(props: FieldsPanelProps) {
  return (
    <>
      <div className="sidebar-heading">
        <div>
          <p className="eyebrow">Workspace</p>
          <h1>{props.targetName}</h1>
        </div>
        <button
          className="btn btn--quiet sidebar-close"
          onClick={props.onClose}
          aria-label="Close fields panel"
        >
          <span className="hamburger-icon" aria-hidden="true" />
        </button>
      </div>
      {props.children}
      <section className="field-settings" aria-label="Field settings">
        <h2>Field settings</h2>
        <div className="field-source">
          <SourceSelector
            source={props.source}
            discovery={props.discovery}
            savedAvailable={props.targetId !== null}
            onChange={props.onSource}
          />
          <p>
            {props.source === "saved"
              ? "Historical observations; comparison unvalidated."
              : props.discovery === "known"
                ? "Verified exposure list, fresh downloads. No new coverage search."
                : "Fresh archive search and downloads."}
          </p>
          {props.spectrumDiscovery === "known" && (
            <p className="spectrum-mode-note">
              Spectrum recovery: known exposures, fresh downloads. Image mode
              unchanged.
            </p>
          )}
        </div>
        <div className="field-position">
          <h3>Field position</h3>
          <dl>
            <div>
              <dt>RA</dt>
              <dd>{props.ra.toFixed(6)}&deg;</dd>
            </div>
            <div>
              <dt>Dec</dt>
              <dd>{props.dec.toFixed(6)}&deg;</dd>
            </div>
            <div>
              <dt>View width</dt>
              <dd>{props.size.toFixed(2)}&deg;</dd>
            </div>
          </dl>
          <p>
            ICRS{" "}
            {props.targetId
              ? "/ catalog query epoch 2025.8"
              : "/ coordinate epoch unspecified"}
          </p>
        </div>
      </section>
    </>
  );
}
