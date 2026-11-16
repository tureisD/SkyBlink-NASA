"""Actual reviewed metadata plus isolated invalid protocol inputs; no sky fixtures."""
import pytest
from pydantic import ValidationError

from core.cachekeys import live_asset_key
from core.config import Settings
from core.source_policy import source_target
from models.sky import SkyQuery
from models.spectrum import SpectrumQuery
from services import indexed_archive as indexed
from services.irsa_client import IRSAUnavailable, IRSAIncompleteDiscovery
from services.spectrophotometry import spectrum_asset_key


@pytest.mark.parametrize('target_id',['wise_0855','barnards_star','eps_indi_b','rw_aurigae','r_draconis'])
def test_real_index_covers_catalog_positions_with_explicit_partial_scope(tmp_path,target_id):
    target=source_target(target_id,'archive')
    client=indexed.IndexedArchiveClient(Settings(cache_dir=tmp_path))
    records=client.query_artifacts(target.ra_epoch2025,target.dec_epoch2025,allow_partial=True)
    assert records and client.use_cache is False
    assert client.settings.max_workers <= 2
    assert client.discovery_metadata['status']=='partial'
    assert client.discovery_metadata['all_archive_complete'] is False
    assert client.discovery_metadata['index_sha256']==indexed.INDEX_SHA256
    assert all(r.collection.startswith('indexed_') for r in records)
    assert all(r.mjd_upper >= r.mjd_lower for r in records)
    with pytest.raises(IRSAIncompleteDiscovery):
        client.query_artifacts(target.ra_epoch2025,target.dec_epoch2025)


def test_arbitrary_position_and_wrap_are_spatial_not_catalog_lookup(tmp_path):
    client=indexed.IndexedArchiveClient(Settings(cache_dir=tmp_path))
    # An actual independently indexed image center from the QR3 control.
    records=client.query_artifacts(286.0012867435891,43.70488424019806,allow_partial=True)
    assert len(records)>=8
    entry=next(e for e in indexed.load_index()['records'] if e['key'].endswith('0001_1D1_spx_l2b-v27-2026-285.fits'))
    assert indexed._contains(entry,286.0012867435891-360,43.70488424019806)
    assert not indexed._contains(entry,106.0012867435891,-43.70488424019806)


def test_subset_miss_is_unknown_coverage_not_no_data(tmp_path):
    client=indexed.IndexedArchiveClient(Settings(cache_dir=tmp_path))
    with pytest.raises(IRSAUnavailable,match='Coverage outside this limited index is unknown'):
        client.query_artifacts(10,20,allow_partial=True)


def test_changed_metadata_is_rejected_before_decoding(tmp_path,monkeypatch):
    path=tmp_path/'changed.gz';path.write_bytes(indexed.INDEX_PATH.read_bytes()+b'changed')
    monkeypatch.setattr(indexed,'INDEX_PATH',path)
    with pytest.raises(IRSAUnavailable,match='approval hash mismatch'):
        indexed.load_index()


@pytest.mark.parametrize('model',[SkyQuery,SpectrumQuery])
def test_explicit_mode_contract(model):
    assert model(ra=1,dec=2,source='archive',discovery='indexed').discovery=='indexed'
    with pytest.raises(ValidationError):model(ra=1,dec=2,source='saved',discovery='indexed')
    with pytest.raises(ValidationError):model(ra=1,dec=2,discovery='invented')


def test_source_work_identity_is_distinct_and_changes_with_index(monkeypatch):
    sky={mode:live_asset_key(1,2,.2,discovery_mode=mode) for mode in ['live','known','indexed']}
    spectrum={mode:spectrum_asset_key(1,2,discovery_mode=mode) for mode in ['live','known','indexed']}
    assert len(set(sky.values()))==len(set(spectrum.values()))==3
    from core import archive_index_approval
    monkeypatch.setattr(archive_index_approval,'INDEX_SHA256','0'*64)
    assert live_asset_key(1,2,.2,discovery_mode='indexed')!=sky['indexed']
    assert spectrum_asset_key(1,2,discovery_mode='indexed')!=spectrum['indexed']
