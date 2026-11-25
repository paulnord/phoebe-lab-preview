#!/usr/bin/env python3
"""Run the held-out AT Peg V-band forward check with native PHOEBE 2.5.4."""
from __future__ import annotations

import csv
import importlib.util
import json
import os
from pathlib import Path
import time
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
os.environ.update(PHOEBE_ENABLE_ONLINE_PASSBANDS="FALSE", PHOEBE_ENABLE_MPI="FALSE",
                  PHOEBE_MULTIPROC_NPROCS="0", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")


def main():
    spec = importlib.util.spec_from_file_location("published_validation_engine", ROOT / "site/engine/model.py")
    engine = importlib.util.module_from_spec(spec); spec.loader.exec_module(engine)
    with (Path(__file__).with_name("data") / "at_peg_johnson_cousins_v.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    times = np.array([float(row["time"]) for row in rows])
    magnitudes = np.array([float(row["magnitude"]) for row in rows])
    epoch, period = 2452500.9285, 1.146065
    phases = ((times - epoch + .5 * period) % period) / period - .5
    order = np.argsort(phases); phases, magnitudes = phases[order], magnitudes[order]
    parameters = engine.parameters(dict(contact=False, semidetached=True, donor="secondary",
        inclination=76.30, mass_ratio=.484, radius_primary=1.86/6.86, radius_secondary=.17,
        fillout_factor=.25, temperature_ratio=5057/8360, period=period, epoch=epoch,
        eccentricity=0., omega=90., distortion=False, irradiation=True))
    started = time.perf_counter()
    _, model = engine._raw_model(parameters, "preview", phases=phases, ntriangles=800)
    seconds = time.perf_counter() - started
    observed = 10 ** (-.4 * (magnitudes - np.median(magnitudes))); observed /= np.median(observed)
    residual = observed - model
    result = {"source":"native PHOEBE 2.5.4", "held_out":True, "observations":len(rows),
      "seconds":seconds, "rms":float(np.sqrt(np.mean(residual**2))),
      "max_abs":float(np.max(np.abs(residual))), "observed_span":float(np.ptp(observed)),
      "model_span":float(np.ptp(model)), "parameters":parameters,
      "note":"Published parameters; no observation was used to optimize this forward model."}
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
