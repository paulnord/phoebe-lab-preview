# Semi-detached preview training report

Native source: PHOEBE 2.5.4 `default_binary(semidetached=donor)` constraints
Baseline: `b7ce074c8231cc8db9bc2e4016b667071daaa845`
Artifact SHA-256: `34e614ac4fd0ce2101fd1bc54bbf1e03940c59d5531aae877bcf7e436a8e28cd`

Each donor: 192 train / 48 tune / 64 untouched test physical systems; splits use independent seeds and never share phase samples.

Domain: inclination 65–90°, q 0.40–1.30, free-star Roche-fill fraction 0.25–0.82, T2/T1 0.76–1.14. Fixed P=1.8 d, M1=1.2 solar masses, T1=6300 K, Johnson:V, circular synchronous orbit, irradiation off.

Native timing: median 3.992 s, p95 12.548 s per curve; 0 retries at 1,500 and 0 at 3,000 triangles.

Generation used four local workers. The complete 648-system native run (train,
tune, untouched test, and slider sweeps for both donor choices) took 828.486 s
(13.8 min) wall time. Model fitting and export took seconds; validation and app
integration were tracked separately from generation time.

## Controlled native recovery benchmark

The Colab notebook's opt-in benchmark generated a total-eclipse primary-donor
system at inclination 88.0 degrees and free-star fill 0.58, then fit only those
two parameters on 65 native phases. Donor, q=0.75, T2/T1=0.90, and period were
deliberately fixed. With physically resolvable finite-difference steps, the
bounded fit converged to 87.993427 degrees and 0.58000846. A separate 513-phase,
1,500-triangle native recompute had normalized-flux RMS 0.00002072 against the
truth. This is a controlled recovery check, not evidence that photometry uniquely
identifies q in a general partial-eclipse system.

## Primary donor

Tune RMS used for model selection: 0.001342

| Regime | N | pooled RMS | p95 curve RMS | p95 absolute | worst absolute |
| --- | ---: | ---: | ---: | ---: | ---: |
| all | 64 | 0.001434 | 0.002866 | 0.002247 | 0.020073 |
| grazing | 17 | 0.000943 | 0.001568 | 0.001827 | 0.011469 |
| near_free_lobe | 12 | 0.001775 | 0.003404 | 0.002834 | 0.017209 |
| unequal_mass | 24 | 0.001579 | 0.002866 | 0.002912 | 0.017209 |

Slider-response validation compares native and surrogate difference vectors; cosine measures shape/direction agreement rather than pointwise curve RMS.

| Anchor | Parameter | native response RMS | difference RMS | cosine | relative norm error |
| ---: | --- | ---: | ---: | ---: | ---: |
| 0 | inclination | 0.003815 | 0.000139 | 0.9994 | 0.0145 |
| 0 | mass_ratio | 0.001800 | 0.000540 | 0.9639 | 0.1738 |
| 0 | free_fill | 0.002953 | 0.000323 | 0.9973 | 0.0786 |
| 0 | temperature_ratio | 0.002667 | 0.000214 | 0.9973 | 0.0291 |
| 1 | inclination | 0.002770 | 0.000584 | 0.9814 | 0.0691 |
| 1 | mass_ratio | 0.000708 | 0.000534 | 0.8481 | 0.3842 |
| 1 | free_fill | 0.002137 | 0.000668 | 0.9590 | 0.1725 |
| 1 | temperature_ratio | 0.008025 | 0.000717 | 0.9967 | 0.0402 |
| 2 | inclination | 0.000550 | 0.000208 | 0.9292 | 0.0146 |
| 2 | mass_ratio | 0.003272 | 0.000755 | 0.9801 | 0.0980 |
| 2 | free_fill | 0.005011 | 0.000526 | 0.9971 | 0.0688 |
| 2 | temperature_ratio | 0.002749 | 0.000300 | 0.9949 | 0.0372 |
| 3 | inclination | 0.004595 | 0.000292 | 0.9980 | 0.0025 |
| 3 | mass_ratio | 0.001049 | 0.000318 | 0.9535 | 0.0159 |
| 3 | free_fill | 0.004433 | 0.000234 | 0.9988 | 0.0183 |
| 3 | temperature_ratio | 0.004572 | 0.000152 | 0.9997 | 0.0241 |

## Secondary donor

Tune RMS used for model selection: 0.001870

| Regime | N | pooled RMS | p95 curve RMS | p95 absolute | worst absolute |
| --- | ---: | ---: | ---: | ---: | ---: |
| all | 64 | 0.002036 | 0.003811 | 0.003111 | 0.036466 |
| grazing | 18 | 0.001181 | 0.002375 | 0.002155 | 0.012168 |
| near_free_lobe | 12 | 0.001693 | 0.003282 | 0.003168 | 0.022380 |
| unequal_mass | 23 | 0.002711 | 0.006226 | 0.003791 | 0.036466 |

Slider-response validation compares native and surrogate difference vectors; cosine measures shape/direction agreement rather than pointwise curve RMS.

| Anchor | Parameter | native response RMS | difference RMS | cosine | relative norm error |
| ---: | --- | ---: | ---: | ---: | ---: |
| 0 | inclination | 0.005787 | 0.000759 | 0.9934 | 0.0708 |
| 0 | mass_ratio | 0.002135 | 0.000377 | 0.9853 | 0.0588 |
| 0 | free_fill | 0.003540 | 0.000691 | 0.9822 | 0.0350 |
| 0 | temperature_ratio | 0.003794 | 0.000453 | 0.9938 | 0.0503 |
| 1 | inclination | 0.001334 | 0.000678 | 0.9450 | 0.3343 |
| 1 | mass_ratio | 0.002158 | 0.000459 | 0.9776 | 0.0091 |
| 1 | free_fill | 0.003869 | 0.000587 | 0.9935 | 0.1064 |
| 1 | temperature_ratio | 0.006242 | 0.001008 | 0.9901 | 0.0895 |
| 2 | inclination | 0.004137 | 0.001904 | 0.8904 | 0.1771 |
| 2 | mass_ratio | 0.003529 | 0.001307 | 0.9574 | 0.2746 |
| 2 | free_fill | 0.007019 | 0.000558 | 0.9971 | 0.0201 |
| 2 | temperature_ratio | 0.006824 | 0.000426 | 0.9981 | 0.0126 |
| 3 | inclination | 0.006608 | 0.000192 | 0.9996 | 0.0100 |
| 3 | mass_ratio | 0.000471 | 0.000069 | 0.9891 | 0.0155 |
| 3 | free_fill | 0.004126 | 0.000189 | 0.9991 | 0.0200 |
| 3 | temperature_ratio | 0.007000 | 0.000348 | 0.9993 | 0.0309 |

## Limits

Display-only preview. Native PHOEBE is authoritative for fitting, statistics, and exports. Photometric q can remain degenerate, especially for grazing/partial eclipses; RV curves provide complementary constraints. No disks, streams, spots, eccentric semi-detached systems, irradiation preview, or joint photometry/RV inference is included.
