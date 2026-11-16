"""Explicit bounded spatial metadata search with fresh upstream image downloads."""
from functools import lru_cache
from dataclasses import replace
import gzip
import hashlib
from io import BytesIO
import json
import math
import re

from astropy.io import fits
from astropy.wcs import WCS
import numpy as np

from core.config import REPO_ROOT
from core.archive_index_approval import INDEX_SHA256
from services.irsa_client import ArtifactRecord, IrsaClient, IRSAUnavailable, IRSAIncompleteDiscovery

INDEX_PATH = REPO_ROOT / 'data/archive-spatial-index.json.gz'
KEY = re.compile(r'(dr1|qr3)/level2/[A-Za-z0-9_]+/l2b-[A-Za-z0-9-]+/([1-6])/level2_[A-Za-z0-9_.-]+\.fits')


def _vector(ra, dec):
    lon, lat = np.deg2rad([ra, dec])
    return np.array([np.cos(lat)*np.cos(lon), np.cos(lat)*np.sin(lon), np.sin(lat)])


@lru_cache(maxsize=1)
def _decode(content):
    with gzip.GzipFile(fileobj=BytesIO(content)) as stream:
        raw = stream.read(64*1024*1024+1)
    if len(raw) > 64*1024*1024:
        raise ValueError('Metadata exceeds decoded size limit')
    index = json.loads(raw)
    if index['schema_version'] != 'skyblink.spatial-index/1' or index['all_archive_complete'] is not False:
        raise ValueError('Unsupported inventory schema or completeness claim')
    seen = set()
    for entry in index['records']:
        match = KEY.fullmatch(entry['key'])
        if not match or entry['key'] in seen or int(match[2]) != entry['detector']:
            raise ValueError('Invalid/duplicate exposure key or detector')
        seen.add(entry['key'])
        lower, upper = entry['mjd_begin'], entry['mjd_end']
        if entry['timesys'] != 'UTC' or not (math.isfinite(lower) and lower <= upper < math.inf):
            raise ValueError('Invalid exposure time bounds')
    return index


def load_index():
    try:
        content = INDEX_PATH.read_bytes()
        if hashlib.sha256(content).hexdigest() != INDEX_SHA256:
            raise ValueError('Inventory approval hash mismatch')
        return _decode(content)
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise IRSAUnavailable(f'Indexed archive metadata is unavailable or invalid: {error}') from error


def _contains(entry, ra, dec):
    cone = entry['cone']
    if cone is not None and np.dot(cone['unit_vector'], _vector(ra, dec)) < cone['cos_radius']-1e-12:
        return False
    header = fits.Header(entry['wcs'])
    wcs = WCS(header).celestial
    with np.errstate(all='ignore'):
        x, y = wcs.all_world2pix([[ra, dec]], 0, quiet=True)[0]
    if not (np.isfinite([x, y]).all() and -.5 <= x < header['NAXIS1']-.5 and -.5 <= y < header['NAXIS2']-.5):
        return False
    result = wcs.all_pix2world([[x, y]], 0)[0]
    return bool(np.linalg.norm(_vector(ra, dec)-_vector(*result)) < np.deg2rad(1e-6))


class IndexedArchiveClient(IrsaClient):
    def __init__(self, settings=None, *, deadline_at=None):
        super().__init__(settings, deadline_at=deadline_at, use_cache=False)
        # The cutout service returned explicit busy responses during concurrent
        # catalog verification. Bound per-build pressure without changing gates.
        self.settings = replace(self.settings, max_workers=min(2, self.settings.max_workers))

    def query_artifacts(self, ra, dec, *, bands=None, allow_partial=False, **kwargs):
        self.remaining_seconds()
        index = load_index()
        records = []
        for entry in index['records']:
            self.remaining_seconds()
            if bands is not None and entry['detector'] not in bands:
                continue
            if not _contains(entry, ra, dec):
                continue
            release = entry['key'].split('/')[0]
            records.append(ArtifactRecord(uri='ibe/data/spherex/'+entry['key'],
                mjd_lower=entry['mjd_begin'], mjd_upper=entry['mjd_end'], band=entry['detector'],
                band_name=f"SPHEREx-D{entry['detector']}", planeid='', release=release.upper(),
                collection='indexed_'+release, contentlength=entry['size'], s_region=entry['s_region']))
        self.discovery_metadata = {
            'status':'partial','mode':'indexed','method':'bounded_aws_header_spatial_index',
            'query':{'ra':float(ra),'dec':float(dec)},'record_count':len(records),
            'index_sha256':INDEX_SHA256,'index_created_at':index['created_at'],
            'index_schema_version':index['schema_version'],'completeness_scope':index['scope'],
            'directory_scopes':index['directory_scopes'], 'all_archive_complete':False,
            'collection_membership':'wide/deep unknown','responses':[],'missing_collections':[],
        }
        if not allow_partial:
            raise IRSAIncompleteDiscovery('Spatial index is an explicitly limited inventory', records=records, missing_collections=[])
        if not records:
            raise IRSAUnavailable('No indexed exposures cover this position. Coverage outside this limited index is unknown. Try live archive search or choose a catalog target.')
        return sorted(records, key=lambda record:(record.mjd_lower, record.uri))

    def fetch_cutouts(self, records, ra, dec, size_deg, **kwargs):
        downloaded = super().fetch_cutouts(records, ra, dec, size_deg, **kwargs)
        accepted = {}
        for record, content in downloaded.items():
            try:
                with fits.open(BytesIO(content), memmap=False) as hdus:
                    h = hdus['IMAGE'].header
                    if (h.get('TIMESYS') != 'UTC' or int(h['DETECTOR']) != record.band
                            or abs(float(h['MJD-BEG'])-record.mjd_lower) > 1e-8
                            or abs(float(h['MJD-END'])-record.mjd_upper) > 1e-8):
                        raise ValueError('Indexed detector/time metadata mismatch')
                accepted[record] = content
            except Exception as error:
                self.discovery_metadata.setdefault('rejected_downloads', []).append(
                    {'uri':record.uri,'reason':str(error),'sha256':hashlib.sha256(content).hexdigest()})
        return accepted
