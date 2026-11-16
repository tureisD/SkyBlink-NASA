/**
 * API access and asset-URL resolution.
 *
 * `VITE_API_BASE` defaults to `/api/v1` (same origin in production, Vite proxy
 * in development). All observation data comes from the API; simulated
 * responses and retired fixture asset paths are rejected.
 */

import type { SkyResponse, SpectrumResponse } from "./types";
export type DataAccess = "archive" | "saved";
export type LiveSource = DataAccess;
export type DiscoveryMode = "live" | "known" | "indexed";

const rawBase = import.meta.env.VITE_API_BASE?.trim() || "/api/v1";
export const API_BASE = rawBase.replace(/\/+$/, "");

export interface SkyRequest {
  source?: DataAccess;
  discovery?: DiscoveryMode;
  ra: number;
  dec: number;
  target: string | null;
  size: number;
}

export interface SpectrumRequest {
  source?: DataAccess;
  discovery?: DiscoveryMode;
  ra: number;
  dec: number;
  target: string | null;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail: unknown;

  constructor(status: number, code: string, message: string, detail: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

interface ErrorEnvelope {
  error?: {
    code?: string;
    message?: string;
    detail?: unknown;
  };
}

function asErrorEnvelope(value: unknown): ErrorEnvelope | null {
  if (typeof value !== "object" || value === null) return null;
  return value as ErrorEnvelope;
}

/** Fetch JSON, parsing the contract §3.7 error envelope when present. */
export async function fetchJson<T>(
  url: string,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(url, {
    signal,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      // The dev proxy / static host may return HTML or empty bodies.
    }
    const envelope = asErrorEnvelope(payload)?.error;
    throw new ApiError(
      response.status,
      envelope?.code ?? `HTTP_${response.status}`,
      envelope?.message ?? `HTTP ${response.status} ${response.statusText}`,
      envelope?.detail ?? null,
    );
  }
  return (await response.json()) as T;
}

/**
 * Fetch JSON with a client-side deadline. A cold backend/IRSA fetch that
 * exceeds the budget fails cleanly instead of leaving the UI loading forever.
 * Both timeout and caller cancellation abort the underlying browser request.
 * This stops waiting; a server may continue already-started shared work.
 */
export async function fetchJsonWithTimeout<T>(
  url: string,
  signal: AbortSignal | undefined,
  timeoutMs = 20_000,
): Promise<T> {
  if (signal?.aborted)
    throw new DOMException("Request cancelled", "AbortError");
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  let cancel: () => void = () => {};
  const interrupted = new Promise<never>((_, reject) => {
    cancel = () => {
      reject(new DOMException("Request cancelled", "AbortError"));
      controller.abort();
    };
    signal?.addEventListener("abort", cancel, { once: true });
    timer = setTimeout(() => {
      reject(
        new ApiError(
          408,
          "REQUEST_TIMEOUT",
          `Request timed out after ${Math.round(timeoutMs / 1000)} s. Retry or choose another field.`,
          null,
        ),
      );
      controller.abort();
    }, timeoutMs);
  });
  try {
    return await Promise.race([
      fetchJson<T>(url, controller.signal),
      interrupted,
    ]);
  } finally {
    if (timer !== undefined) clearTimeout(timer);
    signal?.removeEventListener("abort", cancel);
  }
}

export function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    const label = error.code.startsWith("HTTP_")
      ? `HTTP ${error.status}`
      : `${error.code} (HTTP ${error.status})`;
    const message =
      error.message.replace(new RegExp(`^HTTP ${error.status}\\s*`), "") ||
      "request failed";
    return `${label}: ${message}`;
  }
  if (error instanceof Error) return error.message;
  return String(error);
}

/** Primary recovery copy comes from typed protocol status, never prose matching.
 * NO_DATA also represents unusable pixels; it does not alone certify no coverage.
 */
