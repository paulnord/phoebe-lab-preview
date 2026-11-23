# Contact-binary preview training report

Frozen model: `contact-rbf-fourier-v1`

Native source: PHOEBE 2.5.4, `default_contact_binary()` with native fill-out → envelope-potential constraint

Split: 128 scrambled-Sobol physical systems for training (seed 42017); 64 independent physical systems for validation (seed 89173). Orbital phase samples from a system never cross splits.

Native artifact SHA-256: `eb4936db6d19f602c227b462bf2b0969d9b83d59dbad750a7af2f7ff2b85d2e9`

Repository baseline: `40b350956d177be2fd078fd4c5ddd6735224214c`

## Physical and numerical scope

- Inclination: 65.0–90.0°
- Mass ratio q=M₂/M₁: 0.45–1.2
- Fill-out factor: 0.1–0.5
- T₂/T₁: 0.78–1.12
- Fixed: P=1.8 d, M₁=1.2 M☉, T₁=6300 K, Johnson:V, irradiation off, circular synchronous contact envelope.
- Native targets: 129 phases including the repeated endpoint. The deterministic mesh policy uses 800 triangles per component, retries at 1,500 after a native mesh/projection failure, and finally at 3,000 if needed; 4 and 0 of 192 systems required those retries respectively.
- Median native time per curve: 2.283 s; p95 3.674 s.

The lightweight model projects curves onto 48 cosine harmonics and uses Gaussian RBF ridge regression over the four scaled physical coordinates. It fails closed outside the rectangular bounds, at non-default period, with irradiation, and when the nearest scaled training-system distance exceeds 0.6631.

## Independent held-out errors

All errors use median-normalized flux. Depth error is the absolute error in primary/secondary eclipse depth. Ingress/egress error is the absolute phase error of the nearest sampled half-depth crossing; its floor is limited by the 129-point native grid.

| Regime | N | pooled RMS | p95 curve RMS | p95 absolute | worst absolute | p95 depth | p95 ingress/egress phase |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| all | 64 | 0.008551 | 0.017097 | 0.018668 | 0.040776 | 0.015250 | 0.00781 |
| shallow_contact | 13 | 0.011231 | 0.021599 | 0.034845 | 0.040776 | 0.028334 | 0.00352 |
| deep_contact | 24 | 0.010482 | 0.023927 | 0.025058 | 0.034943 | 0.017978 | 0.00781 |
| unequal_mass | 21 | 0.011590 | 0.024994 | 0.031575 | 0.040776 | 0.022621 | 0.00664 |

## Limits

This preview is a display surrogate, not a likelihood or uncertainty model. Contact photometry can have strong q/fill-out/inclination/temperature degeneracies. Native PHOEBE recomputation is authoritative for fitting, statistics and export. No semi-detached systems, gas streams, discs, spots, third light, eccentric contact configurations or irradiation are represented.

The separate synthetic recovery check fixes q=0.75 in a high-inclination system. A 65-phase search recovered inclination 87.919° (truth 88°), fill-out 0.3184 (truth 0.32), and T₂/T₁ 0.8995 (truth 0.90); the 513-phase, 1,500-triangle native validation RMS was 0.000351. The optimizer hit its deliberately short evaluation limit, so this is bounded recovery evidence, not a convergence or uncertainty claim. Partial-eclipse forward matches are validation of flux prediction only and do not establish uniqueness of q.
