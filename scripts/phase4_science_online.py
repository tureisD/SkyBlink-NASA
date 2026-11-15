"""Fresh, preregistered multi-field research. Never writes golden or production data.

The initial stages inspect only catalogs/discovery/calibration metadata. A locked
control/pair record must exist before extracting any SPHEREx control flux.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from itertools import combinations
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import sys
import time

import httpx
import numpy as np
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.time import Time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "backend"))
from phase4_science_validation import digest, read_json, write_json, table_rows, position

CACHE = ROOT / "backend/.cache/phase4/online-science"
PLAN = ROOT / "docs/evidence/phase4/phase4-science-online-preregistration.json"
CELL_VARIANT = ""
RETRY_FAILED = False
FIELDS = (
    ("north_galactic_pole",192.85948,27.12825),
    ("south_galactic_pole",12.85948,-27.12825),
    ("north_b60",159.8833073544,39.5544404047),
    ("south_b60",339.8833073544,-39.5544404047),
)


def now():
    return datetime.now(timezone.utc).isoformat()


def register():
    if PLAN.exists():
        return read_json(PLAN)
    old = read_json(ROOT / "docs/evidence/phase4/phase4-science-preregistration.json")
    plan = {
        "registered_at": now(), "stage": "before_new_catalogs_or_SPHEREx_control_flux",
        "fields": [{"id": name,"ra": ra,"dec": dec,"research_radius_deg": .5} for name,ra,dec in FIELDS],
        "detector_order": [1,3], "field_order": [name for name,_,_ in FIELDS],
        "excluded_prior_control_ids": old["excluded_phase3_source_ids"],
        "catalog_selection": {
            "gaia_neighbor_g_limit":20, "control_g_range":[10,17], "maximum_ruwe":1.4,
            "maximum_pm_mas_yr":100, "maximum_abs_parallax_mas":10, "exclude_gaia_variable":True,
            "gaia_neighbor_exclusion_arcsec":30.75,"allwise_neighbor_exclusion_arcsec":30.75,
            "allwise_match_arcsec":3,"allwise_reference_decimalyear":2010.5,
            "allwise_quality":"W1/W2ph_qualA/B,cc_flags00,var_flg0/1,ext_flg0,SNR>=10; unknown fails",
            "region_margin_deg":.05,"maximum_controls_per_region":20,
            "ordering":"AllWISE W1 catalog magnitude ascending, numeric Gaia source_id ascending; lock before SPHEREx flux. No replacements after flux failures.",
            "neighbors":"All returned AllWISE catalog entries, GaiaG<=20; positions propagated where measured PM exists. Unresolved/subthreshold blends remain unexcluded.",
        },
        "pair_selection":{
            "minimum_time_separation_days":1,"maximum_time_separation_days":400,
            "same_release_required":True,"detectors":[1,3],
            "maximum_downloaded_candidates_per_detector_region":8,
            "ranking":"First by greatest footprint overlap/minimum corner displacement when polygons retained, then shortest separation>=1day, then URI; metadata/calibration only. Without polygons rank time then URI. Freeze ranking before downloads.",
            "selection":"First ranked pair whose recorded footprints cover>=3lockedcontrols with all per-control spectral/astrometry/support prerequisites. No flux values or residuals select a pair. One accepted pair per field/detector; no replacement after flux measurement.",
            "spectral_gate":"CWAVE/CBAND matched to release/detector/orientation and exact WCS-WAVE table identity; max center shift<=.25narrowerwidth, bandwidthratio>=.8 at control aperture footprint; full-field visual gate remains separate.",
            "astrometry_gate":"Independent native image peaks/Gaia association, no residual clipping;>=3stars per exposure, robustRMS includingbias<=1.5375arcsec. Use parent Phase3centroid method and freshGaia neighborhood.",
        },
        "measurement_methods":{
            "primary_candidate":"Photutils CircularAperture5x5subpixel, radius12.3arcsec",
            "baseline":"Existing center-pixel radius12.3arcsec",
            "convergence_diagnostic":"Photutils exact fractional intersection, same radius/background; not a posthoc replacement acceptance method",
            "psf_diagnostic":"If release-matched EPSF available, compare predicted encircled-energy/pixel-phase effects and nativePSF amplitude+background. Diagnostic only; noPSFmethod adopted using these outcomes.",
            "annulus":"Native pixel centers3<=r<=5, hard/warning/SOURCE excluded,>=10cleanpixels; no field-only fallback for acceptance",
            "field_background":"Supported fixed production maskedmedian/heldoutplane; no new fitted normalization from controls",
            "mask":"Hard and warning excluded; SOURCE retained in aperture only; complete nonzero-weight aperture support for all compared methods",
            "variance":"K²[sum(w²V)+sum(w)²Var(b)], Var(b)=max[(pi/2)mean(Vann)/Nann,(1.2533*MADscaled)²/Nann]",
            "solid_angle":"Use release-matched SAPM when available; report constant localWCS approximation separately and do not claim absolute totalflux calibration without correction",
            "no_tuning":"No empirical error inflation, flux-scale fitting, residual clipping or threshold relaxation from holdout data",
        },
        "acceptance":{
            "minimum_usable_controls_per_field_detector":3,
            "minimum_independent_fields":2,"minimum_detectors":2,
            "minimum_snr_each_method_each_visit":5,
            "max_abs_median_z":1,"max_robust_scatter_z":2,"max_abs_individual_z":5,
            "five_subpixel_exact_convergence":"For each retained measurement, |F5-Fexact|<=0.1*its approximate sigma; report all departures, no deletion",
            "global_gate":"All measured valid cells must pass primarycandidate stability and convergence; require2fields and2detectors. Missingprerequisites/insufficientcells cannot be counted aspass.",
        },
        "limits":"Engineering validation of scoped repeatability, not proof every catalog control is infraredconstant, absolutephotometric calibration, discovery significance, all-sky reliability or all detectors/releases",
        "retention":"Hash all rawFITS,catalogs,calibrations, queries and lockedIDs; preserve previous failedresults; researchcache ignored, no golden writes",
    }
    write_json(PLAN,plan)
    print(json.dumps({"registered":str(PLAN.relative_to(ROOT)),"sha256":digest(PLAN.read_bytes())}),flush=True)
    return plan


def fetch_catalog(field, kind):
    directory = CACHE / field["id"]
    directory.mkdir(parents=True,exist_ok=True)
    path = directory / f"{kind}.xml"
    metadata_path = directory / f"{kind}-source.json"
    if path.exists() and metadata_path.exists():
        metadata=read_json(metadata_path)
        if digest(path.read_bytes())!=metadata["sha256"]:
            raise ValueError("Catalog cache identity changed")
        return table_rows(path.read_bytes()),metadata
    ra,dec=field["ra"],field["dec"]
    if kind=="gaia":
        url="https://gea.esac.esa.int/tap-server/tap/sync"
        query=f"SELECT TOP 20000 source_id,ra,dec,ref_epoch,pmra,pmdec,parallax,ruwe,phot_g_mean_mag,phot_variable_flag FROM gaiadr3.gaia_source WHERE 1=CONTAINS(POINT('ICRS',ra,dec),CIRCLE('ICRS',{ra},{dec},0.5)) AND phot_g_mean_mag<=20 ORDER BY source_id"
        params={"REQUEST":"doQuery","LANG":"ADQL","FORMAT":"votable","QUERY":query}
    else:
        url="https://irsa.ipac.caltech.edu/cgi-bin/Gator/nph-query"
        params={"catalog":"allwise_p3as_psd","spatial":"Cone","objstr":f"{ra} {dec}",
                "radius":"30","radunits":"arcmin","outfmt":"3",
                "selcols":"designation,ra,dec,w1mpro,w2mpro,w1snr,w2snr,ph_qual,cc_flags,var_flg,ext_flg"}
    started=time.monotonic()
    response=httpx.get(url,params=params,timeout=60,follow_redirects=True)
    response.raise_for_status()
    rows=table_rows(response.content)
    metadata={"url":url,"parameters":params,"retrieved_at":now(),"sha256":digest(response.content),
              "bytes":len(response.content),"rows":len(rows),"elapsed_seconds":time.monotonic()-started,
              "path":path.relative_to(ROOT).as_posix(),"is_simulated_fallback":False}
    path.write_bytes(response.content);write_json(metadata_path,metadata)
    return rows,metadata


def catalog_selection(field, gaia, infrared, plan):
    """Only catalog values; no SPHEREx image data is loaded at this stage."""
    from collections import Counter
    ref=Time(2025.8,format="decimalyear",scale="tt")
    moved=[position(row,ref) for row in gaia]
    positions=SkyCoord(ra=[c.ra.deg for c in moved]*u.deg,dec=[c.dec.deg for c in moved]*u.deg)
    ircoords=SkyCoord(ra=[r["ra"] for r in infrared]*u.deg,dec=[r["dec"] for r in infrared]*u.deg)
    center=SkyCoord(field["ra"],field["dec"],unit="deg")
    selected=[];rejections=Counter()
    for index,row in enumerate(gaia):
        if row["source_id"] in plan["excluded_prior_control_ids"]:
            rejections["previous_control"]+=1;continue
        if any(row.get(key) is None for key in ("pmra","pmdec","ruwe","parallax","phot_g_mean_mag")):
            rejections["missing_quality"]+=1;continue
        if not(10<=row["phot_g_mean_mag"]<=17 and row["ruwe"]<=1.4 and abs(row["parallax"])<=10
               and math.hypot(row["pmra"],row["pmdec"])<=100 and row.get("phot_variable_flag")!="VARIABLE"):
            rejections["gaia_quality"]+=1;continue
        if moved[index].separation(center).deg>.45:
            rejections["region_margin"]+=1;continue
        distances=moved[index].separation(positions).arcsec;distances[index]=np.inf
        if float(distances.min())<30.75:
            rejections["gaia_neighbor"]+=1;continue
        oldpos=position(row,Time(2010.5,format="decimalyear",scale="utc"))
        separation=oldpos.separation(ircoords).arcsec;matches=np.where(separation<=3)[0]
        if len(matches)!=1:
            rejections["allwise_missing_or_ambiguous"]+=1;continue
        irindex=int(matches[0]);ir=infrared[irindex]
        neighbors=ircoords[irindex].separation(ircoords).arcsec;neighbors[irindex]=np.inf
        if float(neighbors.min())<30.75:
            rejections["allwise_neighbor"]+=1;continue
        var,ph=str(ir.get("var_flg")or""),str(ir.get("ph_qual")or"")
        if not(len(var)>=2 and all(c in "01" for c in var[:2]) and len(ph)>=2 and all(c in "AB" for c in ph[:2])
               and str(ir.get("cc_flags")or"")[:2]=="00" and ir.get("ext_flg")==0
               and (ir.get("w1snr") or 0)>=10 and (ir.get("w2snr") or 0)>=10 and ir.get("w1mpro") is not None):
            rejections["allwise_quality"]+=1;continue
        selected.append({"gaia":row,"allwise":ir,"query_2025_8":{"ra":moved[index].ra.deg,"dec":moved[index].dec.deg},
                         "nearest_gaia_arcsec":float(distances.min()),"nearest_allwise_arcsec":float(neighbors.min()),
                         "allwise_match_arcsec":float(separation[irindex])})
    selected.sort(key=lambda item:(item["allwise"]["w1mpro"],int(item["gaia"]["source_id"])))
    return {"field":field,"catalog_eligible_count":len(selected),"locked_controls":selected[:20],"rejections":dict(rejections),
            "gaia_missing_neighbor_pm":sum(r.get("pmra") is None or r.get("pmdec") is None for r in gaia),
            "position_check":"Catalog lock at2025.8; per-exposure geometry and propagated neighbor checks repeated before flux",
            "preregistration_sha256":digest(PLAN.read_bytes())}


def catalogs(plan, selected_fields=None):
    results=[]
    for field in plan["fields"]:
        if selected_fields and field["id"] not in selected_fields:
            continue
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures={name:executor.submit(fetch_catalog,field,name) for name in ("gaia","allwise")}
                values={name:future.result() for name,future in futures.items()}
            lock=catalog_selection(field,values["gaia"][0],values["allwise"][0],plan)
            lock["sources"]={name:metadata for name,(_,metadata) in values.items()}
            path=ROOT/f"docs/evidence/phase4/phase4-science-online-{field['id']}-controls.json"
            if path.exists() and read_json(path)!=lock:
                raise ValueError("Frozen catalog lock changed")
            if not path.exists():write_json(path,lock)
            results.append({"field":field["id"],"status":"locked","count":len(lock["locked_controls"]),"catalog_eligible":lock["catalog_eligible_count"],"rejections":lock["rejections"],"path":path.relative_to(ROOT).as_posix(),"sha256":digest(path.read_bytes())})
        except Exception as exc:
            results.append({"field":field["id"],"status":"unavailable","error":str(exc)})
        print(json.dumps(results[-1]),flush=True)
    write_json(ROOT/"docs/evidence/phase4/phase4-science-online-catalog-results.json",{"created_at":now(),"fields":results,"scope":"Catalog screening only; no SPHEREx control flux extracted"})


def polygon_vertices(region):
    tokens=str(region).split()
    if tokens[:2]!=["POLYGON","ICRS"]:
        raise ValueError("Unsupported footprint; no fabricated geometry")
    values=np.asarray([float(x) for x in tokens[2:]]).reshape(-1,2)
    if np.allclose(values[0],values[-1]):values=values[:-1]
    if len(values)!=4:raise ValueError("Expected recorded four-corner detector footprint")
    return SkyCoord(values[:,0]*u.deg,values[:,1]*u.deg)


def inside_footprint(vertices, coordinates, margin_arcsec=31):
    xyz=vertices.cartesian.xyz.value.T
    edges=np.cross(xyz,np.roll(xyz,-1,axis=0))
    edges/=np.linalg.norm(edges,axis=1)[:,None]
    centroid=xyz.mean(axis=0)
    edges*=np.sign(edges@centroid)[:,None]
    return np.all(edges@coordinates.cartesian.xyz.value >= math.sin(math.radians(margin_arcsec/3600)),axis=0)


def rank_pairs(plan,field_id,reports):
    from services.irsa_client import _rows_from_votable,IrsaClient
    field=next(item for item in plan["fields"] if item["id"]==field_id)
    lock=read_json(ROOT/f"docs/evidence/phase4/phase4-science-online-{field_id}-controls.json")
    coords=SkyCoord([c["query_2025_8"]["ra"] for c in lock["locked_controls"]]*u.deg,
                    [c["query_2025_8"]["dec"] for c in lock["locked_controls"]]*u.deg)
    sources=[];records={}
    for report_path in reports:
        report=read_json(Path(report_path))
        requests=list(report["requests"])
        for entry in report.get("fields",[]):
            if entry["id"]!=field_id.replace("_","-"):continue
            for response in entry.get("discovery",{}).get("responses",[]):
                if response["http_status"]!=200 or response["parameters"].get("COLLECTION")not in ("spherex_dr1","spherex_qr3"):continue
                rawpath=ROOT/"backend/.cache/phase4/online-discovery"/report["run"]/entry["id"]/response["cache_relative_path"]
                requests.append({"id":"sia_"+response["parameters"]["COLLECTION"],"status":200,
                                 "votable_rows":len(_rows_from_votable(rawpath.read_bytes())),
                                 "response_path":rawpath.relative_to(ROOT).as_posix(),"sha256":response["sha256"],
                                 "endpoint":response["source_url"],"parameters":response["parameters"],"requested_at":response["retrieved_at"]})
        for request in requests:
            if request.get("status")!=200 or not request.get("votable_rows") or "sia" not in request["id"]:
                continue
            path=ROOT/request["response_path"];content=path.read_bytes()
            if digest(content)!=request["sha256"]:raise ValueError("Discovery response hash mismatch")
            sources.append({key:request[key] for key in ("id","endpoint","parameters","sha256","response_path","requested_at","votable_rows")})
            for row in _rows_from_votable(content):
                record=IrsaClient._record_from_sia2_row(row,request["parameters"]["COLLECTION"])
                if record is None or record.band not in (1,3):continue
                vertices=polygon_vertices(row["s_region"])
                contains=inside_footprint(vertices,coords)
                records[record.uri]={"artifact":asdict(record),"s_region":row["s_region"],
                                     "control_indices_inside":np.where(contains)[0].tolist()}
    cells=[]
    for detector in (1,3):
        candidates=[item for item in records.values() if item["artifact"]["band"]==detector and len(item["control_indices_inside"])>=3]
        ranked=[]
        for first,second in combinations(candidates,2):
            a,b=first["artifact"],second["artifact"]
            dt=abs(a["mjd_lower"]-b["mjd_lower"])
            common=sorted(set(first["control_indices_inside"])&set(second["control_indices_inside"]))
            if not(1<=dt<=400 and a["release"]==b["release"] and len(common)>=3):continue
            av,bv=polygon_vertices(first["s_region"]),polygon_vertices(second["s_region"])
            distance=float(np.mean(av.separation(bv).arcsec))
            earlier,later=sorted((a,b),key=lambda row:(row["mjd_lower"],row["uri"]))
            ranked.append({"first_uri":earlier["uri"],"second_uri":later["uri"],"corner_distance_arcsec":distance,
                           "time_separation_days":dt,"control_indices_inside":common})
        ranked.sort(key=lambda pair:(pair["corner_distance_arcsec"],pair["time_separation_days"],pair["first_uri"],pair["second_uri"]))
        chosen=set()
        for pair in ranked:
            needed={pair["first_uri"],pair["second_uri"]}-chosen
            if len(chosen)+len(needed)<=8:chosen|=needed
        restricted=[pair for pair in ranked if pair["first_uri"] in chosen and pair["second_uri"] in chosen]
        cells.append({"detector":detector,"available_footprint_qualified_records":len(candidates),"ranked_pair_count":len(ranked),
                      "candidate_records":[records[uri] for uri in sorted(chosen)],"pairs_in_order":restricted})
    result={"registered_at":now(),"field":field,"preregistration_sha256":digest(PLAN.read_bytes()),
            "catalog_lock_sha256":digest((ROOT/f"docs/evidence/phase4/phase4-science-online-{field_id}-controls.json").read_bytes()),
            "discovery_sources":sources,"discovery_scope":"Fresh available wide-fieldSIAresponses; no claim of fullarchive/deep completeness",
            "selection":"Metadata-only footprint ranking with >=3 locked controls in both frames plus31arcsec margin; no flux inspected",
            "cells":cells}
    path=ROOT/f"docs/evidence/phase4/phase4-science-online-{field_id}-pair-ranks.json"
    if path.exists():
        old=read_json(path)
        if {k:v for k,v in old.items() if k!="registered_at"}!={k:v for k,v in result.items() if k!="registered_at"}:
            raise ValueError("Frozen pair ranks changed")
    else:write_json(path,result)
    print(json.dumps({"field":field_id,"cells":[{"detector":c["detector"],"records":len(c["candidate_records"]),"pairs":len(c["pairs_in_order"]),"best":c["pairs_in_order"][:1]}for c in cells],"sha256":digest(path.read_bytes())}),flush=True)


def retained_download(url,path,limit=128*1024*1024,deadline_at=None):
    """Bounded real upstream bytes, with exact retrieval metadata retained."""
    metadata_path=path.with_suffix(path.suffix+".json")
    if path.exists() and metadata_path.exists():
        metadata=read_json(metadata_path)
        if digest(path.read_bytes())!=metadata["sha256"]:raise ValueError("Retained bytes changed")
        return metadata
    path.parent.mkdir(parents=True,exist_ok=True)
    started=time.monotonic();parts=[];size=0
    remaining=90 if deadline_at is None else deadline_at-time.monotonic()
    if remaining<=0:raise ValueError("Shared transfer deadline expired")
    with httpx.stream("GET",url,timeout=min(45,remaining),follow_redirects=True) as response:
        response.raise_for_status()
        for piece in response.iter_bytes():
            size+=len(piece)
            if size>limit or time.monotonic()-started>90 or (deadline_at is not None and time.monotonic()>deadline_at):raise ValueError("Bounded transfer exceeded")
            parts.append(piece)
    content=b"".join(parts)
    if not content.startswith(b"SIMPLE"):raise ValueError("Archive input is not FITS")
    metadata={"url":url,"path":path.relative_to(ROOT).as_posix(),"sha256":digest(content),"bytes":len(content),
              "retrieved_at":now(),"elapsed_seconds":time.monotonic()-started,"is_simulated_fallback":False}
    path.write_bytes(content);write_json(metadata_path,metadata)
    print(json.dumps({"downloaded":metadata["path"],"bytes":len(content),"seconds":metadata["elapsed_seconds"]}),flush=True)
    return metadata


def fetch_exposure(field,record):
    from services.irsa_client import ArtifactRecord
    artifact=ArtifactRecord(**record)
    # .45degree radial control region plus annulus margin, enclosed at arbitrary roll.
    url=artifact.cutout_url(field["ra"],field["dec"],1.4)
    path=CACHE/field["id"]/"fits"/(digest(url.encode())+".fits")
    attempts=[];deadline_at=time.monotonic()+90
    for attempt in range(3 if RETRY_FAILED else 1):
        try:
            result=retained_download(url,path,deadline_at=deadline_at)
            if attempts:
                result=dict(result,retry_failures=attempts)
            return result
        except (httpx.HTTPError,ValueError) as exc:
            attempts.append({"attempt":attempt+1,"time":now(),"error":str(exc)})
    raise ValueError("Exact-input bounded retries failed: "+json.dumps(attempts))


def cell_path(field_id,detector,kind):
    variant="-"+CELL_VARIANT if CELL_VARIANT else ""
    return ROOT/f"docs/evidence/phase4/phase4-science-online-{field_id}-D{detector}{variant}-{kind}.json"


def calibration_file(release,detector):
    release=release.lower()
    url=f"https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/{release}/spectral_wcs/cal-swcs-v5-2026-191/{detector}/spectral_wcs_D{detector}_spx_cal-swcs-v5-2026-191.fits"
    return retained_download(url,CACHE/"calibration"/f"{release}_spectral_D{detector}.fits",40_000_000)


def calibrated_control_signature(content,calibration,coord):
    from astropy.io import fits
    from astropy.wcs import WCS
    from scipy.ndimage import map_coordinates
    with fits.open(BytesIO(content),memmap=False) as hdul, fits.open(ROOT/calibration["path"],memmap=False) as cal:
        header=hdul["IMAGE"].header
        if header.get("DETCOORD")!="sky" or cal["CWAVE"].header.get("DETCOORD")!="sky":
            raise ValueError("Calibration orientation mismatch")
        if not all(np.array_equal(hdul["WCS-WAVE"].data[name],cal["WCS-WAVE"].data[name])for name in ("X","Y","VALUES")):
            raise ValueError("Unmatched spectral calibration version")
        # Fixed31arcsec-radius neighborhood includes aperture and background annulus.
        grid=WCS(naxis=2);grid.wcs.ctype=["RA---TAN","DEC--TAN"]
        grid.wcs.crval=[coord.ra.deg,coord.dec.deg];grid.wcs.crpix=[11,11];grid.wcs.cdelt=[-3.075/3600,3.075/3600]
        yy,xx=np.indices((21,21));sky=grid.pixel_to_world(xx.ravel(),yy.ravel())
        spatial=WCS(header);x,y=spatial.world_to_pixel(sky)
        ny,nx=hdul["IMAGE"].data.shape
        if np.any((x<0)|(y<0)|(x>nx-1)|(y>ny-1)):raise ValueError("Native footprint does not cover control neighborhood")
        xo,yo=1+x-header["CRPIX1A"],1+y-header["CRPIX2A"]
        values=np.asarray([map_coordinates(np.asarray(cal[name].data,float),[yo,xo],order=1,mode="constant",cval=np.nan)for name in ("CWAVE","CBAND")])
        return values


def prepare_pair(field_id,detector):
    """Lock the first calibrated pair using no aperture flux values."""
    from astropy.io import fits
    from astropy.wcs import WCS
    from services.live_selection import compatible
    from services.spherex_pipeline import parse_cutout
    ranks=read_json(ROOT/f"docs/evidence/phase4/phase4-science-online-{field_id}-pair-ranks.json")
    lock=read_json(ROOT/f"docs/evidence/phase4/phase4-science-online-{field_id}-controls.json")
    cell=next(cell for cell in ranks["cells"] if cell["detector"]==detector)
    records={item["artifact"]["uri"]:item["artifact"] for item in cell["candidate_records"]}
    downloaded={};attempts=[];download_failures={}
    for pair in cell["pairs_in_order"]:
        result={"pair":pair,"status":"rejected_before_flux"};attempts.append(result)
        try:
            needed=[uri for uri in (pair["first_uri"],pair["second_uri"]) if uri not in downloaded]
            exhausted=[uri for uri in needed if uri in download_failures]
            if exhausted:raise ValueError("Previously exhausted exact-input transfer budget: "+json.dumps({uri:download_failures[uri]for uri in exhausted}))
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures={uri:executor.submit(fetch_exposure,ranks["field"],records[uri]) for uri in needed}
                for uri,future in futures.items():
                    try:downloaded[uri]=future.result()
                    except Exception as exc:
                        download_failures[uri]=str(exc)
                        raise
            inputs=[downloaded[pair[key]] for key in ("first_uri","second_uri")]
            calibration=calibration_file(records[pair["first_uri"]]["release"],detector)
            contents=[(ROOT/item["path"]).read_bytes() for item in inputs]
            headers=[]
            for content in contents:
                with fits.open(BytesIO(content),memmap=False)as hdul:headers.append(hdul["IMAGE"].header.copy())
            passing=[];failures=[]
            for index in pair["control_indices_inside"]:
                control=lock["locked_controls"][index]
                try:
                    positions=[position(control["gaia"],Time(header["MJD-AVG"],format="mjd",scale=header.get("TIMESYS","UTC").lower()))for header in headers]
                    # Match at the SAME sky coordinates: mean-time source position is
                    # sufficient for<=100mas/yr controls, but evaluate both visit centers.
                    checks=[]
                    for center in positions:
                        signatures=[calibrated_control_signature(content,calibration,center)for content in contents]
                        checks.append(compatible(*signatures))
                    if all(checks):passing.append(index)
                    else:failures.append({"index":index,"reason":"calibrated_wavelength_mismatch"})
                except Exception as exc:failures.append({"index":index,"reason":str(exc)})
            result.update(calibration=calibration,inputs=inputs,calibrated_control_indices=passing,control_rejections=failures)
            if len(passing)<3:
                result["reason"]="Fewer than3 lockedcontrols pass calibrated neighborhood matching"
                continue
            times=[Time(h["MJD-AVG"],format="mjd",scale=h.get("TIMESYS","UTC").lower())for h in headers]
            isolation=observation_isolation(field_id,lock,times)
            images=[parse_cutout(content,ranks["field"]["ra"],ranks["field"]["dec"])for content in contents]
            supporting=[]
            for index in passing:
                support=[]
                for image,header,epoch in zip(images,headers,times):
                    x,y=WCS(header).world_to_pixel(position(lock["locked_controls"][index]["gaia"],epoch))
                    support.append(preflight_support(image,float(x),float(y))["passed"])
                if all(support)and all(row["passed"]for row in isolation[index]):supporting.append(index)
            result["support_qualified_control_indices"]=supporting
            if len(supporting)<3:
                result["reason"]="Fewer than3 lockedcontrols pass fixed aperture/background/isolation prerequisites"
                continue
            gaia=table_rows((CACHE/field_id/"gaia.xml").read_bytes())
            astrometry=[region_astrometry(content,gaia,ranks["field"])["summary"]for content in contents]
            result["independent_astrometry_prerequisite"]=astrometry
            if not all(row["status"]=="pass"for row in astrometry):
                result["reason"]="Independent astrometry prerequisite failed"
                continue
            result["status"]="calibrated_candidate_locked_before_flux"
            result["positions"]=[{"mjd":h["MJD-AVG"],"scale":h.get("TIMESYS","UTC")}for h in headers]
            break
        except Exception as exc:
            result["error"]={"type":type(exc).__name__,"message":str(exc)}
        print(json.dumps({"field":field_id,"detector":detector,"pair_status":result["status"],"error":result.get("error"),"calibrated_controls":len(result.get("calibrated_control_indices",[]))}),flush=True)
    output={"created_at":now(),"field":ranks["field"],"detector":detector,
            "pair_ranks_sha256":digest((ROOT/f"docs/evidence/phase4/phase4-science-online-{field_id}-pair-ranks.json").read_bytes()),
            "attempts":attempts,"selected":next((item for item in attempts if item["status"]=="calibrated_candidate_locked_before_flux"),None),
            "flux_extracted":False,"scope":"Calibrated geometry first; astrometry/support prerequisites will be assessed without flux residual-based selection"}
    path=cell_path(field_id,detector,"pair-lock")
    if path.exists():raise ValueError("Pair lock exists; never rerank after flux")
    write_json(path,output)
    print(json.dumps({"field":field_id,"detector":detector,"selected":output["selected"] is not None,"attempts":len(attempts)}),flush=True)


def aperture_weights(shape,x,y,radius,method):
    from photutils.aperture import CircularAperture
    if method not in ("center","subpixel","exact"):raise ValueError("Unknown aperture method")
    if method=="center":
        yy,xx=np.indices(shape)
        return (np.hypot(xx-x,yy-y)<=radius).astype(float)
    ap=CircularAperture((float(x),float(y)),r=float(radius))
    return ap.to_mask(method="exact" if method=="exact" else "subpixel",subpixels=5).to_image(shape)


def preflight_support(parsed,x,y):
    from core import flags as policy
    shape=parsed.flags.shape
    if min(x,y,shape[1]-1-x,shape[0]-1-y)<5.5:return {"passed":False,"reason":"edge"}
    good=np.isfinite(parsed.image_mjy_sr)&np.isfinite(parsed.variance_mjy_sr2)&(parsed.variance_mjy_sr2>0)&((parsed.flags&policy.PHOTOMETRY_EXCLUDE_MASK)==0)
    yy,xx=np.indices(shape);distance=np.hypot(xx-x,yy-y)
    annulus=(distance>=3)&(distance<=5)&good&((parsed.flags&policy.BIT_SOURCE)==0)
    complete={method:bool(np.all(good[aperture_weights(shape,x,y,12.3/parsed.native_pixel_scale_arcsec,method)>0]))for method in ("center","subpixel","exact")}
    background=bool((parsed.background_metadata or {}).get("subtracted",False))
    return {"passed":all(complete.values()) and int(annulus.sum())>=10 and background,
            "complete_aperture":complete,"clean_annulus_pixels":int(annulus.sum()),"field_background_supported":background,
            "background_method":(parsed.background_metadata or {}).get("method")}


def region_astrometry(content,rows,field):
    from astropy.io import fits
    from astropy.wcs import WCS
    from astropy.wcs.utils import proj_plane_pixel_scales
    from phase3_astrometry import detect,propagate,summary
    from core import flags as policy
    from collections import Counter
    with fits.open(BytesIO(content),memmap=False)as hdul:
        header=hdul["IMAGE"].header.copy()
        image=np.asarray(hdul["IMAGE"].data,float)-np.asarray(hdul["ZODI"].data,float)
        variance=np.asarray(hdul["VARIANCE"].data,float);flags=np.asarray(hdul["FLAGS"].data,np.uint32)
    spatial=WCS(header);scale=float(np.mean(proj_plane_pixel_scales(spatial))*3600)
    peaks=detect(image,variance,(flags&policy.PHOTOMETRY_EXCLUDE_MASK)!=0,scale)
    moved,valid,missing=propagate(rows,header["MJD-AVG"],header.get("TIMESYS","UTC").lower())
    matches=[];rejected=Counter();center=SkyCoord(field["ra"],field["dec"],unit="deg")
    if peaks:
        sky=spatial.pixel_to_world([p["x"]for p in peaks],[p["y"]for p in peaks])
        nearest,distance,_=sky.match_to_catalog_sky(moved)
        associations=Counter(int(i) for i,d in zip(nearest,distance)if d.arcsec<=12.3)
        for peak,index,sep,coord in zip(peaks,nearest,distance,sky):
            row=valid[int(index)]
            if sep.arcsec>12.3 or associations[int(index)]!=1:rejected["association"]+=1;continue
            if moved[int(index)].separation(center).deg>.45:rejected["outside_region"]+=1;continue
            if any(row.get(k)is None for k in ("ruwe","parallax","phot_g_mean_mag"))or row["ruwe"]>1.4 or abs(row["parallax"])>10 or row["phot_g_mean_mag"]>17:
                rejected["quality"]+=1;continue
            if np.count_nonzero(moved[int(index)].separation(moved).arcsec<30.75)>1:rejected["neighbor"]+=1;continue
            unknown=[r for r in rows if r.get("pmra")is None or r.get("pmdec")is None]
            if unknown:
                unknowncoords=SkyCoord([r["ra"]for r in unknown]*u.deg,[r["dec"]for r in unknown]*u.deg)
                if np.any(moved[int(index)].separation(unknowncoords).arcsec<30.75):rejected["unknown_motion_neighbor"]+=1;continue
            dra,ddec=moved[int(index)].spherical_offsets_to(coord)
            matches.append({"source_id":row["source_id"],"native_dra_cosdec_arcsec":float(dra.arcsec),"native_ddec_arcsec":float(ddec.arcsec),"fit":peak})
    return {"summary":summary(matches,"native"),"matches":matches,"rejections":dict(rejected),"missing_neighbor_pm":missing,
            "scope":"Independent native image peaks vs propagatedGaia; no residual clipping; region.45degree; unresolvedIRblends notexcluded by astrometry"}


def preflight(field_id,detector):
    from astropy.io import fits
    from astropy.wcs import WCS
    from services.spherex_pipeline import parse_cutout
    pairpath=cell_path(field_id,detector,"pair-lock")
    pair=read_json(pairpath);selected=pair["selected"]
    if selected is None:raise ValueError("No calibrated candidate pair")
    controls=read_json(ROOT/f"docs/evidence/phase4/phase4-science-online-{field_id}-controls.json")
    gaia=table_rows((CACHE/field_id/"gaia.xml").read_bytes())
    contents=[(ROOT/item["path"]).read_bytes()for item in selected["inputs"]]
    parsed=[];wcs=[];times=[];astrometry=[]
    for content in contents:
        parsed.append(parse_cutout(content,pair["field"]["ra"],pair["field"]["dec"]))
        with fits.open(BytesIO(content),memmap=False)as hdul:
            header=hdul["IMAGE"].header;wcs.append(WCS(header));times.append(Time(header["MJD-AVG"],format="mjd",scale=header.get("TIMESYS","UTC").lower()))
        astrometry.append(region_astrometry(content,gaia,pair["field"]))
    isolation=observation_isolation(field_id,controls,times)
    rows=[]
    for index in selected["calibrated_control_indices"]:
        control=controls["locked_controls"][index];support=[];positions=[]
        for image,spatial,epoch in zip(parsed,wcs,times):
            coord=position(control["gaia"],epoch);x,y=spatial.world_to_pixel(coord)
            positions.append({"ra":coord.ra.deg,"dec":coord.dec.deg,"x":float(x),"y":float(y),"mjd":float(epoch.mjd),"time_scale":epoch.scale})
            support.append(preflight_support(image,float(x),float(y)))
        rows.append({"control_index":index,"source_id":control["gaia"]["source_id"],"positions":positions,"support":support,
                     "isolation":isolation[index],
                     "support_passed":all(item["passed"]for item in support)and all(item["passed"]for item in isolation[index])})
    result={"locked_at":now(),"field":field_id,"detector":detector,"pair_lock_sha256":digest(pairpath.read_bytes()),
            "amendment_sha256":digest((ROOT/"docs/evidence/phase4/phase4-science-online-amendment-exact.json").read_bytes()),
            "astrometry":astrometry,"controls":rows,"support_passing_controls":sum(row["support_passed"]for row in rows),
            "all_prerequisites_passed":all(item["summary"]["status"]=="pass"for item in astrometry)and sum(row["support_passed"]for row in rows)>=3,
            "flux_extracted":False,"selection":"Locked before aperture sums or intervisitresiduals; SNR gate is assessed later with no replacement"}
    path=cell_path(field_id,detector,"preflight")
    if path.exists():raise ValueError("Preflight already frozen")
    write_json(path,result)
    print(json.dumps({"field":field_id,"detector":detector,"support_count":result["support_passing_controls"],"astrometry":[a["summary"]for a in astrometry],"ready":result["all_prerequisites_passed"]}),flush=True)


def observation_isolation(field_id,controls,times):
    """Repeat fixed neighbor cut at actual exposure times, without loading flux."""
    gaia=table_rows((CACHE/field_id/"gaia.xml").read_bytes())
    infrared=table_rows((CACHE/field_id/"allwise.xml").read_bytes())
    ids=np.asarray([str(row["source_id"])for row in gaia])
    irids=np.asarray([str(row["designation"])for row in infrared])
    ircoords=SkyCoord([r["ra"]for r in infrared]*u.deg,[r["dec"]for r in infrared]*u.deg)
    output=[[]for _ in controls["locked_controls"]]
    for epoch in times:
        moved=[position(row,epoch)for row in gaia]
        neighbors=SkyCoord([c.ra.deg for c in moved]*u.deg,[c.dec.deg for c in moved]*u.deg)
        for index,control in enumerate(controls["locked_controls"]):
            coord=position(control["gaia"],epoch)
            gd=coord.separation(neighbors).arcsec;gd[ids==str(control["gaia"]["source_id"])]=np.inf
            ir=coord.separation(ircoords).arcsec;ir[irids==str(control["allwise"]["designation"])]=np.inf
            output[index].append({"mjd":float(epoch.mjd),"time_scale":epoch.scale,
                                  "nearest_gaia_arcsec":float(gd.min()),"nearest_allwise_arcsec":float(ir.min()),
                                  "passed":bool(gd.min()>=30.75 and ir.min()>=30.75),
                                  "limits":"Gaia missing PM retained at reference position; AllWISE has no PM in this query, so neighbors use catalog positions; unresolved/faint blends remain possible"})
    return output


def isolation_audit(field_id,detector):
    """Supplement earlier preflight without replacing measured results or sources."""
    pairpath=cell_path(field_id,detector,"pair-lock");pair=read_json(pairpath)
    controls=read_json(ROOT/f"docs/evidence/phase4/phase4-science-online-{field_id}-controls.json")
    times=[Time(row["mjd"],format="mjd",scale=row["scale"].lower())for row in pair["selected"]["positions"]]
    rows=observation_isolation(field_id,controls,times)
    result={"audited_at":now(),"field":field_id,"detector":detector,
            "pair_lock_sha256":digest(pairpath.read_bytes()),"all_locked_controls_pass":all(v["passed"]for row in rows for v in row),
            "controls":[{"source_id":c["gaia"]["source_id"],"visits":row}for c,row in zip(controls["locked_controls"],rows)],
            "timing":"Supplement after first D3 measurements discovered omitted per-exposure repeat of catalog isolation; unchanged threshold, no control deletion or replacement"}
    out=cell_path(field_id,detector,"isolation-audit")
    if out.exists():raise ValueError("Audit exists")
    write_json(out,result)
    print(json.dumps({"field":field_id,"detector":detector,"all_locked_controls_pass":result["all_locked_controls_pass"]}),flush=True)


def sapm_file(release,detector):
    release=release.lower()
    url=f"https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/{release}/solid_angle_pixel_map/cal-sapm-v3-2026-191/{detector}/solid_angle_pixel_map_D{detector}_spx_cal-sapm-v3-2026-191.fits"
    return retained_download(url,CACHE/"calibration"/f"{release}_sapm_D{detector}.fits",40_000_000)


def pixel_conversion(content,sapm):
    from astropy.io import fits
    with fits.open(BytesIO(content),memmap=False)as hdul,fits.open(ROOT/sapm["path"],memmap=False)as cal:
        header=hdul["IMAGE"].header;ch=cal["IMAGE"].header
        if str(ch.get("DETECTOR"))!=str(header.get("DETECTOR")) or ch.get("DETCOORD")!=header.get("DETCOORD") or ch.get("BUNIT")!="arcsec2":
            raise ValueError("SAPM detector/orientation/units mismatch")
        yy,xx=np.indices(hdul["IMAGE"].data.shape)
        ox,oy=1+xx-header["CRPIX1A"],1+yy-header["CRPIX2A"]
        if np.any(ox!=np.rint(ox))or np.any(oy!=np.rint(oy)):raise ValueError("Noninteger original detector pixel mapping")
        array=np.asarray(cal["IMAGE"].data,float)
        if ox.min()<0 or oy.min()<0 or ox.max()>=array.shape[1] or oy.max()>=array.shape[0]:raise ValueError("SAPM footprint mismatch")
        return array[oy.astype(int),ox.astype(int)]*(np.pi/(180*3600))**2*1e12


def weighted_measurement(parsed,x,y,method,conversion):
    from core import flags as policy
    image,variance,flags=parsed.image_mjy_sr,parsed.variance_mjy_sr2,parsed.flags
    weights=aperture_weights(image.shape,x,y,12.3/parsed.native_pixel_scale_arcsec,method)
    good=np.isfinite(image)&np.isfinite(variance)&(variance>0)&((flags&policy.PHOTOMETRY_EXCLUDE_MASK)==0)
    yy,xx=np.indices(image.shape);distance=np.hypot(xx-x,yy-y)
    annulus=(distance>=3)&(distance<=5)&good&((flags&policy.BIT_SOURCE)==0)
    support=weights>0
    if int(annulus.sum())<10 or not np.all(good[support])or not(parsed.background_metadata or{}).get("subtracted",False):
        return {"flux_ujy":None,"error_ujy":None,"reason":"unsupported_measurement","annulus_pixels":int(annulus.sum())}
    b=float(np.median(image[annulus]));scatter=1.4826*float(np.median(np.abs(image[annulus]-b)))
    varb=max((np.pi/2)*float(np.mean(variance[annulus]))/int(annulus.sum()),1.2533**2*scatter**2/int(annulus.sum()))
    k=np.broadcast_to(conversion,image.shape)[support];w=weights[support]
    flux=float(np.sum(w*k*(image[support]-b)))
    error=float(np.sqrt(np.sum(w*w*k*k*variance[support])+np.sum(w*k)**2*varb))
    return {"flux_ujy":flux,"error_ujy":error,"snr":flux/error,"weighted_area_pixels":float(weights.sum()),
            "annulus_pixels":int(annulus.sum()),"annulus_background_mjy_sr":b,"background_variance_mjy_sr2":varb,
            "pixel_conversion_min_max_ujy_per_mjy_sr":[float(k.min()),float(k.max())],"method":method}


def epsf_diagnostic(content,parsed,x,y,conversion):
    from astropy.io import fits
    from photutils.psf import ImagePSF
    from core import flags as policy
    with fits.open(BytesIO(content),memmap=False)as hdul:
        header=hdul["IMAGE"].header;table=hdul["EPSF"].data;eh=hdul["EPSF"].header
        if eh.get("DETCOORD")!=header.get("DETCOORD"):raise ValueError("EPSF orientation mismatch")
        ox,oy=1+x-header["CRPIX1A"],1+y-header["CRPIX2A"]
        zones=np.where((np.abs(table["XCENTER"]-ox)<=table["XWIDTH"]/2)&(np.abs(table["YCENTER"]-oy)<=table["YWIDTH"]/2))[0]
        if not len(zones):raise ValueError("No EPSF detector zone")
        zone=int(zones[0]);stamp=np.asarray(table["EPSF"][zone],float)
        model=ImagePSF(data=stamp,oversampling=(int(eh["OVSMPY"]),int(eh["OVSMPX"])))
    left,bottom=int(np.floor(x-5)),int(np.floor(y-5))
    yy,xx=np.mgrid[bottom:bottom+11,left:left+11]
    template=np.asarray(model.evaluate(xx,yy,flux=1,x_0=x,y_0=y),float)
    template/=template.sum()  # Official native-grid template convention, not a flux rescaling from controls.
    image=parsed.image_mjy_sr[bottom:bottom+11,left:left+11];variance=parsed.variance_mjy_sr2[bottom:bottom+11,left:left+11]
    flags=parsed.flags[bottom:bottom+11,left:left+11];k=np.asarray(conversion)[bottom:bottom+11,left:left+11]
    good=np.isfinite(image)&np.isfinite(variance)&(variance>0)&((flags&policy.PHOTOMETRY_EXCLUDE_MASK)==0)
    if good.sum()<25:return {"status":"insufficient_PSF_pixels"}
    design=np.column_stack([template[good],k[good]])
    values=image[good]*k[good];errors=np.sqrt(variance[good])*k[good]
    normal=(design/errors[:,None]).T@(design/errors[:,None])
    covariance=np.linalg.inv(normal)
    coefficients=covariance@((design/errors[:,None]).T@(values/errors))
    residual=(values-design@coefficients)/errors
    response={method:float(np.sum(template*aperture_weights(template.shape,x-left,y-bottom,12.3/parsed.native_pixel_scale_arcsec,method)))for method in ("center","subpixel","exact")}
    return {"status":"diagnostic_only","zone_index":zone,"native_stamp_size":11,"template_sum":float(template.sum()),
            "aperture_response_fraction":response,"psf_amplitude_ujy":float(coefficients[0]),"approx_error_ujy":float(np.sqrt(covariance[0,0])),
            "residual_background_mjy_sr":float(coefficients[1]),"reduced_chi2":float(np.sum(residual**2)/max(1,good.sum()-2)),
            "source_position_fixed":True,"limits":"Local amplitude+constant background, no neighbor fit, finite ePSF stamp renormalized; no absolute totalflux or officialTractor equivalence claimed"}


def residual_summary(rows,method,area):
    z=[(row["visits"][1][area][method]["flux_ujy"]-row["visits"][0][area][method]["flux_ujy"])/math.hypot(row["visits"][0][area][method]["error_ujy"],row["visits"][1][area][method]["error_ujy"])for row in rows]
    if len(z)<3:return {"status":"insufficient","count":len(z),"z":z}
    median=float(np.median(z));scatter=float(1.4826*np.median(np.abs(np.asarray(z)-median)));maximum=max(map(abs,z))
    return {"status":"pass"if abs(median)<=1 and scatter<=2 and maximum<=5 else"failed","count":len(z),
            "median_z":median,"robust_scatter_z":scatter,"max_abs_z":maximum,"z":z}


def measure_locked(field_id,detector):
    from services.spherex_pipeline import parse_cutout
    path=cell_path(field_id,detector,"preflight")
    pre=read_json(path)
    if not pre["all_prerequisites_passed"]:raise ValueError("Preflight prerequisite gate not passed; no acceptance flux extraction")
    pair=read_json(cell_path(field_id,detector,"pair-lock"))
    selected=pair["selected"];release="QR3"if"/qr3/"in selected["pair"]["first_uri"]else"DR1"
    sapm=sapm_file(release,detector)
    contents=[(ROOT/item["path"]).read_bytes()for item in selected["inputs"]]
    for content,item in zip(contents,selected["inputs"]):
        if digest(content)!=item["sha256"]:raise ValueError("Input bytes changed")
    images=[parse_cutout(content,pair["field"]["ra"],pair["field"]["dec"])for content in contents]
    factors=[pixel_conversion(content,sapm)for content in contents]
    controls=[]
    for row in pre["controls"]:
        if not row["support_passed"]:continue
        result={"source_id":row["source_id"],"positions":row["positions"],"visits":[]}
        for content,image,conv,pos in zip(contents,images,factors,row["positions"]):
            visit={"sapm":{},"constant_wcs":{}}
            for method in ("center","subpixel","exact"):
                visit["sapm"][method]=weighted_measurement(image,pos["x"],pos["y"],method,conv)
                local=1e12*(image.native_pixel_scale_arcsec*np.pi/(180*3600))**2
                visit["constant_wcs"][method]=weighted_measurement(image,pos["x"],pos["y"],method,local)
            try:visit["epsf_diagnostic"]=epsf_diagnostic(content,image,pos["x"],pos["y"],conv)
            except Exception as exc:visit["epsf_diagnostic"]={"status":"unavailable","error":str(exc)}
            exact,sub=visit["sapm"]["exact"],visit["sapm"]["subpixel"]
            visit["subpixel_minus_exact_sigma"]=(sub["flux_ujy"]-exact["flux_ujy"])/exact["error_ujy"]
            result["visits"].append(visit)
        result["snr_eligible"]=all(value.get("snr",0)>=5 for visit in result["visits"]for value in visit["sapm"].values())
        controls.append(result)
    eligible=[row for row in controls if row["snr_eligible"]]
    summaries={area:{method:residual_summary(eligible,method,area)for method in ("center","subpixel","exact")}for area in ("sapm","constant_wcs")}
    result={"measured_at":now(),"field":field_id,"detector":detector,"primary_method":"exact_SAPM",
            "preflight_sha256":digest(path.read_bytes()),"amendment_sha256":digest((ROOT/"docs/evidence/phase4/phase4-science-online-amendment-exact.json").read_bytes()),
            "sapm":sapm,"controls":controls,"summaries":summaries,"status":summaries["sapm"]["exact"]["status"],
            "scope":"Independent scoped repeatability; no totalflux calibration, globalerror fitting or allskyclaim; bothconstantWCS andSAPM reported distinctly"}
    out=cell_path(field_id,detector,"measurements")
    if out.exists():raise ValueError("Measured result exists; preserve it instead of overwriting")
    write_json(out,result)
    print(json.dumps({"field":field_id,"detector":detector,"primary":result["status"],"summaries":summaries}),flush=True)


def historical_diagnostic():
    """Explanatory reanalysis only; never overwrites the Phase 3 failed gate."""
    from services.spherex_pipeline import parse_cutout
    source=ROOT/"docs/evidence/phase3/phase3-science-results.json";old=read_json(source)
    controls=next(row for row in old["static_controls"]if row["target_id"]=="eps_indi_b")["controls"]
    samples=[s for s in old["samples"]if s["target_id"]=="eps_indi_b"and s["band"]==3]
    contents=[(ROOT/s["path"]).read_bytes()for s in samples]
    for data,sample in zip(contents,samples):
        if digest(data)!=sample["sha256"]:raise ValueError("Historical input changed")
    sapm=sapm_file("DR1",3)
    images=[parse_cutout(data,s["ra"],s["dec"])for data,s in zip(contents,samples)]
    factors=[pixel_conversion(data,sapm)for data in contents]
    output=[]
    for control in controls:
        row={"source_id":control["gaia_source_id"],"original_z":control["standardized_residual"],"visits":[]}
        for data,image,factor,diagnostic in zip(contents,images,factors,control["exploratory_diagnostics"]):
            x,y=diagnostic["center_x"],diagnostic["center_y"]
            visit={"x":x,"y":y,"sapm":{method:weighted_measurement(image,x,y,method,factor)for method in ("center","subpixel","exact")}}
            try:visit["epsf"]=epsf_diagnostic(data,image,x,y,factor)
            except Exception as exc:visit["epsf"]={"status":"unavailable","error":str(exc)}
            row["visits"].append(visit)
        output.append(row)
    result={"created_at":now(),"scope":"Posthoc explanatory diagnostic on original ten controls, not independent acceptance; original positions retained; no new control exclusions/thresholds",
            "original_report_sha256":digest(source.read_bytes()),"inputs":[{k:s[k]for k in ("path","sha256","uri")}for s in samples],
            "sapm":sapm,"controls":output,"original_gate":"Failed and unchanged"}
    path=ROOT/"docs/evidence/phase4/phase4-science-online-historical-diagnostic.json"
    if path.exists():raise ValueError("Historical diagnostic exists")
    write_json(path,result)
    print(json.dumps({"diagnostic_controls":len(output),"path":str(path.relative_to(ROOT))}),flush=True)


def aggregate_results():
    cells=[];valid=[];references=[]
    for field,_,_ in FIELDS:
        for detector in (1,3):
            base=ROOT/f"docs/evidence/phase4/phase4-science-online-{field}-D{detector}"
            retry=Path(str(base)+"-retry-pair-lock.json")
            prefix=str(base)+("-retry"if retry.exists()else"")
            pairpath=Path(prefix+"-pair-lock.json");measurepath=Path(prefix+"-measurements.json")
            cell={"field":field,"detector":detector,"status":"pending"}
            if pairpath.exists():
                pair=read_json(pairpath);references.append(pairpath)
                cell["pair_lock"]=pairpath.relative_to(ROOT).as_posix()
                cell["pair_attempts"]=len(pair["attempts"])
                if pair["selected"]is None:
                    cell["status"]="no_qualified_pair_within_frozen_bounds"
                    from collections import Counter
                    cell["rejections"]=dict(Counter(a.get("reason","transport_or_processing_error")for a in pair["attempts"]))
            if measurepath.exists():
                data=read_json(measurepath);references.append(measurepath)
                cell.update(status=data["status"],primary=data["summaries"]["sapm"]["exact"],
                            summaries=data["summaries"],measurement=measurepath.relative_to(ROOT).as_posix())
                cell["subpixel_exact_max_abs_sigma"]=max(abs(v["subpixel_minus_exact_sigma"])for c in data["controls"]for v in c["visits"])
                cell["subpixel_exact_above_point1_sigma"]=sum(abs(v["subpixel_minus_exact_sigma"])>.1 for c in data["controls"]for v in c["visits"])
                cell["eligible_source_ids"]=[c["source_id"]for c in data["controls"]if c["snr_eligible"]]
                if data["status"]in("pass","failed"):valid.append(cell)
            cells.append(cell)
    complete=all(c["status"]!="pending"for c in cells)
    enough=len({c["field"]for c in valid})>=2 and len({c["detector"]for c in valid})>=2
    status="pending"if not complete else("failed"if any(c["status"]=="failed"for c in valid)else("pass"if enough else"insufficient"))
    result={"created_at":now(),"status":status,"all_eight_cells_attempted":complete,"primary_method":"exact_SAPM",
            "preregistration_sha256":digest(PLAN.read_bytes()),"amendment_sha256":digest((ROOT/"docs/evidence/phase4/phase4-science-online-amendment-exact.json").read_bytes()),
            "cells":cells,"valid_cells":len(valid),"passing_cells":sum(c["status"]=="pass"for c in valid),
            "eligible_source_detector_comparisons":sum(c["primary"]["count"]for c in valid),
            "unique_eligible_gaia_sources":len({s for c in valid for s in c["eligible_source_ids"]}),
            "references":[{"path":p.relative_to(ROOT).as_posix(),"sha256":digest(p.read_bytes())}for p in references],
            "scope":"Scoped repeatability only: isolated full-support clean-annulus controls, D1/D3, recorded calibration/release/input pairs. Not all-sky or crowded/saturated certification; no totalflux or significance claim.",
            "source_code_sha256":digest(Path(__file__).read_bytes())}
    import platform
    import importlib.metadata
    result["software"]={"python":platform.python_version(),**{name:importlib.metadata.version(name)for name in("numpy","astropy","photutils","scipy","reproject")}}
    result["secondary_existing_production_method"]={
        "method":"center_pixel_constant_WCS", "role":"Predeclared baseline, separate secondary result; cannot redefine failed primary study",
        "population":"Same full-support/annulus/SAPM-SNR-qualified controls as primary; no method-specific reselection",
        "status":"pending"if not complete else("failed"if any(c["summaries"]["constant_wcs"]["center"]["status"]=="failed"for c in valid)else("pass"if enough else"insufficient")),
        "passing_cells":sum(c["summaries"]["constant_wcs"]["center"]["status"]=="pass"for c in valid),"valid_cells":len(valid)}
    out=ROOT/"docs/evidence/phase4/phase4-science-online-results.json"
    if out.exists()and read_json(out)["status"]!="pending":raise ValueError("Final aggregate frozen")
    write_json(out,result)
    print(json.dumps({k:result[k]for k in("status","valid_cells","passing_cells","eligible_source_detector_comparisons","unique_eligible_gaia_sources")}),flush=True)


def historical_eligibility():
    """Describe stronger eligibility on original ten; no reclassification of old gate."""
    from core import flags as policy
    original=read_json(ROOT/"docs/evidence/phase3/phase3-science-results.json")
    old=next(r for r in original["static_controls"]if r["target_id"]=="eps_indi_b")["controls"]
    diagnostic=read_json(ROOT/"docs/evidence/phase4/phase4-science-online-historical-diagnostic.json")
    rows=[]
    for control,measured in zip(old,diagnostic["controls"]):
        visits=[]
        for previous,current in zip(control["exploratory_diagnostics"],measured["visits"]):
            reference=previous["reference"];reasons=[]
            if reference["clean_pixels"]!=reference["aperture_pixels"]:reasons.append("incomplete_center_aperture_support")
            if current["sapm"]["center"]["annulus_pixels"]<10:reasons.append("fewer_than10_clean_annulus_pixels")
            if previous["flags_at_extraction_center"]&policy.HARD_BAD_MASK:reasons.append("hard_bad_center")
            eligible=current["sapm"]["center"]["flux_ujy"]is not None and not reasons
            if not eligible and not reasons:reasons.append("unsupported_background_or_nonfinite_measurement")
            visits.append({"eligible":eligible,"reasons":reasons,"clean_center_aperture_pixels":reference["clean_pixels"],
                           "center_aperture_pixels":reference["aperture_pixels"],"clean_annulus_pixels":current["sapm"]["center"]["annulus_pixels"]})
        rows.append({"source_id":control["gaia_source_id"],"original_z":control["standardized_residual"],
                     "both_visits_eligible":all(v["eligible"]for v in visits),"visits":visits})
    result={"created_at":now(),"scope":"Posthoc eligibility explanation only; original ten-control failed result unchanged, no recalculated passing subset claimed",
            "controls":rows,"eligible_in_both_visits":sum(r["both_visits_eligible"]for r in rows),
            "ineligible_in_at_least_one_visit":sum(not r["both_visits_eligible"]for r in rows),
            "criterion":"Centerpixel full usable support,>=10cleanlocalannulus pixels,supportedfieldbackground,nonhardcenter; catalogisolation is separate and not implied"}
    path=ROOT/"docs/evidence/phase4/phase4-science-online-historical-eligibility.json"
    if path.exists():raise ValueError("Historical eligibility record exists")
    write_json(path,result)
    print(json.dumps({k:result[k]for k in("eligible_in_both_visits","ineligible_in_at_least_one_visit")}),flush=True)


def main():
    global CELL_VARIANT, RETRY_FAILED
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register",action="store_true")
    parser.add_argument("--catalogs",action="store_true")
    parser.add_argument("--fields",nargs="*")
    parser.add_argument("--rank",metavar="FIELD")
    parser.add_argument("--discovery-reports",nargs="*")
    parser.add_argument("--prepare",metavar="FIELD")
    parser.add_argument("--detector",type=int,choices=(1,3))
    parser.add_argument("--preflight",metavar="FIELD")
    parser.add_argument("--measure",metavar="FIELD")
    parser.add_argument("--audit-isolation",metavar="FIELD")
    parser.add_argument("--historical-diagnostic",action="store_true")
    parser.add_argument("--summarize",action="store_true")
    parser.add_argument("--historical-eligibility",action="store_true")
    parser.add_argument("--retry-failed",action="store_true",help="Approved transport-only retry; same frozen ranks and inputs, before flux in that cell")
    parser.add_argument("--variant",default="",choices=("","retry"))
    args=parser.parse_args()
    CELL_VARIANT=args.variant;RETRY_FAILED=args.retry_failed
    if args.register:register()
    if not PLAN.exists():parser.error("Register before querying catalogs")
    if args.catalogs:catalogs(read_json(PLAN),args.fields)
    if args.rank:rank_pairs(read_json(PLAN),args.rank,args.discovery_reports or [])
    if args.prepare:prepare_pair(args.prepare,args.detector)
    if args.preflight:preflight(args.preflight,args.detector)
    if args.measure:measure_locked(args.measure,args.detector)
    if args.audit_isolation:isolation_audit(args.audit_isolation,args.detector)
    if args.historical_diagnostic:historical_diagnostic()
    if args.summarize:aggregate_results()
    if args.historical_eligibility:historical_eligibility()


if __name__=="__main__":main()
