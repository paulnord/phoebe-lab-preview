# Independent published-system validation

These observations are held-out checks. They were not used to train, tune, select, or extend any PHOEBE Lab preview model. Native PHOEBE remains the scientific reference, and an unsupported comparison is reported as unsupported rather than forced through a preview domain.

## V1128 Tau: double-lined spectroscopy

Source: Rucinski et al. (2008), [DOI](https://doi.org/10.1088/0004-6256/136/2/586), [arXiv paper](https://arxiv.org/abs/0805.1695), and [VizieR J/AJ/136/586 table1](https://vizier.cds.unistra.fr/viz-bin/VizieR-3?-source=J/AJ/136/586). The checked-in `v1128_tau_ddo_all.csv` preserves all 104 catalog rows, blank velocities, published weights, phases, and the two earlier observing sets. The 1997 and 2003 velocities remain present but are not included in the final-orbit check, exactly as stated by the paper. The app-ready `v1128_tau_ddo_recent_app.csv` is a documented derived selection of the 38 recent pairs for which both published weights equal one; it does not invent errors.

Using the paper's T0 = HJD 2453864.7026 and P = 0.3053707 d, a shared-gamma circular least-squares check of those 38 recent full-weight pairs gives:

| quantity | reproduced | published |
|---|---:|---:|
| gamma (km/s) | -12.2646 | -12.27(76) |
| K1 (km/s) | 130.4780 | 130.48(1.27) |
| K2 (km/s) | 244.1890 | 244.19(1.28) |
| q = K1/K2 = M2/M1 | 0.534332 | 0.534(6) |
| pooled RMS (km/s) | 6.3285 | component unit-weight errors 5.75 / 7.68 |

The published deeper-light epoch HJD 2454842.3470 is at spectroscopic phase **0.5003404**. PHOEBE Lab's model-alignment `t0_supconj`, HJD 2454842.4996855, is at phase **0.0003409**. Thus the independent double-lined orbit corroborates the half-orbit alignment; q is not inverted.

The workbench RV overlay deliberately fixes M1 = 1.2 solar masses. At q = 0.534, i = 86 deg, the published photometric period, and a fitted display gamma only, it gives K1/K2 = 134.56/251.98 km/s and pooled RMS 8.21 km/s. The ratio remains correct, but the absolute amplitudes are not a re-fit of the paper's mass scale. The Lab photometric fitter does not fit RVs.

## BO CVn: held-out contact case

Source: Zola et al. (2012), [publisher article](https://www.sciencedirect.com/science/article/pii/S1384107612000358), [DOI](https://doi.org/10.1016/j.newast.2012.04.004), and [arXiv paper](https://arxiv.org/abs/1204.3584). `bo_cvn_rv.csv` is a visually checked transcription of the ten rows in primary-source Table 1, including its per-point uncertainties and published phases.

A weighted shared-gamma circular check gives gamma = 17.746 km/s, K1 = 73.901 km/s, K2 = 236.804 km/s, q = **0.31208**, and weighted RMS = 5.852 km/s. This reproduces the paper's spectroscopic q = 0.31 +/- 0.01 (the later combined light/RV solution reports q = 0.340).

BO CVn is not a valid PHOEBE Lab contact-preview or fit benchmark: the published 88% fill-out exceeds the Lab's hard maximum of 50%, its period 0.5174629 d lies outside the V1128-local trained period interval, and the published V solution requires about 21.7% third light, which the simple Lab fitter does not expose. The source also fixes T1 = 6980 K rather than the Lab's 6300 K. No light curve was fabricated or extrapolated, and no native Lab residual is claimed.

## AT Peg: held-out semi-detached case

Source: Zola et al. (2016), [DOI](https://doi.org/10.3847/0004-6256/152/2/33), [arXiv paper](https://arxiv.org/abs/1607.06930), and the publisher's machine-readable [Figure 2 RV archive](https://content.cld.iop.org/journals/1538-3881/152/2/33/revision1/aj523543f2.tar.gz) and [Figure 5 light-curve archive](https://content.cld.iop.org/journals/1538-3881/152/2/33/revision1/aj523543f5.tar.gz). `at_peg_zola_rv.csv` preserves the nine published gamma-corrected double-lined measurements and their errors. `at_peg_johnson_cousins_v.csv` preserves all 895 V rows. The paper gives epoch HJD 2452500.9285 and period 1.146065 d.

The nine-point weighted RV check gives K1 = 93.904 km/s, K2 = 194.463 km/s and q = **0.48289**, reproducing the paper's own-RV solution q = 0.484(3). The earlier Maxted et al. series is stored separately in `at_peg_maxted_caleb.csv`, from the public CALeb transcription of the original paper's Table 1. Its 21 rows give q = **0.47744** unweighted, consistent with the literature value near 0.473. These series are never pooled: the 2016 paper reports gamma = 10.0(1.9) km/s for its own series and 4.1(0.6) km/s for the Maxted series, and its Figure 2 archive has already subtracted systemic velocity.

AT Peg's published secondary-donor geometry is inside the native engine's physical controls but outside the trained SZ Her preview neighborhood: i = 76.3 deg is below 82 deg, T2/T1 = 5057/8360 = 0.605 below 0.62, and P = 1.146065 d exceeds 1.05 d. The browser preview correctly declines it.

A held-out native PHOEBE 2.5.4 forward calculation used all 895 sorted V phases, q = 0.484, i = 76.30 deg, free-primary radius/separation = 1.86/6.86, T2/T1 = 5057/8360, the secondary Roche constraint, Johnson V, irradiation on, and 800 triangles. No parameter was optimized against the light curve. It completed locally in 9.52 s with normalized-flux RMS **0.01352**, maximum absolute residual **0.03677**, observed span 0.55632 and model span 0.55366. This is a useful shape check, not a reproduction of the published WD solution: PHOEBE Lab fixes M1 = 1.2 solar masses and T1 = 6300 K, while the paper reports about 2.22 solar masses and fixes T1 = 8360 K. The publisher supplies Johnson-Cousins V; the Lab computes Johnson:V.

## Reproduction and limitations

- `build_data.py` regenerates the CSVs from unmodified downloaded VizieR/AAS source files and the visually checked BO CVn table transcription.
- `analyze.py` reproduces all circular RV checks without using preview models.
- `native_at_peg.py` reproduces the native held-out forward calculation with the repository's PHOEBE environment.
- The shared RV importer accepts the 38-row V1128 app CSV. It cannot express catalog weights directly, so only the full-weight recent subset is offered for display; the all-row archival CSV remains authoritative.
- No hosted Colab runtime was started for this validation. The native AT Peg check ran locally in the same PHOEBE 2.5.4 wrapper used by the Colab bridge. No BO CVn native model was run because its published geometry and third light are out of scope.

The VizieR catalog retains its own [usage and licensing terms](https://cds.unistra.fr/vizier-org/licences_vizier.html). The repository does not relicense the measurements.
