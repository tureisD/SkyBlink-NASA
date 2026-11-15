"""Generated mathematical inputs only; no synthetic observation/product assets."""
from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))
from phase4_science_online import aperture_weights,weighted_measurement,residual_summary
import phase4_science_online as study


def test_exact_circle_area_is_pixel_phase_invariant():
    # Analytic geometric area, independent of aperture implementation.
    for x,y in ((10.,10.),(10.13,10.7),(10.499,10.501)):
        assert aperture_weights((23,23),x,y,2,"exact").sum()==pytest.approx(4*np.pi,abs=1e-12)


def test_variable_solid_angle_uncertainty_matches_independent_noise_trials():
    yy,xx=np.indices((23,23));x,y=10.13,10.7
    radius=np.hypot(xx-x,yy-y)
    parsed=SimpleNamespace(image_mjy_sr=np.where(radius<2.8,10.,0.),
                           variance_mjy_sr2=np.full((23,23),4.),flags=np.zeros((23,23),np.uint32),
                           native_pixel_scale_arcsec=6.15,background_metadata={"subtracted":True})
    conversion=1+xx*.03
    result=weighted_measurement(parsed,x,y,"exact",conversion)
    weights=aperture_weights((23,23),x,y,2,"exact");positive=weights>0
    effective=weights[positive]*conversion[positive]
    rng=np.random.default_rng(20261114)
    pixel_noise=rng.normal(0,2,(40000,len(effective)))@effective
    annulus_noise=np.median(rng.normal(0,2,(40000,result["annulus_pixels"])),axis=1)
    empirical=np.std(pixel_noise-effective.sum()*annulus_noise)
    assert result["error_ujy"]==pytest.approx(empirical,rel=.035)
    assert result["flux_ujy"]==pytest.approx(10*effective.sum())


def test_unknown_method_fails_instead_of_silently_using_subpixel():
    with pytest.raises(ValueError):
        aperture_weights((23,23),10,10,2,"unsupported")


def test_stability_threshold_failure_is_preserved():
    rows=[]
    for z in (0.,0.,6.):
        rows.append({"visits":[{"sapm":{"exact":{"flux_ujy":0.,"error_ujy":1.}}},
                               {"sapm":{"exact":{"flux_ujy":z*np.sqrt(2),"error_ujy":1.}}}]})
    result=residual_summary(rows,"exact","sapm")
    assert result["status"]=="failed"
    assert result["count"]==3
    assert result["max_abs_z"]==pytest.approx(6.)


def test_neighbor_isolation_uses_actual_observation_epoch(tmp_path,monkeypatch):
    from astropy.time import Time
    field=tmp_path/"control";field.mkdir()
    (field/"gaia.xml").write_bytes(b"gaia")
    (field/"allwise.xml").write_bytes(b"allwise")
    star={"source_id":"1","ra":10.,"dec":0.,"pmra":0.,"pmdec":0.,"ref_epoch":2016.}
    moving_neighbor=dict(star,source_id="2",ra=10+31/3600,pmra=-1000.)
    infrared=[{"designation":"a","ra":10.,"dec":0.},{"designation":"b","ra":10.1,"dec":0.}]
    monkeypatch.setattr(study,"CACHE",tmp_path)
    monkeypatch.setattr(study,"table_rows",lambda content:[star,moving_neighbor]if content==b"gaia"else infrared)
    controls={"locked_controls":[{"gaia":star,"allwise":infrared[0]}]}
    rows=study.observation_isolation("control",controls,[Time(2016,format="jyear",scale="tcb"),Time(2020,format="jyear",scale="tcb")])[0]
    assert rows[0]["passed"] is True
    assert rows[1]["passed"] is False
    assert rows[1]["nearest_gaia_arcsec"]==pytest.approx(27.,abs=.01)
