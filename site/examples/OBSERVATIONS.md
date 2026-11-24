# Published Johnson V observation examples

These files are unchanged numeric columns selected from public CDS/VizieR tables and renamed with explicit CSV headers so PHOEBE Lab recognizes time and magnitude. They are observational inputs, not fitted models. No phase column is stored and no observation was synthesized, filtered, averaged, or converted to flux.

## Contact: GSC 3822-1056 (LP UMa)

- File: `observed-gsc3822-1056-johnson-v.csv`
- SHA-256: `40eff8095b35cc0534a1a427c91a774eeab96c255d04e730615f9f486f31c395`
- Geometry: over-contact. Csizmadia, Bíró & Borkovits report a contact solution with fill-out factor about 0.57.
- Data: 271 standard Johnson V measurements, `HJD` in days and `Vmag` in magnitudes, copied from CDS/VizieR table `J/A+A/403/637/table2a`.
- Folding values for this observing run: primary-eclipse epoch **HJD 2450495.5212** and period **0.30989069 d**, the published linear elements cited with the observations. Period evolution is reported, so do not apply these elements uncritically to other epochs.
- Point uncertainties / flags: the Johnson V source table publishes neither. The separate unfiltered relative-photometry table has scatter values, but those values do not belong to the Johnson V measurements and were not transplanted.
- Sources: [CDS/VizieR catalog](https://cdsarc.cds.unistra.fr/viz-bin/cat/J/A+A/403/637), [machine-readable query](https://vizier.idia.ac.za/viz-bin/asu-tsv?-source=J/A%2BA/403/637&-out=HJD,Vmag&-out.max=500), [paper DOI](https://doi.org/10.1051/0004-6361:20030388).

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
3. Enter the epoch and period above. Select **Contact** for GSC 3822-1056, or **Semi-detached → Secondary fills lobe** for SZ Her.
4. The app converts magnitude to relative flux internally. Retain the original CSV as the archival observation table.

These examples only demonstrate import and model comparison. They are not evidence that the app's fixed 1.2-solar-mass, 6300 K reference system represents either target, and a low residual does not establish a unique physical solution. No radial-velocity file is bundled: these two CDS data sets contain no two-component RV table, and unrelated or non-contemporaneous velocities were not combined.

The source catalogs are publicly served by CDS/VizieR. Cite both the original paper and VizieR when using the data, and follow the [VizieR usage and licensing information](https://cds.unistra.fr/vizier-org/licences_vizier.html). The repository does not relicense the authors' measurements.

