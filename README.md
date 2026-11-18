# PHOEBE Lab

**[Open the live app on GitHub Pages](https://paulnord.github.io/phoebe-lab-preview/)**

An original, browser-based eclipsing-binary light-curve explorer. The browser
runs **real PHOEBE 2.5.4**, including its compiled C++ extensions, through
Pyodide/WebAssembly. GitHub Pages serves static files only; no PHOEBE server,
JupyterHub account, API key, or connection to boole is required.

## Use the lab

Open the site in a recent desktop browser. The initial download is about 60 MB
of runtime and scientific packages; model initialization can take a while.
Downloads are subject to the browser's HTTP cache. Keep the tab open while
calculations finish. The Stop button terminates the worker and reloads the
engine, leaving the interface responsive.

In Preview quality, drag a supported slider to see a broad, translucent approximate
curve. Release to calculate the PHOEBE curve. Fitting, residual statistics and CSV
exports use the current PHOEBE result.

- At the default circular orbit, vary inclination, either fractional radius and
  temperature ratio together. Keep the other settings at their defaults.
- Starting from defaults, vary eccentricity from 0 to 0.24 with either
  inclination or periastron angle. Other combinations calculate on release.

The display model uses limb-darkened spherical discs for the circular family and
interpolated PHOEBE curves for the eccentric pairs. The two paired families met
the display flux criteria on 96 held-out combinations (pooled RMS 0.00096,
largest absolute error 0.0132 in median-normalized flux).

Move sliders to calculate a new light curve. Preview uses 81 orbital phases and
400 triangles per star; Refined uses 201 phases and 1,500 triangles per star.
The synthetic example is explicitly labeled and was generated with PHOEBE.
It is observational input, not a library of precomputed models.

Load CSV, TSV, or whitespace-separated text with coordinate, brightness, and
optional uncertainty columns. Explicitly choose phase or time and flux or
magnitude. Time data require a period and primary-eclipse epoch in the same
time system. No UTC/HJD/BJD conversion is performed. Magnitudes and their
uncertainties are converted to relative flux before comparison.

The plot overlays observations and the calculated model, with residuals,
RMS and reduced chi-square when measurement uncertainties are available.
A weighted multiplicative flux normalization is fitted for every comparison.
Save session downloads parameters and observations as JSON; Load data restores
that JSON. Export model CSV downloads the computed phase and flux values.
Files are processed locally. There is no observation-upload or analytics endpoint.

## Scope of this demonstration

The starting model uses spherical stars for faster interaction. Switch on
**Tidal distortion** to compute Roche surfaces; those calculations can take
minutes per model in the browser. Irradiation is also optional. All modes use
PHOEBE's numerical engine, including mesh generation and eclipse integration.
On the development machine, the browser took about 5.5 seconds for the first
spherical preview, 1.8 seconds for an inclination change, and 10.5 seconds for
a seven-evaluation one-parameter fit. These are measurements, not guarantees;
loading time and performance depend on the device and model.

The model is a detached binary in Johnson V with primary mass 1.2 solar masses,
primary temperature 6,300 K, a Keplerian orbit, PHOEBE atmosphere/limb-darkening
defaults, selectable Roche distortion and irradiation. Radii are fractions of
semimajor axis. The star illustration is a size guide, not an orbital animation.
Other PHOEBE features such as radial velocities, spots, third light, other
passbands, contact binaries and posterior sampling are not exposed here.

The optional fit uses SciPy bounded least squares and calls real PHOEBE for
each evaluation. Select at most two of inclination, radii and temperature ratio.
It starts from the current sliders, uses preview resolution, and has a short
iteration budget. Inspect residuals and parameter degeneracies; a stopping
message is not evidence of a unique physical solution or an uncertainty estimate.
Reduced chi-square accounts for fitted normalization and the selected fit values.

## Run the already-built site locally

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory site
```

Open http://127.0.0.1:8765/ . Opening index.html directly as a file will not work.
The host Python only serves files; the browser performs all model calculations.
For access from another computer, serve the static directory with your chosen
web server, preferably HTTPS. No special cross-origin isolation headers are
required because the scientific worker runs serially.

## Build from source

On Linux with Python 3.14 and a C/C++ host toolchain:

```sh
python3.14 tools/build_engine.py
```

The script creates an isolated `.build/venv`, installs pyodide-build 0.39.3 and
the Pyodide 314.0.8 cross environment (which fetches Emscripten 5.0.3), verifies
pinned source archives, compiles ndpolator 1.3.1 and PHOEBE 2.5.4, and vendors
the runtime packages. It requires internet access and roughly 3 GB of temporary
disk space. It does not install anything into JupyterHub or change system Python.
The generated `site/` directory is the complete deployment artifact.

PHOEBE source commit: `cbbd79cee12296b1fe7eeb0662898450a9567cfd`.
The C++ and scientific Python sources are unchanged. The build-only NumPy
constraint is adjusted for Python 3.14, terminal tab completion is optional,
and server configuration discovery uses Python filesystem access instead of a
shell. Large trained KNN estimator data, unused by this interface, are omitted.
The exact adjustments are in `tools/package_browser_wheel.py`.

The deployment includes source archives and these build scripts under `source/`
and licenses in `LICENSE.txt`, `NOTICE.txt` and the scientific package wheels.
The app links its interface source and notices from How it works.

## GitHub Pages

Create a public repository and choose **Settings → Pages → Source → GitHub Actions**.
Push this project to its `main` branch. The included workflow builds the engine,
runs a real Chromium calculation and native-reference comparison, then publishes
the static artifact. Generated wheels, sources and runtime files stay out of Git;
the build assembles them in the deployment artifact. Relative asset paths support
a project URL such as `https://paulnord.github.io/phoebe-lab-preview/`.

## Verify

With a built site served locally:

```sh
python3 -m pip install numpy playwright
python3 -m playwright install chromium
python3 tests/browser_smoke.py http://127.0.0.1:8765/
```

The reference curve in `tests/native-reference.json` was produced by the same
model wrapper using native PHOEBE 2.5.4. Tests run the WebAssembly engine, compare
the actual calculated curve, and exercise user controls and data import.
The spherical model is compared at an absolute tolerance of 1e-7 in normalized
flux. An independent local comparison agreed to roughly 1e-11. The coarse Roche
mesh showed platform differences up to 0.00082; inspect resolution convergence
before drawing scientific conclusions from small differences.

Regenerate the synthetic data and reference using native PHOEBE with
`python tools/generate_example.py`. Identical parameter sets reuse a small
in-memory geometry cache, so changing only the observations avoids repeating
the surface calculation. New physical parameter values are calculated by PHOEBE.

GPL-3.0-or-later. See LICENSE and NOTICE.txt. Independent educational prototype;
not an official PHOEBE distribution or a complete scientific analysis pipeline.
