#!/usr/bin/env python3
"""Fetch real SkyView DSS2 Red / WISE and Gaia DR3 pins into the golden cache.

This is the S4 Stage-1 tool: it updates the **existing** golden manifests with
real reference overlays without rebuilding any SPHEREx frame.  It:

1. fetches ``DSS2 Red`` and ``WISE 3.4`` 240 x 240 FITS cutouts (plus
   ``WISE 4.6`` for WISE 0855) at each target's 2025.8 position, retrying the
   known blank one-element SkyView response and falling back to 200 x 200;
2. reprojects anything that is not already the exact contract 240 x 240 TAN
   grid, applies a documented 0.5-99.5% display stretch, and writes
   ``ref_optical.webp`` / ``ref_wise.webp`` / ``ref_wise_w2.webp``;
3. queries IRSA TAP ``gaia_dr3_source`` for display pins capped to
   ``phot_g_mean_mag <= 16`` and the brightest 200 sources, preserving null
   proper motions, and writes ``gaia_dr3.json``;
4. writes a structured ``ref_attribution.json`` credit bundle;
5. updates ``reference_overlays`` (1.0.0 keys preserved, 1.1.0 keys added),
   ``reference_overlay_provenance``, and the manifest notes.

Every asset is real survey data and is marked ``is_simulated_fallback: false``.
No synthetic image is ever written here.

Usage::

    ../.venv311/Scripts/python.exe scripts/build_reference_overlays.py --target all
    ../.venv311/Scripts/python.exe scripts/build_reference_overlays.py --target wise_0855 --force
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import reference_overlays as overlays  # noqa: E402

DEFAULT_GOLDEN_DIR = REPO_ROOT / "golden_cache"
TARGET_IDS = (
    "wise_0855",
    "barnards_star",
    "eps_indi_b",
    "rw_aurigae",
    "r_draconis",
)

logger = logging.getLogger("skyblink.build_reference_overlays")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text + "\n", encoding="utf-8")
    temporary.replace(path)


def _target_center(manifest: dict[str, Any]) -> tuple[float, float]:
    query = manifest.get("query") or {}
    target = manifest.get("target") or {}
    ra = float(query["ra"])
    dec = float(query["dec"])
    if "ra_epoch2025" in target:
        if abs(ra - float(target["ra_epoch2025"])) > 1e-6:
            raise ValueError("query RA is not the target's 2025.8 coordinate")
        if abs(dec - float(target["dec_epoch2025"])) > 1e-6:
            raise ValueError("query Dec is not the target's 2025.8 coordinate")
    return ra, dec


def build_target(
    target_id: str,
    *,
    golden_dir: Path,
    force: bool,
    fetch_missing: bool,
    gaia_cap: int,
    gaia_g_limit: float,
) -> dict[str, Any]:
    target_dir = golden_dir / target_id
    manifest_path = target_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Golden manifest not found: {manifest_path}")
    manifest = _load_json(manifest_path)
    if str(manifest.get("target_id")) != target_id:
        raise ValueError(f"{target_id}: manifest target_id mismatch")
    if (manifest.get("provenance") or {}).get("is_simulated_fallback") is not False:
        raise ValueError(
            f"{target_id}: refusing to attach real overlays to a synthetic manifest"
        )
    ra, dec = _target_center(manifest)
    reuse = manifest.get("reference_overlay_provenance")
    if isinstance(reuse, dict) and reuse.get("target_id") not in {None, target_id}:
        raise ValueError(f"{target_id}: overlay provenance belongs to another target")

    metadata = overlays.ensure_reference_overlays(
        target_id,
        target_dir,
        ra,
        dec,
        fetch_missing=fetch_missing,
        force=force,
        reuse=reuse if isinstance(reuse, dict) else None,
        gaia_cap=gaia_cap,
        gaia_g_limit=gaia_g_limit,
    )
    overlays.apply_reference_overlays(manifest, target_id, metadata)
    _atomic_write_json(manifest_path, manifest)
    summary = overlays.reference_asset_summary(manifest)
    summary["manifest_path"] = str(manifest_path)
    return summary


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch real DSS2 Red / WISE / Gaia DR3 reference assets and update "
            "the existing golden-cache manifests (S4 Stage 1)."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--target",
        default="all",
        choices=(*TARGET_IDS, "all"),
        help="Catalog target to update.",
    )
    parser.add_argument(
        "--golden-dir",
        type=Path,
        default=DEFAULT_GOLDEN_DIR,
        help="Golden cache root directory.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download every overlay and the Gaia catalog even if hashes match.",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Only reuse existing assets; fail if any is missing.",
    )
    parser.add_argument(
        "--gaia-cap",
        type=int,
        default=overlays.GAIA_CAP,
        help="Maximum Gaia DR3 pins written per target.",
    )
    parser.add_argument(
        "--gaia-g-limit",
        type=float,
        default=overlays.GAIA_G_LIMIT,
        help="Gaia G magnitude limit for the display pins.",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    targets = list(TARGET_IDS) if args.target == "all" else [args.target]
    golden_dir = args.golden_dir.expanduser().resolve()

    updated: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for target_id in targets:
        try:
            summary = build_target(
                target_id,
                golden_dir=golden_dir,
                force=args.force,
                fetch_missing=not args.no_fetch,
                gaia_cap=args.gaia_cap,
                gaia_g_limit=args.gaia_g_limit,
            )
        except Exception as exc:  # noqa: BLE001 - report every target, then fail
            logger.error("%s: FAILED: %s", target_id, exc)
            failures.append(
                {"target_id": target_id, "error": f"{type(exc).__name__}: {exc}"}
            )
            continue
        updated.append({"target_id": target_id, **summary})
        logger.info(
            "%s: %d reference files, %.1f KB, %d Gaia pins (%d total G<=%.1f), keys=%s",
            target_id,
            summary["count"],
            summary["total_bytes"] / 1000.0,
            summary["gaia_returned"],
            summary["gaia_total_g_le_limit"],
            args.gaia_g_limit,
            ",".join(summary["keys"]),
        )

    print(
        json.dumps(
            {
                "ok": not failures,
                "golden_dir": str(golden_dir),
                "gaia": {"cap": args.gaia_cap, "g_limit": args.gaia_g_limit},
                "updated": updated,
                "failures": failures,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
