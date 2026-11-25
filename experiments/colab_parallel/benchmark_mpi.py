"""Benchmark an explicit PHOEBE MPI launch on a fixed native contact curve."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time

import numpy as np

rank = int(os.environ.get("OMPI_COMM_WORLD_RANK", os.environ.get("PMI_RANK", "0")))
size = int(os.environ.get("OMPI_COMM_WORLD_SIZE", os.environ.get("PMI_SIZE", "1")))
print(json.dumps({"event":"rank_started","rank":rank,"size":size,"pid":os.getpid()}), flush=True)

root = Path(__file__).resolve().parents[2]
started = time.perf_counter()
spec = importlib.util.spec_from_file_location("phoebe_lab_mpi_benchmark", root / "site" / "engine" / "model.py")
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)
import_seconds = time.perf_counter() - started

# Nonzero ranks wait inside PHOEBE's import-time MPI worker loop and exit when
# rank zero calls shutdown_workers below.
if rank == 0:
    parameters = dict(model.DEFAULTS, contact=True, fillout_factor=.25,
                      mass_ratio=.75, temperature_ratio=.84, inclination=84.5)
    phases = np.linspace(-.5, .5, 65)
    began = time.perf_counter()
    actual_phases, flux = model._raw_model(parameters, "preview", phases=phases)
    compute_seconds = time.perf_counter() - began
    normalized = np.asarray(flux) / np.median(flux)
    print(json.dumps({
        "event":"result", "ranks":size, "import_seconds":import_seconds,
        "compute_seconds":compute_seconds, "points":len(actual_phases),
        "flux_sha256":hashlib.sha256(normalized.astype("<f8").tobytes()).hexdigest(),
        "flux_min":float(normalized.min()), "flux_max":float(normalized.max()),
        "mpi_mode":model.phoebe.mpi.mode,
    }), flush=True)
    model.phoebe.mpi.shutdown_workers()
