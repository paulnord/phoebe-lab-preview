"""Pinned native PHOEBE 2.5.4 semi-detached forward model."""
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
TRIANGLES = 800
DONORS = ("primary", "secondary")
KEYS = ("inclination", "mass_ratio", "free_fill", "temperature_ratio")
BOUNDS = {"inclination": (65.0, 90.0), "mass_ratio": (0.40, 1.30),
          "free_fill": (0.25, 0.82), "temperature_ratio": (0.76, 1.14)}

def validate(parameters):
    result = {}
    for key, (lo, hi) in BOUNDS.items():
        value = float(parameters[key])
        if not np.isfinite(value) or not lo <= value <= hi:
            raise ValueError(f"{key} must be between {lo} and {hi}")
        result[key] = value
    donor = parameters.get("donor")
    if donor not in DONORS: raise ValueError("donor must be primary or secondary")
    result["donor"] = donor
    return result

def make_bundle(donor, phases=129, triangles=TRIANGLES):
    if phoebe.__version__ != PHOEBE_VERSION:
        raise RuntimeError(f"Expected PHOEBE {PHOEBE_VERSION}, found {phoebe.__version__}")
    if donor not in DONORS: raise ValueError("unknown donor")
    b = phoebe.default_binary(semidetached=donor)
    b.flip_constraint("mass@primary", solve_for="sma@binary")
    b.set_value("mass", component="primary", value=PRIMARY_MASS)
    b.add_dataset("lc", compute_phases=np.linspace(-.5, .5, phases),
                  dataset="semi_lc", passband=PASSBAND)
    b.set_value_all("ntriangles", value=int(triangles))
    b.set_value("irrad_method", value="none")
    return b

def apply_parameters(bundle, parameters):
    p = validate(parameters); donor = p["donor"]
    free = "secondary" if donor == "primary" else "primary"
    bundle.set_value("period", component="binary", value=PERIOD)
    bundle.set_value("q", component="binary", value=p["mass_ratio"])
    max_radius = bundle.get_value("requiv_max", component=free, context="component")
    bundle.set_value("requiv", component=free, context="component", value=p["free_fill"] * max_radius)
    bundle.set_value("teff", component="primary", value=PRIMARY_TEFF)
    bundle.set_value("teff", component="secondary", value=PRIMARY_TEFF * p["temperature_ratio"])
    bundle.set_value("incl", component="binary", value=p["inclination"])
    sma = bundle.get_value("sma", component="binary", context="component")
    p["radius_primary"] = bundle.get_value("requiv", component="primary", context="component") / sma
    p["radius_secondary"] = bundle.get_value("requiv", component="secondary", context="component") / sma
    return p

def semi_flux(parameters, phases=129, triangles=TRIANGLES, bundle=None):
    p = validate(parameters); bundle = bundle or make_bundle(p["donor"], phases, triangles)
    p = apply_parameters(bundle, p); target = np.linspace(-.5, .5, phases)
    bundle.set_value("compute_phases", dataset="semi_lc", context="dataset", value=target)
    bundle.set_value_all("ntriangles", value=int(triangles))
    bundle.run_compute(model="semi_model", overwrite=True, progressbar=False)
    flux = np.asarray(bundle.get_value("fluxes", dataset="semi_lc", model="semi_model"), dtype=float)
    if flux.shape != target.shape or not np.all(np.isfinite(flux) & (flux > 0)):
        raise ValueError("PHOEBE did not return a finite positive semi-detached curve")
    return target, flux / np.median(flux), p
