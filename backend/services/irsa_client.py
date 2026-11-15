"""IRSA TAP / SIA2 query and cutout client.

Verified recipes (``docs/verification/pre-event-verification.md`` §3):

* TAP fallback: ``spherex.artifact`` joined to ``spherex.plane`` with
  ``CONTAINS(POINT('ICRS', ra, dec), p.poly)``, ``a.producttype='science'``
  and ``a.contenttype='image/fits'``.  ``a.uri`` is relative; prepend
  ``https://irsa.ipac.caltech.edu/``.  Band names are ``SPHEREx-D1``…``D6``.
* SIA2 primary: ``COLLECTION=spherex_dr1``, ``spherex_qr3`` and the
  optional ``*_deep`` collections, wide collections first; a zero-radius
  circle queries coverage of the requested center.
* Cutout: ``{access_url}?center={ra},{dec}&size={size_deg}``.  Transient
  ``503 Server busy`` responses are retried with exponential backoff.

The client never fabricates observations: an empty result raises
:class:`IRSANoData`.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
import tempfile
import time
import warnings
from datetime import datetime, timezone
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout, wait, FIRST_COMPLETED
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import httpx
import numpy as np
from astropy.io.votable import parse as parse_votable

from core.config import Settings, settings

logger = logging.getLogger(__name__)

BAND_NAME_RE = re.compile(r"SPHEREx-D([1-6])$")

RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
FITS_MAGIC = b"SIMPLE"
USER_AGENT = "SPHEREx-SkyBlink/1.0 (NASA Space Apps 2026)"
MAX_TAP_PAGES = 20
MAX_RESPONSE_BYTES = 128 * 1024 * 1024


def canonical_cutout_position(ra: float, dec: float, *, precision: int = 6) -> tuple[float, float]:
    """Serialize a valid ICRS position without rounding RA across 360 degrees."""
    ra, dec = float(ra), float(dec)
    if not (math.isfinite(ra) and math.isfinite(dec) and 0 <= ra <= 360 and -90 <= dec <= 90):
        raise ValueError("Invalid ICRS coordinates")
    return round(ra % 360, precision) % 360, round(dec, precision) + 0.0

#: SIA2 fallback order: current wide collections first, then DEEP.  QR2 is
#: historical and no longer advertised as a primary fallback.
DEFAULT_SIA_COLLECTIONS: tuple[str, ...] = (
    "spherex_dr1",
    "spherex_qr3",
    "spherex_dr1_deep",
    "spherex_qr3_deep",
)


class IRSAError(RuntimeError):
    """Base class for IRSA client errors."""


class IRSAUnavailable(IRSAError):
    """TAP/SIA2/cutout service is unreachable or timed out."""


class IRSAIncompleteDiscovery(IRSAUnavailable):
    """Valid rows from complete collections, with explicit missing collections."""

    def __init__(self, message: str, *, records: list[ArtifactRecord], missing_collections: list[str]):
        super().__init__(message)
        self.records = list(records)
        self.missing_collections = list(missing_collections)


class IRSANoData(IRSAError):
    """No science artifacts overlap the requested position."""

    def __init__(
        self,
        message: str,
        *,
        collections_tried: list[str] | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.collections_tried = list(collections_tried or [])
        self.detail = dict(detail or {})


@dataclass(frozen=True)
class ArtifactRecord:
    """One SPHEREx Level 2 science artifact returned by TAP or SIA2."""

    uri: str
    mjd_lower: float
    mjd_upper: float | None
    band: int
    band_name: str
    planeid: str
    release: str
    collection: str
    contentlength: int | None = None
    # Original SIA detector footprint. Ranking hint only, never a wavelength gate.
    s_region: str | None = None

    @property
    def mjd_mid(self) -> float:
        if self.mjd_upper is None:
            return float(self.mjd_lower)
        return 0.5 * (float(self.mjd_lower) + float(self.mjd_upper))

    @property
    def access_url(self) -> str:
        """Absolute FITS URL (TAP ``a.uri`` is relative)."""
        if self.uri.startswith("http://") or self.uri.startswith("https://"):
            return self.uri
        return "https://irsa.ipac.caltech.edu/" + self.uri.lstrip("/")

    def cutout_url(
        self,
        ra: float,
        dec: float,
        size_deg: float,
        *,
        irsa_base: str = "https://irsa.ipac.caltech.edu/",
    ) -> str:
        """Build the verified ``?center=ra,dec&size=deg`` cutout URL."""
        url = self.uri
        if not (url.startswith("http://") or url.startswith("https://")):
            url = irsa_base.rstrip("/") + "/" + url.lstrip("/")
        separator = "&" if "?" in url else "?"
        ra, dec = canonical_cutout_position(ra, dec)
        return f"{url}{separator}center={ra:.6f},{dec:.6f}&size={size_deg:.6f}"


def _detect_release(uri: str, collection_hint: str | None = None) -> tuple[str, str]:
    """Return ``(release, collection)`` from a product URI or SIA2 collection."""
    text = (uri or "").lower()
    if "/dr1/" in text:
        return "DR1", "spherex_dr1"
    if "/qr3/" in text:
        return "QR3", "spherex_qr3"
    if "/qr2/" in text:
        return "QR2", "spherex_qr2"
    hint = (collection_hint or "").lower()
    if "dr1" in hint:
        return "DR1", "spherex_dr1"
    if "qr3" in hint:
        return "QR3", "spherex_qr3"
    if "qr2" in hint:
        return "QR2", "spherex_qr2"
    return "unknown", "spherex"


def _coerce(value: Any) -> Any:
    """Convert VOTable/numpy scalars to plain Python values."""
    if value is None:
        return None
    if np.ma.is_masked(value):
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, np.generic):
        return value.item()
    return value


def _rows_from_votable(content: bytes) -> list[dict[str, Any]]:
    """Parse a VOTable document into a list of dicts keyed by FIELD name."""
    try:
        # DALI permits a trailing INFO after TABLE (including OVERFLOW).
        # Inspect the XML at every depth; VOTable.infos only sees root INFOs.
        root = ElementTree.fromstring(content)
        for info in root.iter():
            if info.tag.rsplit("}", 1)[-1] == "INFO" and info.get("name", "").upper() == "QUERY_STATUS":
                value = info.get("value", "").strip().upper()
                if value not in {"OK", ""}:
                    raise IRSAUnavailable(f"IRSA query incomplete or failed: QUERY_STATUS={value}")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            votable = parse_votable(BytesIO(content), verify="ignore")
        table = votable.get_first_table()
    except IRSAError:
        raise
    except Exception as exc:
        raise IRSAUnavailable(f"Invalid IRSA VOTable: {exc}") from exc
    names = [field.name for field in table.fields]
    array = table.array
    if array is None or not names:
        return []
    dtype_names = array.dtype.names or ()
    rows: list[dict[str, Any]] = []
    for index in range(len(array)):
        row: dict[str, Any] = {}
        for position, name in enumerate(names):
            column = dtype_names[position] if position < len(dtype_names) else name
            row[name] = _coerce(array[column][index])
        rows.append(row)
    return rows


class IrsaClient:
    """Synchronous IRSA client with retries, caching, and parallel downloads."""

    def __init__(self, config: Settings | None = None, *, deadline_at: float | None = None,
                 use_cache: bool = True) -> None:
        self.settings = config or settings
        self.deadline_at = deadline_at
        self.use_cache = bool(use_cache)
        self.discovery_metadata: dict[str, Any] = {"status": "not_started"}
        self.acquisition_metadata: list[dict[str, Any]] = []
        self._metadata_lock = Lock()
        self.settings.ensure_dirs()

    def _record_discovery_response(self, response: httpx.Response, params: dict[str, Any] | None) -> None:
        """Retain actual response bytes and safe query metadata, including failures."""
        if response.request.url.path.rstrip("/") not in {"/SIA", "/TAP/sync"}:
            return
        content = response.content
        digest = hashlib.sha256(content).hexdigest()
        relative = f"discovery-responses/{digest}.response"
        metadata = {"source_url": str(response.request.url), "parameters": params or {},
                    "http_status": response.status_code, "sha256": digest, "size_bytes": len(content),
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "cache_relative_path": relative}
        try:
            path = self.settings.cache_dir / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
                    stream.write(content)
                    temporary = Path(stream.name)
                temporary.replace(path)
            metadata["raw_response_retained"] = True
        except OSError as exc:
            metadata.update(raw_response_retained=False, retention_error=type(exc).__name__)
        with self._metadata_lock:
            self.discovery_metadata.setdefault("responses", []).append(metadata)

    def _discovery_complete(self, method: str, records: list[ArtifactRecord], **metadata: Any) -> list[ArtifactRecord]:
        self.discovery_metadata.update(status="complete", method=method, record_count=len(records),
                                       completeness_scope="requested_current_release_collections_at_query_time",
                                       **metadata)
        return records

    def remaining_seconds(self, deadline_at: float | None = None) -> float | None:
        """Remaining shared monotonic budget; never reset it on a retry."""
        deadlines = [value for value in (self.deadline_at, deadline_at) if value is not None]
        if not deadlines:
            return None
        remaining = min(deadlines) - time.monotonic()
        if remaining <= 0:
            raise IRSAUnavailable("IRSA request deadline exhausted")
        return remaining

    def _backoff(self, attempt: int, deadline_at: float | None) -> None:
        delay = self.settings.retry_backoff_seconds * (2**attempt)
        remaining = self.remaining_seconds(deadline_at)
        if remaining is not None and delay >= remaining:
            raise IRSAUnavailable("IRSA request deadline exhausted before retry")
        time.sleep(delay)

    # ------------------------------------------------------------------
    # HTTP plumbing
    # ------------------------------------------------------------------
    def _new_client(self) -> httpx.Client:
        timeout = httpx.Timeout(
            connect=self.settings.connect_timeout_seconds,
            read=self.settings.request_timeout_seconds,
            write=self.settings.request_timeout_seconds,
            pool=self.settings.connect_timeout_seconds,
        )
        headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
        if not self.use_cache:
            headers["Cache-Control"] = "no-cache"
        return httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers=headers,
        )

    def _request(
        self,
        client: httpx.Client,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
        retries: int | None = None,
        deadline_at: float | None = None,
    ) -> httpx.Response:
        remaining = self.remaining_seconds(deadline_at)
        if remaining is None:
            return self._request_with_retries(
                client, url, params=params, timeout=timeout, retries=retries,
                deadline_at=deadline_at,
            )
        # HTTP timeouts bound individual socket operations, not their sum.
        # Keep the caller inside its absolute budget even during DNS, headers,
        # or a stalled read after earlier chunks consumed most of the budget.
        pool = ThreadPoolExecutor(max_workers=1)
        future = pool.submit(
            self._request_with_retries, client, url, params=params, timeout=timeout,
            retries=retries, deadline_at=deadline_at,
        )
        try:
            return future.result(timeout=self.remaining_seconds(deadline_at))
        except FutureTimeout as exc:
            raise IRSAUnavailable("IRSA request deadline exhausted") from exc
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    def _request_with_retries(
        self,
        client: httpx.Client,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
        retries: int | None = None,
        deadline_at: float | None = None,
    ) -> httpx.Response:
        attempts = max(1, retries if retries is not None else self.settings.retries)
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                remaining = self.remaining_seconds(deadline_at)
                limit = timeout or self.settings.request_timeout_seconds
                if remaining is not None:
                    limit = min(limit, remaining)
                request = client.build_request(
                    "GET", url, params=params,
                    timeout=httpx.Timeout(limit, connect=min(limit, self.settings.connect_timeout_seconds)),
                )
                streamed = client.send(request, stream=True)
                try:
                    chunks: list[bytes] = []
                    length = 0
                    iterator = streamed.iter_bytes()
                    while True:
                        remaining = self.remaining_seconds(deadline_at)
                        if remaining is not None:
                            # Bound the body timeout to what remains after
                            # headers. Some transports cache it for the body;
                            # the outer future enforces the absolute deadline.
                            request.extensions["timeout"]["read"] = min(limit, remaining)
                        try:
                            chunk = next(iterator)
                        except StopIteration:
                            break
                        self.remaining_seconds(deadline_at)
                        length += len(chunk)
                        if length > MAX_RESPONSE_BYTES:
                            raise IRSAUnavailable("IRSA response exceeded bounded download size")
                        chunks.append(chunk)
                    response = httpx.Response(
                        streamed.status_code,
                        headers={key: value for key, value in streamed.headers.items()
                                 if key.lower() not in {"content-encoding", "content-length"}},
                        content=b"".join(chunks), request=request,
                    )
                finally:
                    # Close the original stream even when a deadline expires.
                    # The fully buffered replacement has no transport resources.
                    streamed.close()
                self._record_discovery_response(response, params)
                if response.status_code in RETRYABLE_STATUS_CODES and attempt < attempts - 1:
                    delay = self.settings.retry_backoff_seconds * (2**attempt)
                    logger.warning(
                        "IRSA %s returned %s; retrying in %.1fs",
                        url,
                        response.status_code,
                        delay,
                    )
                    self._backoff(attempt, deadline_at)
                    continue
                if response.status_code >= 400:
                    body = response.text[:300].replace("\n", " ")
                    if response.status_code in RETRYABLE_STATUS_CODES:
                        message = (
                            f"IRSA request failed with HTTP {response.status_code}: {body}"
                        )
                        last_error = IRSAUnavailable(message)
                        if attempt < attempts - 1:
                            delay = self.settings.retry_backoff_seconds * (2**attempt)
                            self._backoff(attempt, deadline_at)
                            continue
                        raise last_error
                    raise IRSAError(
                        f"IRSA request failed with HTTP {response.status_code}: {body}"
                    )
                return response
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                if attempt < attempts - 1:
                    delay = self.settings.retry_backoff_seconds * (2**attempt)
                    logger.warning("IRSA transport error %s; retrying in %.1fs", exc, delay)
                    self._backoff(attempt, deadline_at)
                    continue
                raise IRSAUnavailable(f"IRSA request failed: {exc}") from exc
        raise IRSAUnavailable(f"IRSA request failed after {attempts} attempts: {last_error}")

    # ------------------------------------------------------------------
    # TAP
    # ------------------------------------------------------------------
    def tap_query(
        self,
        ra: float,
        dec: float,
        *,
        bands: list[int] | None = None,
        maxrec: int = 5000,
    ) -> list[ArtifactRecord]:
        """Complete, bounded keyset discovery; ``maxrec`` is a page size.

        SELECT TOP alone does not report truncation. A full page always needs
        another query, ordered by both time and unique artifact URI so equal
        timestamps are not lost. An overflow or exhausted page budget is an
        upstream failure, never a plausible-looking partial epoch inventory.
        """
        query_position = {"ra": float(ra), "dec": float(dec)}
        ra, dec = canonical_cutout_position(ra, dec, precision=8)
        page_size = max(1, min(int(maxrec), 5000))
        remaining = self.remaining_seconds()
        tap_budget = self.settings.tap_timeout_seconds
        if remaining is not None:
            tap_budget = min(tap_budget, remaining / 2)
        stage_deadline = time.monotonic() + tap_budget
        band_clause = ""
        if bands:
            names = ",".join(f"'SPHEREx-D{int(band)}'" for band in bands)
            band_clause = f"\n  AND p.energy_bandpassname IN ({names})"
        cursor: tuple[float, str] | None = None
        records_by_url: dict[str, ArtifactRecord] = {}
        url = self.settings.irsa_tap.rstrip("/") + "/sync"
        with self._new_client() as client:
            for _ in range(MAX_TAP_PAGES):
                self.remaining_seconds(stage_deadline)
                cursor_clause = ""
                if cursor is not None:
                    stamp, uri = cursor
                    literal_uri = uri.replace("'", "''")
                    cursor_clause = (
                        f"\n  AND (p.time_bounds_lower > {stamp!r} OR "
                        f"(p.time_bounds_lower = {stamp!r} AND a.uri > '{literal_uri}'))"
                    )
                query = f"""SELECT TOP {page_size}
       'https://irsa.ipac.caltech.edu/' || a.uri AS cutout_uri,
       p.time_bounds_lower AS mjd_obs,
       p.time_bounds_upper AS mjd_obs_upper,
       p.energy_bandpassname AS detector_band,
       p.planeid AS planeid,
       a.uri AS uri,
       a.contentlength AS contentlength,
       p.datarelease AS datarelease
