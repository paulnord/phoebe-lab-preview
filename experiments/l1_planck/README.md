# L1 low-temperature Planck candidate

This directory contains an isolated validation candidate for PHOEBE 2.5.4. It
does not patch PHOEBE Lab or the installed PHOEBE package.

At the exactly critical L1 cusp in the SZ Herculis secondary-donor model, the
native marching mesh can place one raw vertex at effectively zero gravity. Its
gravity-darkened temperature is positive but below the blackbody table's 316 K
floor. PHOEBE's existing CK2004-to-blackbody blend then receives a NaN from the
finite blackbody table, poisoning the six triangles that share that vertex.

`candidate.py` keeps the existing CK2004 and limb-darkening paths. Within a
temporary context manager, only finite positive blackbody queries below the
table floor are evaluated from the Planck function over the active passband.
Photon and energy weighting are both supported. Non-positive, non-finite, and
high out-of-range inputs retain PHOEBE's failure behavior. The original method
is restored in `finally`.

`validation.py` performs one native test sequence:

- reproduce the original five-phase failure on the exact-axis critical mesh;
- run SZ Her Preview at 129 phases / 800 requested triangles;
- run SZ Her Refined at 513 phases / 1500 requested triangles;
- report passband luminosities, published Johnson V residuals, and resolution
  convergence;
- require photon- and energy-weighted continuity immediately below and at the
  native blackbody table's lower temperature knot;
- compare ordinary detached and contact 129-phase curves before and during the
  candidate and require exact array equality.

The exact-axis override is test-only. It deterministically selects the same
native symmetry branch observed in managed Colab while preserving the critical
Roche potential, volume, radius, and all scientific parameters. It is not a
proposed production change.

Run locally:

```bash
python -m experiments.l1_planck.validation
```

The generated Colab entry point is
`notebooks/PHOEBE_L1_Planck_Colab_Test.ipynb`. Choose **Runtime → Run all** once.
The final JSON report is the complete result. A hosted pass is required before
considering a PHOEBE Lab change or drafting an upstream report.
