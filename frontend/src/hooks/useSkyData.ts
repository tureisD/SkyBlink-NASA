import { useCallback, useEffect, useRef, useState } from "react";
import type { SkyResponse } from "../lib/types";
import {
  buildSkyUrl,
  describeError,
  fetchJsonWithTimeout,
  isAbortError,
  normaliseManifest,
  assertSkyResponse,
  assertDataAccess,
  assertDiscoveryMode,
  skyRequestError,
  canRecoverKnownExposures,
} from "../lib/api";
import type { LiveSource } from "../lib/api";

export interface SkyRequestState {
  source: LiveSource;
  discovery?: "live" | "known";
  ra: number;
  dec: number;
  target: string | null;
  size: number;
}

export interface SkyDataState {
  status: "loading" | "ready" | "error" | "cancelled";
  manifest: SkyResponse | null;
  source: LiveSource | null;
  /** Technical detail when a live request failed; never a fixture fallback. */
  liveError: string | null;
  error: string | null;
  canRecoverKnown: boolean;
  reload: () => void;
  /** Stops browser waiting. Already-started server work may continue. */
  cancel: () => void;
}

const ARCHIVE_TIMEOUT_MS = 130_000;
const SAVED_TIMEOUT_MS = 20_000;

/**
 * Load `/api/v1/sky` for the resolved query. Normal operation is live data
 * only: a failed request returns a clean error and never loads a fixture.
 * Simulated responses are rejected before they reach the viewer.
 */
export function useSkyData(query: SkyRequestState): SkyDataState {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<SkyDataState>({
    status: "loading",
    manifest: null,
    source: null,
    liveError: null,
    error: null,
    canRecoverKnown: false,
    reload: () => setAttempt((value) => value + 1),
    cancel: () => {},
  });

  const key = [
    query.discovery ?? "live",
    query.source,
    String(query.ra),
    String(query.dec),
    query.target ?? "",
    String(query.size),
  ].join("|");
  const activeRequest = useRef<{
    key: string;
    attempt: number;
    cancel: () => void;
  } | null>(null);
  const resolvedRequest = useRef<{ key: string; attempt: number } | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;
    activeRequest.current = {
      key,
      attempt,
      cancel: () => {
        cancelled = true;
        controller.abort();
        resolvedRequest.current = { key, attempt };
        setState((previous) => ({
          ...previous,
          status: "cancelled",
          manifest: null,
          source: null,
          error: null,
          canRecoverKnown: false,
          liveError: null,
        }));
      },
    };
    resolvedRequest.current = { key, attempt };

    setState((previous) => ({
      ...previous,
      status: "loading",
      manifest: null,
      source: null,
      error: null,
      canRecoverKnown: false,
      liveError: null,
    }));

    const finish = (patch: Partial<SkyDataState>) => {
      if (cancelled) return;
      setState((previous) => ({
        ...previous,
        status: "ready",
        error: null,
        canRecoverKnown: false,
        ...patch,
      }));
    };

    const fail = (
      message: string,
      liveError: string | null = null,
      canRecoverKnown = false,
    ) => {
      if (cancelled) return;
      setState((previous) => ({
        ...previous,
        status: "error",
        manifest: null,
        source: null,
        liveError,
        error: message,
        canRecoverKnown,
      }));
    };

    const loadLive = async () => {
      const url = buildSkyUrl(query);
      const timeoutMs =
        query.source === "archive" ? ARCHIVE_TIMEOUT_MS : SAVED_TIMEOUT_MS;
      try {
        const raw = await fetchJsonWithTimeout<SkyResponse>(
          url,
          controller.signal,
          timeoutMs,
        );
        assertSkyResponse(raw);
        assertDataAccess(raw.provenance.data_access, query.source);
        assertDiscoveryMode(
          raw.provenance.discovery_mode,
          query.discovery ?? "live",
          query.source,
        );
        if (cancelled) return;
        finish({
          manifest: normaliseManifest(raw),
          source: raw.provenance.data_access ?? query.source,
          liveError: null,
        });
      } catch (error) {
        if (cancelled || isAbortError(error)) return;
        fail(
          skyRequestError(error, query.source),
          `Live SPHEREx request failed (${url}): ${describeError(error)}`,
          canRecoverKnownExposures(error),
        );
      }
    };

    void loadLive();
    return () => {
      cancelled = true;
      controller.abort();
      if (
        activeRequest.current?.key === key &&
        activeRequest.current.attempt === attempt
      )
        activeRequest.current = null;
    };
    // The key captures every request-relevant input.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, attempt]);

  const reload = useCallback(() => setAttempt((value) => value + 1), []);
  const cancel = useCallback(() => activeRequest.current?.cancel(), []);

  // A changed render can precede effect cleanup. Never expose the old field
  // under a new query, even during that single render.
  const current =
    resolvedRequest.current?.key === key &&
    resolvedRequest.current.attempt === attempt;
  return current
    ? { ...state, reload, cancel }
    : {
        status: "loading",
        manifest: null,
        source: null,
        error: null,
        canRecoverKnown: false,
        liveError: null,
        reload,
        cancel,
      };
}
