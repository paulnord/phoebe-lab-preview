# Reproducing the contact preview

This directory owns the native PHOEBE targets, frozen split, trainer, and validation report for the experimental contact-binary drag preview. It does not modify or reuse the detached Fourier artifacts.

## Pinned physics

- PHOEBE 2.5.4 `default_contact_binary()`
- primary mass 1.2 solar masses and primary temperature 6300 K
- Johnson:V; circular synchronous contact envelope; irradiation off
- component radii are derived by PHOEBE's native fill-out/envelope-potential constraints
- 129 uniformly spaced phases, including both repeated endpoints
- deterministic 800, 1500, then 3000-triangle retry policy for native mesh failures

## Generate, train, and validate

From the repository root, in a clean Python environment:

```bash
python -m pip install phoebe==2.5.4 numpy scipy
PHOEBE_ENABLE_ONLINE_PASSBANDS=FALSE python experiments/contact/train_contact.py all --workers 4
node tests/contact_predict.mjs
```

`train_contact.py` uses scrambled Sobol physical-system designs with fixed seeds. Training and validation systems are independent; phase samples from one system cannot cross the split. It writes:

- `artifacts/contact-curves.npz`: native parameters, curves, split, mesh used, and timing
- `../../site/experiment/contact-model.json`: frozen browser artifact
- `REPORT.md`: selected hyperparameters, held-out metrics by regime, timings, and limitations

The committed artifact was selected on the documented 128-system training split and evaluated once on the separate 64-system validation split. Re-running generation is intentionally a CPU task and does not require a cluster or paid service.
