"""Opt-in candidate for positive blackbody temperatures below the table floor.

This module is a validation artifact, not a production PHOEBE Lab patch. It
leaves all atmosphere interpolation unchanged except where PHOEBE's blackbody
table returns a non-finite normal intensity for a finite, positive temperature
below that table's lower bound. Those points are evaluated from the Planck
function over the active passband with the requested photon/energy weighting.
"""
from contextlib import contextmanager
from functools import wraps

import numpy as np
from phoebe.atmospheres import models, passbands


def direct_blackbody_passband(passband, temperatures, weighting):
    """Return un-limb-darkened normal intensities by direct passband quadrature."""
    if weighting not in {"photon", "energy"}:
        raise ValueError("weighting must be 'photon' or 'energy'")
    temperatures = np.asarray(temperatures, dtype=float).reshape(-1)
    wavelengths = np.asarray(passband.ptf_table["wl"], dtype=float)
    transmission = np.asarray(passband.ptf_table["fl"], dtype=float)
    area = passband.ptf_photon_area if weighting == "photon" else passband.ptf_area
    answers = np.full(temperatures.shape, np.nan, dtype=float)
    for index, temperature in enumerate(temperatures):
        if not np.isfinite(temperature) or temperature <= 0:
            continue
        with np.errstate(over="ignore", divide="ignore", invalid="ignore", under="ignore"):
            integrand = transmission * passband._planck(wavelengths, temperature)
        if weighting == "photon":
            integrand = wavelengths * integrand
        answers[index] = np.trapezoid(integrand, wavelengths) / area
    return answers


def _candidate_method(original):
    @wraps(original)
    def interpolate_inorms(
        self,
        query,
        atm=models.CK2004ModelAtmosphere,
        ldatm=models.CK2004ModelAtmosphere,
        ldint=None,
        ld_func="interp",
        ld_coeffs=None,
        intens_weighting="photon",
        atm_extrapolation_method="none",
        ld_extrapolation_method="none",
        blending_method="none",
        blending_margin=3,
        dist_threshold=1e-5,
    ):
        result = original(
            self,
            query,
            atm=atm,
            ldatm=ldatm,
            ldint=ldint,
            ld_func=ld_func,
            ld_coeffs=ld_coeffs,
            intens_weighting=intens_weighting,
            atm_extrapolation_method=atm_extrapolation_method,
            ld_extrapolation_method=ld_extrapolation_method,
            blending_method=blending_method,
            blending_margin=blending_margin,
            dist_threshold=dist_threshold,
        )
        if atm.name != "blackbody":
            return result

        temperatures = query.subset(atm.basic_axis_names).pts[:, 0]
        values = np.asarray(result.interps, dtype=float)
        use_direct = (
            np.isfinite(temperatures)
            & (temperatures > 0)
            & (temperatures < atm.teffs[0])
            & ~np.isfinite(values[:, 0])
        )
        if not np.any(use_direct):
            return result

        if ldint is None:
            resolved_ldint = self.interpolate_ldints(
                query=query,
                ldatm=ldatm,
                ld_func=ld_func,
                ld_coeffs=ld_coeffs,
                intens_weighting=intens_weighting,
                ld_extrapolation_method=ld_extrapolation_method,
            ).get_interpolated_values()
        else:
            resolved_ldint = ldint
        resolved_ldint = np.asarray(resolved_ldint, dtype=float).reshape(-1)

        values = values.copy()
        values[use_direct, 0] = (
            direct_blackbody_passband(self, temperatures[use_direct], intens_weighting)
            / resolved_ldint[use_direct]
        )
        result.interps = values
        return result

    return interpolate_inorms


@contextmanager
def low_temperature_planck_candidate():
    """Temporarily enable the candidate and restore PHOEBE even after failure."""
    original = passbands.Passband.interpolate_inorms
    candidate = _candidate_method(original)
    passbands.Passband.interpolate_inorms = candidate
    try:
        yield candidate
    finally:
        if passbands.Passband.interpolate_inorms is candidate:
            passbands.Passband.interpolate_inorms = original
