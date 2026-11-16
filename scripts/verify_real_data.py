#!/usr/bin/env python3
"""Inventory data origins and verify the approved real-only release payload.

Run --write-inventory only after reviewing new data provenance. Verification
never silently regenerates approval hashes. Historical screenshots, design
artwork and generated unit-test inputs are explicitly outside observations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

TARGETS = ("wise_0855", "barnards_star", "eps_indi_b", "rw_aurigae", "r_draconis")
KNOWN_EXPOSURE_INDEX = "data/catalog-exposure-index.json"
SPATIAL_EXPOSURE_INDEX = "data/archive-spatial-index.json.gz"
EDUCATIONAL_UI = {
    "frontend/public/help/guide-workspace.png",
    "frontend/public/help/guide-compare.png",
    "frontend/public/help/guide-spectrum.png",
}
DATA_SUFFIXES = {".json", ".jsonc", ".yaml", ".yml", ".toml", ".csv", ".tsv",
                 ".webp", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf",
                 ".gz", ".fits", ".fit", ".bin", ".lock"}
TEST_INPUTS = {
    "backend/tests/test_indexed_archive.py": "Reviewed real spatial metadata and isolated invalid hashes/protocol inputs verify partial coverage, arbitrary positions, mode contracts and distinct work identities; no generated sky observations.",
    "frontend/qa/phase6/browser-compare-sidebar.mjs": "Narrow relocation regression uses explicit saved Epsilon Indi B to verify left-rail comparison controls, native keyboard order, A/B/layout selection and persistent real-frame playback; no archive acquisition or generated observations.",
    "backend/tests/test_build_limits.py": "Isolated temporary storage trees, capacity values and concurrency synchronization test admission and immutable retention; no generated observations.",
    "frontend/qa/phase6/browser-release.mjs": "Real saved products verify compact navigation, persistent canvas, responsive layout, notifications, modal focus, differences and reduced motion; no generated observations.",
    "frontend/qa/phase6/browser-requests.mjs": "Delayed unchanged real saved responses and isolated failed transports exercise cancellation, retry and stale-query rejection; never product fallback.",
    "frontend/qa/phase6/browser-spectrum-recovery.mjs": "Unchanged retained real sky, outage and current known-spectrum responses verify independent explicit recovery, all-null/excluded/eligible states and source restoration; isolated routes only.",
    "frontend/qa/phase6/browser-shortcuts.mjs": "Actual saved observations and isolated keyboard/protocol events verify transport controls, reduced motion, missing bands and exact coordinate requests; no generated observation data.",
    "frontend/qa/phase6/browser-captures.mjs": "Documentation captures of explicitly saved real products with exact build/source/input hashes; screenshots are UI evidence, never runtime observations.",
    "backend/tests/test_known_exposures.py": "Exact real exposure index plus isolated invalid metadata/protocol substitutions verify explicit bounded recovery, fresh transfer policy and rejected arbitrary/saved combinations; never synthetic observations.",
    "frontend/qa/phase5/browser-known-recovery.mjs": "Unchanged actual live-error and fresh known sky/spectrum responses test explicit recovery, responsive source controls, known provenance, query-only history and no automatic fallback; isolated replay only.",
    "frontend/qa/phase5/browser-known-live.mjs": "Unintercepted actual user API live failure followed by explicit known-exposure acquisition checks real fresh playback and honest bounded-inventory labels; no generated observations.",
    "frontend/qa/phase5/browser-catalog-live.mjs": "One unintercepted real archive request through the user's actual frontend/API verifies processing identity, matched playback and real asset distinction; no generated observations or response substitution.",
    "frontend/qa/phase5/browser-catalog-spectrum.mjs": "Repeated earliest-ready single-key interactions use real saved spectra to detect selection reset races; no generated scientific inputs.",
    "backend/tests/test_runtime_source.py": "Generated temporary source trees and protocol failures verify loaded-source drift rejection; no generated observation arrays or runtime products.",
    "frontend/qa/phase5/browser-catalog-viewer.mjs": "Actual saved observations verify sidebar-local controls, nonmodal notifications, keyboard focus, persistent blink and accessibility across engines; no generated sky products.",
    "frontend/qa/phase5/browser-catalog-products.mjs": "Unchanged retained real matched/single/partial responses and their exact asset bytes verify notification recovery; isolated replay only, never runtime fallback.",
    "frontend/qa/phase5/browser-catalog-captures.mjs": "Documentation captures of actual explicitly saved observations retain source/build and real input hashes; screenshots are UI evidence, not observations.",
    "frontend/qa/phase5/browser-centered-header.mjs": "Actual saved focus view and isolated pending transport verify source-selector text bounds and typography across engines; no generated observation products.",
    "frontend/qa/phase5/browser-centered-targeted.mjs": "Actual saved UI and isolated transport failures check desktop Play visibility and mobile loading/error source controls; generated protocol errors are never observations or runtime fallback.",
    "frontend/qa/phase5/browser-centered-captures.mjs": "Final centered-workspace documentation captures use actual saved observations, with source/build and input hashes; no generated astronomical imagery.",
    "frontend/qa/phase5/browser-centered-baseline.mjs": "Actual explicit-saved observations establish pre-layout canvas geometry and UI screenshots; no generated sky data.",
    "frontend/qa/phase5/browser-centered.mjs": "Actual saved products test centered rails, focus/collapse, persistent canvas playback, keyboard/modal behavior and responsive accessibility across browser engines; UI evidence only.",
    "frontend/qa/phase5/browser-centered-products.mjs": "Isolated unchanged real matched/single/partial API responses and transport failures verify centered-layout recovery and source controls; no runtime fixtures or generated observations.",
    "frontend/qa/phase5/browser-polish-partial.mjs": "Unchanged real Epsilon Indi archive response with incomplete discovery and null comparison reason verifies plain-language recovery and same-query retry; isolated routing only, no generated observations.",
    "frontend/qa/phase5/browser-polish-captures.mjs": "Final UI documentation captures use explicit saved real products and record observation/source hashes; no generated sky imagery.",
    "frontend/qa/phase5/browser-polish-export.mjs": "Actual real saved spectra verify exported epoch colors retain their full-response identity after pair selection; report pixels are UI evidence, not observations.",
    "frontend/qa/phase5/browser-polish-matched.mjs": "Isolated browser replay of an unchanged freshly acquired method-12 Barnard response and its real served assets verifies distinct epochs, playback and differences; no fabricated images or runtime fallback.",
    "frontend/qa/phase5/browser-polish-spectrum.mjs": "Actual saved negative and null spectra verify responsive selection, tooltip bounds and honest measurement presentation; no generated observations.",
    "frontend/qa/phase5/browser-polish.mjs": "Actual saved observations test responsive chart typography, filtering, signed sorting and interface accessibility; browser evidence, not generated science data.",
    "frontend/qa/phase5/browser-polish-recovery.mjs": "Isolated replay of unchanged retained real archive responses tests one-epoch explanations, fresh retry actions and query-settings history; no runtime fallback or generated observations.",
    "backend/tests/test_comparison_first.py": "Test-only archive footprints, protocol/download doubles and wavelength signatures verify balanced acquisition, budget limits and rejection of geometrically similar but spectrally incompatible pairs; no runtime observations.",
    "frontend/qa/phase5/browser-final-captures.mjs": "Final real-data UI screenshots and targeted checks; documentation evidence, not generated observations.",
    "frontend/qa/phase5/browser-retained.py": "Adapts existing retained real archive products to API responses for isolated browser verification; no generated observation arrays or runtime fallback.",
    "frontend/qa/phase5/browser-retained.mjs": "Isolated browser replay of retained real archive responses verifies limited-comparison/lineage states; intercepted data is never a product fallback.",
    "frontend/qa/phase5/browser-performance.mjs": "Real saved-data loads and playback/target-switch measurements provide local browser performance observations; no generated science data or calibrated flash-safety claim.",
    "frontend/qa/phase5/browser-matrix.mjs": "Actual saved API observations exercise browser layout, modal focus, sharing and accessibility across engines; screenshots and audits are UI evidence.",
    "frontend/qa/phase5/browser-requests.mjs": "Isolated browser transport aborts and delayed unchanged real saved API bodies verify cancellation/stale-query handling and explicit source recovery; no generated observations or runtime fallback.",
    "frontend/qa/phase5/share.test.mjs": "Isolated invalid/versioned URL values and interrupted HTTP protocol responses test sharing, cancellation and exact selection; observation metadata comes from real saved products, never generated sky data.",
    "frontend/qa/phase5/browser-baseline.mjs": "Browser observations of actual explicitly saved API products establish the pre-redesign baseline; screenshots are UI evidence, not synthetic observations.",
    "frontend/qa/phase5/browser-spectrum.mjs": "Actual saved spectra verify signed error extents, sparse points, selection and all-null presentation; no generated measurement products.",
    "backend/tests/test_archive_source_policy.py": "Isolated protocol/failure doubles and real target metadata verify explicit archive/saved routing; no generated observations.",
    "backend/tests/test_online_irsa.py": "Generated archive metadata/status responses, delays and non-observation byte strings verify bounded transport and immutable receipts; test-only.",
    "backend/tests/test_phase4_science_online.py": "Test-only exact-circle geometry, variable solid angles, seeded independent noise, stability failures and moving catalog-neighbor coordinates verify numerical and screening boundaries; never runtime observation data.",
    "backend/tests/test_bitmasks.py": "Generated 4x4 FITS arrays isolate exact SOURCE, warning and hard-mask bits; no natural sample guarantees all bit combinations.",
    "backend/tests/test_spectra.py": "Generated pixel/variance/flag planes give known aperture integrals, null/error and exclusion boundaries; missing/nonfinite spectral coordinates and off-image/empty-aperture inputs verify explicit omission reasons. These are unit inputs, never observation products.",
    "backend/tests/test_golden_telemetry.py": "Generated float16/uint32 codec planes and malformed payloads test exact layout and rejection boundaries.",
    "backend/tests/test_contract_1_1.py": "Handwritten model boundary values for validation; integration payloads and sidecars now come from real golden observations.",
    "backend/tests/test_api_contract.py": "Handwritten schema/query boundaries and projected real golden payloads; synthetic fallback integration removed.",
    "backend/tests/test_live_budget.py": "Handwritten environment/configuration values verify budgets without generating observations.",
    "backend/tests/test_release_detection.py": "Handwritten artifact URI/collection records test release classification, not sky measurements.",
    "backend/tests/test_real_only.py": "Deliberately rejected namespace files and simulated provenance mutations exercise fail-closed policy; never shipped.",
    "backend/tests/test_coordinate_matrix.py": "Controlled empty-archive response proves coordinate/FOV routing boundaries without inventing observed frames.",
    "backend/tests/test_discovery_boundaries.py": "Generated protocol VOTables/status errors, URI metadata and controlled delays isolate pagination, completeness and deadline boundaries; no observation products.",
    "backend/tests/test_live_selection.py": "Generated wavelength/bandwidth signature arrays isolate the compatibility algorithm, not observed spectra or images.",
    "backend/tests/test_live_pipeline_decisions.py": "Isolated network/render-stage doubles with real golden metadata and telemetry verify orchestration; no synthetic products are written.",
    "backend/tests/test_singleflight.py": "Thread events and dummy return values test shared-work/waiting behavior; no observation data.",
    "backend/tests/test_phase3_science.py": "Cached real raw FITS regressions plus explicitly test-only SOURCE-mask and annulus-variance perturbations; no generated sky products. Real-input cases skip when ignored research cache is absent.",
    "backend/tests/test_phase3_astrometry.py": "Generated Gaussian/math catalog inputs isolate centroid and astrometric error calculations; test-only, never packaged observations.",
    "backend/tests/test_phase4_science.py": "Isolated constant-intensity/variance arrays, controlled flags and 30000 seeded Gaussian noise trials verify fractional integration and uncertainty mathematics; protocol XML/JSON and evidence-replay mutations test rejection. These are test-only inputs, not observed fluxes or product data.",
    "backend/tests/test_provenance.py": "Generated non-observation byte strings, record JSON, URL/status boundaries and mocked HTTP responses verify content identity and fail-closed replay. Optional integration uses hashed real Phase3 FITS; missing research inputs skip explicitly.",
    "backend/tests/test_phase4_products.py": "Real saved products and retained Phase3 FITS validate creation dates, staged catalog coordinates and image replay; isolated archive adapters and metadata/reason mutations test orchestration without generating observation products.",
    "frontend/qa/phase1/real-data.test.mjs": "Protocol/payload mutations test rejection of simulated data; runtime observation data is never generated by these tests.",
    "frontend/qa/phase2/wcs-reference.py": "Mathematical TAN coordinate grids evaluated with Astropy provide independent projection references; not sky observations.",
    "frontend/qa/phase2/wcs.test.mjs": "Coordinate/round-trip and invalid-domain mathematical test inputs verify TAN transformations; no science assets generated.",
    "frontend/qa/phase4/semantics.test.mjs": "Real saved observations with test-only metadata/state variations verify null/unused flux, observed date labels, coordinate epochs and telemetry quantity/band semantics; never generated observations.",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(root: Path) -> dict:
    output = subprocess.check_output(["git", "ls-files", "-z"], cwd=root)
    entries = []
    for raw in sorted(set(output.decode("utf-8").split("\0")) | {KNOWN_EXPOSURE_INDEX} | EDUCATIONAL_UI):
        if not raw or raw == "docs/evidence/phase1/phase1-data-inventory.json":
            continue
        path = root / raw
        if not path.is_file():
            continue
        content = path.read_bytes()
        if path.suffix.lower() not in DATA_SUFFIXES and b"\0" not in content[:8192]:
            try:
                content.decode("utf-8")
            except UnicodeDecodeError:
                pass
            else:
                continue
        parts = Path(raw).parts
        item = {"path": raw, "sha256": digest(path), "bytes": len(content),
                "approved_runtime_observation": False}
        if len(parts) >= 3 and parts[0] == "golden_cache" and parts[1] in TARGETS:
            manifest_path = root / "golden_cache" / parts[1] / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest["provenance"].get("is_simulated_fallback") is not False:
                raise ValueError(f"Unapproved manifest provenance: {raw}")
            uris = sorted({uri for epoch in manifest["epochs"]
                           for stats in epoch["band_stats"].values()
                           for uri in stats.get("artifact_uris", [])})
            if not uris or any("/dr1/" not in uri and "/qr3/" not in uri for uri in uris):
                raise ValueError(f"Missing/current-release input provenance: {raw}")
            reference = path.name.startswith(("ref_", "gaia_"))
            item.update(category="other_measured_reference" if reference else "derived_real_observation",
                        approved_runtime_observation=True,
                        evidence=f"golden_cache/{parts[1]}/ref_attribution.json" if reference else f"golden_cache/{parts[1]}/manifest.json#epochs.band_stats.artifact_uris",
                        origin="SkyView DSS2/AllWISE and IRSA Gaia DR3" if reference else "NASA/IPAC IRSA SPHEREx DR1+QR3 derived product",
                        source_urls=["https://skyview.gsfc.nasa.gov/", "https://irsa.ipac.caltech.edu/TAP"] if reference else ["https://irsa.ipac.caltech.edu/" + uris[0].lstrip("/")],
                        limitation="Metadata/recorded lineage and frozen hashes; not an independent per-exposure science validation. Spectrum channels lack individual exposure lineage (audit Phase 4).")
        elif raw == KNOWN_EXPOSURE_INDEX:
            index = json.loads(content)
            item.update(category="bounded_real_exposure_metadata", approved_runtime_metadata=True,
                        origin="Exact official exposure metadata from previously hash-verified analysis inputs; no FITS pixels or rendered products",
                        evidence="docs/verification/phase5-discovery-outage-verification.md",
                        source_analysis_ids=[value["analysis_id"] for value in index["targets"].values()],
                        source_analysis_record_sha256=[value["analysis_record_sha256"] for value in index["targets"].values()],
                        limitation="Explicit known-exposure lookup only; historical bounded inventory, never complete current discovery. FITS must be downloaded fresh and all current gates rerun.")
        elif raw == SPATIAL_EXPOSURE_INDEX:
            item.update(category="bounded_real_spatial_metadata", approved_runtime_metadata=True,
                        origin="Verified real AWS IMAGE headers: bounded directory scans plus targeted fresh headers at historical catalog addresses; no image pixels",
                        evidence="docs/decisions/indexed-archive-contract-decision.md",
                        limitation="Explicit indexed mode only; partial spatial coverage and unknown newer observations. Fresh downloads and unchanged scientific gates required.")
        elif raw == "backend/core/staged_astrometry.json":
            profile = json.loads(content)
            item.update(category="real_catalog_staged_profile", origin="Primary Gaia DR3 and Kirkpatrick et al.2021 astrometry with derived barycentric query coordinates; proposed staging profile only",
                        evidence="docs/evidence/phase4/phase4-science-coordinate-profile.json",
                        source_urls=sorted({entry["source"]["url"] for entry in profile["targets"]}),
                        source_catalog_sha256=sorted({entry["source"]["sha256"] for entry in profile["targets"]}),
                        limitation="Not promoted; does not update the five approved saved datasets or certify uncontaminated infrared photocenters. Full reference epoch/format/time scale retained; no observer parallax or perspective acceleration applied.")
        elif raw in EDUCATIONAL_UI:
            item.update(category="educational_ui_capture", approved_runtime_ui=True,
                        educational_only=True,
                        origin="Current UI with numbered HTML annotations, displaying unchanged retained real SPHEREx responses; not new acquisition",
                        evidence="docs/screenshots/guide-20261115/origins.json",
                        limitation="Help documentation artwork only. Never loaded as observation data or fallback. Highlights identify controls and recorded status, not astronomical detections.")
        elif (raw.startswith(("docs/screenshots/", "frontend/qa/")) and path.suffix.lower() != ".svg") or path.suffix.lower() in {".png", ".jpg", ".webp"}:
            item.update(category="historical_ui_evidence_origin_unresolved", origin="Repository UI screenshot; may depict synthetic fixtures or illustrative models", evidence="Historical QA/documentation; not a measured observation", limitation="Retained as historical evidence, not certified synthetic-free or science data")
        elif path.suffix.lower() == ".pdf":
            item.update(category="document_origin_unresolved", origin="Research/background document; authorship and embedded image origins not independently verified")
        elif path.suffix.lower() == ".svg":
            item.update(category="design_artwork", origin="Repository vector UI/design diagram; not observation data",
                        approved_runtime_ui=raw in {"frontend/public/favicon.svg", "frontend/public/help/how-it-works.svg"})
        elif raw.startswith("golden_cache/"):
            item.update(category="validation_metadata", origin="Repository validation report/checksum metadata; not observations")
        else:
            item.update(category="software_configuration_or_schema", origin="Repository configuration, dependency lockfile, or API schema; not observations")
        entries.append(item)
    return {"inventory_version": 1, "date": "2026-11-14", "scope": "Tracked existing binary/data/configuration files; inventory excludes itself to avoid a recursive hash. Deleted assets and Git history are not current products.",
            "claim": "Approved runtime observation datasets only; NOT a claim of no synthetic material anywhere in tests, historical screenshots, diagrams, documents or Git history.",
            "generated_test_inputs": TEST_INPUTS, "files": entries}


def verify(root: Path, inventory_path: Path, require_dist: bool = False) -> list[str]:
    errors = []
    payload = json.loads(inventory_path.read_text(encoding="utf-8"))
    approved = {item["path"]: item["sha256"] for item in payload["files"]
                if item.get("approved_runtime_observation")}
    approved_ui = {item["path"].removeprefix("frontend/public/"): item["sha256"]
                   for item in payload["files"] if item.get("approved_runtime_ui")}
    approved_metadata = {item["path"]: item["sha256"] for item in payload["files"]
                         if item.get("approved_runtime_metadata")}
    if set(approved_metadata) != {KNOWN_EXPOSURE_INDEX, SPATIAL_EXPOSURE_INDEX}:
        errors.append("Exactly the two approved bounded exposure metadata indexes are required")
    for name, expected in approved_metadata.items():
        path = root / name
        if not path.is_file() or digest(path) != expected:
            errors.append(f"Missing or changed approved runtime metadata: {name}")
    for path in (root / "data").rglob("*"):
        if path.is_file() and path.relative_to(root).as_posix() not in approved_metadata:
            errors.append(f"Unapproved runtime metadata/data file: {path.relative_to(root)}")
    expected_targets = {Path(name).parts[1] for name in approved}
    if expected_targets != set(TARGETS):
        errors.append("Approval inventory must contain exactly the five real targets")
    golden = root / "golden_cache"
    for target in TARGETS:
        if not (golden / target / "manifest.json").is_file():
            errors.append(f"Missing real target: {target}")
    for path in golden.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if path.parent == golden and path.name in {"validation_report.json", "w0_metrics.json", "w0_overlay_metrics.json", ".gitkeep"}:
            continue
        if relative not in approved:
            errors.append(f"Unapproved golden asset: {relative}")
        elif digest(path) != approved[relative]:
            errors.append(f"Changed approved asset: {relative}; provenance review/reinventory required")
    for name in approved:
        if not (root / name).is_file():
            errors.append(f"Missing approved asset: {name}")
    for base in (root / "frontend/public", root / "frontend/dist"):
        if require_dist and base.name == "dist" and not (base / "index.html").is_file():
            errors.append("Built frontend is required")
        for path in base.rglob("*"):
            relative = path.relative_to(base)
            if any(part.lower() == "mock" or part.lower().startswith("fallback_") for part in relative.parts):
                errors.append(f"Forbidden packaged fixture path: {path.relative_to(root)}")
            if path.is_file():
                approved_hash = approved_ui.get(relative.as_posix())
                compiled = (base.name == "dist" and
                            (relative.as_posix() == "index.html" or
                             (relative.parts[0] == "assets" and path.suffix in {".js", ".css"})))
                if approved_hash is not None:
                    if digest(path) != approved_hash:
                        errors.append(f"Changed approved UI asset: {path.relative_to(root)}")
                elif not compiled:
                    errors.append(f"Unapproved packaged UI/data asset: {path.relative_to(root)}")
            if path.is_file() and path.suffix.lower() in {".json", ".js"}:
                content = path.read_text(encoding="utf-8", errors="replace")
                if any(marker in content for marker in ('"is_simulated_fallback":true', '"is_simulated_fallback": true', '"is_illustrative_model": true', '"is_illustrative_model":true', 'Planck blackbody shapes', 'eps_indi_templates')):
                    errors.append(f"Synthetic/model content in package: {path.relative_to(root)}")
    for relative in ("scripts/generate_fallback_fixtures.py", "frontend/src/data/eps_indi_templates.json", "frontend/src/components/ForwardComparator.tsx"):
        if (root / relative).exists():
            errors.append(f"Retired synthetic generator/model remains: {relative}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--write-inventory", action="store_true")
    parser.add_argument("--require-dist", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    path = args.inventory or root / "docs/evidence/phase1/phase1-data-inventory.json"
    if args.write_inventory:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(inventory(root), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Inventory written: {path}; review origin classifications before approval")
        return 0
    errors = verify(root, path, args.require_dist)
    for error in errors:
        print(f"ERROR: {error}")
    if not errors:
        print("PASS: five approved real datasets match inventory hashes; no packaged mock/fallback/model-spectrum assets")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