FROM spherex.artifact a
JOIN spherex.plane p ON a.planeid = p.planeid
WHERE 1 = CONTAINS(POINT('ICRS', {float(ra):.8f}, {float(dec):.8f}), p.poly)
  AND a.producttype = 'science'
  AND a.contenttype = 'image/fits'
  AND (a.uri LIKE '%/dr1/%' OR a.uri LIKE '%/qr3/%'){band_clause}{cursor_clause}
ORDER BY p.time_bounds_lower ASC, a.uri ASC"""
                response = self._request(
                    client, url,
                    params={"query": query, "format": "votable", "MAXREC": page_size},
                    timeout=self.settings.tap_timeout_seconds,
                    deadline_at=stage_deadline,
                )
                rows = _rows_from_votable(response.content)
                self.remaining_seconds(stage_deadline)
                if len(rows) > page_size:
                    raise IRSAUnavailable("TAP ignored the discovery page limit")
                for row in rows:
                    try:
                        record = self._record_from_tap_row(row)
                    except (ValueError, TypeError, OverflowError) as exc:
                        raise IRSAUnavailable("TAP returned invalid artifact metadata") from exc
                    if record is None or not math.isfinite(record.mjd_lower):
                        raise IRSAUnavailable("TAP returned incomplete artifact metadata")
                    key = (record.mjd_lower, record.uri)
                    if cursor is not None and key <= cursor:
                        raise IRSAUnavailable("TAP discovery cursor did not advance")
                    cursor = key
                    if record.release in {"DR1", "QR3"}:
                        records_by_url.setdefault(record.access_url, record)
                if len(rows) < page_size:
                    return self._discovery_complete("tap", list(records_by_url.values()),
                        query=query_position, collections=list(DEFAULT_SIA_COLLECTIONS),
                        pagination="time_uri_keyset", page_size=page_size)
        raise IRSAUnavailable("TAP discovery exceeded its page budget; inventory is incomplete")

    @staticmethod
    def _record_from_tap_row(row: dict[str, Any]) -> ArtifactRecord | None:
        uri = row.get("uri")
        band_name = row.get("detector_band")
        if not uri or not band_name:
            return None
        match = BAND_NAME_RE.fullmatch(str(band_name))
        if match is None:
            return None
        band = int(match.group(1))
        mjd_lower = row.get("mjd_obs")
        if mjd_lower is None:
            return None
        mjd_upper = row.get("mjd_obs_upper")
        release, collection = _detect_release(str(uri))
        planeid = row.get("planeid")
        contentlength = row.get("contentlength")
        return ArtifactRecord(
            uri=str(uri),
            mjd_lower=float(mjd_lower),
            mjd_upper=float(mjd_upper) if mjd_upper is not None else None,
            band=band,
            band_name=f"SPHEREx-D{band}",
            planeid=str(planeid) if planeid is not None else "",
            release=release,
            collection=collection,
            contentlength=int(contentlength) if contentlength is not None else None,
        )

    # ------------------------------------------------------------------
    # SIA2 discovery
    # ------------------------------------------------------------------
    def sia2_query(
        self,
        ra: float,
        dec: float,
        *,
        radius_deg: float = 0.0,
        bands: list[int] | None = None,
        collections: tuple[str, ...] = DEFAULT_SIA_COLLECTIONS,
        parallel: bool = False,
    ) -> list[ArtifactRecord]:
        """Complete current-release discovery, using a point-sized circle.

        SIA POS uses footprint intersection, so the zero-radius circle makes
        its default coverage equivalent to TAP center containment.
        """
        query_position = {"ra": float(ra), "dec": float(dec)}
        ra, dec = canonical_cutout_position(ra, dec, precision=8)
        position = f"circle {float(ra):.8f} {float(dec):.8f} {float(radius_deg):.6f}"
        if not collections:
            raise IRSAUnavailable("No SIA2 collections were requested")
        remaining = self.remaining_seconds()
        stage_deadline = None if remaining is None else time.monotonic() + remaining / 2
        def fetch_collection(collection: str):
            try:
                with self._new_client() as client:
                    response = self._request(
                        client,
                        self.settings.irsa_sia2,
                        params={
                            "COLLECTION": collection,
                            "POS": position,
                            "RESPONSEFORMAT": "votable",
                            "MAXREC": 100000,
                        },
                        timeout=self.settings.request_timeout_seconds,
                        deadline_at=stage_deadline,
                    )
                rows = _rows_from_votable(response.content)
                self.remaining_seconds(stage_deadline)
                if len(rows) >= 100000:
                    raise IRSAUnavailable("SIA2 reached its row limit; inventory may be incomplete")
                records = []
                for row in rows:
                    try:
                        record = self._record_from_sia2_row(row, collection)
                    except (ValueError, TypeError, OverflowError) as exc:
                        raise IRSAUnavailable("SIA2 returned invalid artifact metadata") from exc
                    if record is not None and bands is not None and record.band not in bands:
                        continue
                    if record is None or not math.isfinite(record.mjd_lower):
                        raise IRSAUnavailable("SIA2 returned incomplete artifact metadata")
                    if record.mjd_upper is not None and (not math.isfinite(record.mjd_upper) or record.mjd_upper < record.mjd_lower):
                        raise IRSAUnavailable("SIA2 returned an invalid observation time range")
                    if record.release in {"DR1", "QR3"}:
                        records.append(record)
                return {"collection": collection, "status": "complete", "rows": len(rows)}, records
            except IRSAError as exc:
                # Never preserve rows from the failed/overflowed collection.
                return {"collection": collection, "status": "failed", "message": str(exc)}, []

        results = {}
        if parallel and len(collections) > 1:
            pool = ThreadPoolExecutor(max_workers=min(4, len(collections)))
            futures = {pool.submit(fetch_collection, collection): collection for collection in collections}
            pending = set(futures)
            try:
                while pending:
                    try:
                        timeout = self.remaining_seconds(stage_deadline)
                    except IRSAUnavailable:
                        break
                    done, pending = wait(pending, timeout=timeout, return_when=FIRST_COMPLETED)
                    if not done:
                        break
                    for future in done:
                        results[futures[future]] = future.result()
            finally:
                pool.shutdown(wait=False, cancel_futures=True)
            for future in pending:
                collection = futures[future]
                results[collection] = ({"collection": collection, "status": "failed", "message": "Shared SIA2 deadline exhausted"}, [])
        else:
            results = {collection: fetch_collection(collection) for collection in collections}
        collection_results = [results[collection][0] for collection in collections]
        missing = [item["collection"] for item in collection_results if item["status"] != "complete"]
        records_by_url: dict[str, ArtifactRecord] = {}
        for collection in collections:
            for record in results[collection][1]:
                records_by_url.setdefault(record.access_url, record)
        records = sorted(records_by_url.values(), key=lambda item: (item.mjd_lower, item.uri))
        if missing:
            self.discovery_metadata.update(status="incomplete", method="sia2", query=query_position,
                collections=list(collections), collection_results=collection_results, missing_collections=missing,
                record_count=len(records), completeness_scope="incomplete collection inventory")
            raise IRSAIncompleteDiscovery(f"SIA2 collection discovery is incomplete: {', '.join(missing)}",
                                          records=records, missing_collections=missing)
        return self._discovery_complete("sia2", records,
            query=query_position, collections=list(collections), collection_results=collection_results,
            missing_collections=[], parallel_collections=parallel,
            ingestion_note="Official IRSA documentation notes SIA may lag new directory/TAP products by about one day")

    @staticmethod
    def _record_from_sia2_row(
        row: dict[str, Any],
        collection_hint: str,
    ) -> ArtifactRecord | None:
        access_url = row.get("access_url")
        band_name = row.get("energy_bandpassname")
        if not access_url or not band_name:
            return None
        match = BAND_NAME_RE.fullmatch(str(band_name))
        if match is None:
            return None
        band = int(match.group(1))
        t_min = row.get("t_min")
        if t_min is None:
            return None
        t_max = row.get("t_max")
        release, collection = _detect_release(str(access_url), collection_hint)
        return ArtifactRecord(
            uri=str(access_url),
            mjd_lower=float(t_min),
            mjd_upper=float(t_max) if t_max is not None else None,
            band=band,
            band_name=f"SPHEREx-D{band}",
            planeid=str(row.get("obs_id") or ""),
            release=release,
            collection=collection,
            s_region=str(row["s_region"]) if row.get("s_region") else None,
        )

    # ------------------------------------------------------------------
    # Public query entry point
    # ------------------------------------------------------------------
    def query_artifacts(
        self,
        ra: float,
        dec: float,
        *,
        bands: list[int] | None = None,
        fallback: bool = True,
        allow_partial: bool = False,
    ) -> list[ArtifactRecord]:
        """Complete SIA2 first, then bounded TAP when necessary.

        An incomplete result is an upstream error. NO_DATA requires a complete
        successful discovery, never an empty list caused by an outage.
        ``fallback=False`` retains the historical explicit TAP-only diagnostic.
        ``allow_partial=True`` permits validated rows from complete collections
        when others fail, with explicit partial metadata; strict callers never
        receive those rows as a complete inventory.
        """
        self.discovery_metadata = {"status": "running", "policy": "sia2_then_tap" if fallback else "tap_only",
                                   "query": {"ra": float(ra), "dec": float(dec)}, "responses": []}
        sia_error: Exception | None = None
        sia_complete = False
        if fallback:
            try:
                sia_records = self.sia2_query(ra, dec, bands=bands, parallel=True)
                sia_complete = True
                if sia_records:
                    return sia_records
            except IRSAError as exc:
                sia_error = exc
                if allow_partial and isinstance(exc, IRSAIncompleteDiscovery) and exc.records:
                    self.discovery_metadata.update(status="partial", record_count=len(exc.records),
                        missing_collections=exc.missing_collections,
                        completeness_scope="explicitly incomplete collection inventory; available real observations only",
                        fallback_note="Partial SIA2 accepted to preserve remaining download/processing budget; TAP not attempted")
                    return exc.records
                logger.warning("SIA2 discovery failed; trying TAP within remaining budget: %s", exc)
        tap_error: Exception | None = None
        tap_records: list[ArtifactRecord] = []
        try:
            tap_records = self.tap_query(ra, dec, bands=bands)
            if tap_records:
                return tap_records
        except IRSAError as exc:
            tap_error = exc

        if not fallback:
            if tap_error is not None:
                raise tap_error
            raise IRSANoData(
                "No SPHEREx observations cover this position.",
                collections_tried=list(DEFAULT_SIA_COLLECTIONS),
                detail={"ra": float(ra), "dec": float(dec)},
            )

        if tap_error is not None and not sia_complete:
            self.discovery_metadata.update(status="incomplete", tap_error=str(tap_error), sia_error=str(sia_error))
            raise IRSAUnavailable(
                f"Observation discovery incomplete: TAP={tap_error}; SIA2={sia_error}"
            )

        raise IRSANoData(
            "No SPHEREx observations cover this position.",
            collections_tried=list(DEFAULT_SIA_COLLECTIONS),
            detail={"ra": float(ra), "dec": float(dec)},
        )

    # ------------------------------------------------------------------
    # Cutouts
    # ------------------------------------------------------------------
    def _cutout_cache_path(
        self,
        record: ArtifactRecord,
        ra: float,
        dec: float,
        size_deg: float,
    ) -> Path:
        key = (
            f"{record.access_url}|{canonical_cutout_position(ra, dec)[0]:.8f}|{canonical_cutout_position(ra, dec)[1]:.8f}"
            f"|{float(size_deg):.6f}"
        )
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.settings.cutout_cache_dir / f"{digest}.fits"

    def fetch_cutout(
        self,
        record: ArtifactRecord,
        ra: float,
        dec: float,
        size_deg: float,
        *,
        use_cache: bool = True,
        client: httpx.Client | None = None,
    ) -> bytes:
        """Download (or read from disk) one cutout, validating FITS magic."""
        self.remaining_seconds()
        cache_path = self._cutout_cache_path(record, ra, dec, size_deg)
        if self.use_cache and use_cache and cache_path.exists() and cache_path.stat().st_size > 0:
            content = cache_path.read_bytes()
            self.remaining_seconds()
            if content.startswith(FITS_MAGIC):
                self.acquisition_metadata.append({"source_url": record.cutout_url(ra, dec, size_deg),
                    "sha256": hashlib.sha256(content).hexdigest(), "size_bytes": len(content),
                    "retrieved_at": None, "from_cache": True, "outcome": "retained_cache_read"})
                return content

        url = record.cutout_url(ra, dec, size_deg)
        owns_client = client is None
        active_client = client or self._new_client()
        try:
            response = self._request(
                active_client,
                url,
                timeout=self.settings.request_timeout_seconds,
            )
        except IRSAError as exc:
            self.acquisition_metadata.append({"source_url": url, "retrieved_at": None,
                "attempted_at": datetime.now(timezone.utc).isoformat(), "from_cache": False,
                "outcome": "failed", "message": str(exc)})
            raise
        finally:
            if owns_client:
                active_client.close()

        content = response.content
        if not content.startswith(FITS_MAGIC):
            raise IRSAError(
                f"Cutout response is not a FITS file (HTTP {response.status_code}, "
                f"content-type {response.headers.get('content-type')!r})"
            )
        if len(content) < 2880:
            raise IRSAError("Cutout response is too small to be a FITS file")
        self.acquisition_metadata.append({"source_url": url,
            "sha256": hashlib.sha256(content).hexdigest(), "size_bytes": len(content),
            "retrieved_at": datetime.now(timezone.utc).isoformat(), "from_cache": False,
            "outcome": "fresh_archive_response",
            "proxy_revalidation_requested": not self.use_cache})
        temporary: Path | None = None
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                dir=cache_path.parent, prefix=cache_path.name + ".", suffix=".tmp", delete=False,
            ) as handle:
                temporary = Path(handle.name)
                handle.write(content)
            self.remaining_seconds()
            temporary.replace(cache_path)
        except OSError as exc:  # cache failure must not break the request
            logger.warning("Could not cache cutout %s: %s", cache_path, exc)
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError as exc:
                    logger.warning("Could not remove temporary cutout %s: %s", temporary, exc)
        return content

    def fetch_cutouts(
        self,
        records: list[ArtifactRecord],
        ra: float,
        dec: float,
        size_deg: float,
        *,
        max_workers: int | None = None,
        stage_deadline_at: float | None = None,
        allow_partial: bool = False,
    ) -> dict[ArtifactRecord, bytes]:
        """Download cutouts, optionally returning completed inputs at a stage deadline.

        A separate child owns the fixed download deadline and receipt buffer.
        Late workers cannot extend the processing budget or mutate the receipt
        snapshot published to the caller. No unfinished bytes enter the result.
        """
        if not records:
            return {}
        deadlines = [value for value in (self.deadline_at, stage_deadline_at) if value is not None]
        batch_deadline = min(deadlines) if deadlines else None
        isolated = stage_deadline_at is not None or allow_partial
        batch = (IrsaClient(self.settings, deadline_at=batch_deadline, use_cache=self.use_cache)
                 if isolated else self)
        workers = max_workers or self.settings.max_workers
        unique_records = list(dict.fromkeys(records))
        results: dict[ArtifactRecord, bytes] = {}
        errors: list[Exception] = []
        failures: dict[ArtifactRecord, str] = {}
        expired = False

        def download(record: ArtifactRecord) -> bytes:
            batch.remaining_seconds()
            content = batch.fetch_cutout(record, ra, dec, size_deg)
            batch.remaining_seconds()
            return content

        pool = ThreadPoolExecutor(max_workers=workers)
        futures = {
            pool.submit(download, record): record for record in unique_records
        }
        pending = set(futures)
        try:
            while pending:
                # Collect already completed work before checking the clock. The
                # worker checks its fixed deadline before accepting any bytes.
                done = {future for future in pending if future.done()}
                pending -= done
                if not done:
                    try:
                        remaining = batch.remaining_seconds()
                    except IRSAUnavailable:
                        expired = True
                        break
                    done, pending = wait(pending, timeout=remaining, return_when=FIRST_COMPLETED)
                    if not done:
                        expired = True
                        break
                for future in done:
                    record = futures[future]
                    try:
                        results[record] = future.result()
                    except Exception as exc:  # noqa: BLE001 - collected for reporting
                        errors.append(exc)
                        failures[record] = str(exc)
                        logger.warning(
                            "Cutout download failed for %s: %s", record.access_url, exc
                        )
        finally:
            # A context manager waits for every worker even after timeout. Each
            # running worker owns its client and stops at the shared deadline;
            # pending work is cancelled immediately without holding the caller.
            pool.shutdown(wait=False, cancel_futures=True)
        if batch_deadline is not None and time.monotonic() >= batch_deadline:
            expired = True
        unfinished_records = {futures[future] for future in pending}
        for record in unfinished_records:
            failures[record] = "Cutout download stage deadline exhausted; input not accepted"
        completed_urls = {record.cutout_url(ra, dec, size_deg) for record in results}
        if isolated:
            # Copy only receipts for accepted completed inputs. All other input
            # outcomes are frozen below; late child receipts stay private.
            receipts = list(batch.acquisition_metadata)
            self.acquisition_metadata.extend(
                dict(receipt) for record in unique_records for receipt in receipts
                if receipt.get("source_url") == record.cutout_url(ra, dec, size_deg)
                and receipt.get("source_url") in completed_urls
            )
        for record in unique_records:
            if record in failures:
                self.acquisition_metadata.append({
                    "source_url": record.cutout_url(ra, dec, size_deg), "retrieved_at": None,
                    "attempted_at": datetime.now(timezone.utc).isoformat(), "from_cache": False,
                    "outcome": "stage_deadline_exhausted" if record in unfinished_records else "failed",
                    "message": failures[record],
                })
        self.download_metadata = {
            "status": "partial" if results and failures else "complete" if results else "failed",
            "requested_count": len(unique_records), "completed_count": len(results),
            "stage_deadline_exhausted": expired,
            "failed_inputs": [{"source_url": record.cutout_url(ra, dec, size_deg),
                               "message": failures[record]}
                              for record in unique_records if record in failures],
        }
        if expired and (not allow_partial or not results):
            raise IRSAUnavailable("Cutout download deadline exhausted")
        if not results and errors:
            raise IRSAUnavailable(f"All cutout downloads failed: {errors[0]}")
        return {record: results[record] for record in unique_records if record in results}

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------
    def check_availability(self, timeout: float = 6.0) -> bool:
        """Quick TAP availability probe used by ``/api/v1/health``."""
        url = self.settings.irsa_tap.rstrip("/") + "/availability"
        try:
            with self._new_client() as client:
                response = self._request(client, url, timeout=timeout, retries=1)
            body = response.content.lower()
            return response.status_code == 200 and b"available" in body and b"true" in body
        except Exception as exc:  # noqa: BLE001 - health must never raise
            logger.warning("IRSA availability probe failed: %s", exc)
            return False
