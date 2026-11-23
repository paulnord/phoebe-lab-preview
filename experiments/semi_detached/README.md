# Reproducing the semi-detached preview

The two donor-specific models use native PHOEBE 2.5.4 `default_binary(semidetached=...)` constraints. The donor radius is solved at its Roche lobe; the other star is sampled by its volume-equivalent radius as a fraction of its own Roche-lobe maximum.

```bash
python -m pip install phoebe==2.5.4 numpy scipy
PHOEBE_ENABLE_ONLINE_PASSBANDS=FALSE python experiments/semi_detached/train_semi.py all --workers 4
node tests/semi_predict.mjs
```

The deterministic run uses independent train, tune, and untouched test seeds for each donor. Boundary-focused points are injected independently into every split. The committed artifact also contains separate native slider-sweep curves used to compare flux-response vectors—not merely absolute-curve RMS—near grazing, high-fill, and unequal-mass regimes.

Outputs:

- `artifacts/semi-curves.npz`: parameters, native curves, derived radii, timings, meshes, and split identities
- `../../site/experiment/semi-model.json`: frozen lightweight browser model
- `REPORT.md`: pointwise and slider-response validation, timing, provenance, and limits
- `../../notebooks/PHOEBE_Semi_Detached_Validation.ipynb`: portable validation and recovery checks
- `../../notebooks/PHOEBE_Semi_Detached_Binary_Colab.ipynb`: interactive observation upload and native fitting utility

No disks, streams, spots, eccentric semi-detached systems, irradiation preview, or joint photometry/RV inference are trained. Native PHOEBE remains the fitting and export reference.