export function skyRequestError(error: unknown, source: DataAccess): string {
  if (isResourceFailure(error)) return error.message;
  if (error instanceof ApiError) {
    if (
      error.status === 503 &&
      error.code === "UPSTREAM_UNAVAILABLE" &&
      typeof error.detail === "object" &&
      error.detail !== null &&
      "reason" in error.detail &&
      error.detail.reason === "PROCESSING_SOURCE_CHANGED"
    ) {
      return "The server needs to restart after an update before new observations can be processed. Retry once it has restarted.";
    }
    if (error.code === "INVALID_COORDINATES") {
      return "These coordinates were rejected. Check that RA and Dec are valid decimal degrees, then search again.";
    }
    if (error.code === "VALIDATION_ERROR") {
      return "Some request settings were rejected. Check the coordinates, target, field size, and data source, then try again.";
    }
    if (error.code === "NO_COMPARABLE") {
      return "No comparable observation pair was established for this request. Individual observations may exist. Inspect the request details or try another field.";
    }
    if (error.code === "NO_DATA") {
      return source === "saved"
        ? "This saved example is unavailable. Choose another saved target or explicitly switch to the online archive."
        : "No displayable SPHEREx observations were returned for this request. Coverage may be missing, or available pixels may be unusable. Inspect the request details or search another position.";
    }
    if (
      error.code === "REQUEST_TIMEOUT" ||
      error.status === 408 ||
      error.status === 504
    ) {
      return "The request ran out of time. Observation coverage is still unknown. Retry, search another field, or explicitly choose a saved example.";
    }
    if (
      error.code === "UPSTREAM_UNAVAILABLE" ||
      error.status === 502 ||
      error.status === 503
    ) {
      return "Observation retrieval or processing is unavailable right now. This does not establish missing sky coverage. Retry later or explicitly choose a saved example.";
    }
    if (error.status === 400 || error.status === 422) {
      return "Some request settings were rejected. Check the coordinates, target, field size, and data source, then try again.";
    }
  }
  return source === "saved"
    ? "This saved example could not be loaded. See the request details, retry, or choose another target. Archive coverage was not checked."
    : "The field could not be loaded, and observation coverage is unknown. See the request details, retry, or search another position.";
}

/** Legacy payloads may omit access metadata; known mismatches must not render. */
export function assertDataAccess(actual: unknown, requested: DataAccess): void {
  if (actual !== undefined && actual !== null && actual !== requested) {
    throw new Error(
      `Data source mismatch: requested ${requested}, received ${String(actual)}.`,
    );
  }
}

/** Failed retrieval is distinct from a returned spectrum with zero eligible samples. */
export function spectrumRequestError(error: unknown): string {
  if (isResourceFailure(error)) return error.message;
  if (error instanceof ApiError) {
    if (
      error.code === "UPSTREAM_UNAVAILABLE" &&
      typeof error.detail === "object" &&
      error.detail !== null &&
      "reason" in error.detail &&
      error.detail.reason === "PROCESSING_SOURCE_CHANGED"
    ) {
      return "The server needs to restart after an update before new spectrum measurements can be processed. Retry once it has restarted.";
    }
    if (error.code === "NO_DATA")
      return "No spectrum measurements were returned for this request. This is not a zero-flux measurement or proof that the position has no observations.";
    if (
      error.code === "REQUEST_TIMEOUT" ||
      error.status === 408 ||
      error.status === 504
    )
      return "The spectrum request reached its time limit. Measurement availability is still unknown; retry the request.";
    if (
      error.code === "UPSTREAM_UNAVAILABLE" ||
      error.status === 502 ||
      error.status === 503
    )
      return "Spectrum retrieval is unavailable right now. Image availability does not guarantee that a separate spectrum request can complete. Retry, or choose an explicit recovery option below.";
  }
  return "The spectrum request failed. No measurement result was returned. Inspect the request details and retry.";
}

