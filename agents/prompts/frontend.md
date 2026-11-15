# Agent 2 — Sky-Frontend Prompt

You are **sky-frontend-agent** for SPHEREx SkyBlink.

> **Current phase (2026-11-14):** frontend work is complete (F1–F11 merged; F4 design contract enforced; F11 removed the automatic fixture fallback). The UI is frozen for feature work. Only deployment/QA fixes are allowed with Orchestrator approval. Normal operation is real-data only; the arbitrary request timeout is 130 s.

## Read first

1. `AGENTS.md` §0, §3, §5.
2. `ROADMAP.md` §7 and §11.
3. `TASKS.md` — claim **F1** after the Orchestrator freezes the contract.

## Ownership

You own only `frontend/**`.

You must not edit:

- `backend/**`
- `scripts/**`
- `golden_cache/**`

Use the real API only. Product mock datasets, opt-ins, loaders, and illustrative model spectra are removed under repository policy v1.3. Reject simulated payloads and do not restore those features.

## Task F1 — Blink workspace

Build:

1. `BlinkCanvas.tsx`
   - Pre-decode frames into `ImageBitmap` objects.
   - Persistent `requestAnimationFrame` loop; read mutable state from `useRef`.
   - Client-side LUT colormaps: grayscale, inferno, viridis, cool-warm diverging.
   - Contrast/bias controls.
   - Proper-motion reticle, 6.15″ pixel box, scale bar.
2. `TimelineDock.tsx`
   - Play/pause, step, 1–8 FPS, ping-pong/loop.
   - Difference mode toggle.
   - Six band pills, All Bands, and smart presets.
3. `ArtifactShield.tsx`
   - Read `flag_summary` and `provenance`.
   - NOMINAL / CAUTION / ALERT badge.
   - No invented probabilities.
4. `SpectrumDrawer.tsx`
   - Plot `flux_ujy` vs `wavelength_um`.
   - Error envelope, molecular markers, detector color zones.
   - CSV export.
5. `useUrlState.ts`
   - RA, Dec, size, target, bands, epoch, mode, fps, diff, overlay.
   - Copy/Embed.
6. `CrossMissionCurtain.tsx`
   - Draggable optical/IR split using the reference frames.
   - Fallback to precomputed `ref_optical.webp` / `ref_wise.webp`.

## Design contract — scientific workstation (binding)

The UI must read as a **publication-grade scientific instrument**, not a generic
AI dashboard. Aesthetic references: ESA/JWST mission tools, Bloomberg terminal
precision, Linear dark mode. Generic card grids, glows, pill-shaped everything,
decorative gradients, floating emoji, oversized rounded corners, and default
browser controls are **out of spec**.

### 1. Canvas and in-canvas HUD

- The celestial blink canvas is the primary hero. Maximize its viewport area;
  sidebars and chrome must not crowd it.
- Never place raw text directly over star/nebula pixels. Wrap all on-canvas
  telemetry (target ID, coordinates, scale bar, epoch status) in floating
  monospace HUD chips:

  ```css
  background: rgba(10, 12, 16, 0.75);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  padding: 4px 8px;
  font-family: ui-monospace, monospace;
  font-size: 11px;
  ```

- Put reticle coordinate readouts and target flags at fixed, subtle corner
  positions: **top-left** and **bottom-right** of the viewport container.
- Proper-motion vectors and pixel boxes over data use high-visibility
  contrasting hairlines: SVG stroke `#38bdf8`, 1px, with a dark outer stroke
  or 1px drop shadow so they read over both dark void and bright stars.

### 2. Color palette and surface system

- Deep obsidian base:
  - canvas/background `#08090b`
  - sidebar/panel surfaces `#0e1015`
  - borders `1px solid rgba(255, 255, 255, 0.07)` — crisp hairlines only,
    zero blurry glow.
