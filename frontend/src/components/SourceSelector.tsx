import type { DataAccess, DiscoveryMode } from "../lib/api";

export function SourceSelector({
  source,
  discovery = "live",
  savedAvailable,
  onChange,
}: {
  source: DataAccess;
  discovery?: DiscoveryMode;
  savedAvailable: boolean;
  onChange: (source: DataAccess, discovery?: DiscoveryMode) => void;
}) {
  return (
    <label className="source-selector">
      Data source{" "}
      <select
        value={source === "archive" && discovery === "known" ? "known" : source}
        onChange={(event) =>
          event.target.value === "known"
            ? onChange("archive", "known")
            : onChange(event.target.value as DataAccess, "live")
        }
      >
        <option value="archive">Online archive — fresh search</option>
        <option value="known" disabled={!savedAvailable}>
          Known exposures — fresh downloads
        </option>
        <option value="saved" disabled={!savedAvailable}>
          Saved catalog data
        </option>
      </select>
    </label>
  );
}
