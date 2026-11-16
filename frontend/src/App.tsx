import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AudioPanel } from "./components/AudioPanel";
import { BlinkCanvas } from "./components/BlinkCanvas";
import type { BlinkCanvasHandle } from "./components/BlinkCanvas";
import { CrossMissionCurtain } from "./components/CrossMissionCurtain";
import { FieldsPanel } from "./components/FieldsPanel";
import { DisplayPanel } from "./components/DisplayPanel";
import { HelpDialog } from "./components/HelpDialog";
import { Modal } from "./components/Modal";
import type { DataAccess, DiscoveryMode } from "./lib/api";
import { SearchDialog } from "./components/SearchDialog";
import { SpectrumDrawer } from "./components/SpectrumDrawer";
import { TargetPanel } from "./components/TargetPanel";
import { TimelineDock } from "./components/TimelineDock";
import type { TimelineEpoch } from "./components/TimelineDock";
import { TopBar } from "./components/TopBar";
import { TrialMotionPanel } from "./components/TrialMotionPanel";
import { TriageModal } from "./components/TriageModal";
import { useGaiaSources } from "./hooks/useGaiaSources";
import { usePrefersReducedMotion } from "./hooks/usePrefersReducedMotion";
import { comparisonRecovery } from "./lib/comparisonRecovery";
import { useRecentFields } from "./hooks/useRecentFields";
import type { RecentField } from "./hooks/useRecentFields";
import { useSkyData } from "./hooks/useSkyData";
import { OVERLAY_KEYS, useUrlState } from "./hooks/useUrlState";
import type { OverlayKey } from "./hooks/useUrlState";
import type { ColormapId } from "./lib/colormaps";
import type { StretchId } from "./lib/display";
import type { LvfHighlight } from "./lib/lvf";
import {
  ARBITRARY_COORDINATES_NOTICE,
  DEFAULT_TARGET,
  targetSeeds,
  separationArcsec,
  targetSeed,
} from "./lib/targets";
import type { Epoch } from "./lib/types";
import { BANDS } from "./lib/types";
import { analysisIdentityNotice, selectionWarnings } from "./lib/share";
import { discoveryNotice, observationDateLabel } from "./lib/semantics";

const FRAME_ORDER = ["all", ...BANDS.map((band) => band.key), "thermal"];

