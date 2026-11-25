# PHOEBE Lab

**[Open PHOEBE Lab on GitHub Pages](https://paulnord.github.io/phoebe-lab-preview/)**

An original, browser-based eclipsing-binary light-curve explorer. The browser
runs **real PHOEBE 2.5.4**, including its compiled C++ extensions, through
Pyodide/WebAssembly. GitHub Pages serves static files only; no PHOEBE server,
JupyterHub account, API key, or connection to boole is required.

Feature-branch reviews can use a commit-pinned raw.githack URL. The reviewed
HTML, JavaScript, trained models, and Python solver wrapper come from that exact
commit. Because generated Pyodide and wheel files are intentionally excluded
from git, only this preview host reuses the identical runtime artifacts from the
current public PHOEBE Lab build. Production Pages and local builds remain fully
same-origin. raw.githack shows a third-party-content notice on first open.

> **Geometry feature branches:** the standalone lab supports geometry-specific Detached, Semi-detached, and Contact previews without deploying from the branch. Geometry is a visible top-level model choice; semi-detached then asks which donor fills its lobe, while contact replaces the two radii with one shared-envelope fill-out factor. Its orbit viewer builds a native phase-zero PHOEBE mesh for constrained systems, then animates the cached co-rotating geometry locally. The [`PHOEBE Lab Colab notebook`](notebooks/PHOEBE_Semi_Detached_Binary_Colab.ipynb) ([open the fitting workbench in Colab](https://colab.research.google.com/github/paulnord/phoebe-lab-preview/blob/semi-detached/notebooks/PHOEBE_Semi_Detached_Binary_Colab.ipynb)) launches this same workbench—observation loading, plots, fit, residuals, export, RVs, and orbit viewer—rather than a separate widget UI. Run its cells and use the iframe they create: exact Compute and Fit fail closed unless that iframe can reach the notebook's native Python bridge; they never fall back to browser WebAssembly. The separate [`semi-detached validation notebook`](notebooks/PHOEBE_Semi_Detached_Validation.ipynb) preserves training-reproducibility checks and is not the fitting workbench. Generation and validation live under [`experiments/semi_detached/`](experiments/semi_detached/) and [`experiments/contact/`](experiments/contact/).

## Developer design specification

See the [PHOEBE Lab design specification](docs/PHOEBE_LAB_DESIGN_SPEC.md) for the feature ledger, runtime contracts, scientific assumptions, and rebuild acceptance checks. Update the relevant feature IDs and checks when changing observable behavior.

## Use the lab

Open the site in a recent desktop browser. The initial download is about 60 MB
of runtime and scientific packages; model initialization can take a while.
Downloads are subject to the browser's HTTP cache. Keep the tab open while
calculations finish. Stop ends ordinary refinement after the current batch. For costly tidal or irradiated models it stops the worker immediately.

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

With spherical stars and heating off, the sharp PHOEBE line appears at 65 uniformly spaced phases.
Three midpoint passes yield nested 129-, 257- and 513-point grids. PHOEBE sends
updates in batches of 64 new points. Preview uses 400 triangles per star and
Refined uses 1,500. Only the final grid supplies the displayed statistics and CSV.
Local Fit can vary any subset of the eight physical sliders, holding the epoch fixed.
The search defaults to 129 model phases. Choose 65 for a quick fit or 513 to
resolve narrow eclipse structure. Every trial uses the selected mesh and all
observations. PHOEBE fills the missing phases of the winning trial for the
513-point plot. Period fits refold timestamped data and preserve exposure identity
and uncertainty weights throughout the search.
RMS, reduced chi-square and the exported CSV use this final curve. Reduced
chi-square accounts for the selected fit parameters and flux normalization.
Tidal plots stop at 129 phases by default. Under **Surface physics and compute → Native curve phases**,
select **513** for a closer look at narrow eclipses. For the same geometry and mesh,
PHOEBE fills the missing phases of a completed 129-point calculation. The residuals
and CSV use the completed plot grid. Heating alone uses 513 phases.
At the opening settings, Preview has exact saved 513-point PHOEBE curves for
tides, heating and both together. Other surface models start with five actual
phase points. Under **Surface physics and compute → Compute workers**, choose 1–8 browser
workers. The first five points come from the primary worker. Additional workers
calculate disjoint phase batches with identical PHOEBE settings. The primary
worker combines absolute fluxes before normalization. Helpers are released at
completion or cancellation. The default is one worker. Local Fit evaluates its trials serially and reuses the winning trial for the final plot.
The synthetic example is explicitly labeled and was generated with PHOEBE.
It is observational input, not a library of precomputed models.

The local three-orbit-slider model also allows inclination, eccentricity and
periastron angle to move together through 65–90°, 0–0.24 and 0–360° with the
remaining inputs at their defaults. A broad amber drag curve marks other spherical,
non-irradiated combinations inside the UI ranges. It solves the eccentric orbit
with limb-darkened discs and applies the trained eight-slider Fourier correction. Mass ratio and period affect surface gravity. The legend
says when gravity is clamped at the atmosphere table edge. Exact PHOEBE can reject
some settings, in which case CSV export, fit and residual statistics stay unavailable.
Turning an effect off restores a matching completed exact result immediately if
available. Eight results are retained for the current observation dataset.

On two measured parameter slices, the amber drag curve includes Roche tides,
Horvat irradiation, or both. Load **Non-eclipsing binary (30°)** and drag
inclination between 18° and 46° to try it. The legend identifies the effects
included. Where only a spherical preview is available, its label lists the omitted effects.
On release the exact worker computes the curve for comparison and export.
[Study results and supported settings](benchmarks/literature-surfaces/REPORT.md)

## Radial velocities

The main lab plots both stars’ predicted line-of-sight orbital velocities in
km/s on the light curve’s phase grid. Solid purple is the primary and dashed
teal is the secondary. K₁ and K₂ give their velocity semi-amplitudes. The
Keplerian calculation uses the same primary mass (1.2 solar masses), mass
ratio, period, inclination, eccentricity and periastron angle as the lab.
It updates during a drag even while the photometric worker is busy.

The reference velocity is the binary center of mass. These curves describe
orbital motion alone; spectroscopic surface effects such as the
Rossiter–McLaughlin anomaly require a flux-weighted RV calculation. Use the
advanced PHOEBE workspace for native RV datasets. The main fitter and its
residual panel use the light-curve observations.

Inclination runs from 0° to 90°. At 0°, both velocities are zero at every
phase. Below the photometric surrogate’s training range, releasing the slider
computes the light curve with PHOEBE.

For the eccentric example, swipe the period slider to see the velocity
amplitudes change. The axis expands to fit larger velocities and keeps that
scale for comparison as the velocities decrease. **Rescale velocity axis**
fits the current pair of curves.

## Example curves

Choose a curve in **Examples** above the chart and click **Load**. The original
synthetic example starts at the lab defaults for fitting practice. Four additional
synthetic datasets start at the generating parameters. The grazing and deep
primary examples use the wide-study 512-phase, 1,500-triangle reference curves.
The eccentric example uses the eight-slider study at the same resolution.
**Non-eclipsing binary (30°)** shows the same orbit at a lower inclination with tidal
distortion enabled. The refined PHOEBE curve varies by 2.34% of its median flux
from minimum to maximum, compared with 0.023% using spherical stars. Switch
**Tidal distortion** off to compare the brightness curves. The orbital RV
semi-amplitudes stay at 18.6 and 39.5 km/s.
Each synthetic dataset in this group has 240 sampled phases with seeded Gaussian measurement noise.
Regenerate the 30° example with native PHOEBE using `python tools/generate_non_eclipsing.py`.

The same picker also includes two published Johnson V datasets. **SZ Her**
selects Semi-detached with the secondary donor and the observing-run ephemeris;
**V1128 Tau** selects Contact and uses its spectroscopic mass ratio of 0.534 as
starting guidance. Its published deeper-minimum epoch remains HJD 2454842.3470;
the preset initializes PHOEBE `t0_supconj` one half-period later at HJD
2454842.4996855 to align the model conjunction convention, without changing q
or any observation timestamp. These entries contain the original timestamps and
differential magnitudes without invented point uncertainties. Loading starts a
native forward calculation, never an automatic fit. See
[`site/examples/OBSERVATIONS.md`](site/examples/OBSERVATIONS.md) for provenance,
starting values and model limitations.

**Kepler · KIC 4544587** contains 432 measured long-cadence points with catalog
phases, detrended fluxes and their reported uncertainties. The initial geometry
uses published parameters rounded to slider steps. The main lab uses Johnson V
and a fixed primary temperature and mass, so the overlay is illustrative.
The static JSON includes provenance and loads without contacting the catalog.
[Catalog target](https://keplerebs.villanova.edu/overview/?k=4544587) ·
[Hambleton et al., Table 6](https://doi.org/10.1093/mnras/stt886)

[Open the unfolded Kepler example](https://paulnord.github.io/phoebe-lab-preview/?example=kepler-4544587-time)

**Kepler · KIC 4544587 (unfolded)** uses the original timestamps of 1,297
measurements from the first 28 days of the same catalog light curve. The upper
plot shows observed flux against days since the first observation (catalog BJD
minus 2400000). Dashed guides mark phase zero. The lower plot folds the same
measurements using the editable epoch and period. The catalog values are
54954.135787 and 2.1890973 days. Timestamped data start with the period slider
centered on the loaded value over ±0.001 day. Choose ±0.00001 day for the
closest mouse adjustment, or use left/right arrows on a zoomed slider for
0.0000001 day (8.64 ms) per step. Typing a period recenters the zoom. Try
2.25 days in the number field to see the eclipses spread out.
The epoch slider has the same fine step and zoom choices, with a one-day
span available for larger offsets. Changing only epoch refolds the timestamps,
reuses the current complete physical curve, and updates its normalization and
statistics. During a timing drag the residual plot follows the displayed curve.
Its heading identifies a completed PHOEBE curve, a display approximation, an
earlier period, or a partially refined PHOEBE curve. Numeric RMS and reduced
chi-square appear when the current exact comparison finishes.
Eccentricity has a full 0–0.35 range with 0.001 steps and a ±0.01
zoom with 0.0001 steps. Typing into either field recenters its slider.
Reopen the example to restore the catalog ephemeris. A saved session retains
the original timestamps and your chosen ephemeris.

Rebuild the additional examples with `python tools/example_library.py /home/pnord/scratch`
in the native NumPy environment. The script checks the source photometry checksum.

## Native PHOEBE files

Choose **Advanced PHOEBE → Open file** for a PHOEBE 2.x JSON bundle or model
ParameterSet. The native file workspace uses its own PHOEBE 2.5.4 worker. A loaded
bundle retains its datasets, components, saved models and compute options.
Select a native PHOEBE compute set and orbit to edit unconstrained orbital values
and calculate a new named model. Save the complete bundle as `.phoebe` or a
selected model as `.model`. Open a standalone model for inspection, or attach it
to a bundle containing the matching datasets and components. The native plot uses
time in days and the parameter's physical units for light curves and radial velocities.

**Create from lab** constructs a bundle from the current authoritative settings and
observations using PHOEBE. Time inputs keep their timestamps. Phase observations
are mapped to times with the lab period and epoch. Relative photometry and its
uncertainties are scaled to the physical flux normalization of the model.
This workspace uses local PHOEBE compute configurations and the passbands packaged
with the browser. Uniform, Gaussian and delta scalar distribution records can be reopened. Files with detached jobs, custom executable objects or
unsupported custom constraint expressions report an import error. The native PHOEBE
reader handles earlier 2.x versions it can migrate. PHOEBE 1.x files use a different
format.

**Create bundle** starts a detached, contact or semi-detached system. Filter by
context or search PHOEBE parameter names in the resulting bundle. Select a row
to see its unit, description, choices and current value. Apply edits to the bundle
before calculating. PHOEBE derives constrained values and supplies candidate
variables for constraint flips. The parameter catalog changes when the physics,
datasets or solvers change. Model and solution arrays are available for inspection.
Use **Save bundle** to retain edits between visits.

**Datasets, physics and solvers** provides the five dataset types, native forward
compute sets, spots, RV offsets and scikit-learn Gaussian processes. Choose one
of the 12 solver configurations in PHOEBE 2.5.4. Configure it in the solver
context before running. Results appear in the solution context. **Adopt solution**
applies the solution’s selected parameters to the active bundle. Free scalar
parameters accept uniform and Gaussian distributions. Browser-native samplers
run serially. A Chromium smoke test exercised a two-iteration emcee chain.
A test initializing from and bounding with the same uniform distribution triggered
an upstream spline error with the default prior-intersection initialization.
Selecting PHOEBE checks for initial positions allowed that small run to complete.
Model calculations and solver runs operate on a copy, and Stop
preserves the previous native document. External forward-model executables,
remote job submission, celerite2 and the EBAI KNN training tables are outside
this WebAssembly build. EBAI uses its MLP option. The figure editor and desktop
plotting windows are not reproduced in this lab. Figure parameters travel with
the native file. The advanced worker loads its libraries from the same static site.

A default detached binary with one Johnson V light curve in PHOEBE 2.5.4 exposes
70 editable physics/dataset/compute/system entries with standard filtering and
85 when advanced fields are shown. The latter have 64 distinct qualifiers.
Component-specific values count separately. These numbers exclude constrained
outputs, figures, application settings and the hierarchy object.

Desktop interoperability can be checked with `phoebe.open("system.phoebe")` and
`b.import_model("saved.model", model="readback")`. The file check can be reproduced
with `tests/native_fixtures.py generate DIRECTORY` in a PHOEBE installation,
`tests/native_files_browser.py BUILT_SITE DIRECTORY` in a Playwright installation,
then `tests/native_fixtures.py verify DIRECTORY` in desktop PHOEBE.

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
The progressive browser test times the first exact stage and every subsequent batch, excluding engine startup. Timing depends on model geometry and the device.

The model is a detached binary in Johnson V with primary mass 1.2 solar masses,
primary temperature 6,300 K, a Keplerian orbit, PHOEBE atmosphere/limb-darkening
defaults, selectable Roche distortion and irradiation. Radii are fractions of
semimajor axis. The compact star illustration is a size guide. The separate orbit
viewer animates detached shapes directly and, for semi-detached/contact modes,
animates a cached native PHOEBE mesh after the browser engine has built it.
Open Advanced PHOEBE to work with a native bundle, including contact or semi-detached binaries, spots, third light and radial velocities.

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

## Browser worker benchmark

[Measured time, memory and curve agreement for one through eight workers](benchmarks/surface-workers.md)

With Chromium installed for Playwright, run these commands from this checkout.
The URL should point at a served build with its browser runtime and PHOEBE wheels.
Each count runs in a fresh browser that first completes the opening spherical
curve. Timings start when the main worker receives the custom-model request and
include startup of the extra workers. Each completed count checkpoints the
parameters, phases, model, residuals, update times, browser version and sampled
Linux process-tree memory in its own JSON file. Reuse the output directory to
resume. The second command verifies against one worker and prints the summary.

```tcsh
python tools/benchmark_browser_workers.py http://127.0.0.1:8765/progressive-lab/ worker-results 1 2 3 4 5 6 7 8
python tools/benchmark_browser_workers.py http://127.0.0.1:8765/progressive-lab/ worker-results
```

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
The 513-phase spherical model is compared against native PHOEBE at an absolute
tolerance of 3e-6 in normalized flux. In Chromium the staged curve and a separate
single-call calculation at the same phases are compared at 1e-10. The coarse Roche
mesh showed platform differences up to 0.00082; inspect resolution convergence
before drawing scientific conclusions from small differences.

Regenerate the synthetic data and reference using native PHOEBE with
`python tools/generate_example.py`. Identical parameter sets reuse a small
in-memory geometry cache, so changing only the observations avoids repeating
the surface calculation. New physical parameter values are calculated by PHOEBE.

GPL-3.0-or-later. See LICENSE and NOTICE.txt. Independent educational prototype;
not an official PHOEBE distribution or a complete scientific analysis pipeline.