function apiFailureReason(error: ApiError): unknown {
  return typeof error.detail === "object" &&
    error.detail !== null &&
    "reason" in error.detail
    ? error.detail.reason
    : undefined;
}

function isResourceFailure(error: unknown): error is ApiError {
  return (
    error instanceof ApiError &&
    ["SERVER_BUSY", "STORAGE_BUDGET_EXCEEDED", "STORAGE_UNAVAILABLE"].includes(
      String(apiFailureReason(error)),
    )
  );
}

/** Recovery changes discovery, so it cannot repair local storage/process errors. */
export function canRecoverKnownExposures(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    error.code === "UPSTREAM_UNAVAILABLE" &&
    !isResourceFailure(error) &&
    apiFailureReason(error) !== "PROCESSING_SOURCE_CHANGED"
  );
}

/** Known-list recovery requires explicit provenance; legacy absence is only live/unknown. */
export function assertDiscoveryMode(
  actual: unknown,
  requested: DiscoveryMode,
  source: DataAccess,
): void {
  if (
    actual !== undefined &&
    actual !== null &&
    actual !== "live" &&
    actual !== "known" &&
    actual !== "indexed"
  ) {
    throw new Error("Observation discovery mode is malformed.");
  }
  if (
    (requested !== "live" && (source !== "archive" || actual !== requested)) ||
    (actual !== undefined && actual !== null && actual !== requested)
  ) {
    throw new Error(
      `Discovery mode mismatch: requested ${requested}, received ${String(actual)}.`,
    );
  }
}

function assertDiscoveryMetadata(provenance: {
  discovery_mode?: unknown;
  discovery_status?: unknown;
  missing_collections?: unknown;
}): void {
  if (
    provenance.discovery_mode != null &&
    provenance.discovery_mode !== "live" &&
    provenance.discovery_mode !== "known" &&
    provenance.discovery_mode !== "indexed"
  )
    throw new Error("Observation discovery mode is malformed.");
  const status = provenance.discovery_status;
  if (
    status !== undefined &&
    status !== null &&
    (typeof status !== "string" ||
      !["complete", "partial", "unknown"].includes(status))
  ) {
    throw new Error("Observation discovery status is malformed.");
  }
  const missing = provenance.missing_collections;
  if (
    missing !== undefined &&
    missing !== null &&
    (!Array.isArray(missing) ||
      missing.some((value) => typeof value !== "string"))
  ) {
    throw new Error("Observation missing-collection metadata is malformed.");
  }
}

export function buildSkyUrl(query: SkyRequest): string {
  const params = new URLSearchParams({
    source: query.source ?? "archive",
    discovery: query.discovery ?? "live",
    ra: String(query.ra),
    dec: String(query.dec),
    size: String(query.size),
    bands: "all",
    epochs: "all",
    include_diff: "true",
  });
  if (query.target) params.set("target_id", query.target);
  return `${API_BASE}/sky?${params.toString()}`;
}

export function buildSpectrumUrl(query: SpectrumRequest): string {
  const params = new URLSearchParams({
    source: query.source ?? "archive",
    discovery: query.discovery ?? "live",
    ra: String(query.ra),
    dec: String(query.dec),
  });
  if (query.target) params.set("target_id", query.target);
  return `${API_BASE}/spectrum?${params.toString()}`;
}

/**
 * Resolve a manifest asset path against the configured API base.
 *
 * The contract returns `/api/v1/assets/...`. With a same-origin base the path
 * is already correct. With an absolute `VITE_API_BASE` (e.g.
 * `https://host/api/v1`) the origin/path are swapped in. Retired synthetic
 * namespaces are rejected, including absolute URLs.
 */
