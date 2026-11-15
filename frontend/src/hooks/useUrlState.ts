import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { KNOWN_TARGET_IDS } from "../lib/targets";
import type { ColormapId } from "../lib/colormaps";
import type { StretchId } from "../lib/display";

/**
 * Bidirectional URL state (AGENTS.md §5.4).
 *
 * Encoded parameters: ra, dec, size, target, bands, epoch, mode, fps, diff,
 * overlay. Invalid values fall back to defaults and raise a non-blocking
 * warning; they never throw and never block the canvas.
 */

export type PlaybackMode = "blink" | "still";

export type OverlayKey =
  | "reticle"
  | "box"
  | "scale"
  | "compass"
  | "flags"
  | "gaia"
  | "lvf";

export const OVERLAY_KEYS: readonly OverlayKey[] = [
  "reticle",
  "box",
  "scale",
  "compass",
  "flags",
  "gaia",
  "lvf",
];

export const DEFAULT_OVERLAYS: readonly OverlayKey[] = ["scale", "compass"];

export interface UrlState {
  /** Version 1 links are view recipes, not immutable analysis retrieval. */
  pair: string | null;
  epochA: string | null;
  epochB: string | null;
  analysis: string | null;
  colormap: ColormapId;
  stretch: StretchId;
  contrast: number;
  bias: number;
  pingpong: boolean;
  zoom: number;
  /** Camera offsets in fractions of the rendered image width/height. */
  panX: number;
  panY: number;
  task: "observe" | "compare" | "measure" | "evidence";
  comparisonLayout: "single" | "side-by-side";
  advanced: boolean;
  source: "archive" | "saved";
  discovery: "live" | "known";
  spectrumDiscovery: "inherit" | "known";
  ra: number | null;
  dec: number | null;
  size: number;
  target: string | null;
  /** "all" | "thermal" | "1" … "6" */
  bands: string;
  /** "all" or an epoch id such as "2025_E1" */
  epoch: string;
  mode: PlaybackMode;
  fps: number;
  diff: boolean;
  overlay: OverlayKey[];
  /** Trial-motion sandbox: ICRS sky-fixed vs target co-moving. */
  track: boolean;
  /** Trial μ_α* (mas/yr); null means use the catalog target's PM. */
  pmra: number | null;
  /** Trial μ_δ (mas/yr); null means use the catalog target's PM. */
  pmdec: number | null;
  /** Parallax reflex overlay (2 AU baseline). */
  parallax: boolean;
  /** Test/assumed distance for the parallax overlay, AU. */
  au: number;
}

export interface UrlStateApi {
  state: UrlState;
  update: (patch: Partial<UrlState>) => void;
  reset: () => void;
  warnings: string[];
  copyLink: () => Promise<boolean>;
  /** Reproducible current URL, including sandbox state. */
  shareUrl: () => string;
  copied: boolean;
}

export const MIN_FPS = 1;
export const MAX_FPS = 8;
export const DEFAULT_FPS = 4;
export const MIN_SIZE_DEG = 0.05;
export const MAX_SIZE_DEG = 0.2;
export const MIN_DISTANCE_AU = 0.1;
export const MAX_DISTANCE_AU = 1e9;
export const DEFAULT_DISTANCE_AU = 400;
export const SHARE_VERSION = "1";

const EPOCH_PATTERN = /^\d{4}_E\d+$/;
const TARGET_PATTERN = /^[A-Za-z0-9_-]{1,64}$/;
const BAND_VALUES = new Set(["all", "thermal", "1", "2", "3", "4", "5", "6"]);

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

function defaultState(): UrlState {
  return {
    pair: null,
    epochA: null,
    epochB: null,
    analysis: null,
    colormap: "gray",
    stretch: "linear",
    contrast: 1,
    bias: 0,
    pingpong: false,
    zoom: 1,
    panX: 0,
    panY: 0,
    task: "observe",
    comparisonLayout: "single",
    advanced: false,
    source: "archive",
    discovery: "live",
    spectrumDiscovery: "inherit",
    ra: null,
    dec: null,
    size: MAX_SIZE_DEG,
    target: null,
    bands: "all",
    epoch: "all",
    mode: "still",
    fps: DEFAULT_FPS,
    diff: false,
    overlay: [...DEFAULT_OVERLAYS],
    track: false,
    pmra: null,
    pmdec: null,
    parallax: false,
    au: DEFAULT_DISTANCE_AU,
  };
}

