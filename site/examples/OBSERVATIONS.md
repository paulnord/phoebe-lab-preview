# Published Johnson V observation examples

These files are unchanged numeric columns selected from public CDS/VizieR tables and renamed with explicit CSV headers so PHOEBE Lab recognizes time and magnitude. They are observational inputs, not fitted models. No phase column is stored and no observation was synthesized, filtered, averaged, or converted to flux.

## Contact: GSC 3822-1056 (LP UMa)

- File: `observed-gsc3822-1056-johnson-v.csv`
- SHA-256: `40eff8095b35cc0534a1a427c91a774eeab96c255d04e730615f9f486f31c395`
- Geometry: over-contact. Csizmadia, Bíró & Borkovits report a contact solution with fill-out factor about 0.57. This is an intentional edge case: the published value exceeds PHOEBE Lab's unchanged contact-fit maximum of 0.50, so it is not an in-range fitting benchmark.
- Data: 271 standard Johnson V measurements, `HJD` in days and `Vmag` in magnitudes, copied from CDS/VizieR table `J/A+A/403/637/table2a`.
- Folding values for this observing run: primary-eclipse epoch **HJD 2450495.5212** and period **0.30989069 d**, the published linear elements cited with the observations. Period evolution is reported, so do not apply these elements uncritically to other epochs.
- Point uncertainties / flags: the Johnson V source table publishes neither. The separate unfiltered relative-photometry table has scatter values, but those values do not belong to the Johnson V measurements and were not transplanted.
- Sources: [CDS/VizieR catalog](https://cdsarc.cds.unistra.fr/viz-bin/cat/J/A+A/403/637), [machine-readable query](https://vizier.idia.ac.za/viz-bin/asu-tsv?-source=J/A%2BA/403/637&-out=HJD,Vmag&-out.max=500), [paper DOI](https://doi.org/10.1051/0004-6361:20030388).

## Contact: V1128 Tauri

- File: `observed-v1128-tau-johnson-v.csv`
- SHA-256: `f4e7d5e7249b02860c2b0a55685a92212d6a884818eee3078e12977118d9e30e`
- Geometry: shallow-contact W UMa binary. Çalışkan et al. report mass ratio **0.534 ± 0.006**, inclination **86.0° ± 0.2°**, fill-out **13.4%**, and component temperatures 6200 K and 6400 K (temperature ratio about **1.032**). Those values, together with the published period, lie inside the current Contact fit controls: mass ratio 0.2–1.5, inclination 0–90°, fill-out 0.10–0.50, temperature ratio 0.58–1.10, and period 0.1–100 d.
- Data: all 690 Johnson V rows selected from the paper's BVRI table, CDS/VizieR `J/AJ/148/126/table3`. The columns retain the published heliocentric Julian date in days and differential magnitude in magnitudes. The published row order and numeric precision are unchanged; only explicit CSV headers were added.
- Observing run: the V rows span **HJD 2454785.2630–2454844.2755**. Use primary-eclipse epoch **HJD 2454842.3470 ± 0.0001** and period **0.305371 ± 0.000002 d** from the observational summary for folding this run. The paper's later O-C solution quotes a smaller period uncertainty and finds long-term period variation; these data are not a long-baseline ephemeris.
- Photometric convention: the source is Johnson-Cousins differential photometry from Ankara University Kreiken Observatory, with comparison star **GSC 664-387**. The paper describes the tabulated differential magnitudes as variable minus comparison.
- Point uncertainties / flags: table 3 publishes neither, so the CSV has no uncertainty or quality column. The paper's band-level values and model residual scatter are not per-point errors and were not copied into the observations.
- Model limitation: the published light-curve solution includes a cool spot on the secondary. PHOEBE Lab's current Contact fit does not fit spots, and its reference primary is fixed at 6300 K rather than the paper's 6200 K; importing successfully is not a scientific validation of the fit.
- Sources: [CDS/VizieR catalog](https://cdsarc.cds.unistra.fr/viz-bin/cat/J/AJ/148/126), [V-band machine-readable query](https://vizier.idia.ac.za/viz-bin/asu-tsv?-source=J/AJ/148/126/table3&Name=V1128%20Tau&Flt=V&-out=HJD,Dmag&-out.max=unlimited), [paper](https://arxiv.org/abs/1410.2449), [paper DOI](https://doi.org/10.1088/0004-6256/148/6/126).

## Semi-detached: SZ Herculis

- File: `observed-sz-her-johnson-v.csv`
- SHA-256: `7cddf77b51037157490fcf4e9d68f8c5d0ef4a141ea44fd852f97a3fd47b1a91`
- Geometry: classical Algol semi-detached binary. Lee et al. find that the secondary fills its Roche lobe while the primary is about 77% lobe filling.
- Data: 437 differential Johnson V measurements, `HJD-V` in days and published `DVmag` (target minus comparison) in magnitudes, copied from CDS/VizieR table `J/AJ/143/34/table2`.
- Folding values: primary-eclipse epoch **HJD 2454588.167997** and period **0.8180837 d**, from the paper's photometric solution (Table 3). The paper discusses eclipse-timing variations, so these values are intended for this 2008 light curve rather than long-baseline timing work.
- Point uncertainties / flags: the source light-curve table publishes neither. The catalog's separate minima table contains timing errors, not photometric errors, and they were not reused.
- Sources: [CDS/VizieR catalog](https://cdsarc.cds.unistra.fr/viz-bin/cat/J/AJ/143/34), [machine-readable query](https://vizier.idia.ac.za/viz-bin/asu-tsv?-source=J/AJ/143/34&-out=HJD-V,DVmag&-out.max=500), [paper](https://arxiv.org/abs/1111.3691), [paper DOI](https://doi.org/10.1088/0004-6256/143/2/34).

## Loading in PHOEBE Lab

1. Choose **Load data** and select a CSV.
2. Keep the first column as **Time**, the second as **Magnitude**, and uncertainty as **None**.
3. Enter the epoch and period above. Select **Contact** for GSC 3822-1056 or V1128 Tau, or **Semi-detached → Secondary fills lobe** for SZ Her.
4. The app converts magnitude to relative flux internally. Retain the original CSV as the archival observation table.

These examples only demonstrate import and model comparison. They are not evidence that the app's fixed 1.2-solar-mass, 6300 K reference system represents any target, and a low residual does not establish a unique physical solution. No radial-velocity file is bundled: these CDS light-curve tables contain no two-component RV table, and unrelated or non-contemporaneous velocities were not combined.

The source catalogs are publicly served by CDS/VizieR. Cite both the original paper and VizieR when using the data, and follow the [VizieR usage and licensing information](https://cds.unistra.fr/vizier-org/licences_vizier.html). The repository does not relicense the authors' measurements.

