"""Portable interactive PHOEBE fitter used by the generated Colab notebook.

The notebook embeds this source and the frozen preview artifacts.  Native PHOEBE
curves are the only curves allowed to populate fit statistics and exports.
"""
from __future__ import annotations

import base64
import io
import json
import math
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares


GEOMETRIES = ("detached", "semi_primary", "semi_secondary", "contact")
LABELS = {
    "detached": "Detached",
    "semi_primary": "Semi-detached",
    "semi_secondary": "Semi-detached",
    "contact": "Contact",
}
DEFAULTS = {
    "geometry": "detached", "donor": "primary", "inclination": 84.5,
    "radius_primary": .21, "radius_secondary": .17, "free_fill": .55,
    "fillout_factor": .25, "temperature_ratio": .84, "mass_ratio": .75,
    "eccentricity": 0., "omega": 90., "period": 1.8, "epoch": 0.,
    "distortion": False, "irradiation": False,
}
BOUNDS = {
    "inclination": (0., 90.), "radius_primary": (.10, .32),
    "radius_secondary": (.08, .29), "free_fill": (.25, .82),
    "fillout_factor": (.10, .50), "temperature_ratio": (.58, 1.14),
    "mass_ratio": (.20, 1.50), "eccentricity": (0., .35),
    "omega": (0., 360.), "period": (.1, 100.),
}
FIT_STEPS = {
    "inclination": .025, "radius_primary": .0002, "radius_secondary": .0002,
    "free_fill": .001, "fillout_factor": .001, "temperature_ratio": .001,
    "mass_ratio": .002, "eccentricity": .0002, "omega": .1,
    "period": .0004,
}


def geometry_name(parameters):
    return str(parameters.get("geometry", "detached"))


def donor_name(parameters):
    geometry = geometry_name(parameters)
    return "secondary" if geometry == "semi_secondary" else "primary"


def allowed_fit_keys(geometry):
    if geometry == "contact":
        return ("inclination", "fillout_factor", "temperature_ratio", "mass_ratio", "period")
    if geometry.startswith("semi_"):
        return ("inclination", "free_fill", "temperature_ratio", "mass_ratio", "period")
    return ("inclination", "radius_primary", "radius_secondary", "temperature_ratio",
            "mass_ratio", "eccentricity", "omega", "period")


def validate_parameters(values):
    p = dict(DEFAULTS, **values)
    if p["geometry"] not in GEOMETRIES:
        raise ValueError("Choose Detached, Semi-detached, or Contact geometry.")
    p["donor"] = donor_name(p)
    for key, (low, high) in BOUNDS.items():
        value = float(p[key])
        if not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"{key.replace('_', ' ')} must be between {low} and {high}.")
        p[key] = value
    for key in ("distortion", "irradiation"):
        p[key] = bool(p[key])
    if p["geometry"] != "detached" and p["eccentricity"] != 0:
        raise ValueError("Semi-detached and contact modes currently require a circular orbit.")
    return p


def _rbf_preview(spec, values, model):
    scaled = []
    for key in spec["keys"]:
        low, high = spec["bounds"][key]
        value = float(values[key])
        if not low <= value <= high:
            raise ValueError(f"{key.replace('_', ' ')} is outside the trained preview range {low}–{high}.")
        scaled.append(2 * (value - low) / (high - low) - 1)
    scaled = np.asarray(scaled)
    centers = np.asarray(model["centers"])
    distance = np.sqrt(np.sum((centers - scaled) ** 2, axis=1))
    if distance.min() > model["nearest_scaled_distance_max"]:
        raise ValueError("This point is too far from a training system; run native PHOEBE.")
    coefficients = np.exp(-model["gamma"] * distance ** 2) @ np.asarray(model["weights"])
    phase = np.linspace(-.5, .5, spec["phases"] + 1)
    basis = np.cos(2 * np.pi * np.outer(phase, np.arange(spec["harmonics"] + 1)))
    flux = basis @ coefficients
    return phase, flux / np.median(flux[:-1])


def _overlap(distance, back_radius, front_radius):
    if distance >= back_radius + front_radius:
        return 0.
    if distance <= abs(back_radius - front_radius):
        return min(back_radius, front_radius) ** 2
    ca = np.clip((distance**2 + back_radius**2 - front_radius**2) /
                 (2 * distance * back_radius), -1., 1.)
    cb = np.clip((distance**2 + front_radius**2 - back_radius**2) /
                 (2 * distance * front_radius), -1., 1.)
    radical = ((back_radius + front_radius - distance) *
               (distance + back_radius - front_radius) *
               (distance - back_radius + front_radius) *
               (distance + back_radius + front_radius))
    return (back_radius**2 * np.arccos(ca) + front_radius**2 * np.arccos(cb) -
            .5 * np.sqrt(max(0., radical))) / np.pi


