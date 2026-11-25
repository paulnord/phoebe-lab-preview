import importlib.util
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_engine():
    spec = importlib.util.spec_from_file_location("contact_test_engine", ROOT / "site/engine/model.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def contact_parameters(**changes):
    values = dict(
        contact=True, inclination=84.5, mass_ratio=.75, fillout_factor=.25,
        temperature_ratio=.84, period=1.8, epoch=0., eccentricity=0.,
        omega=90., radius_primary=.21, radius_secondary=.17,
        distortion=False, irradiation=False,
    )
    values.update(changes)
    return values


def test_contact_parameter_contract():
    model = load_engine()
    parsed = model.parameters(contact_parameters())
    assert parsed["contact"] is True
    assert parsed["fillout_factor"] == .25
    with pytest.raises(ValueError, match="circular"):
        model.parameters(contact_parameters(eccentricity=.02))
    with pytest.raises(ValueError, match="fillout factor"):
        model.parameters(contact_parameters(fillout_factor=.51))


def test_native_contact_smoke():
    model = load_engine()
    phases = np.linspace(-.5, .5, 9)
    x, flux = model._raw_model(model.parameters(contact_parameters()), "preview", phases=phases)
    assert np.array_equal(x, phases)
    assert np.isfinite(flux).all()
    assert (flux > 0).all()
    assert np.ptp(flux) > .01
    assert np.median(flux) == pytest.approx(1.)


def test_fit_scope_and_final_grid_are_explicit_in_source():
    source = (ROOT / "site/engine/model.py").read_text()
    assert 'allowed = {"inclination", "fillout_factor", "temperature_ratio", "mass_ratio", "period"}' in source
    assert "progressive_curve(dict(payload, parameters=best, plot_phases=513)" in source


def test_cross_mode_change_invalidates_exact_outputs_in_ui_source():
    source = (ROOT / "site/assets/app.js").read_text()
    assert "state.current.mode!==modeOf(state.parameters)" in source
    assert "requestMatches(current,state.revision,modeOf(state.parameters))" in source
    assert "state.revision++;" in source
    assert "state.revision++;\n  updateExportButtons();" in source
    assert "$('export-button').disabled=!exact" in source
    assert "$('figure-export-button').disabled=!exact" in source
    assert "updateStats()" in source
