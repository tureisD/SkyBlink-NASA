"""Protocol-boundary tests; generated VOTables are not observation products."""
from dataclasses import replace
from html import escape
from io import BytesIO
from threading import Event
import time

import httpx
import pytest

from core.config import settings
from services import irsa_client as irsa


def votable(rows, trailing=""):
    fields = '<FIELD name="uri" datatype="char" arraysize="*"/><FIELD name="mjd_obs" datatype="double"/><FIELD name="detector_band" datatype="char" arraysize="*"/>'
    cells = ''.join('<TR>'+''.join(f'<TD>{escape(str(value))}</TD>' for value in row)+'</TR>' for row in rows)
    return (f'<VOTABLE version="1.3" xmlns="http://www.ivoa.net/xml/VOTable/v1.3"><RESOURCE type="results"><INFO name="QUERY_STATUS" value="OK"/><TABLE>{fields}<DATA><TABLEDATA>{cells}</TABLEDATA></DATA></TABLE>{trailing}</RESOURCE></VOTABLE>').encode()


def client_with_transport(tmp_path, monkeypatch, handler, deadline=None):
    client = irsa.IrsaClient(replace(settings, cache_dir=tmp_path, retries=1), deadline_at=deadline)
    monkeypatch.setattr(client, "_new_client", lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    return client


@pytest.mark.parametrize("status", ["OVERFLOW", "ERROR"])
def test_nested_trailing_status_rejects_plausible_partial_table(status):
    body = votable([("ibe/data/spherex/dr1/a.fits", 60000, "SPHEREx-D1")],
                   f'<INFO name="QUERY_STATUS" value="{status}">truncated</INFO>')
    with pytest.raises(irsa.IRSAUnavailable, match=status):
        irsa._rows_from_votable(body)


def test_same_timestamp_pagination_keeps_all_uris_and_probes_final_page(tmp_path, monkeypatch):
    requests = []
    pages = [votable([("ibe/data/spherex/dr1/a.fits", 60000, "SPHEREx-D1"),
                       ("ibe/data/spherex/dr1/b.fits", 60000, "SPHEREx-D2")]),
             votable([("ibe/data/spherex/qr3/c.fits", 60000, "SPHEREx-D3")])]
    def handler(request):
        requests.append(dict(request.url.params))
        return httpx.Response(200, content=pages[len(requests)-1])
    client = client_with_transport(tmp_path, monkeypatch, handler)
    records = client.tap_query(0.01, -20, maxrec=2)
    assert [record.band for record in records] == [1, 2, 3]
    assert len(requests) == 2
    assert all(request["MAXREC"] == "2" for request in requests)
    assert "p.time_bounds_lower = 60000.0 AND a.uri > 'ibe/data/spherex/dr1/b.fits'" in requests[1]["query"]
    assert "ORDER BY p.time_bounds_lower ASC, a.uri ASC" in requests[1]["query"]
    assert "OFFSET" not in requests[1]["query"]


def test_full_last_page_is_not_accepted_as_complete(tmp_path, monkeypatch):
    monkeypatch.setattr(irsa, "MAX_TAP_PAGES", 1)
    client = client_with_transport(tmp_path, monkeypatch,
        lambda request: httpx.Response(200, content=votable([("ibe/data/spherex/dr1/a.fits", 60000, "SPHEREx-D1")])))
    with pytest.raises(irsa.IRSAUnavailable, match="page budget"):
        client.tap_query(1, 1, maxrec=1)


def test_nonadvancing_archive_cursor_fails_instead_of_looping(tmp_path, monkeypatch):
    client = client_with_transport(tmp_path, monkeypatch,
        lambda request: httpx.Response(200, content=votable([("ibe/data/spherex/dr1/a.fits", 60000, "SPHEREx-D1")])))
    with pytest.raises(irsa.IRSAUnavailable, match="cursor"):
        client.tap_query(1, 1, maxrec=1)


def test_sia_partial_collection_failure_does_not_claim_complete_inventory(tmp_path, monkeypatch):
    seen = []
    def handler(request):
        seen.append(dict(request.url.params))
        return httpx.Response(502 if len(seen)==1 else 200, content=b"outage" if len(seen)==1 else votable([]))
    client = client_with_transport(tmp_path, monkeypatch, handler)
    with pytest.raises(irsa.IRSAUnavailable, match="incomplete"):
        client.sia2_query(359.99, 89.9)
    assert len(seen) == 4
    assert all(item["POS"] == "circle 359.99000000 89.90000000 0.000000" for item in seen)


def test_complete_empty_sia_can_resolve_failed_tap_as_no_data(tmp_path, monkeypatch):
    client = irsa.IrsaClient(replace(settings, cache_dir=tmp_path))
    def outage(*args, **kwargs):
        raise irsa.IRSAUnavailable("TAP offline")
    monkeypatch.setattr(client, "tap_query", outage)
    monkeypatch.setattr(client, "sia2_query", lambda *args, **kwargs: [])
    with pytest.raises(irsa.IRSANoData):
        client.query_artifacts(1, 2)


def test_expired_shared_deadline_stops_before_network_and_backoff(tmp_path, monkeypatch):
    contacted = []
    client = client_with_transport(tmp_path, monkeypatch,
        lambda request: contacted.append(request) or httpx.Response(200), deadline=time.monotonic()-1)
    with client._new_client() as http:
        with pytest.raises(irsa.IRSAUnavailable, match="deadline"):
            client._request(http, "https://example.invalid")
    assert not contacted
    client.deadline_at = time.monotonic() + .01
    with pytest.raises(irsa.IRSAUnavailable, match="before retry"):
        client._backoff(0, None)


def test_deadline_is_not_reset_by_fallback(tmp_path, monkeypatch):
    client = irsa.IrsaClient(replace(settings, cache_dir=tmp_path), deadline_at=time.monotonic()+30)
    original = client.deadline_at
    def outage(*args, **kwargs):
        raise irsa.IRSAUnavailable("TAP offline")
    monkeypatch.setattr(client, "tap_query", outage)
    def fallback(*args, **kwargs):
        assert client.deadline_at == original
        assert 0 < client.remaining_seconds() <= 30
        return []
    monkeypatch.setattr(client, "sia2_query", fallback)
    with pytest.raises(irsa.IRSANoData):
        client.query_artifacts(1, 2)


def test_blocked_http_response_is_bounded_by_absolute_deadline(tmp_path, monkeypatch):
    release = Event()
    def stalled(request):
        release.wait(.5)
        return httpx.Response(200, content=b"late")
    client = client_with_transport(tmp_path, monkeypatch, stalled, deadline=time.monotonic()+.04)
    started = time.monotonic()
    try:
        with client._new_client() as http:
            with pytest.raises(irsa.IRSAUnavailable, match="deadline|Deadline"):
                client._request(http, "https://example.invalid", timeout=20)
        assert time.monotonic()-started < .3
    finally:
        release.set()


def test_cutout_worker_wait_does_not_exceed_shared_deadline(tmp_path, monkeypatch):
    release = Event()
    client = irsa.IrsaClient(replace(settings, cache_dir=tmp_path), deadline_at=time.monotonic()+.04)
    record = irsa.ArtifactRecord("unit-test", 60000, None, 1, "SPHEREx-D1", "unit", "DR1", "spherex_dr1")
    def stalled(*args, **kwargs):
        release.wait(.5)
        return b"never served"
    monkeypatch.setattr(client, "fetch_cutout", stalled)
    started = time.monotonic()
    try:
        with pytest.raises(irsa.IRSAUnavailable, match="deadline"):
            client.fetch_cutouts([record], 1, 2, .05)
        assert time.monotonic()-started < .3
    finally:
        release.set()
