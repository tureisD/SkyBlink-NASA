"""Verify real retained headers and prototype query receipts; no network calls.

Uses real header samples and coordinate controls, not generated observations.
This is an internal geometry/provenance check, not science validation.
"""
import argparse
import json
from pathlib import Path
import warnings

from astropy.wcs import WCS

from cloud_index_probe import contains, digest, image_header, save_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--header-samples", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text())
    snapshot_hash = digest(args.snapshot.read_bytes())
    assert snapshot["all_archive_complete"] is False
    header_hashes = []
    for item in snapshot["objects"]:
        raw = (args.snapshot.parent / item["header_file"]).read_bytes()
        assert digest(raw) == item["header_sha256"]
        header_hashes.append(item["header_sha256"])
    samples, checks = [], 0
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="All-NaN slice encountered", category=RuntimeWarning)
        for path in sorted(args.header_samples.glob("detector-*.header")):
            raw = path.read_bytes()
            header, _ = image_header(raw)
            wcs = WCS(header).celestial
            assert image_header(raw[:2880]) is None
            checks += 1
            width, height = header["NAXIS1"], header["NAXIS2"]
            center = ((width-1)/2, (height-1)/2)
            points = [(*center, True), (0, 0, True), (width-1, height-1, True),
                      (-1, center[1], False), (width, center[1], False),
                      (center[0], -1, False), (center[0], height, False)]
            for x, y, expected in points:
                ra, dec = wcs.all_pix2world([[x, y]], 0)[0]
                assert contains(header, float(ra), float(dec)) == expected
                assert contains(header, float(ra)+360, float(dec)) == expected
                checks += 2
            ra, dec = wcs.all_pix2world([center], 0)[0]
            assert not contains(header, (float(ra)+180) % 360, -float(dec))
            checks += 1
            samples.append({"path": str(path), "sha256": digest(raw)})
    assert len(samples) == 6, "Require actual headers from all six detectors"
    queries = []
    for path in sorted(args.snapshot.parent.glob("*-query.json")):
        result = json.loads(path.read_text())
        assert result["snapshot_sha256"] == snapshot_hash
        assert result["all_archive_complete"] is False
        assert not result["search_failures"]
        if path.name == "header_center_control-query.json":
            assert any(x["key"] == snapshot["objects"][0]["key"] for x in result["matches"])
        queries.append({"path": str(path), "sha256": digest(path.read_bytes()),
                        "matches": len(result["matches"])})
    assert len(queries) == 7, "Require five catalog queries and two control queries"
    report = {"passed": True, "script_sha256": digest(Path(__file__).read_bytes()),
              "snapshot_sha256": snapshot_hash, "verified_header_hashes": len(header_hashes),
              "real_header_geometry_checks": checks, "samples": samples, "queries": queries,
              "scope": "Internal header identity, spatial boundary/wrap and receipt checks only"}
    save_json(args.out, report)
    print(json.dumps({k: v for k, v in report.items() if k not in {"samples", "queries"}}))


if __name__ == "__main__":
    main()