export default function App() {
  const reducedMotion = usePrefersReducedMotion();
  const { state, update, warnings, copyLink, shareUrl, copied } = useUrlState();
  const canvasRef = useRef<BlinkCanvasHandle | null>(null);

  const { colormap, stretch, contrast, bias, pingpong } = state;
  const setColormap = (colormap: ColormapId) => update({ colormap });
  const setStretch = (stretch: StretchId) => update({ stretch });
  const setContrast = (contrast: number) => update({ contrast });
  const setBias = (bias: number) => update({ bias });
  const setPingpong = (pingpong: boolean) => update({ pingpong });
  const [elapsed, setElapsed] = useState(0);
  const sideBySide = state.comparisonLayout === "side-by-side";
  const setSideBySide = (side: boolean) =>
    update({ comparisonLayout: side ? "side-by-side" : "single" });
  const [searchOpen, setSearchOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [helpKeyboardOnly, setHelpKeyboardOnly] = useState(false);
  const [spectrumOpen, setSpectrumOpen] = useState(false);
  const [curtainOpen, setCurtainOpen] = useState(false);
  const [triageOpen, setTriageOpen] = useState(false);
  const [lvfHover, setLvfHover] = useState<LvfHighlight | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [warningsHidden, setWarningsHidden] = useState(false);
  const [fieldsOpen, setFieldsOpen] = useState(() => window.innerWidth >= 1280);
  const [inspectorOpen, setInspectorOpen] = useState(
    () => window.innerWidth >= 1000,
  );
  const [focusViewer, setFocusViewer] = useState(false);
  const [inspectorView, setInspectorView] = useState<
    "evidence" | "display" | "notice"
  >(state.advanced ? "display" : "evidence");
  const fieldsVisible = fieldsOpen && !focusViewer;
  const inspectorVisible = inspectorOpen && !focusViewer;
  useEffect(() => {
    const adapt = () => {
      if (window.innerWidth < 1280) setFieldsOpen(false);
      if (window.innerWidth < 1000) setInspectorOpen(false);
    };
    const medium = window.matchMedia("(min-width: 1280px)");
    const small = window.matchMedia("(min-width: 1000px)");
    medium.addEventListener("change", adapt);
    small.addEventListener("change", adapt);
    return () => {
      medium.removeEventListener("change", adapt);
      small.removeEventListener("change", adapt);
    };
  }, []);
  const toggleFields = () => {
    setFocusViewer(false);
    setFieldsOpen(!fieldsVisible);
    if (window.innerWidth < 1280) setInspectorOpen(false);
    requestAnimationFrame(() => {
      document
        .querySelector<HTMLButtonElement>("#fields-panel .sidebar-close")
        ?.focus();
    });
  };
  const toggleInspector = () => {
    setFocusViewer(false);
    setInspectorOpen(!inspectorVisible);
    if (window.innerWidth < 1280) setFieldsOpen(false);
    requestAnimationFrame(() => {
      document
        .querySelector<HTMLButtonElement>("#inspector-panel .sidebar-close")
        ?.focus();
    });
  };
  const closeFields = () => {
    setFieldsOpen(false);
    requestAnimationFrame(() =>
      document.getElementById("fields-toggle")?.focus(),
    );
  };
  const closeInspector = () => {
    setInspectorOpen(false);
    requestAnimationFrame(() =>
      document.getElementById("inspector-toggle")?.focus(),
    );
  };

  const seeds = targetSeeds(state.source);
  const defaultTarget = seeds[DEFAULT_TARGET.id];
  const seed = targetSeed(state.target, state.source);
  // A target id always wins over URL-supplied coordinates (LAW 5): stale
  // reference-epoch share links must query the propagated 2025.8 centre or the
  // backend rejects them with a 422. Arbitrary positions have no seed and are
  // passed through untouched.
  const resolvedRa = seed ? seed.ra : (state.ra ?? defaultTarget.ra);
  const resolvedDec = seed ? seed.dec : (state.dec ?? defaultTarget.dec);
  const resolvedTarget =
    state.target ??
    (state.ra === null && state.dec === null ? DEFAULT_TARGET.id : null);
  const skyQuery = useMemo(
    () => ({
      source: state.source,
      discovery: state.discovery,
      ra: resolvedRa,
      dec: resolvedDec,
      target: resolvedTarget,
      // Saved catalog assets are size-independent; archive fields use the request.
      size: resolvedTarget && state.source === "saved" ? 0.2 : state.size,
    }),
    [
      resolvedRa,
      resolvedDec,
      resolvedTarget,
      state.size,
      state.source,
      state.discovery,
    ],
  );
  const sky = useSkyData(skyQuery);
  const manifest =
    sky.status === "ready" && sky.source === state.source ? sky.manifest : null;
  const recentFields = useRecentFields(
    manifest,
    state.source,
    state.spectrumDiscovery,
  );
  const gaiaUrl = manifest?.reference_overlays?.gaia_sources_url ?? null;
  const gaia = useGaiaSources(gaiaUrl);

  const catalogPmRa = manifest?.target?.pm_ra_mas_yr ?? 0;
  const catalogPmDec = manifest?.target?.pm_dec_mas_yr ?? 0;
  const trialPmRa = state.pmra ?? catalogPmRa;
  const trialPmDec = state.pmdec ?? catalogPmDec;
  const lvfAvailable = Boolean(
    manifest?.epochs.some((epoch) => (epoch.lvf_geometry?.length ?? 0) > 0),
  );

  const availability = useMemo(() => {
    if (!manifest) {
      return {
        bands: [] as string[],
        epochsByBand: new Map<string, Epoch[]>(),
      };
    }
    const epochsByBand = new Map<string, Epoch[]>();
    for (const key of FRAME_ORDER) {
      epochsByBand.set(
        key,
        manifest.epochs.filter(
          (entry) => typeof entry.frames[key] === "string",
        ),
      );
    }
    const bands = FRAME_ORDER.filter(
      (key) => (epochsByBand.get(key) ?? []).length > 0,
    );
    return { bands, epochsByBand };
  }, [manifest]);

  const diffPairs = useMemo(() => {
    if (!manifest || manifest.epochs.length < 2)
      return [] as Array<{ key: string; label: string }>;
    return Object.keys(manifest.differences).map((key) => {
      const [later, earlier] = key.split("_minus_");
      return {
        key,
        label: `${later ?? key} − ${earlier ?? ""}`.trim(),
      };
    });
  }, [manifest]);

  const diffPair = state.pair;
  const activeDiffKey = useMemo(() => {
    if (!manifest || !state.diff || diffPairs.length === 0) return null;
    if (diffPair)
      return manifest.differences[diffPair]?.[state.bands] ? diffPair : null;
    return (
      diffPairs.find(
        (entry) =>
          typeof manifest.differences[entry.key]?.[state.bands] === "string",
      )?.key ?? diffPairs[0].key
    );
  }, [manifest, state.diff, diffPair, diffPairs, state.bands]);

  const activeDiffBands = useMemo(() => {
    if (!manifest || !state.diff || !activeDiffKey) return [] as string[];
    const frames = manifest.differences[activeDiffKey] ?? {};
    return FRAME_ORDER.filter((key) => typeof frames[key] === "string");
  }, [manifest, state.diff, activeDiffKey]);

  const currentEpochs = useMemo(
    () => availability.epochsByBand.get(state.bands) ?? [],
    [availability, state.bands],
  );

  const diffEpochs = useMemo<TimelineEpoch[]>(() => {
    if (!manifest || !activeDiffKey) return [];
    const order = new Map(
      manifest.epochs.map((entry, index) => [entry.epoch_id, index] as const),
    );
    return activeDiffKey
      .split("_minus_")
      .filter(Boolean)
      .sort((a, b) => (order.get(a) ?? 99) - (order.get(b) ?? 99))
      .map((id) => {
        const entry = manifest.epochs.find(
          (candidate) => candidate.epoch_id === id,
        );
        return {
          id,
          label: `Epoch ID ${id}`,
          date: entry
            ? observationDateLabel(entry)
            : "Observation dates unavailable",
          status: entry?.flag_summary.status ?? "NOMINAL",
        };
      });
  }, [manifest, activeDiffKey]);

  // Make sure a shared URL always carries the resolved position and target.
  // Guard against a stale manifest from the previous query: during an
  // arbitrary-coordinate transition React still renders the old catalog
  // manifest for one frame, and enriching from it would put the old target id
  // back into the URL.
  const manifestMatchesQuery =
    manifest !== null &&
    separationArcsec(
      { ra: manifest.query.ra, dec: manifest.query.dec },
      { ra: resolvedRa, dec: resolvedDec },
    ) <= 0.01;
  useEffect(() => {
    if (!manifest || !manifestMatchesQuery) return;
    const patch: { ra?: number; dec?: number; target?: string } = {};
    if (state.ra === null) patch.ra = manifest.query.ra;
    if (state.dec === null) patch.dec = manifest.query.dec;
    if (state.target === null && manifest.query.target_id) {
      patch.target = manifest.query.target_id;
    }
    if (Object.keys(patch).length > 0) update(patch);
  }, [
    manifest,
    manifestMatchesQuery,
    state.ra,
    state.dec,
    state.target,
    update,
  ]);

  // Rewrite stale catalog share links: `?target=wise_0855&ra=<2010 coords>`
  // must use the selected source position, not fail the API 1″ check.
  useEffect(() => {
    if (!seed) return;
    const hasCoords = state.ra !== null || state.dec !== null;
    const staleRa = state.ra !== null && Math.abs(state.ra - seed.ra) > 1e-6;
    const staleDec =
      state.dec !== null && Math.abs(state.dec - seed.dec) > 1e-6;
    if (!staleRa && !staleDec) return;
    if (hasCoords) {
      setWarningsHidden(false);
      setNotice(
        `${seed.name}: using the ${state.source} catalog position at query epoch 2025.8.`,
      );
    }
    update({ ra: seed.ra, dec: seed.dec });
  }, [seed, state.ra, state.dec, state.source, update]);

  const timelineEpochs = useMemo<TimelineEpoch[]>(() => {
    if (!manifest) return [];
    if (state.diff) return diffEpochs;
    return currentEpochs.map((entry) => ({
      id: entry.epoch_id,
      label: `Epoch ID ${entry.epoch_id}`,
      date: observationDateLabel(entry),
      status: entry.flag_summary.status,
    }));
  }, [manifest, state.diff, diffEpochs, currentEpochs]);

  const availableBands = state.diff ? activeDiffBands : availability.bands;
  const selectedPairKey = `${state.epochB ?? currentEpochs[1]?.epoch_id}_minus_${state.epochA ?? currentEpochs[0]?.epoch_id}`;
  const canDiff = Boolean(
    manifest?.differences[selectedPairKey]?.[state.bands],
  );

  // Non-blocking corrections so a shared URL always resolves to real data.
  // Skip while the previous manifest is still on screen during a query change.
  useEffect(() => {
    if (!manifest || !manifestMatchesQuery) return;
    if (state.diff && diffPairs.length === 0) {
      setNotice(
        "This manifest has no difference frames; showing epoch frames.",
      );
      update({ diff: false });
      return;
    }
    const allowed = state.diff ? activeDiffBands : availability.bands;
    if (allowed.length === 0) return;
    if (!allowed.includes(state.bands)) {
      const fallback = allowed.includes("all") ? "all" : allowed[0];
      setNotice(
        `“${state.bands}” is not available here; showing “${fallback}”.`,
      );
      // Preserve an unavailable shared band until the user chooses a real one.
      return;
    }
    if (state.diff) return;
    const ids = currentEpochs.map((entry) => entry.epoch_id);
    if (state.epoch !== "all" && !ids.includes(state.epoch)) {
      setNotice(
        `Epoch “${state.epoch}” is not in this set; pinning “${ids[0] ?? "all"}”.`,
      );
      // Preserve missing shared identity; persistent selection notice explains it.
      return;
    }
    if (state.mode === "still" && state.epoch === "all" && ids.length > 0) {
      update({ epoch: ids[0] });
    }
  }, [
    manifest,
    manifestMatchesQuery,
    state.diff,
    state.bands,
    state.epoch,
    state.mode,
    availability,
    activeDiffBands,
    diffPairs,
    currentEpochs,
    update,
  ]);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 7000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  useEffect(() => {
    setWarningsHidden(false);
  }, [warnings.length]);

  // If the OS switches to reduced motion mid-session, stop autoplay.
  useEffect(() => {
    if (!reducedMotion || state.mode !== "blink") return;
    const id =
      state.epoch !== "all"
        ? state.epoch
        : (currentEpochs[0]?.epoch_id ?? "all");
    update({ mode: "still", epoch: id });
    setNotice("prefers-reduced-motion is set: autoplay disabled.");
  }, [reducedMotion, state.mode, state.epoch, currentEpochs, update]);

  const handlePlay = useCallback(() => {
    if (
      reducedMotion ||
      state.diff ||
      currentEpochs.length < 2 ||
      (state.epochA !== null && state.epochA === state.epochB)
    )
      return;
    setSideBySide(false);
    update({ mode: "blink", task: "compare" });
  }, [
    reducedMotion,
    state.diff,
    currentEpochs.length,
    state.epochA,
    state.epochB,
    update,
  ]);

  const handlePause = useCallback(() => {
    const id =
      canvasRef.current?.getActiveEpochId() ??
      (state.epoch !== "all" ? state.epoch : currentEpochs[0]?.epoch_id) ??
      "all";
    update({ mode: "still", epoch: id });
  }, [state.epoch, currentEpochs, update]);

  const handleStep = useCallback(
    (direction: -1 | 1) => {
      if (state.diff || currentEpochs.length === 0) return;
      const sequence =
        state.task === "compare"
          ? currentEpochs.filter(
              (e) =>
                e.epoch_id === (state.epochA ?? currentEpochs[0]?.epoch_id) ||
                e.epoch_id === (state.epochB ?? currentEpochs[1]?.epoch_id),
            )
          : currentEpochs;
      if (!sequence.length) return;
      const id =
        state.mode === "still"
          ? state.epoch
          : canvasRef.current?.getActiveEpochId();
      const index = Math.max(
        0,
        sequence.findIndex((e) => e.epoch_id === id),
      );
      setSideBySide(false);
      update({
        mode: "still",
        epoch:
          sequence[(index + direction + sequence.length) % sequence.length]
            .epoch_id,
      });
    },
    [
      state.diff,
      state.task,
      state.epochA,
      state.epochB,
      state.mode,
      state.epoch,
      currentEpochs,
      update,
    ],
  );

  const handleBand = useCallback(
    (key: string) => {
      if (!availableBands.includes(key)) return;
      update({ bands: key });
    },
    [availableBands, update],
  );

  const handleCoordinateSearch = useCallback(
    (ra: number, dec: number) => {
      setSearchOpen(false);
      setWarningsHidden(false);
      update({
        source: "archive",
        discovery: state.discovery === "indexed" ? "indexed" : "live",
        spectrumDiscovery: "inherit",
        analysis: null,
        pair: null,
        epochA: null,
        epochB: null,
        mode: "still",
        comparisonLayout: "single",
        zoom: 1,
        panX: 0,
        panY: 0,
        track: false,
        pmra: null,
        pmdec: null,
        parallax: false,
        target: null,
        ra,
        dec,
        bands: "all",
        epoch: "all",
        diff: false,
      });
      setNotice(
        (state.discovery === "indexed" ? "Limited indexed archive selected for these coordinates. " : "Fresh archive search selected for these coordinates. ") +
          ARBITRARY_COORDINATES_NOTICE,
      );
    },
    [update, state.discovery],
  );

  const handleTarget = useCallback(
    (id: string) => {
      const selected = targetSeed(id, state.source);
      if (!selected) return;
      setSearchOpen(false);
      update({
        analysis: null,
        pair: null,
        epochA: null,
        epochB: null,
        mode: "still",
        comparisonLayout: "single",
        zoom: 1,
        panX: 0,
        panY: 0,
        track: false,
        pmra: null,
        pmdec: null,
        parallax: false,
        target: id,
        spectrumDiscovery: "inherit",
        ra: selected.ra,
        dec: selected.dec,
        bands: "all",
        epoch: "all",
        diff: false,
      });
    },
    [state.source, update],
  );

  const handleSource = useCallback(
    (source: DataAccess, discovery: DiscoveryMode = "live") => {
      const selected = targetSeed(resolvedTarget, source);
      update({
        analysis: null,
        pair: null,
        epochA: null,
        epochB: null,
        mode: "still",
        comparisonLayout: "single",
        zoom: 1,
        panX: 0,
        panY: 0,
        track: false,
        pmra: null,
        pmdec: null,
        parallax: false,
        source,
        discovery,
        spectrumDiscovery: "inherit",
        ...(selected
          ? { ra: selected.ra, dec: selected.dec, target: selected.id }
          : {}),
        epoch: "all",
        diff: false,
      });
      setSpectrumOpen(false);
      setTriageOpen(false);
      setCurtainOpen(false);
    },
    [resolvedTarget, update],
  );

  const handleEpoch = useCallback(
    (epoch: string) => {
      update({ mode: "still", epoch });
    },
    [update],
  );

  const handleDiff = useCallback(
    (next: boolean) => {
      if (next && !canDiff) {
        setNotice(
          "No recorded difference exists for this selected A/B pair and band.",
        );
        return;
      }
      setSideBySide(false);
      update({
        diff: next,
        pair: next ? selectedPairKey : state.pair,
        mode: "still",
        ...(next ? { colormap: "coolwarm" as const } : {}),
      });
    },
    [canDiff, selectedPairKey, state.pair, update],
  );

  const handleDiffPair = useCallback(
    (key: string) => {
      const [epochB, epochA] = key.split("_minus_");
      update({ pair: key, epochA, epochB, mode: "still" });
    },
    [update],
  );

  const handleOverlay = useCallback(
    (key: OverlayKey, enabled: boolean) => {
      const next = new Set(state.overlay);
      if (enabled) next.add(key);
      else next.delete(key);
      update({ overlay: OVERLAY_KEYS.filter((entry) => next.has(entry)) });
    },
    [state.overlay, update],
  );

  const handlePm = useCallback(
    (axis: "ra" | "dec", value: number) => {
      update(axis === "ra" ? { pmra: value } : { pmdec: value });
    },
    [update],
  );

  const handleResetTrial = useCallback(() => {
    update({ pmra: null, pmdec: null });
  }, [update]);

  // Viewer shortcuts respect native controls and modal keyboard ownership.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (
        event.defaultPrevented ||
        event.metaKey ||
        event.ctrlKey ||
        event.altKey
      )
        return;
      if (document.querySelector('[role="dialog"][aria-modal="true"]')) return;
      const target = event.target instanceof Element ? event.target : null;
      if (
        target?.closest(
          'input, textarea, select, [contenteditable]:not([contenteditable="false"]), [role="textbox"], [role="combobox"], [role="slider"], [role="listbox"], [role="menu"], [role="tablist"]',
        )
      )
        return;
      const key = event.key.toLowerCase();
      const space = event.key === " " || event.code === "Space";
      // Space on a native control belongs to that control, including key repeat.
      if (
        space &&
        target?.closest('button, a, summary, [role="button"], [role="switch"]')
      )
        return;
      const globalShortcut = key === "/" || key === "?";
      const viewerContext =
        !target ||
        target === document.body ||
        target === document.documentElement ||
        Boolean(target.closest('[data-workspace-region="stage"]'));
      if (!globalShortcut && (!manifest || !viewerContext)) return;
      const supported =
        globalShortcut ||
        space ||
        ["ArrowLeft", "ArrowRight"].includes(event.key) ||
        ["r", "d", "a", "t", "1", "2", "3", "4", "5", "6"].includes(key);
      if (!supported) return;
      // Holding a key must never rapidly toggle playback/difference or queue steps.
      if (event.repeat) {
        event.preventDefault();
        return;
      }
      if (event.shiftKey && !["?", "r", "d", "a", "t"].includes(key)) return;
      event.preventDefault();
      if (key === "/") {
        setSearchOpen(true);
        return;
      }
      if (key === "?") {
        setHelpKeyboardOnly(true);
        setHelpOpen(true);
        return;
      }
      if (space) {
        if (state.mode === "blink") handlePause();
        else handlePlay();
        return;
      }
      if (event.key === "ArrowRight") {
        handleStep(1);
        return;
      }
      if (event.key === "ArrowLeft") {
        handleStep(-1);
        return;
      }
      if (key === "r") {
        update({ zoom: 1, panX: 0, panY: 0 });
        return;
      }
      if (key === "d") {
        handleDiff(!state.diff);
        return;
      }
      if (key === "a") {
        handleBand("all");
        return;
      }
      if (key === "t") {
        handleBand("thermal");
        return;
      }
      handleBand(key);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [
    manifest,
    state.mode,
    state.diff,
    handlePause,
    handlePlay,
    handleStep,
    handleDiff,
    handleBand,
    update,
  ]);

  const isWiseField =
    manifest?.query.target_id === "wise_0855" ||
    manifest?.target?.id === "wise_0855";
  const overlayMap = manifest?.reference_overlays ?? {};
  // Prefer the 1.1.0 DSS2/W1 keys; the 1.0.0 keys remain valid fallbacks.
  const opticalKey =
    typeof overlayMap.optical_dss2_red === "string"
      ? "optical_dss2_red"
      : typeof overlayMap.optical_dss_gaia === "string"
        ? "optical_dss_gaia"
        : null;
  // WISE 0855 is a 4.6 µm source: W2 is the honest curtain default when the
  // backend provides it. W1 and the 1.0.0 mid_ir_wise key stay as fallbacks
  // for the other four targets and older manifests.
  const infraredKey =
    isWiseField && typeof overlayMap.mid_ir_wise_w2 === "string"
      ? "mid_ir_wise_w2"
      : typeof overlayMap.mid_ir_wise_w1 === "string"
        ? "mid_ir_wise_w1"
        : typeof overlayMap.mid_ir_wise === "string"
          ? "mid_ir_wise"
          : null;
  const opticalUrl = opticalKey ? overlayMap[opticalKey] : null;
  const infraredUrl = infraredKey ? overlayMap[infraredKey] : null;
  const curtainAvailable = Boolean(opticalUrl && infraredUrl);
  const opticalLabel =
    opticalKey === "optical_dss2_red"
      ? "Optical · DSS2 Red"
      : opticalKey === "optical_dss_gaia"
        ? "Optical · DSS/Gaia"
        : "Optical reference";
  const infraredLabel =
    infraredKey === "mid_ir_wise_w2"
      ? "Mid-IR · WISE W2 4.6 µm"
      : infraredKey === "mid_ir_wise_w1"
        ? "Mid-IR · WISE W1 3.4 µm"
        : infraredKey === "mid_ir_wise"
          ? "Mid-IR · WISE"
          : "Mid-IR reference";

  useEffect(() => {
    if (!curtainAvailable) setCurtainOpen(false);
  }, [curtainAvailable]);

  useEffect(() => {
    if (!spectrumOpen) setLvfHover(null);
  }, [spectrumOpen]);

  useEffect(() => {
    if (sky.status !== "loading") return;
    const started = Date.now();
    setElapsed(0);
    const timer = window.setInterval(
      () => setElapsed(Math.floor((Date.now() - started) / 1000)),
      1000,
    );
    return () => window.clearInterval(timer);
  }, [sky.status, skyQuery]);
  useEffect(() => {
    if (manifest?.provenance.analysis_id && !state.analysis)
      update({ analysis: manifest.provenance.analysis_id });
  }, [manifest, state.analysis, update]);
  const epochA =
    currentEpochs.find((e) => e.epoch_id === state.epochA) ?? currentEpochs[0];
  const epochB =
    currentEpochs.find((e) => e.epoch_id === state.epochB) ?? currentEpochs[1];
  useEffect(() => {
    if (!manifest) return;
    const patch: { epochA?: string; epochB?: string } = {};
    if (!state.epochA && epochA) patch.epochA = epochA.epoch_id;
    if (!state.epochB && epochB) patch.epochB = epochB.epoch_id;
    if (Object.keys(patch).length) update(patch);
  }, [manifest, state.epochA, state.epochB, epochA, epochB, update]);
  const pairManifest = useMemo(
    () =>
      manifest && state.task === "compare" && epochA && epochB
        ? {
            ...manifest,
            epochs: [epochA, epochB].filter(
              (e, i, list) =>
                list.findIndex((x) => x.epoch_id === e.epoch_id) === i,
            ),
          }
        : manifest,
    [manifest, state.task, epochA, epochB],
  );
  const identityNotice = manifest
    ? analysisIdentityNotice(state.analysis, manifest.provenance.analysis_id)
    : null;
  const missingSelection = manifest ? selectionWarnings(state, manifest) : [];
  const savedExample = () => {
    const example = targetSeed("wise_0855", "saved")!;
    update({
      source: "saved",
      discovery: "live",
      spectrumDiscovery: "inherit",
      target: example.id,
      ra: example.ra,
      dec: example.dec,
      analysis: null,
      pair: null,
      epochA: null,
      epochB: null,
      epoch: "all",
      diff: false,
      mode: "still",
    });
  };
  const revisitField = (field: RecentField) => {
    setSearchOpen(false);
    setSpectrumOpen(false);
    update({
      source: field.source,
      discovery: field.discovery,
      spectrumDiscovery: field.spectrumDiscovery,
      target: field.target,
      ra: field.ra,
      dec: field.dec,
      size: field.size,
      analysis: null,
      pair: null,
      epochA: null,
      epochB: null,
      epoch: "all",
      mode: "still",
      diff: false,
      zoom: 1,
      panX: 0,
      panY: 0,
      comparisonLayout: "single",
      track: false,
      parallax: false,
      pmra: null,
      pmdec: null,
    });
  };
  const retryComparison = () => {
    update({
      analysis: null,
      pair: null,
      epochA: null,
      epochB: null,
      epoch: "all",
      mode: "still",
      diff: false,
      task: "compare",
    });
    sky.reload();
  };
  const header = (
    <TopBar
      manifest={manifest}
      sourceInSidebar={Boolean(manifest) && fieldsVisible}
      source={state.source}
      discovery={state.discovery}
      savedAvailable={resolvedTarget !== null}
      onSourceChange={handleSource}
      curtainAvailable={curtainAvailable}
      onOpenCurtain={() => {
        setSpectrumOpen(false);
        setCurtainOpen(true);
      }}
      onHelp={() => {
        setHelpKeyboardOnly(false);
        setHelpOpen(true);
      }}
      onSearch={() => setSearchOpen(true)}
    />
  );
  if (!manifest)
    return (
      <div
        className="app"
        onClickCapture={(event) => {
          const button = (event.target as Element).closest<HTMLButtonElement>(
            "button",
          );
          if (button && !button.disabled) button.focus();
        }}
      >
        {header}
        <main id="workspace" className="request-state">
          <p className="eyebrow">Explore real infrared observations</p>
          <h1>
            {sky.status === "error"
              ? "This field could not be loaded"
              : sky.status === "cancelled"
                ? "Request cancelled"
                : "Looking for sky observations"}
          </h1>
          <p>
            ICRS {resolvedRa.toFixed(6)}, {resolvedDec.toFixed(6)} degrees /
            field {state.size} degrees /{" "}
            {state.source === "archive"
              ? state.discovery === "known"
                ? "known exposures / fresh downloads (no new archive search)"
                : state.discovery === "indexed" ? "indexed archive / fresh downloads (limited coverage)" : "online archive / fresh search"
              : "saved observations"}
          </p>
          <div role="status">
            {sky.status === "loading" ? (
              <p>
                {elapsed}s elapsed.{" "}
                {state.source === "archive"
                  ? "The browser waits up to 130 seconds. Coverage and comparable observations are not guaranteed."
                  : "Loading saved observations (up to 20 seconds)."}
              </p>
            ) : sky.status === "error" ? (
              <>
                <p>{sky.error}</p>
                <details>
                  <summary>Request details</summary>
                  <p>{sky.liveError}</p>
                </details>
              </>
            ) : (
              <p>Browser waiting stopped. Shared server work may continue.</p>
            )}
          </div>
          {sky.status === "error" &&
            sky.canRecoverKnown &&
            state.source === "archive" &&
            state.discovery === "live" &&
            resolvedTarget && (
              <section
                className="known-exposure-recovery"
                aria-label="Known exposure recovery"
              >
                <p>
                  Archive search unavailable? Use a previously verified exposure
                  list for this catalog target. Every image is downloaded online
                  again; this does not search for newer coverage or guarantee a
                  comparison.
                </p>
                <button
                  className="btn"
                  onClick={() => handleSource("archive", "known")}
                >
                  Fetch known exposures online
                </button>
              </section>
            )}
          {sky.status === "error" && state.source === "archive" && state.discovery !== "indexed" && (
            <section className="known-exposure-recovery" aria-label="Indexed archive recovery">
              <p>Search unavailable? A limited spatial index can locate some exposures for fresh online downloads. Other coverage remains unknown.</p>
              <button className="btn" onClick={() => handleSource("archive", "indexed")}>Try indexed archive online</button>
            </section>
          )}
          <div className="action-row">
            {sky.status === "loading" ? (
              <button className="btn" onClick={sky.cancel}>
                Cancel request
              </button>
            ) : (
              <button className="btn" onClick={sky.reload}>
                Retry request
              </button>
            )}
            <button className="btn" onClick={() => setSearchOpen(true)}>
              Change coordinates
            </button>
            <button className="btn" onClick={savedExample}>
              Open saved WISE example
            </button>
          </div>
          <p className="supporting-copy">
            Saved examples are real historical observations with unvalidated
            comparisons. They never replace an archive failure automatically.
          </p>
        </main>
        {searchOpen && (
          <Modal
            onClose={() => setSearchOpen(false)}
            labelledBy="search-title"
            className="modal-panel--search"
          >
            <SearchDialog
              recent={recentFields.recent}
              onRecent={revisitField}
              onClearRecent={recentFields.clear}
              source={state.source}
              discovery={state.discovery}
              onTarget={handleTarget}
              onResolve={handleCoordinateSearch}
              onClose={() => setSearchOpen(false)}
            />
          </Modal>
        )}
        {helpOpen && (
          <HelpDialog
            keyboardOnly={helpKeyboardOnly}
            onClose={() => setHelpOpen(false)}
          />
        )}
      </div>
    );
  const liveSingleEpoch = manifest.epochs.length < 2;
  const recovery = comparisonRecovery(
    manifest.provenance.comparison_reason,
    manifest.provenance.discovery_status,
    manifest.provenance.discovery_mode,
  );
  const comparisonReady =
    !liveSingleEpoch &&
    manifest.provenance.comparison_status === "matched_visual";
  const observationNoticeCount =
    (comparisonReady ? 0 : 1) +
    (manifest.provenance.discovery_mode === "known" ||
    manifest.provenance.discovery_status === "partial"
      ? 1
      : 0);
  const comparisonText =
    manifest.provenance.comparison_status === "matched_visual"
      ? "Visual comparison available. Compatible sampling does not establish astrophysical variability."
      : liveSingleEpoch
        ? "One returned epoch: no temporal comparison is available in this response."
        : manifest.provenance.data_access === "saved" ||
            manifest.provenance.comparison_status === "legacy_unvalidated"
          ? "Historical comparison: unvalidated. Wavelength sampling, artifacts and blending can mimic change."
          : "Comparison eligibility unrecorded. Wavelength sampling, artifacts and blending can mimic change.";
  return (
    <div
      className="app"
      onClickCapture={(event) => {
        const button = (event.target as Element).closest<HTMLButtonElement>(
          "button",
        );
        if (button && !button.disabled) button.focus();
      }}
    >
      {header}
      <main
        className={`workspace centered-workspace workspace--${state.task} ${fieldsVisible ? "has-fields" : "no-fields"} ${inspectorVisible ? "has-inspector" : "no-inspector"} ${focusViewer ? "is-focused" : ""}`}
        id="workspace"
      >
        <aside
          className="fields-sidebar"
          id="fields-panel"
          data-workspace-region="fields"
          aria-label="Fields and source"
          hidden={!fieldsVisible}
        >
          <FieldsPanel
            source={state.source}
            discovery={state.discovery}
            targetId={manifest.query.target_id}
            targetName={manifest.target?.name ?? "Sky field"}
            spectrumDiscovery={state.spectrumDiscovery}
            ra={manifest.query.ra}
            dec={manifest.query.dec}
            size={state.size}
            onSource={handleSource}
            onClose={closeFields}
          >
            <nav className="task-nav" aria-label="Workspace task">
              {(
                [
                  ["observe", "Observe"],
                  ["compare", "Compare"],
                  ["measure", "Spectrum"],
                  ["evidence", "Evidence"],
                ] as const
              ).map(([task, label]) => (
                <button
                  key={task}
                  className="btn"
                  aria-pressed={state.task === task}
                  onClick={() => {
                    update({
                      task,
                      mode: "still",
                      ...(task === "observe" ? { diff: false } : {}),
                      ...(task === "compare"
                        ? { epoch: epochA?.epoch_id ?? "all" }
                        : {}),
                    });
                    if (task === "measure") setSpectrumOpen(true);
                    if (window.innerWidth < 1000 && task === "observe")
                      closeFields();
                    if (task === "evidence") {
                      setFocusViewer(false);
                      setInspectorOpen(true);
                      setInspectorView("evidence");
                      if (window.innerWidth < 1280) setFieldsOpen(false);
                      if (window.innerWidth < 1000)
                        requestAnimationFrame(() =>
                          document
                            .getElementById("inspector-panel")
                            ?.scrollIntoView({ block: "start" }),
                        );
                    }
                  }}
                >
                  {label}
                </button>
              ))}
            </nav>
            {state.task === "compare" && (
              <div className="comparison-controls">
                <h2>Compare dates</h2>
                <div className="pair-selectors">
                  {(["A", "B"] as const).map((letter) => (
                    <label key={letter}>
                      {letter}
                      <select
                        aria-label={`Observation ${letter}`}
                        disabled={letter === "B" && !epochB}
                        value={
                          (letter === "A" ? epochA : epochB)?.epoch_id ?? ""
                        }
                        onChange={(event) => {
                          const a =
                            letter === "A"
                              ? event.target.value
                              : epochA?.epoch_id;
                          const b =
                            letter === "B"
                              ? event.target.value
                              : epochB?.epoch_id;
                          update({
                            epochA: a ?? null,
                            epochB: b ?? null,
                            pair:
                              a &&
                              b &&
                              manifest.differences[`${b}_minus_${a}`]?.[
                                state.bands
                              ]
                                ? `${b}_minus_${a}`
                                : null,
                            diff: false,
                            epoch: a ?? "all",
                            mode: "still",
                          });
                        }}
                      >
                        {letter === "B" && !epochB && (
                          <option value="">No second epoch returned</option>
                        )}
                        {currentEpochs.map((e) => (
                          <option key={e.epoch_id} value={e.epoch_id}>
                            {observationDateLabel(e)}
                          </option>
                        ))}
                      </select>
                    </label>
                  ))}
                </div>
                <div className="action-row">
                  <button
                    className="btn"
                    disabled={!epochB || epochA?.epoch_id === epochB.epoch_id}
                    aria-pressed={sideBySide}
                    onClick={() => {
                      setSideBySide(!sideBySide);
                      update({ mode: "still", diff: false });
                    }}
                  >
                    Side by side
                  </button>
                  <button
                    className="btn"
                    onClick={() => {
                      setSideBySide(false);
                      handleEpoch(epochA?.epoch_id ?? "all");
                    }}
                  >
                    Show A
                  </button>
                  <button
                    className="btn"
                    disabled={!epochB}
                    onClick={() => {
                      setSideBySide(false);
                      handleEpoch(epochB?.epoch_id ?? "all");
                    }}
                  >
                    Show B
                  </button>
                </div>
                <p className="supporting-copy">
                  Selection is ordinal, not a time-proportional axis.{" "}
                  {epochA && epochB
                    ? `${Math.abs(epochB.mjd_mean - epochA.mjd_mean).toFixed(1)} days between mean dates.`
                    : "A second observation is required."}
                </p>
              </div>
            )}
          </FieldsPanel>
        </aside>
        <div className="observation-column" data-workspace-region="stage">
          <div className="workspace-heading">
            <p className="eyebrow">
              {manifest.provenance.data_access === "saved"
                ? "Saved real observations"
                : manifest.provenance.data_access === "archive"
                  ? manifest.provenance.discovery_mode === "known"
                    ? "Known exposures / fresh downloads"
                    : manifest.provenance.discovery_mode === "indexed" ? "Indexed archive / fresh downloads" : "Online archive observations"
                  : "Data access unrecorded"}{" "}
              / {manifest.provenance.release}
            </p>
            <div className="viewer-title-row">
              {!fieldsVisible && (
                <button
                  id="fields-toggle"
                  className="btn sidebar-menu"
                  aria-label="Show fields"
                  title="Show fields"
                  aria-controls="fields-panel"
                  aria-expanded={false}
                  onClick={toggleFields}
                >
                  <span className="hamburger-icon" aria-hidden="true" />
                </button>
              )}
              <span className="viewer-section-label">Observation viewer</span>
              <button
                className="btn viewer-focus-toggle"
                aria-pressed={focusViewer}
                onClick={() => setFocusViewer((value) => !value)}
              >
                {focusViewer ? "Exit focus" : "Focus image"}
              </button>
              {!inspectorVisible && (
                <button
                  id="inspector-toggle"
                  className="btn sidebar-menu"
                  aria-label="Show inspector"
                  title="Show inspector"
                  aria-controls="inspector-panel"
                  aria-expanded={false}
                  onClick={toggleInspector}
                >
                  <span className="hamburger-icon" aria-hidden="true" />
                </button>
              )}
            </div>
            <p hidden={fieldsVisible}>
              {manifest.query.ra.toFixed(6)}, {manifest.query.dec.toFixed(6)}{" "}
              degrees ICRS.{" "}
              {manifest.target
                ? "Catalog query epoch 2025.8."
                : "Coordinate epoch unspecified."}
            </p>

            <div
              className="observation-status"
              data-comparison-ready={comparisonReady}
            >
              <p
                id="observation-status-text"
                role="status"
                data-live-single-epoch={liveSingleEpoch ? "1" : undefined}
              >
                {state.spectrumDiscovery === "known"
                  ? "Spectrum: known exposures. "
                  : ""}
                {manifest.epochs.length}{" "}
                {liveSingleEpoch
                  ? "returned epoch; blink unavailable"
                  : comparisonReady
                    ? "epochs; visual comparison"
                    : "epochs; comparison unvalidated"}
                {manifest.provenance.discovery_mode === "known"
                  ? "; known exposure list"
                  : manifest.provenance.discovery_mode === "indexed" ? "; limited spatial index"
                  : manifest.provenance.discovery_status === "partial"
                    ? "; archive search incomplete"
                    : ""}
              </p>
              <button
                id="comparison-notice-toggle"
                className="btn notification-toggle"
                aria-label={
                  observationNoticeCount > 0
                    ? `Comparison details: ${observationNoticeCount} ${observationNoticeCount === 1 ? "notice" : "notices"}`
                    : "Comparison details"
                }
                aria-describedby="observation-status-text"
                aria-controls="comparison-notification"
                aria-expanded={inspectorVisible && inspectorView === "notice"}
                onClick={() => {
                  setFocusViewer(false);
                  setInspectorOpen(true);
                  setInspectorView("notice");
                  if (window.innerWidth < 1280) setFieldsOpen(false);
                  requestAnimationFrame(() => {
                    const panel = document.getElementById(
                      "comparison-notification",
                    );
                    panel?.focus();
                    if (window.innerWidth < 1000)
                      panel?.scrollIntoView({ block: "start" });
                  });
                }}
              >
                {observationNoticeCount > 0
                  ? `${observationNoticeCount} ${observationNoticeCount === 1 ? "notice" : "notices"}`
                  : "Comparison details"}
              </button>
            </div>
            {identityNotice && (
              <div className="notice-bar" role="status">
                <p>{identityNotice}</p>
                <button
                  className="btn"
                  onClick={() =>
                    update({
                      analysis: manifest.provenance.analysis_id ?? null,
                    })
                  }
                >
                  Use current analysis identity
                </button>
              </div>
            )}
            {missingSelection.map((message) => (
              <p className="notice-bar" role="status" key={message}>
                {message}
              </p>
            ))}
            {!warningsHidden && (notice || warnings.length > 0) && (
              <div className="notice-bar" role="status">
                <p>
                  {notice} {warnings.join(" ")}
                </p>
                <button className="btn" onClick={() => setWarningsHidden(true)}>
                  Dismiss
                </button>
              </div>
            )}
          </div>

          <div className="observation-caption">
            <p>
              <strong>
                {state.diff
                  ? "Difference: B minus A"
                  : sideBySide && state.task === "compare"
                    ? "A / B observations"
                    : "Observation"}
              </strong>{" "}
              {state.diff || (sideBySide && state.task === "compare")
                ? `A: ${epochA ? observationDateLabel(epochA) : "Unavailable"}; B: ${epochB ? observationDateLabel(epochB) : "Unavailable"}`
                : state.mode === "blink"
                  ? `Playing A: ${epochA ? observationDateLabel(epochA) : "Unavailable"}; B: ${epochB ? observationDateLabel(epochB) : "Unavailable"}`
                  : currentEpochs.length
                    ? observationDateLabel(
                        currentEpochs.find((e) => e.epoch_id === state.epoch) ??
                          currentEpochs[0],
                      )
                    : "No image for this band"}
            </p>
            <p className="supporting-copy">
              Pixel warnings:{" "}
              {state.mode === "blink" ||
              (sideBySide && state.task === "compare") ||
              state.diff
                ? `A: ${epochA?.flag_summary.status ?? "Unknown"}; B: ${epochB?.flag_summary.status ?? "Unknown"}`
                : ((
                    currentEpochs.find((e) => e.epoch_id === state.epoch) ??
                    currentEpochs[0]
                  )?.flag_summary.status ?? "Unknown")}
              . Aperture status is distinct from field-wide warning coverage;
              inspect Evidence for the flags.
            </p>
          </div>
          <div
            className={
              sideBySide && state.task === "compare"
                ? "image-pair"
                : "image-single"
            }
            data-viewer-images="true"
          >
            <section
              className="stage"
              data-inspection={state.advanced ? "true" : "false"}
              aria-label="Observation viewport"
            >
              <BlinkCanvas
                ref={canvasRef}
                camera={{
                  zoom: state.zoom,
                  panX: state.panX,
                  panY: state.panY,
                }}
                onCameraChange={(camera) => update(camera)}
                manifest={pairManifest ?? manifest}
                band={state.bands}
                epoch={
                  sideBySide && state.task === "compare"
                    ? (epochA?.epoch_id ?? state.epoch)
                    : state.epoch
                }
                sizeDeg={state.size}
                diffKey={activeDiffKey}
                mode={
                  sideBySide && state.task === "compare" ? "still" : state.mode
                }
                fps={state.fps}
                diff={state.diff}
                pingpong={pingpong}
                colormap={colormap}
                stretch={stretch}
                contrast={contrast}
                bias={bias}
                overlays={state.overlay}
                reducedMotion={reducedMotion}
                gaia={gaia}
                track={state.track}
                trialPmRa={trialPmRa}
                trialPmDec={trialPmDec}
                parallax={state.parallax}
                parallaxAu={state.au}
                lvfHighlight={lvfHover}
              />
            </section>
            {sideBySide && state.task === "compare" && epochB && (
              <section
                className="stage"
                data-inspection={state.advanced ? "true" : "false"}
                aria-label="Observation B"
              >
                {" "}
                <BlinkCanvas
                  camera={{
                    zoom: state.zoom,
                    panX: state.panX,
                    panY: state.panY,
                  }}
                  onCameraChange={(camera) => update(camera)}
                  manifest={pairManifest ?? manifest}
                  band={state.bands}
                  epoch={epochB?.epoch_id ?? state.epoch}
                  sizeDeg={state.size}
                  diffKey={activeDiffKey}
                  mode="still"
                  fps={state.fps}
                  diff={false}
                  pingpong={pingpong}
                  colormap={colormap}
                  stretch={stretch}
                  contrast={contrast}
                  bias={bias}
                  overlays={state.overlay}
                  reducedMotion={reducedMotion}
                  gaia={gaia}
                  track={state.track}
                  trialPmRa={trialPmRa}
                  trialPmDec={trialPmDec}
                  parallax={state.parallax}
                  parallaxAu={state.au}
                  lvfHighlight={lvfHover}
                />
              </section>
            )}
          </div>
          <TimelineDock
            state={state}
            availableBands={availableBands}
            epochs={
              state.task === "compare"
                ? timelineEpochs.filter(
                    (e) =>
                      e.id === epochA?.epoch_id || e.id === epochB?.epoch_id,
                  )
                : timelineEpochs
            }
            canDiff={canDiff}
            diffPairs={diffPairs}
            activeDiffKey={activeDiffKey}
            onDiffPair={handleDiffPair}
            reducedMotion={reducedMotion}
            pingpong={pingpong}
            onPlay={handlePlay}
            onPause={handlePause}
            onStep={handleStep}
            onBand={handleBand}
            onEpoch={handleEpoch}
            onDiff={handleDiff}
            onFps={(fps) => update({ fps })}
            onPingpong={setPingpong}
            spectrumOpen={spectrumOpen}
            onSpectrum={() => {
              setCurtainOpen(false);
              setSpectrumOpen((open) => !open);
            }}
            getActiveIndex={() => canvasRef.current?.getActiveIndex() ?? 0}
          />

          <div className="view-tools">
            <span className="supporting-copy">
              Zoom {state.zoom.toFixed(2)}x
            </span>
            <button
              className="btn"
              onClick={() => update({ zoom: Math.min(12, state.zoom * 1.5) })}
            >
              Zoom in
            </button>
            <button
              className="btn"
              onClick={() => update({ zoom: Math.max(1, state.zoom / 1.5) })}
            >
              Zoom out
            </button>
            <button
              className="btn"
              onClick={() => update({ zoom: 1, panX: 0, panY: 0 })}
            >
              Reset view
            </button>
          </div>
          <div className="keyboard-guide">
            <kbd>/</kbd> Search <span aria-hidden="true">·</span> <kbd>R</kbd>{" "}
            Reset camera <span aria-hidden="true">·</span> <kbd>←</kbd>{" "}
            <kbd>→</kbd> Step <span aria-hidden="true">·</span> <kbd>Space</kbd>{" "}
            Play / pause
            <button
              className="btn"
              aria-keyshortcuts="Shift+/"
              onClick={() => {
                setHelpKeyboardOnly(true);
                setHelpOpen(true);
              }}
            >
              Keyboard shortcuts <kbd>?</kbd>
            </button>
          </div>
          <p className="image-caption">
            {state.bands === "all"
              ? "Available contributing bands combined (not necessarily all six)."
              : state.bands === "thermal"
                ? "Thermal composite: available bands 5/6, not a measured temperature."
                : `Detector band ${state.bands}.`}{" "}
            {state.discovery === "known"
              ? "Known-exposure spectra use this catalog center only; coordinate Search starts fresh discovery. "
              : ""}
            Dark uncovered margins are unavailable sky, not zero flux. Inspect
            coordinates through Search and measurements through the Spectrum
            table.
          </p>
        </div>
        <aside
          className="inspector-sidebar"
          id="inspector-panel"
          data-workspace-region="inspector"
          aria-label="Inspector"
          hidden={!inspectorVisible}
        >
          <div className="sidebar-heading">
            <div>
              <p className="eyebrow">Interpret</p>
              <h2>Inspector</h2>
            </div>
            <button
              className="btn btn--quiet sidebar-close"
              onClick={closeInspector}
              aria-label="Close inspector panel"
            >
              <span className="hamburger-icon" aria-hidden="true" />
            </button>
          </div>
          <section
            id="comparison-notification"
            className="comparison-notification"
            tabIndex={-1}
            aria-label="Comparison notification"
            hidden={inspectorView !== "notice"}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                setInspectorView("evidence");
                document.getElementById("comparison-notice-toggle")?.focus();
              }
            }}
          >
            <div className="notification-heading">
              <h2>
                {manifest.provenance.discovery_mode === "known"
                  ? "Known exposure list"
                  : manifest.provenance.discovery_mode === "indexed" ? "Limited archive index" : "Observation notice"}
              </h2>
              <button
                className="btn"
                onClick={() => {
                  setInspectorView("evidence");
                  document.getElementById("comparison-notice-toggle")?.focus();
                }}
              >
                Dismiss notification
              </button>
            </div>
            <p>{comparisonText}</p>
            {discoveryNotice(manifest.provenance) && (
              <p
                className="notice-bar"
                role="status"
                data-discovery-status={
                  manifest.provenance.discovery_mode === "known"
                    ? "known"
                    : (manifest.provenance.discovery_status ?? "unknown")
                }
              >
                {discoveryNotice(manifest.provenance)}
              </p>
            )}
            {liveSingleEpoch && (
              <section
                className="comparison-recovery"
                aria-labelledby="comparison-recovery-title"
              >
                <div>
                  <h2 id="comparison-recovery-title">{recovery.title}</h2>
                  <p>{recovery.explanation}</p>
                </div>
                {state.source === "archive" && (
                  <div className="action-row">
                    <button
                      className="btn btn--accent"
                      onClick={retryComparison}
                    >
                      Retry comparison
                    </button>
                    {recovery.smallerFieldMayHelp && state.size > 0.05 && (
                      <button
                        className="btn"
                        onClick={() =>
                          update({
                            size: 0.05,
                            analysis: null,
                            pair: null,
                            epochA: null,
                            epochB: null,
                            epoch: "all",
                            diff: false,
                            mode: "still",
                            task: "compare",
                          })
                        }
                      >
                        Try a 0.05 degree field
                      </button>
                    )}
                    <button className="btn" onClick={() => setSearchOpen(true)}>
                      Choose another field
                    </button>
                  </div>
                )}
                <details>
                  <summary>Comparison search details</summary>
                  <p>
                    Recorded reason:{" "}
                    <code>
                      {manifest.provenance.comparison_reason ?? "Not recorded"}
                    </code>
                    . Retrying makes a new archive request; it does not
                    guarantee a matched pair. Saved observations are never
                    substituted automatically.
                  </p>
                </details>
              </section>
            )}
          </section>
          <div
            className="inspector-tabs"
            role="group"
            aria-label="Inspector content"
          >
            <button
              className="btn"
              aria-pressed={inspectorView === "evidence"}
              aria-label="Evidence inspector"
              onClick={() => setInspectorView("evidence")}
            >
              Evidence
            </button>
            <button
              className="btn"
              aria-pressed={inspectorView === "display"}
              aria-label="Display inspector"
              onClick={() => {
                setInspectorView("display");
                update({ advanced: true });
              }}
            >
              Display
            </button>
          </div>
          <div
            className="evidence-panel"
            aria-label="Evidence and limitations"
            hidden={inspectorView !== "evidence"}
          >
            <h2>What this view supports</h2>
            <dl className="quality-dimensions">
              <div>
                <dt>Origin</dt>
                <dd>
                  {manifest.provenance.data_access === "archive"
                    ? manifest.provenance.discovery_mode === "known"
                      ? "Previously verified exposure list; images downloaded afresh. No new coverage search."
                      : manifest.provenance.discovery_mode === "indexed" ? "Fresh online downloads selected from a limited spatial index. Other coverage is unknown." : "Retrieved from the online archive."
                    : manifest.provenance.data_access === "saved"
                      ? "Saved real observations; archive not refreshed."
                      : "Access mode unrecorded."}
                </dd>
              </div>
              <div>
                <dt>Comparison</dt>
                <dd>{comparisonText}</dd>
              </div>
              <div>
                <dt>Measurement</dt>
                <dd>
                  Image brightness is display intensity. Inspect Spectrum for
                  native flux availability and exclusions.
                </dd>
              </div>
              <div>
                <dt>Validation scope</dt>
                <dd>
                  Scientific validity for this selected field and pair is not
                  established by real origin or reproducible arithmetic.
                </dd>
              </div>
            </dl>
            <p>
              Artifacts, wavelength samples, point-spread functions and blending
              at 6.15 arcseconds can explain differences.
            </p>
            <div className="action-row">
              <button className="btn" onClick={() => setSpectrumOpen(true)}>
                Inspect spectrum
              </button>
              <button
                className="btn"
                disabled={
                  missingSelection.length > 0 || Boolean(identityNotice)
                }
                onClick={() => setTriageOpen(true)}
              >
                Evidence report
              </button>
              <button className="btn" onClick={() => void copyLink()}>
                {copied ? "Link copied" : "Copy view link"}
              </button>
            </div>
            <details open={state.task === "evidence"}>
              <summary>Technical evidence and pixel warnings</summary>
              <TargetPanel
                manifest={manifest}
                pinnedEpoch={
                  state.mode === "blink" || sideBySide ? "all" : state.epoch
                }
                diff={state.diff}
                overlays={state.overlay}
                onOverlay={handleOverlay}
                onSearch={() => setSearchOpen(true)}
              />
            </details>
          </div>
          <div
            className="inspector-display"
            hidden={inspectorView !== "display"}
          >
            <details
              className="advanced-display"
              open={state.advanced}
              onToggle={(event) => {
                if (event.currentTarget.open !== state.advanced)
                  update({ advanced: event.currentTarget.open });
              }}
            >
              <summary>Advanced display and overlays</summary>
              <div className="rail rail--right">
                {" "}
                <DisplayPanel
                  colormap={colormap}
                  stretch={stretch}
                  contrast={contrast}
                  bias={bias}
                  overlays={state.overlay}
                  gaiaAvailable={Boolean(gaiaUrl)}
                  gaiaCount={gaia.sources.length}
                  lvfAvailable={lvfAvailable}
                  diffMode={state.diff}
                  fov={state.size}
                  onColormap={setColormap}
                  onStretch={setStretch}
                  onContrast={setContrast}
                  onBias={setBias}
                  onOverlay={handleOverlay}
                  onFov={(size) => update({ size })}
                  onResetView={() => {
                    canvasRef.current?.resetView();
                    update({ zoom: 1, panX: 0, panY: 0 });
                  }}
                  copied={copied}
                  onCopy={() => {
                    void copyLink();
                  }}
                  onTriage={() => {
                    setSpectrumOpen(false);
                    setCurtainOpen(false);
                    if (missingSelection.length || identityNotice) {
                      setNotice(
                        "Resolve the shared selection or analysis identity before exporting a report.",
                      );
                      return;
                    }
                    setTriageOpen(true);
                  }}
                />
              </div>
              <details>
                <summary>Trial motion, parallax and audio</summary>{" "}
                <TrialMotionPanel
                  manifest={manifest}
                  band={state.bands}
                  diff={state.diff}
                  track={state.track}
                  pmRa={trialPmRa}
                  pmDec={trialPmDec}
                  catalogPmRa={catalogPmRa}
                  catalogPmDec={catalogPmDec}
                  parallax={state.parallax}
                  distanceAu={state.au}
                  onTrack={(next) => update({ track: next })}
                  onPm={handlePm}
                  onParallax={(next) => update({ parallax: next })}
                  onDistance={(au) => update({ au })}
                  onReset={handleResetTrial}
                />
                <AudioPanel
                  discoveryOverride={state.spectrumDiscovery}
                  manifest={manifest}
                  skySource={sky.source}
                  reducedMotion={reducedMotion}
                />
              </details>
            </details>
          </div>
        </aside>
      </main>
      {helpOpen ? (
        <HelpDialog
          keyboardOnly={helpKeyboardOnly}
          onClose={() => setHelpOpen(false)}
        />
      ) : null}

      {searchOpen ? (
        <Modal
          onClose={() => setSearchOpen(false)}
          labelledBy="search-title"
          className="modal-panel--search"
        >
          <SearchDialog
            recent={recentFields.recent}
            onRecent={revisitField}
            onClearRecent={recentFields.clear}
            source={state.source}
            discovery={state.discovery}
            onTarget={handleTarget}
            onResolve={handleCoordinateSearch}
            onClose={() => setSearchOpen(false)}
          />
        </Modal>
      ) : null}

      {curtainOpen && opticalUrl && infraredUrl ? (
        <Modal
          onClose={() => setCurtainOpen(false)}
          labelledBy="curtain-title"
          className="modal-panel--curtain"
        >
          <header className="drawer-head">
            <div>
              <p className="drawer-kicker">Cross-mission curtain</p>
              <h2 id="curtain-title">
                {manifest.target?.name ?? "Sky field"} · optical ↔ mid-IR
              </h2>
              <p className="drawer-sub">
                Reference overlays on the same WCS; not simultaneous exposures.
              </p>
            </div>
            <button
              type="button"
              className="icon-btn"
              onClick={() => setCurtainOpen(false)}
              aria-label="Close cross-mission curtain"
            >
              ✕
            </button>
          </header>
          <CrossMissionCurtain
            opticalUrl={opticalUrl}
            infraredUrl={infraredUrl}
            opticalLabel={opticalLabel}
            infraredLabel={infraredLabel}
            attribution={overlayMap.attribution ?? null}
          />
        </Modal>
      ) : null}

      {spectrumOpen ? (
        <Modal
          onClose={() => setSpectrumOpen(false)}
          labelledBy="spectrum-title"
          className="modal-panel--drawer"
        >
          <SpectrumDrawer
            discoveryOverride={state.spectrumDiscovery}
            onKnownRecovery={() =>
              update({
                spectrumDiscovery: "known",
                target: manifest.query.target_id,
              })
            }
            onInheritDiscovery={() => update({ spectrumDiscovery: "inherit" })}
            manifest={manifest}
            skySource={sky.source}
            onClose={() => {
              setLvfHover(null);
              setSpectrumOpen(false);
            }}
            onLvfHover={setLvfHover}
          />
        </Modal>
      ) : null}

      {triageOpen ? (
        <Modal
          onClose={() => setTriageOpen(false)}
          labelledBy="triage-title"
          className="modal-panel--triage"
        >
          <TriageModal
            discoveryOverride={state.spectrumDiscovery}
            manifest={manifest}
            band={state.bands}
            diffKey={state.diff ? activeDiffKey : null}
            epochA={epochA?.epoch_id ?? null}
            epochB={epochB?.epoch_id ?? null}
            skySource={sky.source}
            gaia={gaia}
            shareUrl={shareUrl}
            onClose={() => setTriageOpen(false)}
          />
        </Modal>
      ) : null}

      <footer className="statusbar">
        NASA / JPL-Caltech / IRSA / Gaia / WISE. Display previews are not
        calibrated variability measurements. Manual stepping is available;
        blinking starts only when requested.
      </footer>
    </div>
  );
}
