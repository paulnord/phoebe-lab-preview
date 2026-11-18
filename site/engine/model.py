"""PHOEBE model calculations shared by the browser worker and native checks.

The browser calls these functions inside Pyodide. No HTTP/model server is used.
"""
import json
import math
import time
from functools import lru_cache
import numpy as np
import phoebe


DEFAULTS = {
    "inclination": 84.5, "radius_primary": 0.21, "radius_secondary": 0.17,
    "temperature_ratio": 0.84, "mass_ratio": 0.75, "eccentricity": 0.0,
    "omega": 90.0, "period": 1.8, "epoch": 0.0,
    "distortion": False, "irradiation": False,
}
LIMITS = {
    "inclination": (65.0, 90.0), "radius_primary": (0.10, 0.32),
    "radius_secondary": (0.08, 0.29), "temperature_ratio": (0.58, 1.10),
    "mass_ratio": (0.2, 1.5), "eccentricity": (0.0, 0.35),
    "omega": (0.0, 360.0), "period": (0.1, 100.0), "epoch": (-1e9, 1e9),
}
_bundle = None


def _stage(message):
    try:
        from js import modelProgress
        modelProgress(json.dumps({"stage": message}))
    except ImportError:
        pass


def parameters(values):
    result = dict(DEFAULTS)
    for key, limits in LIMITS.items():
        value = float(values.get(key, result[key]))
        if not math.isfinite(value) or not limits[0] <= value <= limits[1]:
            raise ValueError(f"{key.replace('_', ' ')} must be between {limits[0]} and {limits[1]}.")
        result[key] = value
    for key in ("distortion", "irradiation"):
        value = values.get(key, result[key])
        if not isinstance(value, bool):
            raise ValueError(f"{key} must be true or false.")
        result[key] = value
    return result


def observations(dataset, p):
    x = np.asarray(dataset.get("x", []), dtype=float)
    y = np.asarray(dataset.get("y", []), dtype=float)
    if x.ndim != 1 or y.ndim != 1 or len(x) != len(y) or not 8 <= len(x) <= 5000:
        raise ValueError("Load between 8 and 5,000 observations with matching horizontal and brightness values.")
    if not (np.isfinite(x).all() and np.isfinite(y).all()):
        raise ValueError("Observations contain missing or non-numeric values.")
    sigma = dataset.get("sigma")
    sigma = None if sigma is None else np.asarray(sigma, dtype=float)
    if sigma is not None and (sigma.shape != y.shape or not np.isfinite(sigma).all() or np.any(sigma <= 0)):
        raise ValueError("Each uncertainty must be finite and greater than zero.")
    if dataset.get("y_kind", "flux") not in {"flux", "magnitude"} or dataset.get("x_kind", "phase") not in {"phase", "time"}:
        raise ValueError("Choose phase or time coordinates, and flux or magnitude brightness.")
    if dataset.get("y_kind", "flux") == "magnitude":
        flux = 10.0 ** (-0.4 * (y - np.median(y)))
        if sigma is not None:
            sigma = (0.4 * np.log(10.0)) * flux * sigma
    else:
        flux = y.copy()
    if not np.isfinite(flux).all() or np.any(flux <= 0):
        raise ValueError("Flux values must be positive. Select Magnitude if the file contains magnitudes.")
    scale = float(np.median(flux))
    flux = flux / scale
    if sigma is not None:
        sigma = sigma / scale
    if dataset.get("x_kind", "phase") == "time":
        phase = (x - p["epoch"]) / p["period"]
    else:
        phase = x.copy()
    phase = (phase + 0.5) % 1.0 - 0.5
    order = np.argsort(phase)
    return phase[order], flux[order], None if sigma is None else sigma[order]


def _raw_model(p, quality, *, phases=None, ntriangles=None):
    global _bundle
    if _bundle is None:
        _stage("Building the binary-star system…")
        _bundle = phoebe.default_binary()
        _bundle.flip_constraint("mass@primary", solve_for="sma@binary")
        _bundle.set_value("mass", component="primary", value=1.2)
        _bundle.add_dataset("lc", compute_phases=np.linspace(-0.5, 0.5, 81),
                            dataset="observed_lc", passband="Johnson:V")
    _stage("Applying the model parameters…")
    b = _bundle
    b.set_value("period", component="binary", value=p["period"])
    b.set_value("q", component="binary", value=p["mass_ratio"])
    separation = b.get_value("sma", component="binary", context="component")
    b.set_value("requiv", component="primary", value=p["radius_primary"] * separation)
    b.set_value("requiv", component="secondary", value=p["radius_secondary"] * separation)
    b.set_value("teff", component="primary", value=6300.0)
    b.set_value("teff", component="secondary", value=6300.0 * p["temperature_ratio"])
    b.set_value("incl", component="binary", value=p["inclination"])
    b.set_value("ecc", component="binary", value=p["eccentricity"])
    b.set_value("per0", component="binary", value=p["omega"])
    b.set_value("irrad_method", value="horvat" if p["irradiation"] else "none")
    b.set_value_all("distortion_method", value="roche" if p["distortion"] else "sphere")
    refined = quality == "refined"
    if phases is None:
        phases = np.linspace(-0.5, 0.5, 201 if refined else 81)
    b.set_value("compute_phases", dataset="observed_lc", context="dataset", value=phases)
    b.set_value_all("ntriangles", value=ntriangles if ntriangles is not None else (1500 if refined else 400))
    try:
        _stage("Calculating the stellar surfaces and light curve…")
        b.run_compute(model="ui_model", overwrite=True, progressbar=False)
    except Exception as error:
        message = str(error)
        if "overflow" in message.lower() or "roche" in message.lower():
            raise ValueError("This geometry reaches a Roche-lobe limit. Reduce a radius or eccentricity, or adjust the mass ratio.") from error
        raise ValueError(message[:650]) from error
    flux = np.asarray(b.get_value("fluxes", dataset="observed_lc", model="ui_model"), dtype=float)
    _stage("Comparing the model with observations…")
    if not np.isfinite(flux).all() or np.any(flux <= 0):
        raise ValueError("The current geometry did not produce a finite, positive light curve.")
    return phases, flux / np.median(flux)


