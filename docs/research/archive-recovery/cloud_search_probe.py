"""Research spatial prefilter, verified against the exhaustive header prototype."""
import argparse
import json
import math
from pathlib import Path
import time

from astropy.io import fits
from astropy.wcs import WCS
import numpy as np

from cloud_index_probe import contains, digest, save_json


def vector(ra, dec):
    lon, lat = np.deg2rad([ra, dec])
    return np.array([np.cos(lat)*np.cos(lon), np.cos(lat)*np.sin(lon), np.sin(lat)])


def bound(header):
    """Conservative cone for TAN + forward SIP over the entire pixel rectangle.

    Absolute polynomial coefficients bound distortion over the rectangle;
    the CD matrix bounds tangent-plane distance. Unsupported WCS is never culled.
    """
    w = WCS(header).celestial
    if (list(w.wcs.ctype) != ['RA---TAN-SIP', 'DEC--TAN-SIP']
            or w.sip is None or w.cpdis1 or w.cpdis2 or w.det2im1 or w.det2im2
            or not np.array_equal(w.sip.crpix, w.wcs.crpix)
            or w.wcs.get_pv()):
        return None
    extent = np.maximum(np.abs(0.5-w.wcs.crpix),
                        np.abs(np.array([header['NAXIS1'],header['NAXIS2']])+0.5-w.wcs.crpix))
    distorted = extent.copy()
    for axis, coefficients in enumerate([w.sip.a, w.sip.b]):
        for i, j in np.ndindex(coefficients.shape):
            distorted[axis] += abs(coefficients[i,j])*extent[0]**i*extent[1]**j
    plane = np.abs(w.pixel_scale_matrix) @ distorted
    radius = math.atan(np.linalg.norm(np.deg2rad(plane)))
    if not math.isfinite(radius):
        return None
    return {'unit_vector':vector(*w.wcs.crval).tolist(), 'cos_radius':math.cos(radius),
            'radius_deg':math.degrees(radius)}


def candidate(cone, ra, dec):
    return cone is None or float(np.dot(cone['unit_vector'],vector(ra,dec))) >= cone['cos_radius']-1e-12


def build(args):
    started=time.monotonic()
    snapshot=json.loads(args.snapshot.read_text())
    entries=[]
    checks=0
    for item in snapshot['objects']:
        raw=(args.snapshot.parent/item['header_file']).read_bytes()
        if digest(raw)!=item['header_sha256']:
            raise ValueError('Header hash mismatch')
        h=fits.Header.fromstring(raw.decode('ascii'),sep='')
        cone=bound(h)
        w=WCS(h).celestial
        # Independent sampled check of the analytic bound using forward WCS.
        for x in [-0.49,(h['NAXIS1']-1)/2,h['NAXIS1']-0.51]:
            for y in [-0.49,(h['NAXIS2']-1)/2,h['NAXIS2']-0.51]:
                ra,dec=w.all_pix2world([[x,y]],0)[0]
                if not candidate(cone,ra,dec):
                    raise ValueError('Cone excluded an in-image control point')
                checks+=1
        entries.append(dict(key=item['key'],cone=cone))
    result={'snapshot_sha256':digest(args.snapshot.read_bytes()),'entries':entries,
            'bound_checks':checks,'seconds':round(time.monotonic()-started,3),
            'script_sha256':digest(Path(__file__).read_bytes()),
            'unculled_entries':sum(x['cone'] is None for x in entries)}
    save_json(args.out,result)
    print(json.dumps({k:v for k,v in result.items() if k!='entries'}),flush=True)


def verify(args):
    snapshot=json.loads(args.snapshot.read_text())
    index=json.loads(args.index.read_text())
    if digest(args.snapshot.read_bytes())!=index['snapshot_sha256']:
        raise ValueError('Index belongs to another snapshot')
    entries={x['key']:x['cone'] for x in index['entries']}
    if set(entries)!={x['key'] for x in snapshot['objects']}:
        raise ValueError('Index has missing/extra objects')
    results=[]
    for path in sorted(args.snapshot.parent.glob('*-query.json')):
        tick=time.monotonic()
        reference=json.loads(path.read_text())
        if reference['snapshot_sha256']!=index['snapshot_sha256'] or reference['search_failures']:
            raise ValueError('Invalid exhaustive reference')
        matches=[]; candidates=0
        for item in snapshot['objects']:
            if not candidate(entries[item['key']],reference['ra'],reference['dec']):
                continue
            candidates+=1
            raw=(args.snapshot.parent/item['header_file']).read_bytes()
            if digest(raw)!=item['header_sha256']:
                raise ValueError('Header hash mismatch')
            h=fits.Header.fromstring(raw.decode('ascii'),sep='')
            if contains(h,reference['ra'],reference['dec']):
                matches.append(item['key'])
        if set(matches)!={x['key'] for x in reference['matches']}:
            raise ValueError('Accelerated and exhaustive search disagree')
        results.append({'query':path.name,'candidates':candidates,'matches':len(matches),
                        'seconds':round(time.monotonic()-tick,3),'identical':True})
    if len(results)!=7:
        raise ValueError('Expected all seven exhaustive queries')
    save_json(args.out,{'passed':True,'queries':results,'index_sha256':digest(args.index.read_bytes()),
                        'script_sha256':digest(Path(__file__).read_bytes()),
                        'scope':'Research subset only; not runtime discovery or science acceptance'})
    print(json.dumps(results),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['build','verify'])
    p.add_argument('--snapshot',type=Path,required=True)
    p.add_argument('--index',type=Path)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.command=='verify' and a.index is None:p.error('--index required')
    (build if a.command=='build' else verify)(a)


if __name__=='__main__':
    main()
