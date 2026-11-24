import importlib.util
from pathlib import Path
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
def load_engine():
    spec=importlib.util.spec_from_file_location("geometry_test_engine",ROOT/"site/engine/model.py");m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def values(donor):
    return dict(contact=False,semidetached=True,donor=donor,inclination=84.5,mass_ratio=.75,
                radius_primary=.22,radius_secondary=.19,fillout_factor=.25,temperature_ratio=.9,
                period=1.8,epoch=0.,eccentricity=0.,omega=90.,distortion=False,irradiation=False)

def test_geometry_contract():
    m=load_engine();assert m.parameters(values("primary"))["semidetached"]
    with pytest.raises(ValueError,match="Donor"):m.parameters(values("invalid"))
    with pytest.raises(ValueError,match="Choose detached"):m.parameters(dict(values("primary"),contact=True))
    with pytest.raises(ValueError,match="circular"):m.parameters(dict(values("primary"),eccentricity=.02))

@pytest.mark.parametrize("donor",["primary","secondary"])
def test_native_semi_detached_smoke(donor):
    m=load_engine();phase=np.linspace(-.5,.5,9);x,flux=m._raw_model(m.parameters(values(donor)),"preview",phases=phase)
    np.testing.assert_array_equal(x,phase);assert np.isfinite(flux).all();assert np.ptp(flux)>.02;assert np.median(flux)==pytest.approx(1.)

def test_semi_fit_scope_and_final_grid_are_explicit():
    source=(ROOT/"site/engine/model.py").read_text()
    assert 'free_radius = "radius_secondary" if initial["donor"] == "primary" else "radius_primary"' in source
    assert "progressive_curve(dict(payload, parameters=best, plot_phases=513)" in source

@pytest.mark.parametrize("donor",["primary","secondary"])
def test_native_semi_surface_mesh_has_two_lobed_components(donor):
    m=load_engine();result=m.surface_mesh({"parameters":values(donor),"triangles":300})
    assert result["source"].startswith("native PHOEBE 2.5.4")
    assert result["geometry"]=="semi" and result["donor"]==donor
    assert result["frame"]=="component_local" and len(result["components"])==2
    for component in result["components"]:
        triangles=np.asarray(component["triangles"])
        assert triangles.ndim==3 and triangles.shape[1:]==(3,3) and np.isfinite(triangles).all()
    donor_index=0 if donor=="primary" else 1
    x=np.asarray(result["components"][donor_index]["triangles"])[...,0]
    assert x.max()>abs(x.min()),"native Roche-lobe donor extends toward L1"

def test_native_contact_surface_is_connected_at_neck_and_cached():
    m=load_engine();p=dict(values("primary"),contact=True,semidetached=False,fillout_factor=.25)
    result=m.surface_mesh({"parameters":p,"triangles":500})
    again=m.surface_mesh({"parameters":p,"triangles":500})
    assert result is again
    assert result["geometry"]=="contact" and result["frame"]=="primary_origin"
    neck=result["neck"];parts=[np.asarray(c["triangles"]) for c in result["components"]]
    assert .2<neck<.8
    assert parts[0][...,0].max()>=neck-0.06
    assert parts[1][...,0].min()<=neck+0.06
    assert parts[0][...,0].max()>=parts[1][...,0].min(),"native common-envelope halves meet without a detached gap"

def test_native_surface_detail_has_more_real_facets():
    m=load_engine();p=values("primary")
    preview=m.surface_mesh({"parameters":p,"triangles":300})
    high=m.surface_mesh({"parameters":p,"triangles":1500})
    preview_count=sum(len(component["triangles"]) for component in preview["components"])
    high_count=sum(len(component["triangles"]) for component in high["components"])
    assert preview["triangles_actual"]==300 and high["triangles_actual"]==1500
    assert high_count>preview_count

def test_contact_preview_and_high_detail_do_not_collapse_to_same_mesh():
    m=load_engine();p=dict(values("primary"),contact=True,semidetached=False,fillout_factor=.25)
    preview=m.surface_mesh({"parameters":p,"triangles":500})
    high=m.surface_mesh({"parameters":p,"triangles":1500})
    preview_count=sum(len(component["triangles"]) for component in preview["components"])
    high_count=sum(len(component["triangles"]) for component in high["components"])
    assert high["triangles_actual"]>preview["triangles_actual"]
    assert high_count>preview_count
