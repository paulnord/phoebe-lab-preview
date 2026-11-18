# Browser workers on a tidal light curve

One complete local Chromium run per count, using PHOEBE 2.5.4 and Chromium
159.0.8154.6 on Linux. Each run loaded the opening spherical example first,
then set inclination to 83.7° and enabled Roche tidal distortion. The model used
a circular 1.8-day orbit, mass ratio 0.75, fractional radii 0.21 and 0.17,
temperature ratio 0.84, Johnson V, 400 mesh triangles per star and heating off.
The selected geometry has no stored reference. Timings start at the custom
calculation request and include initialization of its extra PHOEBE workers.

| Workers | First 5 phases (s) | All 513 phases (s) | Speedup | Peak memory (GiB) |
|---:|---:|---:|---:|---:|
| 1 | 5.0 | 308.2 | 1.00× | 0.97 |
| 2 | 4.9 | 167.2 | 1.84× | 1.41 |
| 3 | 4.8 | 123.4 | 2.50× | 1.81 |
| 4 | 4.7 | 98.6 | 3.13× | 2.37 |
| 5 | 4.9 | 86.5 | 3.56× | 2.55 |
| 6 | 4.8 | 77.1 | 4.00× | 2.91 |
| 7 | 4.8 | 77.0 | 4.00× | 4.01 |
| 8 | 4.8 | 76.0 | 4.06× | 4.41 |

Every final flux and every observation residual matched the one-worker result
exactly for all eight counts. Peak memory is summed proportional set size across
the Chromium and Playwright child processes, sampled every three seconds.
Shorter peaks may have been missed. The test used a shared machine at low
scheduling priority, with CPU affinity limited to logical CPUs 24–31. The
one-worker run overlapped part of the seven- and eight-worker measurements.
Other existing workloads continued throughout. Treat differences of a few
seconds as indistinguishable in this single-run comparison.

On this machine six workers finished within two seconds of eight while saving
approximately 1.5 GiB. Four workers completed the curve in under 100 seconds
with about 2.4 GiB. One worker is the default for smaller devices. The first
five points arrived in about five seconds at every count because the primary
worker draws those points before starting helpers. These timings cover this
Preview mesh and geometry. A Mac, a finer mesh or a different binary may give
different timings.

To reproduce the sweep or verify individual fluxes, see the browser worker
benchmark commands in the [project README](../README.md#browser-worker-benchmark).
