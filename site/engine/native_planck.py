"""Native-Colab integration for the validated low-temperature Planck path.

This module is loaded explicitly by the notebook bridge.  The standalone
WebAssembly application does not import it.  PHOEBE's normal atmosphere and
limb-darkening paths remain unchanged except when the blackbody table returns
a non-finite normal intensity for a finite, positive temperature below its
lowest tabulated temperature.
"""
from contextlib import contextmanager
from functools import wraps
import logging
import threading

import numpy as np
from phoebe.atmospheres import models, passbands


_PATCH_MARKER = "_phoebe_lab_low_temperature_planck"
_STATE_MARKER = "_phoebe_lab_low_temperature_planck_state"
_ROUNDING_TEXT = "slightly over critical value, likely due to numerics: setting to critical value of"


def direct_blackbody_passband(passband, temperatures, weighting):
    """Evaluate positive blackbody temperatures over the active passband."""
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


def _candidate_method(original, state):
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
        with state["lock"]:
            state["activations"] += int(np.count_nonzero(use_direct))
        return result

    setattr(interpolate_inorms, _PATCH_MARKER, True)
    setattr(interpolate_inorms, _STATE_MARKER, state)
    return interpolate_inorms


def install_low_temperature_planck():
    """Install the narrow native patch once in this Python process."""
    current = passbands.Passband.interpolate_inorms
    if getattr(current, _PATCH_MARKER, False):
        return False
    state={"activations":0,"lock":threading.Lock()}
    passbands.Passband.interpolate_inorms = _candidate_method(current,state)
    return True


def activation_count():
    state=getattr(passbands.Passband.interpolate_inorms,_STATE_MARKER,None)
    if state is None:return 0
    with state["lock"]:
        return state["activations"]


class _CriticalVolumeRoundoffFilter(logging.Filter):
    _phoebe_lab_roundoff_filter = True

    def __init__(self):
        super().__init__()
        self.count = 0

    def filter(self, record):
        message = record.getMessage()
        matched = (
            record.levelno == logging.WARNING
            and message.startswith("target_volume of ")
            and _ROUNDING_TEXT in message
        )
        if matched:
            self.count += 1
            return False
        return True


@contextmanager
def capture_critical_volume_roundoff():
    """Count only PHOEBE's known clamped roundoff warning; preserve all others."""
    logger = logging.getLogger("UNIVERSE")
    warning_filter = _CriticalVolumeRoundoffFilter()
    logger.addFilter(warning_filter)
    try:
        yield warning_filter
    finally:
        logger.removeFilter(warning_filter)


def reset_inherited_roundoff_filters():
    """Remove a parent operation's copied filter after a process fork."""
    logger=logging.getLogger("UNIVERSE")
    for warning_filter in tuple(logger.filters):
        if getattr(warning_filter,"_phoebe_lab_roundoff_filter",False):
            logger.removeFilter(warning_filter)


def warning_summary(count):
    return {
        "count": int(count),
        "message": (
            "PHOEBE clamped a Roche target volume to its critical value after "
            f"{int(count)} numerically equivalent near-critical evaluations."
        ),
    }