def _detached_preview(spec, p):
    fixed = spec["fixed"]
    for key in ("mass_ratio", "eccentricity", "omega", "period"):
        if not np.isclose(p[key], fixed[key]):
            raise ValueError(f"Detached trained preview requires {key}={fixed[key]}; run native PHOEBE.")
    if p["distortion"] or p["irradiation"]:
        raise ValueError("Detached trained preview is spherical with irradiation off; run native PHOEBE.")
    for key, (low, high) in zip(spec["keys"], spec["bounds"]):
        if not low <= p[key] <= high:
            raise ValueError(f"{key.replace('_', ' ')} is outside the trained preview range {low}–{high}.")
    table = spec["table"]
    teffs = np.asarray(table["teffs"]); gravities = np.asarray(table["gravities"])
    radii = np.asarray(table["radii"]); rings = len(radii) - 1
    values = np.frombuffer(base64.b64decode(table["log_intensity_f32le"]), dtype="<f4")
    values = values.reshape(len(teffs), len(gravities), rings)
    areas = radii[1:]**2 - radii[:-1]**2

    def interval(axis, value):
        if value < axis[0] or value > axis[-1]:
            raise ValueError("The detached preview is outside its atmosphere table.")
        index = min(np.searchsorted(axis, value, side="right") - 1, len(axis) - 2)
        index = max(0, index)
        return index, (value - axis[index]) / (axis[index + 1] - axis[index])

    def profile(teff, gravity, radius):
        i, u = interval(teffs, teff); j, v = interval(gravities, gravity)
        a = (1 - v) * values[i, j] + v * values[i, j + 1]
        b = (1 - v) * values[i + 1, j] + v * values[i + 1, j + 1]
        intensity = np.exp((1 - u) * a + u * b)
        weights = intensity - np.r_[intensity[1:], 0.]
        return {"radius": radius, "weights": weights,
                "light": float(np.sum(intensity * areas) * radius**2)}

    def blocked(distance, back, front):
        if distance >= back["radius"] + front["radius"]:
            return 0.
        if distance + back["radius"] <= front["radius"]:
            return back["light"]
        separation = distance / back["radius"]
        size = front["radius"] / back["radius"]
        fraction = sum(_overlap(separation, radii[k + 1], size) * back["weights"][k]
                       for k in range(rings))
        return fraction * back["radius"]**2

    r1, r2 = p["radius_primary"], p["radius_secondary"]
    star1 = profile(table["primary_teff"], table["base_logg"][0] - 2*np.log10(r1), r1)
    star2 = profile(table["primary_teff"] * p["temperature_ratio"],
                    table["base_logg"][1] - 2*np.log10(r2), r2)
    total = star1["light"] + star2["light"]
    n = int(spec["n"]); phase = np.linspace(-.5, .5, n + 1); flux = np.empty(n + 1)
    cosine = math.cos(math.radians(p["inclination"]))
    for j in range(n // 4 + 1):
        angle = 2 * np.pi * j / n
        distance = math.hypot(math.sin(angle), cosine * math.cos(angle))
        primary = 1 - blocked(distance, star1, star2) / total
        secondary = 1 - blocked(distance, star2, star1) / total
        flux[n//2-j] = flux[n//2+j] = primary
        flux[j] = flux[n-j] = secondary
    return phase, flux


class PreviewModels:
    def __init__(self, detached, semi, contact):
        self.detached = detached; self.semi = semi; self.contact = contact

    def curve(self, parameters):
        p = validate_parameters(parameters); geometry = p["geometry"]
        if geometry == "detached":
            return _detached_preview(self.detached, p)
        if geometry == "contact":
            fixed = self.contact["fixed"]
            if not np.isclose(p["period"], fixed["period"]) or p["irradiation"]:
                raise ValueError("Contact preview requires P=1.8 d and irradiation off; run native PHOEBE.")
            values = {key: p[key] for key in self.contact["keys"]}
            return _rbf_preview(self.contact, values, self.contact)
        fixed = self.semi["fixed"]
        if not np.isclose(p["period"], fixed["period"]) or p["irradiation"]:
            raise ValueError("Semi-detached preview requires P=1.8 d and irradiation off; run native PHOEBE.")
        values = {"inclination": p["inclination"], "mass_ratio": p["mass_ratio"],
                  "free_fill": p["free_fill"], "temperature_ratio": p["temperature_ratio"]}
        return _rbf_preview(self.semi, values, self.semi["donors"][p["donor"]])


@dataclass
class ObservationSet:
    x: np.ndarray
    y: np.ndarray
    sigma: np.ndarray | None
    x_kind: str
    y_kind: str
    name: str


def parse_csv_bytes(content, name="observations.csv"):
    if isinstance(content, str):
        content = content.encode()
    try:
        data = np.genfromtxt(io.StringIO(content.decode("utf-8-sig")), delimiter=",",
                             names=True, dtype=float, encoding=None)
    except Exception as error:
        raise ValueError(f"Could not read CSV: {error}") from error
    names = list(data.dtype.names or [])
    if len(names) < 2:
        raise ValueError("CSV needs named phase/time and flux/magnitude columns.")
    lower = {key.lower().strip(): key for key in names}
    x_key = next((lower[k] for k in ("phase", "time", "bjd", "hjd", "jd") if k in lower), None)
    y_key = next((lower[k] for k in ("flux", "normalized_flux", "brightness", "magnitude", "mag") if k in lower), None)
    if x_key is None or y_key is None:
        raise ValueError("Use a phase or time column and a flux or magnitude column.")
    sigma_key = next((lower[k] for k in ("sigma", "error", "uncertainty", "flux_error", "mag_error") if k in lower), None)
    x = np.atleast_1d(np.asarray(data[x_key], dtype=float)); y = np.atleast_1d(np.asarray(data[y_key], dtype=float))
    sigma = None if sigma_key is None else np.atleast_1d(np.asarray(data[sigma_key], dtype=float))
    if not 8 <= len(x) <= 5000 or len(y) != len(x):
        raise ValueError("Load 8–5,000 matching observations.")
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("Observations contain missing or non-numeric values.")
    if sigma is not None and (len(sigma) != len(x) or not np.isfinite(sigma).all() or np.any(sigma <= 0)):
        raise ValueError("Uncertainties must be finite, positive, and match the observations.")
    return ObservationSet(x, y, sigma, "phase" if x_key.lower() == "phase" else "time",
                          "magnitude" if y_key.lower() in ("magnitude", "mag") else "flux", name)


def observation_arrays(observations, parameters, sort=True):
    p = validate_parameters(parameters); x = observations.x.copy(); y = observations.y.copy()
    sigma = None if observations.sigma is None else observations.sigma.copy()
    if observations.y_kind == "magnitude":
        flux = 10 ** (-.4 * (y - np.median(y)))
        if sigma is not None:
            sigma = .4 * np.log(10.) * flux * sigma
    else:
        flux = y
    if not np.isfinite(flux).all() or np.any(flux <= 0):
        raise ValueError("Flux values must be finite and positive.")
    scale = np.median(flux); flux = flux / scale
    if sigma is not None:
        sigma = sigma / scale
    phase = x if observations.x_kind == "phase" else (x - p["epoch"]) / p["period"]
    phase = (phase + .5) % 1 - .5
    if not sort:
        return phase, flux, sigma
    order = np.argsort(phase)
    return phase[order], flux[order], None if sigma is None else sigma[order]


def compare_curve(model_phase, model_flux, observations, parameters, fitted_count=0, sort=True):
    phase, flux, sigma = observation_arrays(observations, parameters, sort=sort)
    predicted = np.interp(phase, model_phase, model_flux)
    weights = np.ones_like(flux) if sigma is None else 1 / sigma**2
    normalization = float(np.sum(weights * flux * predicted) / np.sum(weights * predicted**2))
    predicted = normalization * predicted; residual = flux - predicted
    dof = len(flux) - fitted_count - 1
    reduced = None if sigma is None or dof <= 0 else float(np.sum((residual / sigma)**2) / dof)
    return {"phase": phase, "flux": flux, "sigma": sigma, "model_at_data": predicted,
            "residual": residual, "rms": float(np.sqrt(np.mean(residual**2))),
            "reduced_chi2": reduced, "normalization": normalization}


class NativeBackend:
    def __init__(self, phoebe_module=None):
        if phoebe_module is None:
            import phoebe as phoebe_module
        self.phoebe = phoebe_module; self.bundles = {}

    def _bundle(self, p, phases, triangles):
        geometry = p["geometry"]
        if geometry not in self.bundles:
            if geometry == "contact":
                b = self.phoebe.default_contact_binary()
                b.flip_constraint("mass@primary", solve_for="sma@binary")
                b.set_value("mass", component="primary", value=1.2)
                b.flip_constraint("pot@contact_envelope", solve_for="requiv@primary")
                b.flip_constraint("fillout_factor@contact_envelope", solve_for="pot@contact_envelope")
            elif geometry.startswith("semi_"):
                b = self.phoebe.default_binary(semidetached=p["donor"])
                b.flip_constraint("mass@primary", solve_for="sma@binary")
                b.set_value("mass", component="primary", value=1.2)
            else:
                b = self.phoebe.default_binary()
                b.flip_constraint("mass@primary", solve_for="sma@binary")
                b.set_value("mass", component="primary", value=1.2)
            b.add_dataset("lc", dataset="fitter_lc", compute_phases=phases, passband="Johnson:V")
            self.bundles[geometry] = b
        b = self.bundles[geometry]
        b.set_value("compute_phases", dataset="fitter_lc", context="dataset", value=phases)
        b.set_value_all("ntriangles", value=int(triangles))
        return b

    def curve(self, parameters, phases, triangles=800):
        p = validate_parameters(parameters); phases = np.asarray(phases, dtype=float)
        b = self._bundle(p, phases, triangles)
        b.set_value("period", component="binary", value=p["period"])
        b.set_value("q", component="binary", value=p["mass_ratio"])
        if p["geometry"] == "contact":
            b.set_value("fillout_factor", component="contact_envelope", context="component",
                        value=p["fillout_factor"])
        elif p["geometry"].startswith("semi_"):
            free = "secondary" if p["donor"] == "primary" else "primary"
            maximum = b.get_value("requiv_max", component=free, context="component")
            b.set_value("requiv", component=free, context="component", value=p["free_fill"] * maximum)
        else:
            separation = b.get_value("sma", component="binary", context="component")
            b.set_value("requiv", component="primary", value=p["radius_primary"] * separation)
            b.set_value("requiv", component="secondary", value=p["radius_secondary"] * separation)
            b.set_value("ecc", component="binary", value=p["eccentricity"])
            b.set_value("per0", component="binary", value=p["omega"])
            b.set_value_all("distortion_method", value="roche" if p["distortion"] else "sphere")
        b.set_value("teff", component="primary", value=6300.)
        b.set_value("teff", component="secondary", value=6300. * p["temperature_ratio"])
        b.set_value("incl", component="binary", value=p["inclination"])
        b.set_value("irrad_method", value="horvat" if p["irradiation"] else "none")
        b.run_compute(model="fitter_model", overwrite=True, progressbar=False)
        flux = np.asarray(b.get_value("fluxes", dataset="fitter_lc", model="fitter_model"), dtype=float)
        if not np.isfinite(flux).all() or np.any(flux <= 0):
            raise ValueError("Native PHOEBE did not produce a finite positive curve.")
        return phases, flux / np.median(flux)


def run_native_compute(backend, observations, parameters, final_phases=513, final_triangles=1500):
    p = validate_parameters(parameters); phase = np.linspace(-.5, .5, int(final_phases))
    started = time.perf_counter(); x, flux = backend.curve(p, phase, final_triangles)
    comparison = compare_curve(x, flux, observations, p)
    return {"parameters": p, "phases": x, "model": flux * comparison["normalization"],
            "comparison": comparison, "fit": None, "seconds": time.perf_counter() - started,
            "source": "native PHOEBE"}


def run_native_fit(backend, observations, parameters, keys, fit_phases=65, max_nfev=8,
                   final_phases=513, search_triangles=None, final_triangles=1500, progress=None):
    initial = validate_parameters(parameters); geometry = initial["geometry"]
    keys = tuple(keys)
    if not keys or len(set(keys)) != len(keys) or not set(keys) <= set(allowed_fit_keys(geometry)):
        raise ValueError("Choose one or more parameters supported for this geometry.")
    if "omega" in keys and initial["eccentricity"] == 0 and "eccentricity" not in keys:
        raise ValueError("Fit eccentricity with periastron angle when starting from a circular orbit.")
    count = int(fit_phases)
    if count not in (65, 129):
        raise ValueError("Fit phases must be 65 or 129; final validation always uses 513.")
    triangles = search_triangles or (800 if geometry != "detached" else 400)
    phase_grid = np.linspace(-.5, .5, count)
    lower = np.asarray([BOUNDS[key][0] for key in keys], dtype=float)
    upper = np.asarray([BOUNDS[key][1] for key in keys], dtype=float)
    if geometry == "contact":
        for key in ("inclination", "mass_ratio", "fillout_factor", "temperature_ratio"):
            if key in keys:
                low, high = initial_preview_bounds = {
                    "inclination": (65., 90.), "mass_ratio": (.45, 1.2),
                    "fillout_factor": (.1, .5), "temperature_ratio": (.78, 1.12),
                }[key]; i = keys.index(key); lower[i], upper[i] = low, high
    elif geometry.startswith("semi_"):
        preview_bounds = {"inclination": (65.,90.), "mass_ratio": (.4,1.3),
                          "free_fill": (.25,.82), "temperature_ratio": (.76,1.14)}
        for key in keys:
            if key in preview_bounds:
                i = keys.index(key); lower[i], upper[i] = preview_bounds[key]
    best = {"cost": float("inf"), "parameters": initial}; evaluations = 0
    _, _, sigma = observation_arrays(observations, initial, sort=False)

    def evaluate(values):
        nonlocal evaluations
        p = dict(initial, **dict(zip(keys, map(float, values))))
        if "omega" in keys:
            p["omega"] %= 360.
        _, model = backend.curve(p, phase_grid, triangles)
        comparison = compare_curve(phase_grid, model, observations, p, len(keys), sort=False)
        residual = comparison["residual"] if sigma is None else comparison["residual"] / sigma
        cost = float(np.dot(residual, residual)); evaluations += 1
        if cost < best["cost"]:
            best.update(cost=cost, parameters=p)
        if progress is not None:
            progress(evaluations, comparison["rms"], p)
        return residual

    def jacobian(x):
        base = evaluate(x); columns = []
        for i, key in enumerate(keys):
            probe = x.copy(); step = max(FIT_STEPS[key], 4*np.spacing(max(1., abs(x[i]))))
            probe[i] += step if x[i] + step <= upper[i] else -step
            columns.append((evaluate(probe) - base) / (probe[i] - x[i]))
        return np.column_stack(columns)

    started = time.perf_counter(); start = np.asarray([initial[key] for key in keys], dtype=float)
    evaluate(start)
    result = least_squares(evaluate, start, bounds=(lower, upper), jac=jacobian,
                           x_scale="jac", max_nfev=int(max_nfev),
                           ftol=2e-4, xtol=1e-8, gtol=2e-4)
    fitted = validate_parameters(best["parameters"]); final_grid = np.linspace(-.5, .5, int(final_phases))
    x, flux = backend.curve(fitted, final_grid, final_triangles)
    comparison = compare_curve(x, flux, observations, fitted, len(keys))
    return {"parameters": fitted, "phases": x, "model": flux * comparison["normalization"],
            "comparison": comparison, "fit": {"parameters": list(keys), "evaluations": evaluations,
            "objective_phases": count, "objective_triangles": triangles,
            "converged": bool(result.success), "message": str(result.message)},
            "seconds": time.perf_counter() - started, "source": "native PHOEBE"}


def export_result(result, destination="phoebe_fit_results.zip"):
    if not result or result.get("source") != "native PHOEBE":
        raise ValueError("Run native PHOEBE compute or fit before exporting.")
    destination = Path(destination); comparison = result["comparison"]
    summary = {"source": result["source"], "parameters": result["parameters"],
               "fit": result["fit"], "seconds": result["seconds"],
               "statistics": {"rms": comparison["rms"],
                              "reduced_chi2": comparison["reduced_chi2"],
                              "normalization": comparison["normalization"]}}
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        model = io.StringIO(); np.savetxt(model, np.c_[result["phases"], result["model"]],
                                          delimiter=",", header="phase,normalized_flux", comments="")
        residual = io.StringIO(); columns = [comparison["phase"], comparison["flux"],
                                             comparison["model_at_data"], comparison["residual"]]
        header = "phase,observed_flux,model_flux,residual"
        if comparison["sigma"] is not None:
            columns.append(comparison["sigma"]); header += ",sigma"
        np.savetxt(residual, np.column_stack(columns), delimiter=",", header=header, comments="")
        archive.writestr("native_model.csv", model.getvalue())
        archive.writestr("residuals.csv", residual.getvalue())
        archive.writestr("fit_summary.json", json.dumps(summary, indent=2))
    return destination


class BinaryFitterApp:
    """ipywidgets surface. Callback methods are public enough for integration QA."""
    def __init__(self, models, backend=None, render_plots=True, export_directory="."):
        import ipywidgets as widgets
        self.widgets = widgets; self.models = models; self.backend = backend or NativeBackend()
        self.render_plots = render_plots; self.export_directory = Path(export_directory)
        self.observations = None; self.preview_result = None; self.exact_result = None
        self._suspend = False; self._observers = []; self._mode_snapshots = {}
        self._build_widgets(); self._register_callbacks(); self._update_mode(); self.load_sample()
        self._mode_snapshots["detached"] = self._snapshot_controls()

    def _build_widgets(self):
        w = self.widgets
        self.geometry = w.ToggleButtons(options=[("Detached","detached"),("Semi-detached","semi"),("Contact","contact")], description="Geometry")
        self.donor = w.ToggleButtons(options=[("Primary donor","primary"),("Secondary donor","secondary")], description="Donor")
        def slider(description, key, step):
            low, high = BOUNDS[key]
            return w.FloatSlider(description=description, min=low, max=high, step=step,
                                 value=DEFAULTS[key], continuous_update=False, readout_format=".4g",
                                 style={"description_width":"150px"}, layout=w.Layout(width="510px"))
        self.controls = {
            "inclination": slider("Inclination (deg)", "inclination", .1),
            "radius_primary": slider("Primary radius / a", "radius_primary", .001),
            "radius_secondary": slider("Secondary radius / a", "radius_secondary", .001),
            "free_fill": slider("Free-star Roche fill", "free_fill", .005),
            "fillout_factor": slider("Contact fill-out", "fillout_factor", .005),
            "temperature_ratio": slider("T2 / T1", "temperature_ratio", .005),
            "mass_ratio": slider("q = M2 / M1", "mass_ratio", .005),
            "eccentricity": slider("Eccentricity", "eccentricity", .001),
            "omega": slider("Periastron angle", "omega", 1.),
            "period": slider("Period (days)", "period", .01),
        }
        self.epoch = w.FloatText(value=0., description="Epoch", style={"description_width":"150px"})
        self.distortion = w.Checkbox(value=False, description="Native detached Roche distortion")
        self.irradiation = w.Checkbox(value=False, description="Native irradiation (Horvat)")
        self.sample_choice = w.Dropdown(options=[("Mode-appropriate sample","auto"),("Grazing sample","grazing")], description="Sample")
        self.sample_button = w.Button(description="Load sample", button_style="info")
        self.upload = w.FileUpload(accept=".csv,text/csv", multiple=False, description="Upload CSV")
        self.preview_button = w.Button(description="Refresh trained preview")
        self.native_button = w.Button(description="Compute native curve", button_style="info")
        self.fit_button = w.Button(description="Run bounded native fit", button_style="primary")
        self.export_button = w.Button(description="Export native result", disabled=True)
        self.fit_phases = w.Dropdown(options=[("65 (fast)",65),("129 (standard)",129)], value=65, description="Fit phases")
        self.max_evaluations = w.Dropdown(options=[4,8,12], value=8, description="Max evals")
        descriptions = {"inclination":"Inclination", "radius_primary":"Primary radius", "radius_secondary":"Secondary radius",
                        "free_fill":"Free-star fill", "fillout_factor":"Contact fill-out", "temperature_ratio":"T2 / T1",
                        "mass_ratio":"Mass ratio q", "eccentricity":"Eccentricity", "omega":"Periastron angle", "period":"Period"}
        self.fit_checks = {key:w.Checkbox(value=key in ("inclination","temperature_ratio"), description=descriptions[key], indent=False)
                           for key in FIT_STEPS}
        self.status = w.HTML(); self.statistics = w.HTML(); self.plot_output = w.Output(); self.log_output = w.Output(); self.download_output = w.Output()
        self.parameter_box = w.VBox(list(self.controls.values()) + [self.epoch, self.distortion, self.irradiation])
        self.fit_box = w.VBox(list(self.fit_checks.values()))
        self.root = w.VBox([
            w.HTML("<h2>PHOEBE binary fitting utility</h2><p><b>Trained previews are approximate and kernel-side.</b> Slider updates make a Colab/Jupyter kernel round trip. Native PHOEBE is authoritative for fitting, statistics, and exports.</p>"),
            self.geometry, self.donor, self.parameter_box,
            w.HBox([self.sample_choice,self.sample_button,self.upload]),
            w.HBox([self.preview_button,self.native_button]), self.status,
            self.plot_output, self.statistics,
            w.HTML("<h3>Bounded native fit</h3><p>Select only identifiable parameters. Photometry alone may not uniquely constrain q; joint RV fitting is not implemented.</p>"),
            self.fit_box, w.HBox([self.fit_phases,self.max_evaluations,self.fit_button]), self.log_output,
            w.HBox([self.export_button]), self.download_output,
        ])

    def _observe(self, widget, handler, name="value"):
        widget.observe(handler, names=name); self._observers.append((widget, handler, name))

    def _register_callbacks(self):
        self._observe(self.geometry, self._geometry_changed); self._observe(self.donor, self._parameter_changed)
        for widget in self.controls.values(): self._observe(widget, self._parameter_changed)
        self._observe(self.epoch, self._parameter_changed); self._observe(self.distortion, self._parameter_changed); self._observe(self.irradiation, self._parameter_changed)
        self._observe(self.upload, self._upload_changed)
        self.sample_button.on_click(self._load_sample_clicked); self.preview_button.on_click(self._preview_clicked)
        self.native_button.on_click(self._native_clicked); self.fit_button.on_click(self._fit_clicked); self.export_button.on_click(self._export_clicked)

    def close(self):
        for widget, handler, name in self._observers:
            widget.unobserve(handler, names=name)
        self._observers.clear()
        for button, handler in ((self.sample_button,self._load_sample_clicked),(self.preview_button,self._preview_clicked),
                                (self.native_button,self._native_clicked),(self.fit_button,self._fit_clicked),(self.export_button,self._export_clicked)):
            button.on_click(handler, remove=True)
        self.root.close()

    def parameters(self):
        geometry = self.geometry.value
        if geometry == "semi": geometry = "semi_secondary" if self.donor.value == "secondary" else "semi_primary"
        p = dict(DEFAULTS, geometry=geometry, donor=self.donor.value, epoch=float(self.epoch.value),
                 distortion=self.distortion.value, irradiation=self.irradiation.value)
        p.update({key:float(widget.value) for key,widget in self.controls.items()})
        return validate_parameters(p)

    def _set_visible(self, key, visible): self.controls[key].layout.display = "" if visible else "none"

    def _update_mode(self):
        mode = self.geometry.value; semi = mode == "semi"; contact = mode == "contact"
        self.donor.layout.display = "" if semi else "none"
        self._set_visible("radius_primary", mode == "detached")
        self._set_visible("radius_secondary", mode == "detached")
        self._set_visible("free_fill", semi); self._set_visible("fillout_factor", contact)
        self._set_visible("eccentricity", mode == "detached"); self._set_visible("omega", mode == "detached")
        self.distortion.layout.display = "" if mode == "detached" else "none"
        allowed = set(allowed_fit_keys(self.parameters()["geometry"]))
        for key, checkbox in self.fit_checks.items(): checkbox.layout.display = "" if key in allowed else "none"

    def _snapshot_controls(self):
        return {"controls":{key:widget.value for key,widget in self.controls.items()},
                "epoch":self.epoch.value,"distortion":self.distortion.value,
                "irradiation":self.irradiation.value,"donor":self.donor.value}

    def _restore_controls(self, snapshot):
        self._suspend = True
        try:
            for key,value in snapshot["controls"].items(): self.controls[key].value = value
            self.epoch.value = snapshot["epoch"]; self.distortion.value = snapshot["distortion"]
            self.irradiation.value = snapshot["irradiation"]; self.donor.value = snapshot["donor"]
        finally: self._suspend = False

    def _invalidate_exact(self, reason="Parameters or observations changed"):
        self.exact_result = None; self.export_button.disabled = True; self.statistics.value = ""
        self.status.value = f"<span style='color:#805500'>{reason}; prior native statistics/export invalidated.</span>"

    def _geometry_changed(self, change):
        if self._suspend: return
        old, new = change.get("old"), change.get("new")
        if old in ("detached","semi","contact"): self._mode_snapshots[old] = self._snapshot_controls()
        if new in self._mode_snapshots:
            self._restore_controls(self._mode_snapshots[new])
        elif new != "detached":
            snapshot = self._snapshot_controls(); snapshot["controls"].update(eccentricity=0.,omega=90.,period=1.8)
            snapshot.update(distortion=False,irradiation=False)
            self._restore_controls(snapshot)
        self._update_mode(); self._invalidate_exact("Geometry changed"); self.refresh_preview()

    def _parameter_changed(self, change):
        if self._suspend: return
        self._invalidate_exact(); self.refresh_preview()

    def _upload_changed(self, change):
        value = change.get("new", self.upload.value)
        if not value: return
        try:
            item = next(iter(value.values())) if isinstance(value, dict) else value[0]
            content = item["content"]; content = content.tobytes() if hasattr(content,"tobytes") else bytes(content)
            self.load_csv_bytes(content, item.get("name", "uploaded.csv"))
        except Exception as error:
            self._set_error(error)

    def load_csv_bytes(self, content, name="uploaded.csv"):
        self.observations = parse_csv_bytes(content, name); self._invalidate_exact("New observations loaded")
        self.status.value = f"<b>Loaded {len(self.observations.x)} rows from {name}.</b> Preview statistics are approximate until native compute/fit."
        self.refresh_preview(); return self.observations

    def load_sample(self):
        p = self.parameters()
        if self.sample_choice.value == "grazing": p["inclination"] = 68.
        try: phase, flux = self.models.curve(p)
        except ValueError:
            p.update(period=1.8, eccentricity=0., omega=90., irradiation=False, distortion=False, mass_ratio=.75)
            phase, flux = self.models.curve(p)
        take = np.linspace(0, len(phase)-2, 120, dtype=int); rng = np.random.default_rng(271828)
        sigma = np.full(len(take), .0015); observed = flux[take] + rng.normal(0, sigma)
        self.observations = ObservationSet(phase[take], observed, sigma, "phase", "flux", "built-in surrogate sample")
        self._invalidate_exact("Sample loaded"); self.refresh_preview(); return self.observations

    def _load_sample_clicked(self, button): self.load_sample()
    def _preview_clicked(self, button): self.refresh_preview()

    def refresh_preview(self):
        try:
            phase, flux = self.models.curve(self.parameters())
            comparison = None if self.observations is None else compare_curve(phase, flux, self.observations, self.parameters())
            self.preview_result = {"phases":phase,"model":flux,"comparison":comparison,"source":"trained preview"}
            self.status.value = "<b>Approximate trained preview.</b> Run native PHOEBE for authoritative statistics/export."
            self._draw(self.preview_result)
            return self.preview_result
        except Exception as error:
            self.preview_result = None; self.status.value = f"<span style='color:#805500'>Preview unavailable: {error}</span>"
            return None

    def _set_busy(self, message):
        self.status.value = f"<b>{message}</b>"; self.native_button.disabled = self.fit_button.disabled = True

    def _set_error(self, error):
        self.status.value = f"<span style='color:#a00000'><b>Error:</b> {error}</span>"

    def _native_clicked(self, button):
        if self.observations is None: self._set_error("Load observations first."); return
        self._set_busy("Running authoritative native PHOEBE compute…")
        try:
            result = run_native_compute(self.backend, self.observations, self.parameters())
            self._accept_exact(result)
        except Exception as error: self._set_error(error)
        finally: self.native_button.disabled = self.fit_button.disabled = False

    def selected_fit_keys(self):
        allowed = set(allowed_fit_keys(self.parameters()["geometry"]))
        return [key for key,checkbox in self.fit_checks.items() if checkbox.value and key in allowed]

    def _fit_clicked(self, button):
        if self.observations is None: self._set_error("Load observations first."); return
        keys = self.selected_fit_keys()
        if not keys: self._set_error("Select at least one supported fit parameter."); return
        self._set_busy("Running bounded native PHOEBE fit…")
        def progress(evaluation, rms, parameters):
            self.status.value = f"<b>Native fit evaluation {evaluation}</b> · current RMS {rms:.6g}"
        try:
            result = run_native_fit(self.backend, self.observations, self.parameters(), keys,
                                    self.fit_phases.value, self.max_evaluations.value, progress=progress)
            self._suspend = True
            try:
                for key, widget in self.controls.items(): widget.value = result["parameters"][key]
            finally: self._suspend = False
            self._accept_exact(result)
        except Exception as error: self._set_error(error)
        finally: self.native_button.disabled = self.fit_button.disabled = False

    def _accept_exact(self, result):
        self.exact_result = result; self.export_button.disabled = False; comparison = result["comparison"]
        reduced = "—" if comparison["reduced_chi2"] is None else f"{comparison['reduced_chi2']:.5g}"
        fit = result.get("fit"); search = "native compute" if fit is None else f"{fit['objective_phases']}-phase fit ({fit['evaluations']} evaluations)"
        self.status.value = f"<b>Authoritative native PHOEBE complete.</b> {search}; final curve: 513 phases, 1,500 triangles."
        self.statistics.value = f"<b>RMS:</b> {comparison['rms']:.7g} &nbsp; <b>Reduced χ²:</b> {reduced} &nbsp; <b>N:</b> {len(comparison['phase'])}"
        self._draw(result)

    def _export_clicked(self, button):
        try:
            path = export_result(self.exact_result, self.export_directory / "phoebe_fit_results.zip")
            with self.download_output:
                self.download_output.clear_output(wait=True)
                try:
                    from google.colab import files
                    files.download(str(path))
                except ImportError:
                    from IPython.display import FileLink, display
                    display(FileLink(str(path)))
        except Exception as error: self._set_error(error)

    def _draw(self, result):
        if not self.render_plots: return
        import matplotlib.pyplot as plt
        from IPython.display import display
        with self.plot_output:
            self.plot_output.clear_output(wait=True)
            if self.observations is None:
                fig, ax = plt.subplots(figsize=(9,3.2)); ax.plot(result["phases"],result["model"]); ax.set(xlabel="Orbital phase",ylabel="Normalized flux")
            else:
                comp = result["comparison"]
                if comp is None:
                    comp = compare_curve(result["phases"],result["model"],self.observations,self.parameters())
                curve = result["model"] if result.get("source") == "native PHOEBE" else result["model"] * comp["normalization"]
                fig,(ax,res)=plt.subplots(2,1,figsize=(9,5.3),sharex=True,gridspec_kw={"height_ratios":[3,1]})
                ax.errorbar(comp["phase"],comp["flux"],yerr=comp["sigma"],fmt=".",alpha=.65,label="observed")
                ax.plot(result["phases"],curve,label=result["source"]); ax.set_ylabel("Normalized flux"); ax.legend()
                res.axhline(0,color=".5",lw=.8); res.plot(comp["phase"],comp["residual"],"."); res.set(xlabel="Orbital phase",ylabel="Residual")
            plt.tight_layout(); display(fig); plt.close(fig)


def launch_fitter(models, backend=None, render_plots=True, export_directory="."):
    """Idempotent notebook entry point: re-running the cell closes old callbacks."""
    global _PHOEBE_FITTER_APP
    try:
        _PHOEBE_FITTER_APP.close()
    except (NameError, AttributeError):
        pass
    _PHOEBE_FITTER_APP = BinaryFitterApp(models, backend, render_plots, export_directory)
    try:
        from IPython.display import display
        display(_PHOEBE_FITTER_APP.root)
    except ImportError:
        pass
    return _PHOEBE_FITTER_APP
