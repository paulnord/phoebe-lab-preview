"""Native end-to-end validation for the opt-in L1 Planck candidate."""
from contextlib import contextmanager, nullcontext
import csv
import hashlib
import importlib.util
import io
import json
import os
import platform
from pathlib import Path
import urllib.request

os.environ.setdefault("PHOEBE_ENABLE_ONLINE_PASSBANDS", "FALSE")
os.environ.setdefault("PHOEBE_ENABLE_MPI", "FALSE")
os.environ.setdefault("PHOEBE_MULTIPROC_NPROCS", "0")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import numpy as np
import phoebe
import libphoebe
from phoebe.atmospheres import models, passbands
from phoebe.backend import universe

from experiments.l1_planck.candidate import (
    direct_blackbody_passband,
    low_temperature_planck_candidate,
)

BASE_REVISION = "fe9e3684eef2ba5ab7ab2aafee448a1f26abda98"
SZ_HER_URL = (
    "https://raw.githubusercontent.com/paulnord/phoebe-lab-preview/"
    f"{BASE_REVISION}/site/examples/observed-sz-her-johnson-v.csv"
)
SZ_HER_SHA256 = "7cddf77b51037157490fcf4e9d68f8c5d0ef4a141ea44fd852f97a3fd47b1a91"
EPOCH = 2454588.167997
PERIOD = 0.8180837


def _sz_her_bundle(ntriangles, phases):
    bundle = phoebe.default_binary(semidetached="secondary")
    bundle.flip_constraint("mass@primary", solve_for="sma@binary")
    bundle.set_value("mass", component="primary", value=1.2)
    bundle.set_value("period", component="binary", value=PERIOD)
    bundle.set_value("q", component="binary", value=0.4715)
    sma = bundle.get_value("sma", component="binary", context="component")
    bundle.set_value("requiv", component="primary", context="component", value=0.318 * sma)
    bundle.set_value("teff", component="primary", value=6300.0)
    bundle.set_value("teff", component="secondary", value=6300.0 * 4881.0 / 7262.0)
    bundle.set_value("incl", component="binary", value=87.566)
    bundle.set_value("irrad_method", value="none")
    bundle.set_value_all("ntriangles", value=ntriangles)
    bundle.add_dataset("lc", dataset="lc01", passband="Johnson:V", compute_phases=phases)
    return bundle


def _control_bundle(geometry, phases):
    bundle = phoebe.default_contact_binary() if geometry == "contact" else phoebe.default_binary()
    bundle.set_value("irrad_method", value="none")
    bundle.set_value_all("ntriangles", value=800)
    bundle.add_dataset("lc", dataset="lc01", passband="Johnson:V", compute_phases=phases)
    return bundle


@contextmanager
def _exact_axis_secondary(enabled):
    """Exercise the managed-Colab symmetry branch deterministically in local QA."""
    if not enabled:
        yield
        return
    original = universe.Star_roche.instantaneous_mesh_args

    def exact_axis_args(self):
        q, synchronicity, distance, spin, potential = original.fget(self)
        if self.component == "secondary":
            spin = np.array([0.0, 0.0, np.nextafter(1.0, 0.0)], dtype=np.float64)
            target = np.float64(self.get_target_volume(scaled=False))
            critical = np.float64(
                libphoebe.roche_misaligned_critical_volume(q, synchronicity, distance, spin)
            )
            if target > critical and abs(target - critical) / target < 1e-10:
                target = critical
            potential = libphoebe.roche_misaligned_Omega_at_vol(
                target, q, synchronicity, distance, spin
            )
        return q, synchronicity, distance, spin, potential

    universe.Star_roche.instantaneous_mesh_args = property(exact_axis_args)
    try:
        yield
    finally:
        universe.Star_roche.instantaneous_mesh_args = original


def _luminosities(bundle):
    raw = bundle.compute_pblums(
        compute="phoebe01", pblum=True, pblum_abs=True,
        pblum_scale=True, pbflux=True, set_value=False,
    )
    return {
        str(key): float(np.asarray(getattr(value, "value", value), dtype=float).reshape(-1)[0])
        for key, value in raw.items()
    }