def _comparison(phases, flux, dataset, p, fitted_count=0):
    x, y, sigma = observations(dataset, p)
    predicted = np.interp(x, phases, flux)
    weights = np.ones_like(y) if sigma is None else 1.0 / sigma ** 2
    normalization = float(np.sum(weights * y * predicted) / np.sum(weights * predicted ** 2))
    predicted *= normalization
    residual = y - predicted
    dof = len(y) - fitted_count - 1  # Includes the fitted multiplicative normalization.
    chi2 = None if sigma is None or dof <= 0 else float(np.sum((residual / sigma) ** 2) / dof)
    return {
        "phase": x.tolist(), "flux": y.tolist(),
        "sigma": None if sigma is None else sigma.tolist(),
        "model_at_data": predicted.tolist(), "residual": residual.tolist(),
        "rms": float(np.sqrt(np.mean(residual ** 2))), "reduced_chi2": chi2,
        "normalization": normalization,
    }


@lru_cache(maxsize=8)
def _cached_geometry(values, quality):
    return _raw_model(dict(values), quality)


def _geometry(p, quality):
    # Changing observations or folding epoch needs only a new comparison.
    # Every distinct physical model is still calculated by PHOEBE.
    return _cached_geometry(tuple(sorted((k, v) for k, v in p.items() if k != "epoch")), quality)


def compute(payload):
    started = time.perf_counter()
    p = parameters(payload.get("parameters", {}))
    quality = "refined" if payload.get("quality") == "refined" else "preview"
    phases, flux = _geometry(p, quality)
    comparison = _comparison(phases, flux, payload["dataset"], p)
    return {
        "parameters": p, "quality": quality, "phases": phases.tolist(),
        "model": (flux * comparison["normalization"]).tolist(),
        "comparison": comparison, "seconds": time.perf_counter() - started,
        "engine": f"PHOEBE {phoebe.__version__}",
    }


def fit(payload):
    from scipy.optimize import least_squares
    started = time.perf_counter()
    initial = parameters(payload.get("parameters", {}))
    keys = payload.get("fit", [])
    allowed = {"inclination", "radius_primary", "radius_secondary", "temperature_ratio"}
    if not 1 <= len(keys) <= 2 or len(set(keys)) != len(keys) or not set(keys) <= allowed:
        raise ValueError("Choose one or two supported parameters for the local fit.")
    x, y, sigma = observations(payload["dataset"], initial)
    best = {"cost": float("inf"), "parameters": initial}
    evaluations = 0

    def residual(values):
        nonlocal evaluations
        evaluations += 1
        p = dict(initial, **dict(zip(keys, map(float, values))))
        phases, curve = _geometry(p, "preview")
        comparison = _comparison(phases, curve, payload["dataset"], p, len(keys))
        values = np.asarray(comparison["residual"])
        if sigma is not None:
            values = values / sigma
        cost = float(np.dot(values, values))
        if cost < best["cost"]:
            best.update(cost=cost, parameters=p.copy())
        try:
            from js import modelProgress
            modelProgress(json.dumps({"evaluation": evaluations, "rms": comparison["rms"]}))
        except ImportError:
            pass
        return values

    # Mesh-based derivatives benefit from finite steps larger than machine epsilon.
    result = least_squares(
        residual, [initial[key] for key in keys],
        bounds=([LIMITS[key][0] for key in keys], [LIMITS[key][1] for key in keys]),
        diff_step=2e-3, x_scale="jac", max_nfev=12, ftol=2e-4, xtol=2e-4, gtol=2e-4,
    )
    output = compute(dict(payload, parameters=best["parameters"], quality="preview"))
    phases, curve = np.asarray(output["phases"]), np.asarray(output["model"])
    # compute() has already normalized the curve; the next best scale is unity.
    output["comparison"] = _comparison(phases, curve, payload["dataset"], best["parameters"], len(keys))
    output["fit"] = {"parameters": keys, "evaluations": evaluations,
                     "converged": bool(result.success), "message": str(result.message)}
    output["seconds"] = time.perf_counter() - started
    return output


def dispatch_json(text):
    payload = json.loads(text)
    result = fit(payload) if payload.get("operation") == "fit" else compute(payload)
    return json.dumps(result, allow_nan=False)