export function resolveAssetUrl(url: string): string {
  if (!url) return url;
  const parsed = new URL(url, "https://skyblink.invalid/");
  const path = decodeURIComponent(parsed.pathname);
  if (
    /(?:^|\/)(?:mock|fixtures?|synthetic|fallback_[^/]*)(?:\/|$)/i.test(path)
  ) {
    throw new Error("Synthetic observation assets are not supported.");
  }
  if (url.startsWith("data:")) {
    throw new Error("Inline observation assets are not supported.");
  }
  if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
    throw new Error("Observation asset URL protocol is not supported.");
  }
  if (/^(?:https?:)?\/\//.test(url)) return url;
  if (!/^https?:/i.test(API_BASE)) return url;

  const base = new URL(API_BASE);
  if (url.startsWith("/api/v1/")) {
    const basePath = base.pathname.replace(/\/+$/, "");
    return `${base.origin}${basePath}${url.slice("/api/v1".length)}`;
  }
  return new URL(url.replace(/^\/+/, ""), `${API_BASE}/`).toString();
}

function mapAssets(map: Record<string, string>): Record<string, string> {
  return Object.fromEntries(
    Object.entries(map).map(([key, url]) => [key, resolveAssetUrl(url)]),
  );
}

/** Rewrite manifest asset URLs for the configured API origin. */
export function normaliseManifest(manifest: SkyResponse): SkyResponse {
  return {
    ...manifest,
    epochs: manifest.epochs.map((epoch) => ({
      ...epoch,
      frames: mapAssets(epoch.frames),
      telemetry: epoch.telemetry
        ? { ...epoch.telemetry, url: resolveAssetUrl(epoch.telemetry.url) }
        : (epoch.telemetry ?? null),
    })),
    differences: Object.fromEntries(
      Object.entries(manifest.differences).map(([key, frames]) => [
        key,
        mapAssets(frames),
      ]),
    ),
    reference_overlays: Object.fromEntries(
      Object.entries(manifest.reference_overlays ?? {}).map(([key, value]) => [
        key,
        // `attribution` is prose, not an asset URL.
        key === "attribution" ? value : resolveAssetUrl(value),
      ]),
    ),
  };
}

export function assertSkyResponse(
  value: unknown,
): asserts value is SkyResponse {
  if (typeof value !== "object" || value === null) {
    throw new Error("Sky manifest is not a JSON object.");
  }
  const candidate = value as Partial<SkyResponse>;
  if (!candidate.wcs || typeof candidate.wcs.width !== "number") {
    throw new Error("Sky manifest is missing the WCS grid.");
  }
  if (!Array.isArray(candidate.epochs) || candidate.epochs.length === 0) {
    throw new Error("Sky manifest has no epochs.");
  }
  if (!candidate.provenance) {
    throw new Error("Sky manifest is missing provenance.");
  }
  if (candidate.provenance.is_simulated_fallback !== false) {
    throw new Error(
      "Sky manifest must identify real observations; simulated data is not supported.",
    );
  }
  assertDiscoveryMetadata(candidate.provenance);
  for (const epoch of candidate.epochs) {
    if (
      typeof epoch.epoch_id !== "string" ||
      typeof epoch.frames !== "object"
    ) {
      throw new Error("Sky manifest epoch is malformed.");
    }
  }
  if (typeof candidate.differences !== "object") {
    throw new Error("Sky manifest is missing differences.");
  }
}

export function assertSpectrumResponse(
  value: unknown,
): asserts value is SpectrumResponse {
  if (typeof value !== "object" || value === null) {
    throw new Error("Spectrum response is not a JSON object.");
  }
  const candidate = value as Partial<SpectrumResponse>;
  if (!Array.isArray(candidate.epochs) || candidate.epochs.length === 0) {
    throw new Error("Spectrum response has no epochs.");
  }
  if (!candidate.provenance) {
    throw new Error("Spectrum response is missing provenance.");
  }
  if (candidate.provenance.is_simulated_fallback !== false) {
    throw new Error(
      "Spectrum must identify real observations; simulated data is not supported.",
    );
  }
  assertDiscoveryMetadata(candidate.provenance);
}