function parseNumber(value: string | null): number | null {
  if (value === null || value.trim() === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

interface ParseResult {
  state: UrlState;
  warnings: string[];
}

function parseUrl(search: string, restorePaused = true): ParseResult {
  const params = new URLSearchParams(search);
  const state = defaultState();
  const warnings: string[] = [];
  const known = new Set([
    "v",
    "pair",
    "epochA",
    "epochB",
    "analysis",
    "colormap",
    "stretch",
    "contrast",
    "bias",
    "pingpong",
    "zoom",
    "panX",
    "panY",
    "task",
    "advanced",
    "comparisonLayout",
    "source",
    "discovery",
    "spectrumDiscovery",
    "ra",
    "dec",
    "size",
    "target",
    "bands",
    "epoch",
    "mode",
    "fps",
    "diff",
    "overlay",
    "track",
    "pmra",
    "pmdec",
    "parallax",
    "au",
  ]);

  const version = params.get("v");
  if (version !== null && version !== SHARE_VERSION) {
    return {
      state,
      warnings: [
        `Share format version ${version} is unsupported. No shared selection was restored.`,
      ],
    };
  }
  for (const key of known) {
    if (params.getAll(key).length > 1)
      warnings.push(`Repeated URL parameter ${key}; using its first value.`);
  }
  for (const key of [
    "ra",
    "dec",
    "size",
    "fps",
    "pmra",
    "pmdec",
    "au",
    "contrast",
    "bias",
    "zoom",
    "panX",
    "panY",
  ]) {
    if (params.has(key) && parseNumber(params.get(key)) === null)
      warnings.push(`Invalid numeric value for ${key}; using the default.`);
  }
  const range = (key: string, fallback: number, min: number, max: number) => {
    const value = parseNumber(params.get(key));
    if (value === null) return fallback;
    if (value < min || value > max)
      warnings.push(`${key} was clamped to ${min}–${max}.`);
    return Math.min(max, Math.max(min, value));
  };
  state.contrast = range("contrast", 1, 0.4, 2.6);
  state.bias = range("bias", 0, -0.3, 0.3);
  state.zoom = range("zoom", 1, 1, 12);
  state.panX = range("panX", 0, -2, 2);
  state.panY = range("panY", 0, -2, 2);
  for (const key of ["pingpong", "advanced"] as const) {
    const value = params.get(key);
    if (value === "1" || value === "true") state[key] = true;
    else if (value !== null && value !== "0" && value !== "false")
      warnings.push(`Invalid ${key} flag; using false.`);
  }
  const colormap = params.get("colormap");
  if (colormap && ["gray", "inferno", "viridis", "coolwarm"].includes(colormap))
    state.colormap = colormap as ColormapId;
  else if (colormap) warnings.push("Unknown colormap; using grayscale.");
  const stretch = params.get("stretch");
  if (stretch && ["linear", "log", "asinh", "zscale"].includes(stretch))
    state.stretch = stretch as StretchId;
  else if (stretch) warnings.push("Unknown display stretch; using linear.");
  const task = params.get("task");
  if (task && ["observe", "compare", "measure", "evidence"].includes(task))
    state.task = task as UrlState["task"];
  else if (task) warnings.push("Unknown workspace task; using Observe.");
  const layout = params.get("comparisonLayout");
  if (layout === "single" || layout === "side-by-side")
    state.comparisonLayout = layout;
  else if (layout)
    warnings.push("Unknown comparison layout; using a single canvas.");
  for (const key of ["epochA", "epochB"] as const) {
    const value = params.get(key);
    if (value && EPOCH_PATTERN.test(value)) state[key] = value;
    else if (value)
      warnings.push(
        `Invalid ${key}; the shared observation could not be restored.`,
      );
  }
  const pair = params.get("pair");
  if (pair && /^\d{4}_E\d+_minus_\d{4}_E\d+$/.test(pair)) state.pair = pair;
  else if (pair)
    warnings.push(
      "Invalid comparison pair; the shared comparison could not be restored.",
    );
  const analysis = params.get("analysis");
  if (analysis && /^sha256:[a-f0-9]{64}$/.test(analysis))
    state.analysis = analysis;
  else if (analysis)
    warnings.push("Invalid analysis fingerprint; identity cannot be checked.");

  for (const key of params.keys()) {
    if (!known.has(key)) {
      warnings.push(`Ignored unknown URL parameter “${key}”.`);
    }
  }

  const source = params.get("source");
  if (source === "archive" || source === "saved") state.source = source;
  else if (source) warnings.push("Unknown data source; using online archive.");

  const ra = parseNumber(params.get("ra"));
  if (ra !== null) {
    if (ra >= 0 && ra < 360) state.ra = ra;
    else warnings.push("RA must be in [0, 360); using the manifest centre.");
  }

  const dec = parseNumber(params.get("dec"));
  if (dec !== null) {
    if (dec >= -90 && dec <= 90) state.dec = dec;
    else warnings.push("Dec must be in [−90, 90]; using the manifest centre.");
  }
  if ((state.ra === null) !== (state.dec === null)) {
    state.ra = null;
    state.dec = null;
    warnings.push(
      "Both valid RA and Dec are required; incomplete coordinates were not restored.",
    );
  }

  const size = parseNumber(params.get("size"));
  if (size !== null) {
    if (size < MIN_SIZE_DEG || size > MAX_SIZE_DEG) {
      warnings.push(
        `FOV ${size}° is out of range; clamped to ${MIN_SIZE_DEG}–${MAX_SIZE_DEG}°.`,
      );
    }
    state.size = Math.min(MAX_SIZE_DEG, Math.max(MIN_SIZE_DEG, size));
  }

  const target = params.get("target");
  if (target) {
    if (TARGET_PATTERN.test(target) && KNOWN_TARGET_IDS.has(target)) {
      state.target = target;
    } else {
      warnings.push(
        `Unknown target id “${target}”; using the manifest target.`,
      );
    }
  }

  const bands = params.get("bands");
  if (bands) {
    const candidates = bands
      .split(",")
      .map((value) => value.trim().toLowerCase())
      .filter(Boolean);
    const valid = candidates.find((value) => BAND_VALUES.has(value));
    if (!valid) {
      warnings.push(`Unknown band selection “${bands}”; showing all bands.`);
    } else {
      state.bands = valid;
      if (candidates.length > 1) {
        warnings.push(
          "This workspace displays one frame key at a time; using " +
            `“${valid}”. Multi-band coadds are server-provided (all / thermal).`,
        );
      }
    }
  }

  const epoch = params.get("epoch");
  if (epoch) {
    if (epoch === "all" || EPOCH_PATTERN.test(epoch)) state.epoch = epoch;
    else warnings.push(`Unknown epoch “${epoch}”; falling back to all epochs.`);
  }

  const mode = params.get("mode");
  if (mode) {
    if (mode === "blink" || mode === "still") state.mode = mode;
    else warnings.push(`Unknown mode “${mode}”; using a paused view.`);
  }

  const fps = parseNumber(params.get("fps"));
  if (fps !== null) {
    const rounded = Math.round(fps);
    if (rounded < MIN_FPS || rounded > MAX_FPS) {
      warnings.push(
        `Blink rate ${fps} FPS is outside ${MIN_FPS}–${MAX_FPS}; clamped. Photosensitivity cap: ${MAX_FPS} FPS.`,
      );
    }
    state.fps = Math.min(MAX_FPS, Math.max(MIN_FPS, rounded));
  }

  const diff = params.get("diff");
  if (diff !== null) {
    if (["1", "true", "yes"].includes(diff.toLowerCase())) state.diff = true;
    else if (["0", "false", "no"].includes(diff.toLowerCase()))
      state.diff = false;
    else warnings.push(`Unknown diff flag “${diff}”; using false.`);
  }

  const overlay = params.get("overlay");
  if (overlay) {
    if (overlay === "none") {
      state.overlay = [];
    } else {
      const requested = overlay
        .split(",")
        .map((value) => value.trim().toLowerCase())
        .filter(Boolean);
      const valid = requested.filter((value): value is OverlayKey =>
        (OVERLAY_KEYS as readonly string[]).includes(value),
      );
      const unknown = requested.filter(
        (value) => !(OVERLAY_KEYS as readonly string[]).includes(value),
      );
      if (unknown.length > 0) {
        warnings.push(`Ignored unknown overlays: ${unknown.join(", ")}.`);
      }
      state.overlay = OVERLAY_KEYS.filter((key) => valid.includes(key));
    }
  }

  const track = params.get("track");
  if (track !== null) {
    if (["1", "true", "yes"].includes(track.toLowerCase())) state.track = true;
    else if (["0", "false", "no"].includes(track.toLowerCase()))
      state.track = false;
    else warnings.push(`Unknown track flag “${track}”; using sky-fixed ICRS.`);
  }

  const pmra = parseNumber(params.get("pmra"));
  if (pmra !== null) {
    if (pmra < -20000 || pmra > 20000) {
      warnings.push(
        `Trial μ_α* ${pmra} mas/yr is outside ±20000; clamped. The default is the catalog proper motion.`,
      );
    }
    state.pmra = Math.min(20000, Math.max(-20000, pmra));
  }

  const pmdec = parseNumber(params.get("pmdec"));
  if (pmdec !== null) {
    if (pmdec < -20000 || pmdec > 20000) {
      warnings.push(
        `Trial μ_δ ${pmdec} mas/yr is outside ±20000; clamped. The default is the catalog proper motion.`,
      );
    }
    state.pmdec = Math.min(20000, Math.max(-20000, pmdec));
  }

  const parallax = params.get("parallax");
  if (parallax !== null) {
    if (["1", "true", "yes"].includes(parallax.toLowerCase()))
      state.parallax = true;
    else if (["0", "false", "no"].includes(parallax.toLowerCase()))
      state.parallax = false;
    else warnings.push(`Unknown parallax flag “${parallax}”; using off.`);
  }

  const au = parseNumber(params.get("au"));
  if (au !== null) {
    if (au < MIN_DISTANCE_AU || au > MAX_DISTANCE_AU) {
      warnings.push(
        `Parallax test distance ${au} AU is outside ${MIN_DISTANCE_AU}–${MAX_DISTANCE_AU}; clamped.`,
      );
    }
    state.au = Math.min(MAX_DISTANCE_AU, Math.max(MIN_DISTANCE_AU, au));
  }

  if ((restorePaused || prefersReducedMotion()) && state.mode === "blink") {
    state.mode = "still";
    if (restorePaused)
      warnings.push(
        "Shared views open paused. Start playback explicitly or step through observations.",
      );
  }

  const discovery = params.get("discovery");
  if (
    discovery === "known" &&
    state.source === "archive" &&
    state.target !== null
  )
    state.discovery = "known";
  else if (discovery === "known")
    warnings.push(
      "Known exposures require an online archive catalog target; recovery mode was not enabled.",
    );
  else if (discovery && discovery !== "live")
    warnings.push("Unknown discovery mode; using a fresh archive search.");
  const spectrumDiscovery = params.get("spectrumDiscovery");
  if (
    spectrumDiscovery === "known" &&
    state.source === "archive" &&
    state.target !== null
  )
    state.spectrumDiscovery = "known";
  else if (spectrumDiscovery === "known")
    warnings.push(
      "Known spectrum recovery requires an archive catalog target; spectrum mode inherits the image mode.",
    );
  else if (spectrumDiscovery && spectrumDiscovery !== "inherit")
    warnings.push(
      "Unknown spectrum discovery mode; inheriting the image mode.",
    );
  return { state, warnings };
}

function serialise(state: UrlState): string {
  const params = new URLSearchParams();
  params.set("v", SHARE_VERSION);
  for (const key of ["pair", "epochA", "epochB", "analysis"] as const)
    if (state[key]) params.set(key, state[key]!);
  for (const key of [
    "colormap",
    "stretch",
    "contrast",
    "bias",
    "zoom",
    "panX",
    "panY",
    "task",
    "comparisonLayout",
  ] as const)
    params.set(key, String(state[key]));
  params.set("pingpong", state.pingpong ? "1" : "0");
  params.set("advanced", state.advanced ? "1" : "0");
  params.set("source", state.source);
  params.set("discovery", state.discovery);
  params.set("spectrumDiscovery", state.spectrumDiscovery);
  if (state.ra !== null) params.set("ra", String(state.ra));
  if (state.dec !== null) params.set("dec", String(state.dec));
  params.set("size", String(state.size));
  if (state.target) params.set("target", state.target);
  params.set("bands", state.bands);
  params.set("epoch", state.epoch);
  params.set("mode", state.mode);
  params.set("fps", String(state.fps));
  params.set("diff", state.diff ? "1" : "0");
  params.set(
    "overlay",
    state.overlay.length === 0 ? "none" : state.overlay.join(","),
  );
  params.set("track", state.track ? "1" : "0");
  if (state.pmra !== null) params.set("pmra", String(state.pmra));
  if (state.pmdec !== null) params.set("pmdec", String(state.pmdec));
  params.set("parallax", state.parallax ? "1" : "0");
  params.set("au", String(state.au));
  return params.toString();
}

export function useUrlState(): UrlStateApi {
  const initial = useMemo(
    () => parseUrl(typeof window !== "undefined" ? window.location.search : ""),
    [],
  );
  const [state, setState] = useState<UrlState>(initial.state);
  const [warnings, setWarnings] = useState<string[]>(initial.warnings);
  const [copied, setCopied] = useState(false);
  const stateRef = useRef(state);
  stateRef.current = state;

  // Debounced URL write; replaceState keeps browser history clean.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      const query = serialise(state);
      const next = `${window.location.pathname}?${query}${window.location.hash}`;
      if (
        `${window.location.pathname}${window.location.search}${window.location.hash}` !==
        next
      ) {
        window.history.replaceState(null, "", next);
      }
    }, 250);
    return () => window.clearTimeout(timer);
  }, [state]);

  const update = useCallback((patch: Partial<UrlState>) => {
    setState((previous) => {
      const next = { ...previous, ...patch };
      if (next.mode === "blink") next.epoch = "all";
      return parseUrl(serialise(next), false).state;
    });
  }, []);

  const reset = useCallback(() => {
    setState((previous) => ({
      ...defaultState(),
      source: previous.source,
      discovery: previous.discovery,
      spectrumDiscovery: previous.spectrumDiscovery,
      analysis: previous.analysis,
      ra: previous.ra,
      dec: previous.dec,
      target: previous.target,
    }));
    setWarnings([]);
  }, []);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const pause = () => {
      if (media.matches)
        setState((previous) => ({ ...previous, mode: "still" }));
    };
    media.addEventListener("change", pause);
    return () => media.removeEventListener("change", pause);
  }, []);

  const copyLink = useCallback(async () => {
    const query = serialise(stateRef.current);
    const url = `${window.location.origin}${window.location.pathname}?${query}`;
    try {
      await navigator.clipboard.writeText(url);
    } catch {
      const textarea = document.createElement("textarea");
      textarea.value = url;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(textarea);
      if (!ok) {
        setWarnings((previous) => [
          ...previous,
          "Could not copy the link; copy the address bar instead.",
        ]);
        return false;
      }
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
    return true;
  }, []);

  const shareUrl = useCallback(() => {
    const query = serialise(stateRef.current);
    return `${window.location.origin}${window.location.pathname}?${query}`;
  }, []);

  // Handle back/forward navigation into a shared URL.
  useEffect(() => {
    const onPopState = () => {
      const parsed = parseUrl(window.location.search);
      setState(parsed.state);
      setWarnings(parsed.warnings);
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  return { state, update, reset, warnings, copyLink, shareUrl, copied };
}
