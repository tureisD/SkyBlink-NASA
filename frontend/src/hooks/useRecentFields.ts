import { useEffect, useState } from "react";
import type { SkyResponse } from "../lib/types";
import type { DataAccess } from "../lib/api";

export interface RecentField {
  ra: number;
  dec: number;
  size: number;
  target: string | null;
  source: DataAccess;
  discovery: "live" | "known";
  spectrumDiscovery: "inherit" | "known";
  name: string;
}
const KEY = "skyblink.recent-fields.v1";

function readRecent(): RecentField[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    if (!Array.isArray(value)) return [];
    return value
      .filter(
        (entry): entry is RecentField =>
          entry &&
          typeof entry === "object" &&
          Number.isFinite(entry.ra) &&
          entry.ra >= 0 &&
          entry.ra < 360 &&
          Number.isFinite(entry.dec) &&
          Math.abs(entry.dec) <= 90 &&
          Number.isFinite(entry.size) &&
          entry.size >= 0.05 &&
          entry.size <= 0.2 &&
          (entry.source === "archive" || entry.source === "saved") &&
          (entry.target === null ||
            [
              "wise_0855",
              "barnards_star",
              "eps_indi_b",
              "rw_aurigae",
              "r_draconis",
            ].includes(entry.target)) &&
          (entry.source !== "saved" || entry.target !== null) &&
          (entry.discovery === undefined ||
            entry.discovery === "live" ||
            (entry.discovery === "known" &&
              entry.source === "archive" &&
              entry.target !== null)) &&
          (entry.spectrumDiscovery === undefined ||
            entry.spectrumDiscovery === "inherit" ||
            (entry.spectrumDiscovery === "known" &&
              entry.source === "archive" &&
              entry.target !== null)) &&
          typeof entry.name === "string",
      )
      .slice(0, 6)
      .map((entry) => ({
        ra: entry.ra,
        dec: entry.dec,
        size: entry.size,
        target: entry.target,
        source: entry.source,
        discovery: entry.discovery ?? "live",
        spectrumDiscovery: entry.spectrumDiscovery ?? "inherit",
        name: entry.name.slice(0, 80),
      }));
  } catch {
    return [];
  }
}

/** Only successful query coordinates are retained locally. Never stores observation products. */
export function useRecentFields(
  manifest: SkyResponse | null,
  source: DataAccess,
  spectrumDiscovery: "inherit" | "known" = "inherit",
) {
  const [recent, setRecent] = useState<RecentField[]>(readRecent);
  useEffect(() => {
    if (!manifest) return;
    const field: RecentField = {
      ra: manifest.query.ra,
      dec: manifest.query.dec,
      size: manifest.query.size_deg,
      target: manifest.query.target_id,
      source,
      discovery: manifest.provenance.discovery_mode ?? "live",
      spectrumDiscovery,
      name:
        manifest.target?.name ??
        `${manifest.query.ra.toFixed(4)}, ${manifest.query.dec.toFixed(4)}`,
    };
    setRecent((previous) => {
      const next = [
        field,
        ...previous.filter(
          (item) =>
            !(
              item.ra === field.ra &&
              item.dec === field.dec &&
              item.size === field.size &&
              item.source === field.source &&
              item.discovery === field.discovery &&
              item.spectrumDiscovery === field.spectrumDiscovery
            ),
        ),
      ].slice(0, 6);
      try {
        localStorage.setItem(KEY, JSON.stringify(next));
      } catch {
        /* Private/storage-limited browsing still works. */
      }
      return next;
    });
  }, [manifest, source, spectrumDiscovery]);
  const clear = () => {
    setRecent([]);
    try {
      localStorage.removeItem(KEY);
    } catch {
      /* Local history is optional. */
    }
  };
  return { recent, clear };
}
