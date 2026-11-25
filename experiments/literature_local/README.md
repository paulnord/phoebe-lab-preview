# Target-neighborhood preview extension

This bounded extension trains display-only surrogates around the published SZ Her and V1128 Tau starting geometries. It uses native PHOEBE 2.5.4 curves, not the observed photometry, and includes orbital period as a continuous input. Exact native PHOEBE remains the fitting, statistics and export reference.

Run a measured pilot before the full deterministic generation:

```bash
PHOEBE_ENABLE_ONLINE_PASSBANDS=FALSE python experiments/literature_local/train_local.py pilot --workers 4
PHOEBE_ENABLE_ONLINE_PASSBANDS=FALSE python experiments/literature_local/train_local.py all --workers 4
```

The train, tune and untouched test splits use different seeds. The exact two picker presets are generated separately and held out of fitting and hyperparameter selection.
