# Native Colab phase-worker benchmark

This bounded benchmark compares serial PHOEBE 2.5.4, an explicit two-rank MPI
launch, and the persistent Python-process phase workers used by the Colab
workbench. It changes no scientific defaults. Commands were run on the review
computer with nine affinity CPUs, no detected cgroup quota, one thread per
process, offline passbands, and the repository's native Contact wrapper.

## MPI pilot

`mpiexec -n 2` started ranks 0 and 1 with distinct PIDs and PHOEBE reported
`internal handling of mpi within mpirun`. On the same 65-phase Contact model,
serial compute took 2.832 s and explicit two-rank MPI took 3.135 s. Both produced
the identical normalized-flux SHA-256
`0862dae4a4bfeb008acb575eb00256431c595f2421de0b781e0ad9ca0a8035f7`.
The repeated startup and small batch made MPI slower. The notebook therefore
does not call `phoebe.mpi_on`: PHOEBE 2.5.4 can route that call through a
separate default job launcher, which is not the persistent notebook bridge.

## Persistent native processes

The implemented pool keeps one independent PHOEBE model in each helper and
uses the notebook process as worker one. The first five real phases remain on
the notebook process, so the first plot update does not wait for helper startup.
Affinity and cgroup quota determine the truthful selector range, capped at four
workers to bound memory. Colab selects that truthful maximum by default, while
one and every lower supported count remain explicit choices.

| 129-phase Contact run | Serial first / total | Two-worker first / total | Parity |
| --- | ---: | ---: | --- |
| Cold | 2.55 / 9.36 s | 2.40 / 8.43 s | exact hash match |
| Warm, new fill-out | 0.56 / 7.09 s | 0.51 / 4.49 s | exact hash match |

The paired final flux hashes were identical for both cold and warm geometries.
The run produced the same cumulative partial sequence (5, 9, 17, …, 121, then
129 final phases).

A real one-parameter Contact fit used 14 identical objective evaluations and
returned the exact same fitted parameter dictionary and final flux hash in both
modes. Serial total time was 36.08 s; two-worker total time was 25.43 s. The fit
search itself took about 12.8 s in either mode and remains serial; the speedup is
in the authoritative final exact curve.

Cancellation was issued while a two-worker wave was running. The stream ended
with `RuntimeError: Cancelled.`, the helper pool was removed, and a subsequent
129-phase two-worker Contact calculation completed successfully with a fresh
pool. Native cancellation is batch-bounded; it cannot interrupt PHOEBE inside
one already-running phase call.

A repeat of the curve and cancellation benchmark after the implementation was
finalized produced exact serial/two-worker hashes again. On that run the warm
129-phase Contact totals were 6.66 s and 4.02 s respectively, the helper count
after cancellation was zero, and the fresh-pool restart returned all 129
phases.

The maximum-default follow-up exercised four actual workers on this machine.
The cold totals for 1/2/4 workers were 8.45/7.43/5.96 s; warm totals were
7.15/4.02/2.52 s. All three counts produced the same cold and warm hashes, and
the four-worker result reported three live helper PIDs plus the notebook
process.

## Standalone browser

MPI is not a useful or available execution model inside the static WebAssembly
site: browser workers are isolated JavaScript/WebAssembly agents, not operating
system processes in an MPI communicator. The standalone workbench already uses
one primary Pyodide Web Worker plus independent helper Web Workers for eligible
phase waves, combines absolute flux before normalization, and releases helpers
on completion or cancellation. No hosted MPI service or browser fallback was
added.

Reproduce the explicit rank pilot with `benchmark_mpi.py`. Reproduce serial,
two-worker, fit-parity, and cancellation checks with
`benchmark_workers.py --fit --cancel`. Timing varies by runtime; hashes and
worker/routing assertions are the acceptance criteria.
