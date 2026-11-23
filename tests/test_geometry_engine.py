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
