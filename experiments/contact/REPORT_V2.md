# Expanded contact preview training report

Baseline: `b7ce074c8231cc8db9bc2e4016b667071daaa845`
Artifact SHA-256: `dde66290f0d8f8a1562b98909e34d534dba8c175db032d04de4f69296e233d03`
Split: 384 train / 96 tune / 128 untouched test systems with independent seeds; boundary-focused systems are included independently in every split.

Native timing: median 2.725 s, p95 4.765 s; 31 retries at 1,500 and 0 at 3,000 triangles.

Generation used four local workers. The complete 628-system run (train, tune,
untouched test, and boundary slider sweeps) took 479.702 s (8.0 min) wall time.
Model fitting and export took seconds; validation and app integration were
tracked separately from generation time.

The frozen v1 and expanded v2 models are compared on the same newly generated test systems. Neither model saw this test split during fitting or hyperparameter selection.

| Model / regime | N | pooled RMS | p95 curve RMS | p95 absolute | worst absolute |
| --- | ---: | ---: | ---: | ---: | ---: |
| v1 / all | 128 | 0.002045 | 0.003930 | 0.004430 | 0.023674 |
| v1 / grazing | 42 | 0.002205 | 0.004036 | 0.004761 | 0.008951 |
| v1 / shallow_contact | 23 | 0.002520 | 0.003815 | 0.005238 | 0.022052 |
| v1 / deep_contact | 29 | 0.002481 | 0.004056 | 0.005148 | 0.023674 |
| v1 / unequal_mass | 46 | 0.002540 | 0.004152 | 0.005232 | 0.023674 |
| v2 / all | 128 | 0.001077 | 0.001806 | 0.002090 | 0.025301 |
| v2 / grazing | 42 | 0.001067 | 0.001926 | 0.001983 | 0.009169 |
| v2 / shallow_contact | 23 | 0.001278 | 0.001720 | 0.002409 | 0.009918 |
| v2 / deep_contact | 29 | 0.001147 | 0.001806 | 0.002447 | 0.011045 |
| v2 / unequal_mass | 46 | 0.001075 | 0.001670 | 0.002059 | 0.025301 |

## Slider-difference comparison

Cosine compares the direction/shape of the native and surrogate flux-response vectors; relative norm error compares response amplitude. This is deliberately separate from pointwise curve RMS.

| Model | Anchor | Parameter | native response RMS | difference RMS | cosine | relative norm error |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| v1 | 0 | inclination | 0.004395 | 0.000809 | 0.9836 | 0.0206 |
| v1 | 0 | mass_ratio | 0.003467 | 0.002078 | 0.8700 | 0.4707 |
| v1 | 0 | fillout_factor | 0.002836 | 0.001688 | 0.9272 | 0.5355 |
| v1 | 0 | temperature_ratio | 0.003928 | 0.001457 | 0.9313 | 0.0006 |
| v1 | 1 | inclination | 0.001857 | 0.000900 | 0.9623 | 0.3635 |
| v1 | 1 | mass_ratio | 0.001471 | 0.000893 | 0.8831 | 0.2684 |
| v1 | 1 | fillout_factor | 0.001582 | 0.000960 | 0.8726 | 0.2329 |
| v1 | 1 | temperature_ratio | 0.009264 | 0.001245 | 0.9945 | 0.0894 |
| v1 | 2 | inclination | 0.002310 | 0.000609 | 0.9681 | 0.0501 |
| v1 | 2 | mass_ratio | 0.004820 | 0.000852 | 0.9910 | 0.1242 |
| v1 | 2 | fillout_factor | 0.002077 | 0.000415 | 0.9799 | 0.0337 |
| v1 | 2 | temperature_ratio | 0.009727 | 0.000367 | 0.9996 | 0.0225 |
| v1 | 3 | inclination | 0.005732 | 0.000195 | 0.9994 | 0.0006 |
| v1 | 3 | mass_ratio | 0.001399 | 0.000923 | 0.7553 | 0.3196 |
| v1 | 3 | fillout_factor | 0.002390 | 0.000635 | 0.9673 | 0.1117 |
| v1 | 3 | temperature_ratio | 0.007437 | 0.000393 | 0.9987 | 0.0102 |
| v2 | 0 | inclination | 0.004395 | 0.000336 | 0.9972 | 0.0150 |
| v2 | 0 | mass_ratio | 0.003467 | 0.001489 | 0.9149 | 0.2310 |
| v2 | 0 | fillout_factor | 0.002836 | 0.000702 | 0.9855 | 0.1950 |
| v2 | 0 | temperature_ratio | 0.003928 | 0.000209 | 0.9987 | 0.0149 |
| v2 | 1 | inclination | 0.001857 | 0.000615 | 0.9847 | 0.2659 |
| v2 | 1 | mass_ratio | 0.001471 | 0.000646 | 0.9425 | 0.2272 |
| v2 | 1 | fillout_factor | 0.001582 | 0.001013 | 0.8465 | 0.2021 |
| v2 | 1 | temperature_ratio | 0.009264 | 0.000555 | 0.9982 | 0.0026 |
| v2 | 2 | inclination | 0.002310 | 0.000631 | 0.9677 | 0.0733 |
| v2 | 2 | mass_ratio | 0.004820 | 0.000711 | 0.9901 | 0.0555 |
| v2 | 2 | fillout_factor | 0.002077 | 0.000375 | 0.9840 | 0.0461 |
| v2 | 2 | temperature_ratio | 0.009727 | 0.000175 | 0.9998 | 0.0038 |
| v2 | 3 | inclination | 0.005732 | 0.000143 | 0.9997 | 0.0030 |
| v2 | 3 | mass_ratio | 0.001399 | 0.000900 | 0.7701 | 0.3128 |
| v2 | 3 | fillout_factor | 0.002390 | 0.000483 | 0.9797 | 0.0031 |
| v2 | 3 | temperature_ratio | 0.007437 | 0.000175 | 0.9998 | 0.0080 |

## Limits

Display-only preview in its fixed-physics domain. Native PHOEBE remains authoritative. Pointwise agreement or a photometric response match does not establish unique q; RV curves remain important complementary evidence.
