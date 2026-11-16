"""Stage a real comparison from bounded AWS metadata snapshots; never publish it.

Research adapter only. Snapshot periods can be chosen using historical coverage
hints, but exposure discovery uses their newly acquired headers. No known-mode
inventory or saved image is passed into the pipeline.
"""
import argparse
from dataclasses import replace
from io import BytesIO
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'backend'))

from astropy.io import fits
from astropy.wcs import WCS
from cloud_index_probe import contains, digest, save_json
from cloud_search_probe import candidate
from core.config import settings
from services.irsa_client import ArtifactRecord, IrsaClient, IRSAUnavailable, IRSAIncompleteDiscovery
from services import spherex_pipeline as pipeline, recording


class SnapshotClient(IrsaClient):
    def __init__(self, config, snapshots, **kwargs):
        super().__init__(config, use_cache=False, **kwargs)
        self.snapshots = snapshots

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
                        raise ValueError('Indexed detector/time mismatch')
                accepted[record] = content
            except Exception as error:
                self.discovery_metadata.setdefault('rejected_downloads', []).append(
                    {'uri':record.uri,'reason':str(error),'sha256':digest(content)})
        return accepted

    def query_artifacts(self, ra, dec, *, bands=None, allow_partial=False, **kwargs):
        records=[]; scopes=[]
        for path in self.snapshots:
            raw=path.read_bytes(); snapshot=json.loads(raw)
            index_path=path.parent/'search-index.json'
            index=json.loads(index_path.read_text())
            if index['snapshot_sha256']!=digest(raw):
                raise IRSAUnavailable('Spatial index/snapshot hash mismatch')
            cones={x['key']:x['cone'] for x in index['entries']}
            if set(cones)!={x['key'] for x in snapshot['objects']}:
                raise IRSAUnavailable('Spatial index has missing/extra objects')
            scopes.append({'prefix':snapshot['scope'],'snapshot_sha256':digest(raw),
                           'index_sha256':digest(index_path.read_bytes()),
                           'indexed_objects':len(snapshot['objects']),
                           'headers_complete':snapshot['headers_complete'],
                           'started_at':snapshot['started_at'],'finished_at':snapshot['finished_at']})
            for item in snapshot['objects']:
                self.remaining_seconds()
                if bands and item['detector'] not in bands:continue
                if not candidate(cones[item['key']],ra,dec):continue
                header_bytes=(path.parent/item['header_file']).read_bytes()
                if digest(header_bytes)!=item['header_sha256']:
                    raise IRSAUnavailable('Header hash mismatch')
                header=fits.Header.fromstring(header_bytes.decode('ascii'),sep='')
                if not contains(header,ra,dec):continue
                # Corners only rank candidates; the unchanged pipeline tests the
                # actual spectral WCS and usable pixels across the output field.
                w=WCS(header).celestial
                corners=w.all_pix2world([[0,0],[header['NAXIS1']-1,0],
                    [header['NAXIS1']-1,header['NAXIS2']-1],[0,header['NAXIS2']-1]],0)
                region='POLYGON ICRS '+' '.join(str(float(v)) for pair in corners for v in pair)
                records.append(ArtifactRecord(uri='ibe/data/spherex/'+item['key'],
                    mjd_lower=item['mjd_begin'],mjd_upper=item['mjd_end'],
                    band=item['detector'],band_name='SPHEREx-D'+str(item['detector']),
                    planeid='',release=item['release'].upper(),collection='unclassified_cloud_subset',
                    contentlength=item['size'],s_region=region))
        self.discovery_metadata={'status':'partial','method':'research_aws_header_snapshot',
            'mode':'research_cloud','query':{'ra':ra,'dec':dec},'scopes':scopes,
            'record_count':len(records),'responses':[],
            'completeness_scope':'Only enumerated detector/period prefixes; archive coverage unknown',
            'collection_membership':'wide/deep unknown; not inferred',
            'period_selection':'Historical WISE coverage hints; fresh listing and header discovery',
            'all_archive_complete':False}
        if not allow_partial:
            raise IRSAIncompleteDiscovery('Research snapshot is incomplete',records=records,missing_collections=[])
        if not records:
            raise IRSAUnavailable('No match in bounded snapshot; archive coverage unknown')
        return sorted(records,key=lambda r:(r.mjd_lower,r.uri))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--snapshot',type=Path,action='append',required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--ra',type=float,required=True)
    p.add_argument('--dec',type=float,required=True)
    args=p.parse_args()
    out=args.out.resolve()
    if not out.is_relative_to((ROOT/'backend/.cache/archive-index-prototype').resolve()):
        p.error('Output must remain in the isolated research cache')
    out.mkdir(parents=True,exist_ok=False)
    config=replace(settings,cache_dir=out/'cache',max_workers=4,
                   request_timeout_seconds=20,retries=3,retry_backoff_seconds=.25)
    config.ensure_dirs()
    pipeline.settings=config;recording.settings=config
    started=time.monotonic()
    client=SnapshotClient(config,args.snapshot,deadline_at=started+120)
    report={'research_only':True,'promotion_eligible':False,'script_sha256':digest(Path(__file__).read_bytes()),
            'ra':args.ra,'dec':args.dec,'deadline_seconds':120}
    try:
        manifest=pipeline._build_manifest('research_cloud_wise',args.ra,args.dec,
            cutout_size_deg=.2,max_visits_per_band=3,max_epochs=3,live_mode=True,
            deadline_seconds=120,force_refresh=True,archive_client=client,allow_single_epoch=True)
        # Keep explicitly labeled copies outside application asset roots.
        manifest.update(research_only=True,promotion_eligible=False,
                        research_source='AWS header snapshots; pipeline live-mode scheduling only')
        save_json(out/'research-manifest.json',manifest)
        report.update(status='built',epochs=len(manifest['epochs']),
                      comparison=manifest['comparison_selection'],
                      difference_keys=list(manifest['differences']),
                      provenance=manifest['provenance'],live_selection=manifest['live_selection'])
    except Exception as error:
        report.update(status='failed',error=type(error).__name__,message=str(error))
    report.update(seconds=round(time.monotonic()-started,3),discovery=client.discovery_metadata,
                  acquisition=client.acquisition_metadata)
    save_json(out/'report.json',report)
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
