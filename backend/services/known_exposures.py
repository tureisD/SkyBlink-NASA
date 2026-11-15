"""Explicit, bounded catalog recovery: old metadata index, newly fetched FITS.

This is never called automatically after live discovery fails. It makes no claim
about newer observations or completeness, and never reads saved image products.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from core.config import REPO_ROOT, Settings
from core.source_policy import source_target
from services.irsa_client import ArtifactRecord, IrsaClient, IRSAIncompleteDiscovery, IRSAUnavailable

INDEX_PATH = REPO_ROOT / "data/catalog-exposure-index.json"
INDEX_SCHEMA = "skyblink.catalog-exposure-index/1"


class KnownExposureClient(IrsaClient):
    """Use only a reviewed target-specific index; inherit fresh bounded transfers."""

    def __init__(self, config: Settings | None = None, *, target_id: str,
                 deadline_at: float | None = None, index_path: Path = INDEX_PATH):
        super().__init__(config, deadline_at=deadline_at, use_cache=False)
        self.target_id = target_id
        self.index_path = Path(index_path)

    def query_artifacts(self, ra: float, dec: float, *, bands=None,
                        fallback: bool = True, allow_partial: bool = False):
        self.remaining_seconds()
        try:
            if self.index_path.stat().st_size > 2 * 1024 * 1024:
                raise ValueError("Index exceeds metadata size bound")
            content = self.index_path.read_bytes()
            index = json.loads(content)
            if index["schema_version"] != INDEX_SCHEMA:
                raise ValueError("Unsupported index schema")
            entry = index["targets"][self.target_id]
            target = source_target(self.target_id, "archive")
            if target is None:
                raise ValueError("Unknown catalog target")
            for pair in ((ra, target.ra_epoch2025), (dec, target.dec_epoch2025),
                         (ra, entry["query"]["ra"]), (dec, entry["query"]["dec"])):
                if not all(math.isfinite(float(value)) for value in pair) or abs(float(pair[0])-float(pair[1])) > 1e-8:
                    raise ValueError("Index or request coordinates differ from the corrected target")
            for key, value in (("extracted_at", index["extracted_at"]),
                               ("record_created_at", entry["record_created_at"])):
                if datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is None:
                    raise ValueError(f"Unknown timezone in {key}")
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", entry["analysis_id"]):
                raise ValueError("Invalid source analysis identity")
            if not re.fullmatch(r"[0-9a-f]{64}", entry["analysis_record_sha256"]):
                raise ValueError("Invalid source record hash")
            rows = entry["records"]
            if not isinstance(rows, list) or not 1 <= len(rows) <= 32:
                raise ValueError("Invalid bounded exposure inventory")
            records = []
            seen = set()
            for row in rows:
                record = ArtifactRecord(**row)
                url = urlsplit(record.uri)
                if (url.scheme != "https" or url.hostname != "irsa.ipac.caltech.edu"
                        or url.username or url.password or url.port not in (None, 443)
                        or url.query or url.fragment or "%" in url.path or "\\" in url.path
                        or any(part in (".", "..") for part in url.path.split("/"))
                        or not re.fullmatch(r"/ibe/data/spherex/(dr1|qr3)/level2/.+\.fits", url.path)):
                    raise ValueError("Index contains an unsupported observation URL")
                release = "DR1" if "/dr1/" in url.path else "QR3"
                if (record.release != release or record.collection != f"spherex_{release.lower()}"
                        or type(record.band) is not int or not 1 <= record.band <= 6
                        or record.band_name != f"SPHEREx-D{record.band}"
                        or record.mjd_upper is None
                        or not math.isfinite(record.mjd_lower) or not math.isfinite(record.mjd_upper)
                        or not 0 < record.mjd_lower <= record.mjd_upper):
                    raise ValueError("Invalid observation release, detector or UTC time bounds")
                if record.uri in seen:
                    raise ValueError("Duplicate indexed exposure")
                seen.add(record.uri)
                if bands is None or record.band in bands:
                    records.append(record)
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            raise IRSAUnavailable(f"Known catalog exposure index is unavailable or invalid: {exc}") from exc
        self.remaining_seconds()
        self.discovery_metadata = {
            "status": "partial", "mode": "known", "method": "recorded_exposure_index",
            "query": {"ra": float(ra), "dec": float(dec)}, "target_id": self.target_id,
            "record_count": len(records), "missing_collections": [], "responses": [],
            "collections": sorted({record.collection for record in records}),
            "index_sha256": hashlib.sha256(content).hexdigest(), "index_schema_version": INDEX_SCHEMA,
            "index_extracted_at": index["extracted_at"], "source_analysis_id": entry["analysis_id"],
            "source_record_sha256": entry["analysis_record_sha256"],
            "source_record_created_at": entry["record_created_at"],
            "completeness_scope": "Bounded previously verified catalog exposures only; no current archive discovery. FITS must be fetched fresh.",
        }
        if not allow_partial:
            raise IRSAIncompleteDiscovery("Known exposure index is an explicitly incomplete inventory",
                                          records=records, missing_collections=[])
        if not records:
            raise IRSAUnavailable("No indexed exposures satisfy this request; current archive coverage is unknown")
        return sorted(records, key=lambda record: (record.mjd_lower, record.uri))
