"""PHOEBE model calculations shared by the browser worker and native checks.

The browser calls these functions inside Pyodide. No HTTP/model server is used.
"""
import hashlib
import inspect
import json
from pathlib import Path
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
    "inclination": (0.0, 90.0), "radius_primary": (0.10, 0.32),
    "radius_secondary": (0.08, 0.29), "temperature_ratio": (0.58, 1.10),
    "mass_ratio": (0.2, 1.5), "eccentricity": (0.0, 0.35),
    "omega": (0.0, 360.0), "period": (0.1, 100.0), "epoch": (-1e9, 1e9),
}
_bundle = None
_last_complete = None


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


def observations(dataset, p, *, sort=True):
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
    if not sort:
        return phase, flux, sigma
    order = np.argsort(phase)
    return phase[order], flux[order], None if sigma is None else sigma[order]


def _physical_flux(p, quality, *, phases=None, ntriangles=None):
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
    return phases, flux


def _raw_model(p, quality, *, phases=None, ntriangles=None):
    grid, flux = _physical_flux(p, quality, phases=phases, ntriangles=ntriangles)
    return grid, flux / np.median(flux)


def _comparison(phases, flux, dataset, p, fitted_count=0, *, sort=True):
    x, y, sigma = observations(dataset, p, sort=sort)
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
    return _curve_result(p, quality, phases, flux, payload["dataset"], started)


def _curve_result(p, quality, phases, flux, dataset, started, fitted_count=0):
    comparison = _comparison(phases, flux, dataset, p, fitted_count)
    return {
        "parameters": p, "quality": quality, "phases": phases.tolist(),
        "model": (flux * comparison["normalization"]).tolist(),
        "comparison": comparison, "seconds": time.perf_counter() - started,
        "engine": f"PHOEBE {phoebe.__version__}",
    }


