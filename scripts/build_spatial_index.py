"""Compile reviewed real header snapshots and fresh catalog-seeded headers.

Offline maintenance tool; the emitted metadata inventory never promises all-sky
coverage. Historical addresses select supplemental samples, not sky pixels.
"""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import quote

import httpx
from astropy.io import fits
from astropy.wcs import WCS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'docs/research/archive-recovery'))
from cloud_index_probe import image_header, digest
from cloud_search_probe import bound


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--snapshots-root',type=Path,required=True)
    args=p.parse_args()
    records={}; scopes=[]; receipts=[]
    def add(item, header, origin):
        w=WCS(header).celestial
        compact=dict(w.to_header(relax=True))
        compact.update(NAXIS=2,NAXIS1=header['NAXIS1'],NAXIS2=header['NAXIS2'])
        vertices=w.all_pix2world([[0,0],[header['NAXIS1']-1,0],
            [header['NAXIS1']-1,header['NAXIS2']-1],[0,header['NAXIS2']-1]],0)
        records[item['key']]={k:item[k] for k in ['key','etag','size','header_sha256']}
        records[item['key']].update(wcs=compact,cone=bound(header),
            detector=int(header['DETECTOR']),mjd_begin=float(header['MJD-BEG']),
            mjd_end=float(header['MJD-END']),timesys=str(header['TIMESYS']),
            origin=origin,s_region='POLYGON ICRS '+' '.join(str(float(v)) for pair in vertices for v in pair))
    for folder in ['qr3-d1','wise-2025-d3','wise-2026-d3']:
        path=args.snapshots_root/folder/'snapshot.json'; raw=path.read_bytes(); s=json.loads(raw)
        if not s['enumeration_complete'] or not s['headers_complete']:
            raise ValueError('Cannot approve an incomplete directory scan')
        scopes.append({k:s[k] for k in ['scope','started_at','finished_at','listed_objects']} | {'snapshot_sha256':digest(raw)})
        for item in s['objects']:
            raw=(path.parent/item['header_file']).read_bytes()
            if digest(raw)!=item['header_sha256']:raise ValueError('Header hash mismatch')
            add(item,fits.Header.fromstring(raw.decode('ascii'),sep=''),'directory_scan')
        print(f'Compiled {folder}: {len(records)} entries',flush=True)
    known=json.loads((ROOT/'data/catalog-exposure-index.json').read_text())
    cache=args.snapshots_root/'catalog-supplement';cache.mkdir(exist_ok=False)
    with httpx.Client(timeout=20,follow_redirects=False) as c:
        keys=sorted({r['uri'].split('/ibe/data/spherex/')[1] for t in known['targets'].values() for r in t['records']})
        for key in keys:
            if key in records:continue
            url='https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/'+quote(key,safe='/')
            head=c.head(url);head.raise_for_status()
            etag=head.headers['etag'];size=int(head.headers['content-length'])
            extracted=None
            for limit in [28800,57600,115200]:
                with c.stream('GET',url,headers={'Range':f'bytes=0-{limit-1}','If-Match':etag}) as response:
                    if response.status_code!=206 or response.headers.get('content-range')!=f'bytes 0-{limit-1}/{size}' or response.headers.get('etag')!=etag:
                        raise ValueError('Invalid fresh range response')
                    body=b''.join(response.iter_bytes())
                    if len(body)!=limit:raise ValueError('Unexpected range length')
                extracted=image_header(body)
                if extracted:break
            if extracted is None:raise ValueError('Header exceeds cap')
            header,raw=extracted
            if header['TIMESYS']!='UTC':raise ValueError('Unsupported time scale')
            path=cache/(digest(key.encode())+'.header');path.write_bytes(raw)
            item={'key':key,'etag':etag,'size':size,'header_sha256':digest(raw)}
            add(item,header,'historical_address_fresh_header')
            receipts.append(item | {'url':url,'retrieved_at':datetime.now(timezone.utc).isoformat()})
            print('Supplemented '+key,flush=True)
    payload={'schema_version':'skyblink.spatial-index/1','created_at':datetime.now(timezone.utc).isoformat(),
        'all_archive_complete':False,'scope':'Bounded directory scans plus fresh headers at historically recorded catalog addresses; not complete archive coverage',
        'directory_scopes':scopes,'supplement_receipts':receipts,
        'builder_sha256':digest(Path(__file__).read_bytes()),'records':list(records.values())}
    raw=json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    compressed=gzip.compress(raw,mtime=0)
    dest=ROOT/'data/archive-spatial-index.json.gz';dest.write_bytes(compressed)
    sha=digest(compressed)
    (ROOT/'backend/core/archive_index_approval.py').write_text('"""Reviewed bounded real metadata inventory; no science pixels."""\nINDEX_SHA256 = '+repr(sha)+'\n')
    (cache/'build-receipt.json').write_text(json.dumps({'sha256':sha,'records':len(records),'bytes':len(compressed),'decoded_bytes':len(raw),'supplement':receipts},indent=2)+'\n')
    print(json.dumps({'sha256':sha,'records':len(records),'bytes':len(compressed),'decoded_bytes':len(raw)}),flush=True)


if __name__=='__main__':main()
