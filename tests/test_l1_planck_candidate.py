from pathlib import Path
import json
import os
import sys

os.environ["PHOEBE_ENABLE_ONLINE_PASSBANDS"] = "FALSE"

import nbformat
import numpy as np
from phoebe.atmospheres import models, passbands

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments.l1_planck.candidate import (
    direct_blackbody_passband,
    low_temperature_planck_candidate,
)

def _query(temperatures):
    return passbands.InterpQuery(cols=["teffs"], pts=np.asarray(temperatures)[:, None])


def test_direct_quadrature_matches_supported_blackbody_spline_for_both_weightings():
    pb = passbands.get_passband("Johnson:V")
    temperatures = np.array([models.BlackbodyModelAtmosphere.teffs[0], 500.0, 1000.0, 5000.0])
    for weighting in ("photon", "energy"):
        expected = pb.interpolate_inorms(
            _query(temperatures), atm=models.BlackbodyModelAtmosphere,
            ldatm=None, ldint=np.ones(len(temperatures)), ld_func="linear",
            intens_weighting=weighting,
        ).get_interpolated_values()[:, 0]
        actual = direct_blackbody_passband(pb, temperatures, weighting)
        np.testing.assert_allclose(actual, expected, rtol=1e-9, atol=0)


def test_candidate_is_continuous_at_blackbody_table_floor_for_both_weightings():
    pb = passbands.get_passband("Johnson:V")
    floor = float(models.BlackbodyModelAtmosphere.teffs[0])
    below = np.nextafter(floor, 0.0)
    for weighting in ("photon", "energy"):
        direct = direct_blackbody_passband(pb, [floor], weighting)[0]
        native = pb.interpolate_inorms(
            _query([floor]), atm=models.BlackbodyModelAtmosphere,
            ldatm=None, ldint=np.ones(1), ld_func="linear",
            intens_weighting=weighting,
        ).get_interpolated_values()[0, 0]
        with low_temperature_planck_candidate():
            patched = pb.interpolate_inorms(
                _query([below, floor]), atm=models.BlackbodyModelAtmosphere,
                ldatm=None, ldint=np.ones(2), ld_func="linear",
                intens_weighting=weighting,
            ).get_interpolated_values()[:, 0]
        assert abs(direct / native - 1.0) < 1e-10
        assert abs(patched[0] / patched[1] - 1.0) < 1e-10


def test_candidate_handles_only_positive_low_temperature_and_restores_method():
    pb = passbands.get_passband("Johnson:V")
    original = passbands.Passband.interpolate_inorms
    temperatures = np.array([238.77155847645616, 0.0, -1.0, np.nan, 600000.0])
    with np.errstate(divide="ignore", invalid="ignore"):
        before = pb.interpolate_inorms(
            _query(temperatures), atm=models.BlackbodyModelAtmosphere,
            ldatm=None, ldint=np.ones(len(temperatures)), ld_func="linear",
        ).get_interpolated_values()[:, 0]
        with low_temperature_planck_candidate():
            after = pb.interpolate_inorms(
                _query(temperatures), atm=models.BlackbodyModelAtmosphere,
                ldatm=None, ldint=np.ones(len(temperatures)), ld_func="linear",
            ).get_interpolated_values()[:, 0]
        assert np.isfinite(after[0]) and after[0] > 0
        assert np.isnan(after[1:]).all()
    assert passbands.Passband.interpolate_inorms is original
    assert np.isnan(before).all()


def test_candidate_preserves_manual_limb_darkening_divisor():
    pb = passbands.get_passband("Johnson:V")
    temperature = np.array([238.77155847645616])
    direct = direct_blackbody_passband(pb, temperature, "photon")[0]
    with low_temperature_planck_candidate():
        value = pb.interpolate_inorms(
            _query(temperature), atm=models.BlackbodyModelAtmosphere,
            ldatm=None, ldint=np.array([0.7]), ld_func="linear",
            ld_coeffs=np.array([0.3]),
        ).get_interpolated_values()[0, 0]
    assert value == direct / 0.7


def test_candidate_resolves_interpolated_limb_darkening_for_low_temperature():
    pb = passbands.get_passband("Johnson:V")
    query = passbands.InterpQuery(
        cols=["teffs", "loggs", "abuns", "mus"],
        pts=np.array([[238.77155847645616, -11.75939611334793, 0.0, 0.5]]),
    )
    with low_temperature_planck_candidate():
        value = pb.interpolate_inorms(
            query,
            atm=models.BlackbodyModelAtmosphere,
            ldatm=models.CK2004ModelAtmosphere,
            ldint=None,
            ld_func="interp",
            ld_extrapolation_method="nearest",
        ).get_interpolated_values()[0, 0]
    assert np.isfinite(value) and value > 0


def test_generated_notebook_is_isolated_collapsed_and_complete():
    notebook = nbformat.read(ROOT / "notebooks" / "PHOEBE_L1_Planck_Colab_Test.ipynb", as_version=4)
    code = [cell for cell in notebook.cells if cell.cell_type == "code"]
    source = "\n".join(cell.source for cell in notebook.cells)
    assert len(code) == 3
    assert all(cell.metadata.get("cellView") == "form" for cell in code)
    assert all(cell.source.startswith("#@title ") for cell in code)
    assert "opt-in" in source and "129 phases" in source and "513 phases" in source
    assert "run_validation()" in source and "original_exact_axis" in source
    assert "blackbody_floor_continuity" in source
    assert "array_equal" in source and "pblum_abs@secondary@lc01" in source
    assert "fe9e3684eef2ba5ab7ab2aafee448a1f26abda98" in source
    assert "PHOEBE_Semi_Detached_Binary_Colab" not in source