def _phase_batches(surface=False):
    """Indices on the final grid. Each batch is spread across the orbit."""
    first_step = 128 if surface else 8
    batch_size = 8 if surface else 64
    yield 512 // first_step + 1, tuple(range(0, 513, first_step))
    step = first_step
    while step > 1:
        step //= 2
        new = range(step, 512, 2 * step)
        # Interleave new samples around the orbit so each update covers both eclipses.
        chunks = max(1, len(new) // batch_size)
        for offset in range(chunks):
            yield 512 // step + 1, tuple(new[offset::chunks])


@lru_cache(maxsize=64)
def _phase_flux(values, quality, indices):
    phases = np.asarray(indices, dtype=float) / 512 - .5
    _, flux = _physical_flux(dict(values), quality, phases=phases)
    return flux


@lru_cache(maxsize=1)
def _surface_references():
    path = Path(__file__).with_name("surface-references.json")
    if not path.is_file():
        return []
    data = json.loads(path.read_text())
    physics = hashlib.sha256(inspect.getsource(_physical_flux).encode()).hexdigest()
    if (data["version"] != phoebe.__version__ or data.get("physics_sha256") != physics
            or data["triangles"] != 400 or data["passband"] != "Johnson:V"
            or not np.array_equal(data["phases"], np.linspace(-.5, .5, 513))):
        return []
    passband = phoebe.list_installed_passbands(full_dict=True)["Johnson:V"]["fname"]
    if hashlib.sha256(Path(passband).read_bytes()).hexdigest() != data["passband_sha256"]:
        return []
    return data["references"]


def progressive_curve(payload, fitted_count=0, initial_flux=None):
    """Yield successive exact display curves, then a complete scientific result."""
    global _last_complete
    started = time.perf_counter()
    p = parameters(payload.get("parameters", {}))
    quality = "refined" if payload.get("quality") == "refined" else "preview"
    values = tuple(sorted((k, v) for k, v in p.items() if k != "epoch"))
    surface = p["distortion"] or p["irradiation"]
    plot_count = payload.get("plot_phases", 513)
    if type(plot_count) is not int or plot_count not in (129, 513):
        raise ValueError("Choose 129 or 513 plot phases.")
    stride = 512 // (plot_count - 1)
    if surface and quality == "preview" and not fitted_count:
        for saved in _surface_references():
            if all(saved["parameters"][key] == value for key, value in values):
                flux = np.asarray(saved["flux"])[::stride]
                result = _curve_result(p, quality, np.linspace(-.5, .5, plot_count), flux / np.median(flux),
                                       payload["dataset"], started, fitted_count)
                result["source"] = "stored_exact"
                yield {"type": "result", "result": result}
                return
    geometry_key = (quality, values)
    if _last_complete is not None and _last_complete[0] == geometry_key:
        phases, flux = _last_complete[1:]
        if len(phases) >= plot_count:
            step = (len(phases) - 1) // (plot_count - 1)
            samples = flux[::step]
            result = _curve_result(p, quality, phases[::step], samples / np.median(samples),
                                   payload["dataset"], started, fitted_count)
            result["source"] = "reused_geometry"
            yield {"type": "result", "result": result}
            return
        if initial_flux is None or len(initial_flux) < len(flux):
            initial_flux = flux  # Reuse the completed coarse grid in absolute flux units.
    physical = np.full(513, np.nan)
    pending = [batch for batch in _phase_batches(surface) if batch[0] <= plot_count]
    if initial_flux is not None:
        count = len(initial_flux)
        indices = tuple(range(0, 513, 512 // (count - 1)))
        pending = [(count, indices)] + [batch for batch in pending if batch[0] > count]
    width = max(1, min(8, int(payload.get("workers", 1)))) if surface else 1
    first = True
    while pending:
        wave = pending[:1 if first else width]
        del pending[:len(wave)]
        first = False
        if initial_flux is not None:
            fluxes = [initial_flux]
            initial_flux = None
        elif len(wave) > 1:
            groups = [indices for _, indices in wave]
            fluxes = yield {"type": "work", "groups": groups, "parameters": p, "quality": quality}
            if len(fluxes) != len(groups):
                raise ValueError("Incomplete PHOEBE worker response.")
        else:
            fluxes = [_phase_flux(values, quality, wave[0][1])]
        for (target, indices), samples in zip(wave, fluxes):
            samples = np.asarray(samples)
            if samples.shape != (len(indices),) or not np.all(np.isfinite(samples) & (samples > 0)):
                raise ValueError("Invalid PHOEBE worker flux.")
            physical[list(indices)] = samples
            present = np.flatnonzero(np.isfinite(physical))
            phases = present / 512 - .5
            flux = physical[present]
            normalized = flux / np.median(flux)
            result = _curve_result(p, quality, phases, normalized, payload["dataset"], started, fitted_count)
            if len(present) == plot_count:
                _last_complete = (geometry_key, phases, flux)
                yield {"type": "result", "result": result}
            else:
                yield {"type": "partial", "phases": result["phases"], "model": result["model"], "target": target}


def worker_flux(payload):
    values = tuple(sorted((k, v) for k, v in parameters(payload["parameters"]).items() if k != "epoch"))
    return _phase_flux(values, payload["quality"], tuple(payload["indices"])).tolist()


def _fit_parameters(payload):
    from scipy.optimize import least_squares
    initial = parameters(payload.get("parameters", {}))
    keys = payload.get("fit", [])
    count = payload.get("fit_phases", 129)
    if type(count) is not int or count not in (65, 129, 513):
        raise ValueError("Choose 65, 129 or 513 fit phases.")
    phases = np.linspace(-.5, .5, count)
    steps = {"inclination": .025, "radius_primary": .0002, "radius_secondary": .0002,
             "temperature_ratio": .0005, "mass_ratio": .002, "eccentricity": .0002,
             "omega": .1, "period": initial["period"] * .0002}
    if not keys or len(set(keys)) != len(keys) or not set(keys) <= steps.keys():
        raise ValueError("Select one or more distinct slider parameters.")
    if "omega" in keys and initial["eccentricity"] == 0 and "eccentricity" not in keys:
        raise ValueError("To fit periastron angle at zero eccentricity, also select eccentricity.")
    dataset = payload["dataset"]
    _, _, sigma = observations(dataset, initial, sort=False)
    if "period" in keys and dataset.get("x_kind") == "time":
        baseline = max(initial["period"], np.max(np.abs(np.asarray(dataset["x"]) - initial["epoch"])))
        # Limit the phase drift of a derivative probe to a tenth of a grid interval.
        steps["period"] = min(steps["period"], initial["period"]**2 / (10 * (count - 1) * baseline))
    quality = "refined" if payload.get("quality") == "refined" else "preview"
    lower = np.array([LIMITS[key][0] for key in keys])
    upper = np.array([LIMITS[key][1] for key in keys])
    if "omega" in keys:
        # Search continuously through the 0/360 seam, then report the slider angle.
        i = keys.index("omega")
        lower[i], upper[i] = initial["omega"] - 180., initial["omega"] + 180.
    best = {"cost": float("inf")}
    evaluations = 0

    @lru_cache(maxsize=20)
    def evaluate(values):
        nonlocal evaluations
        evaluations += 1
        p = dict(initial, **dict(zip(keys, values)))
        if "omega" in keys:
            p["omega"] %= 360.
        geometry_key = (quality, tuple(sorted((k,v) for k,v in p.items() if k != "epoch")))
        if (_last_complete is not None and _last_complete[0] == geometry_key
                and len(_last_complete[1]) >= count):
            flux = _last_complete[2][::(len(_last_complete[1]) - 1) // (count - 1)]
            seed = None  # The complete display grid is already available.
        else:
            _, flux = _physical_flux(p, quality, phases=phases)
            seed = flux  # Keep absolute flux for merging with later midpoint batches.
        # Each optimizer row must follow the same exposure as trial periods reorder phases.
        comparison = _comparison(phases, flux / np.median(flux), dataset, p, len(keys), sort=False)
        residual = np.asarray(comparison["residual"])
        if sigma is not None:
            residual = residual / sigma
        cost = float(np.dot(residual, residual))
        if cost < best["cost"]:
            best.update(cost=cost, parameters=p, seed=seed)
        try:
            from js import modelProgress
            modelProgress(json.dumps({"evaluation": evaluations, "rms": comparison["rms"]}))
        except ImportError:
            pass
        return residual

    def residual(x):
        return evaluate(tuple(map(float, x)))

    def jacobian(x):
        base = residual(x)
        columns = []
        for i, key in enumerate(keys):
            probe = x.copy()
            step = max(steps[key], 4 * np.spacing(max(1., abs(x[i]))))
            probe[i] += step if x[i] + step <= upper[i] else -step
            columns.append((residual(probe) - base) / (probe[i] - x[i]))
        return np.column_stack(columns)

    start = [initial[key] for key in keys]
    residual(start)  # Include the exact starting model, even when a bound is active.
    result = least_squares(
        residual, start, bounds=(lower, upper), jac=jacobian,
        x_scale="jac", max_nfev=12, ftol=2e-4, xtol=1e-8, gtol=2e-4,
    )
    info = {"parameters": keys, "evaluations": evaluations, "objective_phases": len(phases),
            "objective_triangles": 1500 if quality == "refined" else 400,
            "converged": bool(result.success), "message": str(result.message)}
    return best["parameters"], info, best["seed"]


def progressive_fit(payload):
    started = time.perf_counter()
    best, info, seed = _fit_parameters(payload)
    yield {"type": "fit_parameters", "parameters": best}
    curve = progressive_curve(dict(payload, parameters=best, plot_phases=513), fitted_count=len(info["parameters"]), initial_flux=seed)
    response = None
    while True:
        update = curve.send(response)
        if update["type"] == "result":
            update["result"]["fit"] = info
            update["result"]["seconds"] = time.perf_counter() - started
            yield update
            return
        response = yield update


def fit(payload):
    for update in progressive_fit(dict(payload, workers=1)):
        if update["type"] == "result":
            return update["result"]


def dispatch_json(text):
    payload = json.loads(text)
    result = fit(payload) if payload.get("operation") == "fit" else compute(payload)
    return json.dumps(result, allow_nan=False)
