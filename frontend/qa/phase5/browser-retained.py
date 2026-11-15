"""Serialize retained real Phase4 products for isolated browser playback, with no network.

This does not populate application caches or claim a fresh archive request.
"""
from pathlib import Path
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"backend"))
from models import SkyQuery,SpectrumQuery,Confidence
from routers.sky import _build_response
from routers.spectrum import _build_spectrum_response

out=ROOT/"backend/.cache/phase5/browser-retained-data"
out.mkdir(parents=True,exist_ok=True)
cases=[("eps_indi_b","live_fe9029eaeacb6da3","live_503ee72058b7cb0b"),
       ("r_draconis","live_91f42a2300e8908c","live_77f6215d8a54a512"),
       ("wise_0855","live_8a9b8e8249c07338","live_228cdbfdb2a74448")]
sources=[]
for target,sky_key,spectrum_key in cases:
    paths=[ROOT/f"backend/.cache/live/{sky_key}/frame.json",ROOT/f"backend/.cache/live/{spectrum_key}/spectrum.json"]
    manifest,spectrum=[json.loads(p.read_text())for p in paths]
    q=manifest["query"];ra,dec=q["ra"],q["dec"]
    sky=_build_response(SkyQuery(ra=ra,dec=dec,size=q["cutout_size_deg"],target_id=target,source="archive"),manifest,ra,dec,sky_key)
    spec=_build_spectrum_response(SpectrumQuery(ra=ra,dec=dec,target_id=target,source="archive"),spectrum,ra,dec,Confidence.LOW)
    for suffix,payload in (("sky",sky),("spectrum",spec)):
        (out/f"{target}-{suffix}.json").write_text(payload.model_dump_json(),encoding="utf-8")
    sources.append({"target":target,"inputs":[{"path":p.relative_to(ROOT).as_posix(),"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}for p in paths],
                    "query":q,"origin":"Real retained Phase4 archive products; serialized by current API builders for isolated UI playback, not a new upstream request"})
(out/"sources.json").write_text(json.dumps(sources,indent=2),encoding="utf-8")
print(json.dumps(sources,indent=2))