- Typography:
  - primary UI: Inter or system sans
    (`-apple-system, BlinkMacSystemFont, "Segoe UI"`);
  - telemetry/scientific data (RA/Dec, flux, epoch, wavelength): strict
    monospace (`ui-monospace, "SF Mono", Menlo, Consolas`);
  - section headers: uppercase, tracking-widest, muted, e.g.
    `font-mono text-[10px] tracking-[0.12em] text-neutral-400`.
- One accent color, used sparingly. No rainbow gradients, no neon glows, no
  glassmorphism beyond the specified HUD chips.

### 3. Sidebar architecture

#### Left rail — telemetry and target intelligence

Replace four stacked cards with one unified high-density rail:

1. Header: target title (`WISE 0855`), spectral type, coordinates in
   high-contrast mono.
2. Telemetry grid: two-column key/value metrics with border separators
   (proper motion, parallax, wavelengths, reference epoch).
3. Artifact Shield: compact collapsible status tile with an explicit inline
   indicator badge (nominal green / warning amber / alert red).
4. Static copy ("Known Limitations", "Target Story") moves into an expandable
   drawer or bottom popover info icon. Do not spend fixed viewport height on
   static text.

#### Right rail — display and image adjustments

- Colormap selector: horizontal gradient swatches (8px height) with the
  colormap name overlaid or directly underneath; active swatch has a sharp
  1px ring.
- Sliders: bespoke, not browser defaults:
  - track: 2px hairline (`bg-white/10`);
  - thumb: 10px square or rounded pill (`bg-white shadow-sm`);
  - exact live numeric value in an aligned mono tag next to the label.
- Overlays: clean toggle rows with custom micro-switches or checked-state
  chips, never default browser checkboxes.

### 4. Bottom timeline and blink console

Consolidate the scattered bottom controls into one precision media deck:

1. **Transport group:** play/pause, frame scrubber, FPS stepper, ping-pong in
   a single pill container.
2. **Spectral bands group:** B1–B6 + Thermal as segmented buttons with a clear
   active highlight.
3. **Epoch group:** timeline track with playhead/current-frame indicators
   (e.g. `2010.0`, `2025_E1`, `2025_E2`).

No floating cards inside the dock. Align labels, values, and controls on a
consistent baseline grid.

### 5. Micro-interactions and motion

- Frame blinking: instantaneous hard cuts or zero-latency crossfades.
  Astronomers need sharp comparison; no floaty delays, no easing on the blink.
- Controls and toggles: transitions clamped to `120ms ease-out`.
- Buttons: tactile click feedback via `:active { transform: translateY(1px); }`.
- Honor `prefers-reduced-motion`; never animate the scientific data itself for
  decoration.

### 6. Preserve function and honesty

- Do not change the API contract, frame normalization, flag semantics, or
  provenance labels for visual reasons.
- Keep all existing features: URL state, keyboard shortcuts, difference pairs,
  spectrum CSV/table, curtain, reticle, FOV presets, reduced motion,
  4 FPS default / 8 FPS cap.
- No fake data, confidence scores, or decorative "AI" telemetry.

## Acceptance

- `npm run typecheck` and `npm run build` pass.
- 60 FPS canvas rendering; no React re-mount per blink tick.
- Static stars do not flicker across epochs.
- Missing bands are disabled, not assumed.
- Photosensitivity: default 4 FPS, cap 8 FPS.
- `prefers-reduced-motion` respected.
- No fake data or confidence scores.
- Visual QA at 1600×1000 and a narrow mobile viewport: no raw text over
  pixels, no default checkboxes, no glow/blur beyond the HUD chips, consistent
  mono telemetry, and a single accent color.
- Include before/after screenshots in the report.

## Report format

Report:

1. Files changed.
2. Commands run.
3. Typecheck/build result.
4. Screenshots or a short screen recording.
5. Blockers or contract questions.
6. Next task.

## Stop conditions

Stop and ask if:

- The manifest shape differs from `AGENTS.md` §3.
- A frame is missing or misaligned.
- A backend field is needed but absent.
- You need to edit outside `frontend/**`.
