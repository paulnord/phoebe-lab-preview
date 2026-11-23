"""Build the self-contained contact-binary Colab notebook from the frozen model."""
from pathlib import Path
import json
import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
MODEL = json.loads((ROOT / "site/experiment/contact-model.json").read_text())
nb = nbf.v4.new_notebook()
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3"},
    "colab": {"name": "PHOEBE Contact Binary Lab.ipynb", "provenance": []},
}
cells = []
cells.append(nbf.v4.new_markdown_cell("""# PHOEBE Contact Binary Lab

An experimental **contact-binary** companion to PHOEBE Lab. The instant preview is a frozen surrogate trained only on native PHOEBE 2.5.4 contact-envelope curves; native PHOEBE remains authoritative for computation and fitting.

Validated preview domain: inclination 65–90°, mass ratio 0.45–1.20, fill-out 0.10–0.50, T₂/T₁ 0.78–1.12. Fixed preview physics: P=1.8 d, M₁=1.2 M☉, T₁=6300 K, Johnson:V, circular synchronous orbit, irradiation off. Inputs outside this contract fail closed and should use `native_flux`.

The training/validation split is by physical system, never by phase sample. This notebook does not claim that a low-residual partial eclipse uniquely constrains mass ratio. The recovery example deliberately fixes q and uses a high-inclination system; broader inference needs RVs or other constraints."""))
cells.append(nbf.v4.new_code_cell("""# Colab installs into its free CPU runtime; local Jupyter reuses an existing environment.
import importlib.util, subprocess, sys
if importlib.util.find_spec("phoebe") is None:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "phoebe==2.5.4", "scipy", "matplotlib", "ipywidgets"])
"""))
cells.append(nbf.v4.new_code_cell("""import json, time
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import least_squares
try:
    import phoebe
except ImportError as exc:
    raise RuntimeError("Install PHOEBE 2.5.4 with the cell above before continuing") from exc
print("PHOEBE", phoebe.__version__)
"""))
cells.append(nbf.v4.new_code_cell("CONTACT_MODEL = json.loads(r'''" + json.dumps(MODEL, separators=(",", ":")) + "''')"))
cells.append(nbf.v4.new_code_cell("""def contact_preview(inclination=84.5, mass_ratio=.75, fillout_factor=.25,
                    temperature_ratio=.84, period=1.8, irradiation=False):
    s = CONTACT_MODEL
    values = dict(inclination=inclination, mass_ratio=mass_ratio,
                  fillout_factor=fillout_factor, temperature_ratio=temperature_ratio)
    if period != s["fixed"]["period"] or irradiation:
        raise ValueError("Preview requires P=1.8 d and irradiation off; use native_flux instead")
    x = []
    for key in s["keys"]:
        lo, hi = s["bounds"][key]
        value = float(values[key])
        if not lo <= value <= hi:
            raise ValueError(f"{key} is outside the validated preview range {lo}–{hi}")
        x.append(2*(value-lo)/(hi-lo)-1)
    x = np.asarray(x)
    centers = np.asarray(s["centers"])
    distance = np.sqrt(np.sum((centers-x)**2, axis=1))
    if distance.min() > s["nearest_scaled_distance_max"]:
        raise ValueError("This point is too far from a training system; use native_flux")
    weights = np.exp(-s["gamma"]*distance**2)
    coeff = weights @ np.asarray(s["weights"])
    phases = np.linspace(-.5, .5, s["phases"]+1)
    k = np.arange(s["harmonics"]+1)
    flux = np.cos(2*np.pi*np.outer(phases, k)) @ coeff
    return phases, flux/np.median(flux[:-1])

def contact_bundle(phases, triangles=800):
    b = phoebe.default_contact_binary()
    b.flip_constraint("mass@primary", solve_for="sma@binary")
    b.set_value("mass", component="primary", value=1.2)
    b.flip_constraint("pot@contact_envelope", solve_for="requiv@primary")
    b.flip_constraint("fillout_factor@contact_envelope", solve_for="pot@contact_envelope")
    b.add_dataset("lc", dataset="contact_lc", compute_phases=phases, passband="Johnson:V")
    b.set_value_all("ntriangles", value=triangles)
    return b

def native_flux(inclination=84.5, mass_ratio=.75, fillout_factor=.25,
                temperature_ratio=.84, period=1.8, irradiation=False,
                phases=None, triangles=800):
    phases = np.linspace(-.5, .5, 129) if phases is None else np.asarray(phases)
    b = contact_bundle(phases, triangles)
    b.set_value("period", component="binary", value=period)
    b.set_value("q", component="binary", value=mass_ratio)
    b.set_value("fillout_factor", component="contact_envelope", context="component", value=fillout_factor)
    b.set_value("teff", component="primary", value=6300.)
    b.set_value("teff", component="secondary", value=6300.*temperature_ratio)
    b.set_value("incl", component="binary", value=inclination)
    b.set_value("irrad_method", value="horvat" if irradiation else "none")
    b.run_compute(model="contact_model", overwrite=True, progressbar=False)
    flux = np.asarray(b.get_value("fluxes", dataset="contact_lc", model="contact_model"))
    return phases, flux/np.median(flux)
"""))
cells.append(nbf.v4.new_markdown_cell("""## Instant preview

This runs in the notebook kernel. Unlike the standalone app’s browser-local JavaScript panel, ipywidgets/Colab controls make a kernel round trip. The frozen model itself is local and does not call a service."""))
cells.append(nbf.v4.new_code_cell("""p, f = contact_preview()
plt.plot(p, f, label="contact surrogate")
plt.xlabel("orbital phase"); plt.ylabel("median-normalized Johnson V flux"); plt.legend();
"""))
cells.append(nbf.v4.new_markdown_cell("""## Observations, residuals, and authoritative export

Provide phase and flux arrays below (or replace the example with `np.loadtxt`). Preview residuals are approximate. Export only after a native recompute, and keep the resulting parameter dictionary beside the CSV."""))
cells.append(nbf.v4.new_code_cell("""# Example parser: CSV columns phase, flux[, sigma]
def read_observations(path):
    a = np.genfromtxt(path, delimiter=",", names=True)
    names = a.dtype.names
    if not names or len(names) < 2:
        raise ValueError("CSV needs named phase and flux columns")
    phase, flux = np.asarray(a[names[0]]), np.asarray(a[names[1]])
    if len(phase) < 8 or len(phase) != len(flux) or not np.isfinite(phase).all() or not np.isfinite(flux).all():
        raise ValueError("Need at least 8 finite phase/flux pairs")
    sigma = np.asarray(a[names[2]]) if len(names) > 2 else None
    if sigma is not None and (not np.isfinite(sigma).all() or np.any(sigma <= 0)):
        raise ValueError("Uncertainties must be finite and positive")
    return phase, flux/np.median(flux), sigma

def compare(model_phase, model_flux, obs_phase, obs_flux):
    predicted = np.interp((obs_phase+.5)%1-.5, model_phase, model_flux)
    scale = np.dot(obs_flux, predicted)/np.dot(predicted, predicted)
    residual = obs_flux-scale*predicted
    return scale*predicted, residual, float(np.sqrt(np.mean(residual**2)))

def export_native_csv(path, parameters, phases=513, triangles=1500):
    grid = np.linspace(-.5, .5, phases)
    x, y = native_flux(**parameters, phases=grid, triangles=triangles)
    np.savetxt(path, np.column_stack([x,y]), delimiter=",", header="phase,normalized_flux", comments="")
    return x, y
"""))
cells.append(nbf.v4.new_markdown_cell("""## Runnable native recovery benchmark

This intentionally fixes q=0.75 and uses a high-inclination synthetic system, so it demonstrates recovery of inclination, fill-out, and temperature ratio under a controlled, identifiable setup. It is not evidence that photometry alone uniquely recovers q. The search phase budget and final 513-phase validation are reported separately."""))
cells.append(nbf.v4.new_code_cell("""RUN_NATIVE_BENCHMARK = False  # Set True when ready; expect several native PHOEBE calculations.
if RUN_NATIVE_BENCHMARK:
    truth = dict(inclination=88., mass_ratio=.75, fillout_factor=.32,
                 temperature_ratio=.90, period=1.8, irradiation=False)
    fit_grid = np.linspace(-.5, .5, 65)
    _, observed = native_flux(**truth, phases=fit_grid)
    def residual(v):
        _, model = native_flux(inclination=v[0], mass_ratio=truth["mass_ratio"],
                               fillout_factor=v[1], temperature_ratio=v[2],
                               period=1.8, phases=fit_grid)
        return model-observed
    result = least_squares(residual, [84., .22, .84], bounds=([65,.10,.78],[90,.50,1.12]), max_nfev=12)
    recovered = dict(inclination=result.x[0], mass_ratio=truth["mass_ratio"],
                     fillout_factor=result.x[1], temperature_ratio=result.x[2],
                     period=1.8, irradiation=False)
    final_grid = np.linspace(-.5,.5,513)
    _, exact_truth = native_flux(**truth, phases=final_grid, triangles=1500)
    _, exact_fit = native_flux(**recovered, phases=final_grid, triangles=1500)
    print("65-phase search:", recovered, "optimizer converged:", result.success, result.message)
    print("513-phase native validation RMS:", np.sqrt(np.mean((exact_fit-exact_truth)**2)))
"""))
cells.append(nbf.v4.new_markdown_cell("""## Held-out forward checks

These points exercise shallow contact, deeper contact, and unequal mass. They compare a fast surrogate forward curve to native PHOEBE; they are not parameter-recovery or uniqueness tests."""))
cells.append(nbf.v4.new_code_cell("""RUN_HELDOUT_FORWARD = False
HELDOUT = [
    dict(name="shallow", inclination=86., mass_ratio=.82, fillout_factor=.12, temperature_ratio=.92),
    dict(name="deep", inclination=82., mass_ratio=.90, fillout_factor=.44, temperature_ratio=.88),
    dict(name="unequal", inclination=87., mass_ratio=.50, fillout_factor=.28, temperature_ratio=.95),
]
if RUN_HELDOUT_FORWARD:
    for case in HELDOUT:
        name = case.pop("name")
        xp, yp = contact_preview(**case)
        xn, yn = native_flux(**case, phases=xp)
        print(name, "normalized-flux RMS", np.sqrt(np.mean((yp-yn)**2)), "max", np.max(np.abs(yp-yn)))
        case["name"] = name
"""))
cells.append(nbf.v4.new_markdown_cell("""## Portability notes

- **Colab:** run the install cell on a free CPU runtime. Widget callbacks, if added, cross the Colab kernel boundary; native PHOEBE is also kernel-side.
- **JupyterLab:** install PHOEBE in the selected kernel. Modern JupyterLab includes ipywidgets support; this notebook’s plain cells work without widgets.
- **Classic Notebook:** select the environment where PHOEBE 2.5.4 is installed. The plotting and fitting cells are otherwise unchanged.
- The embedded preview is the exact frozen branch artifact, not retrained in the notebook. Training provenance and validation metrics live in `experiments/contact/REPORT.md`.
"""))
nb["cells"] = cells
out = ROOT / "notebooks/PHOEBE_Contact_Binary_Colab.ipynb"
out.parent.mkdir(parents=True, exist_ok=True)
nbf.write(nb, out)
print(out)
