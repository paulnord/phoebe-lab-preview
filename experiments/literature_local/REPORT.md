# Literature-neighborhood preview training

Baseline: `c5364d1714c5c4ca7ba4aa003031ae1c2929c6a8`
Native artifact SHA-256: `0f2acbabd08ab980f3ba0c37bc5005aabd59d721afd07b85e7de53ed7f04f959`

Per mode: 96 train / 24 tune / 32 untouched test systems plus the exact published preset as a separate one-system holdout. Splits use independent Sobol seeds and never share phase samples. The observed photometry is not a training target.

Generation: 306 native PHOEBE systems with four local workers in 316.4 s; median 3.080 s, p95 8.879 s per curve; 21 retries at 1,500 triangles and 1 at 3,000.

| Mode / holdout | pooled RMS | p95 curve RMS | max abs | primary depth p95 | secondary depth p95 | primary eclipse RMS | secondary eclipse RMS |
|---|---:|---:|---:|---:|---:|---:|---:|
| contact / independent test | 0.001384 | 0.002409 | 0.008810 | 0.006534 | 0.005695 | 0.001014 | 0.001370 |
| contact / exact preset | 0.000529 | 0.000529 | 0.001196 | 0.000734 | 0.000433 | 0.000516 | 0.000502 |
| semi_secondary / independent test | 0.001335 | 0.002617 | 0.033654 | 0.019822 | 0.001346 | 0.002263 | 0.000440 |
| semi_secondary / exact preset | 0.000634 | 0.000634 | 0.003943 | 0.002490 | 0.000345 | 0.001044 | 0.000319 |

## Validated display domains

- V1128 Tau contact neighborhood: inclination 78–90°, q 0.45–0.65, fill-out 0.10–0.23, T2/T1 0.94–1.10, P 0.22–0.45 d.
- SZ Her secondary-donor neighborhood: inclination 82–90°, q 0.40–0.58, free-primary Roche fill 0.55–0.82, T2/T1 0.62–0.74, P 0.60–1.05 d.

The browser adapter fails closed outside a small confidence margin and the existing broad contact/semi models remain unchanged at their original P=1.8 d domains. Native PHOEBE remains authoritative for fitting, residual statistics and export. These local previews omit spots and do not establish unique photometric q.
