import type { SkyResponse } from "../lib/types";
import { SourceSelector } from "./SourceSelector";
import type { DataAccess, DiscoveryMode } from "../lib/api";
export interface TopBarProps {
  manifest: SkyResponse | null;
  curtainAvailable: boolean;
  onOpenCurtain: () => void;
  onHelp: () => void;
  onSearch: () => void;
  source: DataAccess;
  discovery: DiscoveryMode;
  savedAvailable?: boolean;
  sourceInSidebar?: boolean;
  onSourceChange: (source: DataAccess, discovery?: DiscoveryMode) => void;
}
export function TopBar({
  manifest,
  curtainAvailable,
  onOpenCurtain,
  onHelp,
  onSearch,
  source,
  discovery,
  savedAvailable,
  sourceInSidebar = false,
  onSourceChange,
}: TopBarProps) {
  return (
    <header
      className={`topbar ${manifest ? "topbar--ready" : "topbar--pending"}`}
    >
      <a className="brand" href="#workspace">
        <svg className="brand-mark" viewBox="0 0 44 44" aria-hidden="true">
          <circle
            cx="22"
            cy="22"
            r="15"
            fill="none"
            stroke="currentColor"
            strokeWidth="1"
          />
          <path
            d="M22 2v10m0 20v10M2 22h10m20 0h10M11 33 33 11"
            fill="none"
            stroke="currentColor"
            strokeWidth="1"
          />
          <circle cx="22" cy="22" r="4" fill="currentColor" />
        </svg>
        <span className="brand-wordmark">
          <span className="brand-name">SkyBlink</span>
          <span className="brand-sub">A SPHEREx observing workspace</span>
        </span>
      </a>
      <button
        className="btn search-primary"
        onClick={onSearch}
        aria-haspopup="dialog"
        aria-label="Search sky or choose a target"
      >
        <span>Search sky or choose a target</span>
        <kbd aria-hidden="true">/</kbd>
      </button>
      <div className="topbar-actions">
        {sourceInSidebar ? (
          <span className="header-source-context">
            {source === "archive"
              ? discovery === "known"
                ? "Known exposures / fresh downloads"
                : "Online archive / fresh search"
              : "Saved observations"}
          </span>
        ) : (
          <SourceSelector
            source={source}
            discovery={discovery}
            savedAvailable={savedAvailable ?? manifest?.target != null}
            onChange={onSourceChange}
          />
        )}
        {curtainAvailable && (
          <button
            className="btn"
            onClick={onOpenCurtain}
            aria-label="Reference images"
          >
            <span className="reference-label-full">Reference images</span>
            <span className="reference-label-short" aria-hidden="true">
              References
            </span>
          </button>
        )}
        <button className="btn" onClick={onHelp} aria-haspopup="dialog">
          Help
        </button>
      </div>
    </header>
  );
}