def _run(bundle, model, *, candidate, exact_axis=False):
    candidate_context = low_temperature_planck_candidate() if candidate else nullcontext()
    with _exact_axis_secondary(exact_axis), candidate_context:
        luminosities = _luminosities(bundle)
        bundle.run_compute(model=model, overwrite=True, progressbar=False)
    flux = np.asarray(bundle.get_value("fluxes", dataset="lc01", model=model), dtype=float)
    return flux, luminosities


def _load_observations(local_path=None):
    if local_path is None:
        payload = urllib.request.urlopen(SZ_HER_URL, timeout=30).read()
    else:
        payload = Path(local_path).read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != SZ_HER_SHA256:
        raise RuntimeError(f"Unexpected SZ Her CSV SHA-256: {digest}")
    rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8"))))
    times = np.asarray([float(row["hjd"]) for row in rows])
    magnitudes = np.asarray([float(row["differential_johnson_v_magnitude"]) for row in rows])
    phases = ((times - EPOCH) / PERIOD + 0.5) % 1.0 - 0.5
    flux = 10.0 ** (-0.4 * (magnitudes - np.median(magnitudes)))
    return phases, flux / np.median(flux), digest


def _residuals(phases, model, observed_phases, observed_flux):
    normalized = model / np.median(model)
    predicted = np.interp(observed_phases, phases, normalized)
    residual = observed_flux - predicted
    return {
        "rms": float(np.sqrt(np.mean(residual**2))),
        "median": float(np.median(residual)),
        "max_abs": float(np.max(np.abs(residual))),
        "count": int(residual.size),
    }


def _native_hash():
    origin = Path(importlib.util.find_spec("libphoebe").origin)
    return hashlib.sha256(origin.read_bytes()).hexdigest()


def _blackbody_floor_continuity():
    """Require continuity where the direct candidate meets the native table."""
    pb = passbands.get_passband("Johnson:V")
    floor = float(models.BlackbodyModelAtmosphere.teffs[0])
    below = np.nextafter(floor, 0.0)
    query = passbands.InterpQuery(
        cols=["teffs"], pts=np.asarray([below, floor])[:, None]
    )
    results = {"temperature_floor_K": floor, "immediately_below_K": float(below)}
    for weighting in ("photon", "energy"):
        direct_at_floor = direct_blackbody_passband(pb, [floor], weighting)[0]
        native_at_floor = pb.interpolate_inorms(
            passbands.InterpQuery(cols=["teffs"], pts=np.asarray([[floor]])),
            atm=models.BlackbodyModelAtmosphere,
            ldatm=None,
            ldint=np.ones(1),
            ld_func="linear",
            intens_weighting=weighting,
        ).get_interpolated_values()[0, 0]
        with low_temperature_planck_candidate():
            patched = pb.interpolate_inorms(
                query,
                atm=models.BlackbodyModelAtmosphere,
                ldatm=None,
                ldint=np.ones(2),
                ld_func="linear",
                intens_weighting=weighting,
            ).get_interpolated_values()[:, 0]
        direct_vs_native = abs(direct_at_floor / native_at_floor - 1.0)
        below_to_floor = abs(patched[0] / patched[1] - 1.0)
        results[weighting] = {
            "direct_vs_native_relative": float(direct_vs_native),
            "below_to_floor_relative_jump": float(below_to_floor),
        }
        if direct_vs_native > 1e-10 or below_to_floor > 1e-10:
            raise AssertionError(f"Blackbody {weighting} boundary is discontinuous")
    return results


