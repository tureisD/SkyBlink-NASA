import { useEffect, useState } from "react";
import { fetchJsonWithTimeout, describeError } from "../lib/api";
import { parseGaiaCatalog } from "../lib/gaia";
import type { GaiaCatalog, GaiaSource } from "../lib/gaia";

export interface GaiaCatalogState extends GaiaCatalog {
  status: "idle" | "loading" | "ready" | "error";
  error: string | null;
}

const EMPTY: GaiaCatalogState = {
  status: "idle",
  sources: [] as GaiaSource[],
  isSimulatedFallback: false,
  attribution: null,
  error: null,
};

const catalogCache = new Map<string, Promise<GaiaCatalog>>();

function loadCatalog(url: string): Promise<GaiaCatalog> {
  const cached = catalogCache.get(url);
  if (cached) return cached;
  const pending = fetchJsonWithTimeout<unknown>(url, undefined, 15_000).then(
    parseGaiaCatalog,
  );
  catalogCache.set(url, pending);
  pending.catch(() => catalogCache.delete(url));
  return pending;
}

/**
 * Load the optional Gaia pin catalog once per manifest. This is not on the
 * blink path: pins are mirrored into the canvas ref and never trigger React
 * updates per animation tick.
 */
export function useGaiaSources(url: string | null): GaiaCatalogState {
  const [state, setState] = useState<GaiaCatalogState>(EMPTY);

  useEffect(() => {
    if (!url) {
      setState(EMPTY);
      return;
    }
    let cancelled = false;
    setState((previous) => ({
      ...previous,
      status: "loading",
      error: null,
    }));
    loadCatalog(url).then(
      (catalog) => {
        if (cancelled) return;
        setState({
          status: "ready",
          sources: catalog.sources,
          isSimulatedFallback: catalog.isSimulatedFallback,
          attribution: catalog.attribution,
          error: null,
        });
      },
      (error: unknown) => {
        if (cancelled) return;
        setState({
          status: "error",
          sources: [],
          isSimulatedFallback: false,
          attribution: null,
          error: `Gaia catalog unavailable: ${describeError(error)}`,
        });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [url]);

  return state;
}
