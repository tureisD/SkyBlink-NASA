# Working on SPHEREx SkyBlink

> API 1.6 defaults to upstream acquisition for every query. Use explicit Saved mode for offline catalog development; use the source-matched `/targets` coordinates. The current contract and evidence are in [Phase 4 online verification](../verification/phase4-online-verification.md). Earlier cache-first descriptions below are historical.

This page is for anyone who wants to use, demo, or change the project without
already knowing astronomy or the build system. You do not need to read the
multi-agent contract to use the app.

> **Public source:** <https://github.com/tureisD/SkyBlink-NASA> contains a fresh
> snapshot without the earlier Git history. For a presentation, use the
> [recorded examples and two-speaker script](../video.md). Public source does not
> imply a hosted app or a working upstream archive.

## What the project is

SPHEREx SkyBlink shows the same patch of sky at different times using NASA's
SPHEREx images. You pick one of five targets (or enter coordinates), press play,
and the viewer flips between survey passes. You can also open a spectrum, see
which pixels have warnings, compare an optical reference image, and export a
one-page summary.

It is a viewer, not an automated discovery tool. It does not decide that
something is a new object.

## The short version of the folders

| Folder | What lives there | Change it if you want to… |
|---|---|---|
| `frontend/` | The website: React, TypeScript, CSS | Change the layout, controls, text, charts, or help dialog |
| `backend/` | The API: Python, FastAPI | Change how images are fetched, combined, measured, or returned |
| `scripts/` | Build and validation scripts | Rebuild the saved target data, check it, or audit real-data packaging |
| `golden_cache/` | Saved target images, spectra, pixel data, reference images | Avoid changing by hand; rebuild with `scripts/build_golden_cache.py` |
| `docs/` | Contract notes, measurements, deployment, screenshots | Add or update documentation |
| `backend/tests/` | Automated checks | Add a test when you change behavior |

## Run it

The easiest path is Docker:

```bash
docker build -t skyblink:final .
docker run --rm -p 8000:8000 --memory=2g \
  -v skyblink-cache:/data/cache skyblink:final
```

Open <http://localhost:8000>. The five catalog targets work offline because
their images are saved in `golden_cache/`. Only arbitrary coordinates need
internet access to IRSA.

If you prefer local development:

```bash
python -m venv .venv311
# Windows: .venv311\Scripts\activate
# macOS/Linux: . .venv311/bin/activate
pip install -r backend/requirements.txt

cd frontend
npm ci
npm run build
cd ..

python scripts/serve.py
```

For hot reload, run `python scripts/dev_api.py` from the repository root in the
project Python environment, and `npm run dev` in `frontend/`. The launcher watches
only `backend/app`, `core`, `models`, `routers` and `services`; large observation
and research caches are outside its watch roots. Optional `--host` and `--port`
arguments default to `127.0.0.1:8000`. Check the API startup log for the loaded
image method and worker PID after processing changes. API version 1.5.0 alone
does not establish that a running worker imported the latest code.

Hidden/background Windows launches should use `python scripts/dev_api.py --no-reload`
and be restarted explicitly after changes. Automatic reload's console shutdown
event did not reach the hidden worker in the measured local setup; source-only
watch roots do not by themselves fix that limitation.

## Where to make a change

- **Text, layout, buttons, or help:** `frontend/src/components/` and
  `frontend/src/styles/global.css`.
- **Coordinate search or URL state:** `frontend/src/lib/coordinates.ts`,
  `frontend/src/lib/targets.ts`, and `frontend/src/hooks/useUrlState.ts`.
- **What the API returns:** `backend/routers/` and `backend/services/`.
- **Sky data and saved targets:** rebuild with `scripts/build_golden_cache.py`;
  do not hand-edit the generated files.
- **A new check:** add it under `backend/tests/`.

If a change crosses those areas, open an issue or ask the maintainer before
editing. Small pull requests are much easier to review.

## How we work

1. Make a branch, make one focused change, and keep the diff small.
2. Run the checks before you ask for review:
   - `pytest backend/tests -q` (currently **83 tests**)
   - `cd frontend && npm run typecheck && npm run build`
3. If you change a saved target, also run:
   - `python scripts/build_golden_cache.py --target all --verify-only --require-telemetry`
   - `python scripts/run_five_target_card.py`
4. Do not invent data, confidence scores, or missing observations. If a value
   is unknown, show “not available” or leave it out.
5. Product datasets must be real observations or traceable derivatives. Do not add mock loaders, synthetic fallback assets, or illustrative model spectra. Generated test-only edge cases must be inventoried and excluded from runtime; see `real-data-policy.md`.
6. Write in plain language. Explain a term the first time you use it.
7. If you are unsure, ask. That is faster than guessing.

## Words you will see

| Word | What it means here |
|---|---|
| **Target** | One of the five catalog objects the challenge asks about. |
| **Epoch / survey pass** | A block of SPHEREx observations taken around the same time. |
| **Band** | One of SPHEREx's wavelength ranges (B1–B6). |
| **Blink** | Flip quickly between epochs to spot motion or brightness changes. |
| **Difference** | One epoch minus another; static stars mostly cancel out. |
| **Artifact / flag** | A pixel warning (saturation, cosmic ray, halo, etc.). |
| **Spectrum** | Brightness measured at many wavelengths. |
| **Golden cache** | The saved, verified target images and spectra used by the demo. |
| **Telemetry sidecar** | A small extra file with a physical brightness value and pixel flags for the cursor readout. |
| **MJy/sr** | A unit of surface brightness used by infrared astronomers. |
| **LVF** | The variable wavelength filter that lets SPHEREx measure a spectrum without moving parts. |
| **RA / Dec** | Sky coordinates: right ascension and declination. |
| **FOV** | Field of view: how much sky the viewer shows. |
| **Saturation** | A pixel that received too much light and cannot be measured reliably. |
| **Blending** | Two close objects falling inside the same 6.15″ SPHEREx pixel. |

## Common tasks

**Change a label or help text.** Edit the relevant component under
`frontend/src/components/`, then run `npm run typecheck` and `npm run build`.

**Add a new help section.** Edit `frontend/src/components/HelpDialog.tsx`.
Keep it short, use the existing section style, and add a screenshot or icon if
it helps.

**Change how a target is displayed.** Use the search resolver in
`frontend/src/lib/targets.ts`; do not hardcode coordinates in a component.

**Check that saved data is still valid.** Run the verify command above. Do not
delete or rewrite files in `golden_cache/` by hand.

**Deploy it.** Follow `docs/guides/deployment.md`. There is no login and no API key.
The container needs 2 GB of memory and a persistent `/data/cache` volume.

## If something is broken

- Read the message in the UI first; it usually names the missing piece.
- Check `docs/guides/deployment.md` for proxy, cache, and port issues.
- Check `STATUS.md` for the current known limitations.
- Open an issue with the URL, a screenshot, and the browser/OS you used.