def run_validation(local_observations=None):
    observed_phase, observed_flux, observation_sha = _load_observations(local_observations)
    results = {
        "status": "PASS",
        "candidate": "opt-in-direct-low-temperature-planck",
        "base_revision": BASE_REVISION,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "phoebe": phoebe.__version__,
            "numpy": np.__version__,
            "libphoebe_sha256": _native_hash(),
            "observation_sha256": observation_sha,
        },
        "controls": {
            "geometry": "semi-detached secondary donor",
            "mass_primary_solar": 1.2,
            "teff_primary_K": 6300.0,
            "q_secondary_over_primary": 0.4715,
            "inclination_deg": 87.566,
            "primary_radius_over_sma": 0.318,
            "temperature_ratio": 4881.0 / 7262.0,
            "period_days": PERIOD,
            "epoch_hjd": EPOCH,
            "passband": "Johnson:V",
            "irradiation": "none",
            "atmosphere": "ck2004 with existing blackbody blending",
        },
        "sz_her": {},
        "unchanged_controls": {},
    }
    results["blackbody_floor_continuity"] = _blackbody_floor_continuity()

    original, _ = _run(
        _sz_her_bundle(800, np.linspace(-0.5, 0.5, 5)),
        "original_exact_axis", candidate=False, exact_axis=True,
    )
    results["original_exact_axis"] = {
        "finite": int(np.isfinite(original).sum()), "samples": int(original.size)
    }
    if np.isfinite(original).any():
        raise AssertionError("The deterministic exact-axis control did not reproduce the L1 failure")

    natural, _ = _run(
        _sz_her_bundle(800, np.linspace(-0.5, 0.5, 5)),
        "natural_runtime_candidate", candidate=True, exact_axis=False,
    )
    results["natural_runtime_candidate"] = {
        "finite": int(np.isfinite(natural).sum()), "samples": int(natural.size)
    }
    if not np.isfinite(natural).all():
        raise AssertionError("The candidate did not produce a finite curve on this runtime's natural mesh")

    curves = {}
    for label, samples, triangles in (("Preview", 129, 800), ("Refined", 513, 1500)):
        phases = np.linspace(-0.5, 0.5, samples)
        flux, luminosities = _run(
            _sz_her_bundle(triangles, phases),
            label.lower(), candidate=True, exact_axis=True,
        )
        if flux.size != samples or not np.isfinite(flux).all() or np.any(flux <= 0):
            raise AssertionError(f"{label} did not return {samples} finite positive samples")
        curves[label] = {
            "samples": samples,
            "requested_ntriangles": triangles,
            "finite": int(np.isfinite(flux).sum()),
            "minimum": float(np.min(flux)),
            "maximum": float(np.max(flux)),
            "median": float(np.median(flux)),
            "luminosities": luminosities,
            "residuals": _residuals(phases, flux, observed_phase, observed_flux),
            "phases": phases,
            "flux": flux,
        }
    preview = curves["Preview"]
    refined = curves["Refined"]
    refined_at_preview = np.interp(preview["phases"], refined["phases"], refined["flux"])
    difference = preview["flux"] / np.median(preview["flux"]) - refined_at_preview / np.median(refined_at_preview)
    results["resolution_convergence"] = {
        "normalized_rms": float(np.sqrt(np.mean(difference**2))),
        "normalized_max_abs": float(np.max(np.abs(difference))),
        "secondary_pblum_abs_ratio_preview_over_refined": (
            preview["luminosities"]["pblum_abs@secondary@lc01"]
            / refined["luminosities"]["pblum_abs@secondary@lc01"]
        ),
    }
    for label, curve in curves.items():
        results["sz_her"][label] = {
            key: value for key, value in curve.items() if key not in {"phases", "flux"}
        }

    control_phases = np.linspace(-0.5, 0.5, 129)
    for geometry in ("detached", "contact"):
        baseline, _ = _run(_control_bundle(geometry, control_phases), f"{geometry}_baseline", candidate=False)
        candidate, _ = _run(_control_bundle(geometry, control_phases), f"{geometry}_candidate", candidate=True)
        equal = bool(np.array_equal(baseline, candidate))
        results["unchanged_controls"][geometry] = {
            "samples": 129,
            "array_equal": equal,
            "max_abs_difference": float(np.max(np.abs(baseline - candidate))),
        }
        if not equal:
            raise AssertionError(f"Candidate changed the ordinary {geometry} control")
    return results


def printable_results(results):
    return json.dumps(results, indent=2, sort_keys=True)


if __name__ == "__main__":
    local = Path(__file__).resolve().parents[2] / "site" / "examples" / "observed-sz-her-johnson-v.csv"
    print(printable_results(run_validation(local)))
