"""Pinned native PHOEBE 2.5.4 contact-binary forward model."""
from __future__ import annotations
import os
os.environ.setdefault("PHOEBE_ENABLE_ONLINE_PASSBANDS", "FALSE")
import numpy as np
import phoebe

PHOEBE_VERSION = "2.5.4"
PRIMARY_MASS = 1.2
PRIMARY_TEFF = 6300.0
PERIOD = 1.8
PASSBAND = "Johnson:V"
# Contact envelopes need a denser mesh than the detached preview.  A 400-face
# pilot failed on 45/192 otherwise valid designs; 800 resolved the sampled
# moderate failure used to choose this pinned production setting.
TRIANGLES = 800
BOUNDS = {"inclination": (65.0, 90.0), "mass_ratio": (0.45, 1.20),
          "fillout_factor": (0.10, 0.50), "temperature_ratio": (0.78, 1.12)}

def validate(parameters):
    result = {}
    for key, (lo, hi) in BOUNDS.items():
        value = float(parameters[key])
        if not np.isfinite(value) or not lo <= value <= hi:
            raise ValueError(f"{key} must be between {lo} and {hi}")
        result[key] = value
    return result

def make_bundle(phases=129, triangles=TRIANGLES):
    if phoebe.__version__ != PHOEBE_VERSION:
        raise RuntimeError(f"Expected PHOEBE {PHOEBE_VERSION}, found {phoebe.__version__}")
    bundle = phoebe.default_contact_binary()
    bundle.flip_constraint("mass@primary", solve_for="sma@binary")
    bundle.set_value("mass", component="primary", value=PRIMARY_MASS)
    bundle.flip_constraint("pot@contact_envelope", solve_for="requiv@primary")
    bundle.flip_constraint("fillout_factor@contact_envelope", solve_for="pot@contact_envelope")
    bundle.add_dataset("lc", compute_phases=np.linspace(-0.5, 0.5, phases),
                       dataset="contact_lc", passband=PASSBAND)
    bundle.set_value_all("ntriangles", value=int(triangles))
    bundle.set_value("irrad_method", value="none")
    return bundle

def apply_parameters(bundle, parameters):
    p = validate(parameters)
    bundle.set_value("period", component="binary", value=PERIOD)
    bundle.set_value("q", component="binary", value=p["mass_ratio"])
    bundle.set_value("fillout_factor", component="contact_envelope", context="component", value=p["fillout_factor"])
    bundle.set_value("teff", component="primary", value=PRIMARY_TEFF)
    bundle.set_value("teff", component="secondary", value=PRIMARY_TEFF * p["temperature_ratio"])
    bundle.set_value("incl", component="binary", value=p["inclination"])
    return p

def contact_flux(parameters, phases=129, triangles=TRIANGLES, bundle=None):
    bundle = bundle or make_bundle(phases, triangles)
    p = apply_parameters(bundle, parameters)
    target = np.linspace(-0.5, 0.5, phases)
    bundle.set_value("compute_phases", dataset="contact_lc", context="dataset", value=target)
    bundle.set_value_all("ntriangles", value=int(triangles))
    bundle.run_compute(model="contact_model", overwrite=True, progressbar=False)
    flux = np.asarray(bundle.get_value("fluxes", dataset="contact_lc", model="contact_model"), dtype=float)
    if flux.shape != target.shape or not np.all(np.isfinite(flux) & (flux > 0)):
        raise ValueError("PHOEBE did not return a finite positive contact light curve")
    return target, flux / np.median(flux), p
