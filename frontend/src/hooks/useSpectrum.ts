import { useCallback, useEffect, useRef, useState } from "react";
import type { SpectrumResponse } from "../lib/types";
import type { LiveSource } from "../lib/api";
import {
  assertSpectrumResponse,
  buildSpectrumUrl,
  fetchJsonWithTimeout,
  isAbortError,
  describeError,
  spectrumRequestError,
  canRecoverKnownExposures,
  assertDataAccess,
  assertDiscoveryMode,
} from "../lib/api";
import type { SpectrumRequest } from "../lib/api";

export type SpectrumLoadSource = LiveSource;

export interface SpectrumState {
  status: "idle" | "loading" | "ready" | "error" | "cancelled";
  spectrum: SpectrumResponse | null;
  source: SpectrumLoadSource | null;
  error: string | null;
  technicalError: string | null;
  canRecoverKnown: boolean;
  reload: () => void;
  cancel: () => void;
}

const SPECTRUM_TIMEOUT_SAVED_MS = 15_000;
const SPECTRUM_TIMEOUT_ARBITRARY_MS = 130_000;

/**
 * Load real observations from `/api/v1/spectrum` when enabled. Failed or
 * simulated responses produce a clean error.
 */
export function useSpectrum(
  query: SpectrumRequest,
  skySource: LiveSource | null,
  enabled: boolean,
): SpectrumState {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<SpectrumState>({
    status: enabled ? "loading" : "idle",
    spectrum: null,
    source: null,
    error: null,
    technicalError: null,
    canRecoverKnown: false,
    reload: () => setAttempt((value) => value + 1),
    cancel: () => {},
  });

  const key = [
    query.discovery ?? "live",
    String(query.ra),
    String(query.dec),
    query.target ?? "",
    skySource ?? query.source ?? "archive",
    enabled ? "1" : "0",
  ].join("|");
  const activeRequest = useRef<{
    key: string;
    attempt: number;
    cancel: () => void;
  } | null>(null);
  const resolvedRequest = useRef<{ key: string; attempt: number } | null>(null);

  useEffect(() => {
    if (!enabled) {
      resolvedRequest.current = { key, attempt };
      setState((previous) => ({
        ...previous,
        status: "idle",
        spectrum: null,
        source: null,
        error: null,
        technicalError: null,
        canRecoverKnown: false,
      }));
      return;
    }

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
          spectrum: null,
          source: null,
          error: null,
          technicalError: null,
          canRecoverKnown: false,
        }));
      },
    };
    resolvedRequest.current = { key, attempt };

    setState((previous) => ({
      ...previous,
      status: "loading",
      spectrum: null,
      source: null,
      error: null,
      technicalError: null,
      canRecoverKnown: false,
    }));

    const finish = (spectrum: SpectrumResponse, source: SpectrumLoadSource) => {
      if (cancelled) return;
      setState((previous) => ({
        ...previous,
        status: "ready",
        spectrum,
        source,
        error: null,
        technicalError: null,
        canRecoverKnown: false,
      }));
    };

    const fail = (error: unknown) => {
      if (cancelled) return;
      setState((previous) => ({
        ...previous,
        status: "error",
        spectrum: null,
        source: null,
        error: spectrumRequestError(error),
        technicalError: describeError(error),
        canRecoverKnown: canRecoverKnownExposures(error),
      }));
    };

    const loadApi = async () => {
      const source = skySource ?? query.source ?? "archive";
      const url = buildSpectrumUrl({ ...query, source });
      const timeoutMs =
        source === "saved"
          ? SPECTRUM_TIMEOUT_SAVED_MS
          : SPECTRUM_TIMEOUT_ARBITRARY_MS;
      try {
        const raw = await fetchJsonWithTimeout<SpectrumResponse>(
          url,
          controller.signal,
          timeoutMs,
        );
        assertSpectrumResponse(raw);
        assertDataAccess(raw.provenance.data_access, source);
        assertDiscoveryMode(
          raw.provenance.discovery_mode,
          query.discovery ?? "live",
          source,
        );
        finish(raw, raw.provenance.data_access ?? source);
      } catch (error) {
        if (cancelled || isAbortError(error)) return;
        fail(error);
      }
    };

    void loadApi();

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
  }, [key, attempt, enabled]);

  const reload = useCallback(() => setAttempt((value) => value + 1), []);
  const cancel = useCallback(() => activeRequest.current?.cancel(), []);

  const current =
    resolvedRequest.current?.key === key &&
    resolvedRequest.current.attempt === attempt;
  return current
    ? { ...state, reload, cancel }
    : {
        status: enabled ? "loading" : "idle",
        spectrum: null,
        source: null,
        error: null,
        technicalError: null,
        canRecoverKnown: false,
        reload,
        cancel,
      };
}
