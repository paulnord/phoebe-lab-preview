"""Generate the non-eclipsing counterpart of the lab's eccentric binary."""
import json
import os
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
os.environ.update(PHOEBE_ENABLE_PLOTTING="FALSE", PHOEBE_ENABLE_ONLINE_PASSBANDS="FALSE",
                  PHOEBE_MULTIPROC_NPROCS="0", PHOEBE_ENABLE_MPI="FALSE")
sys.path.insert(0, str(ROOT / "site/engine"))
import model


def generate():
    examples = ROOT / "site/examples"
    eccentric = json.loads((examples / "eccentric.json").read_text())
    params = dict(eccentric["truth"], inclination=30.0, distortion=True)
    separation_bound = (1 - params["eccentricity"]) * np.cos(np.deg2rad(params["inclination"]))
    assert separation_bound > params["radius_primary"] + params["radius_secondary"]
    phases = np.linspace(-0.5, 0.5, 512, endpoint=False)
    _, flux = model._raw_model(params, "refined", phases=phases, ntriangles=1500)
    _, spherical = model._raw_model(dict(params, distortion=False), "refined", phases=phases, ntriangles=1500)
    seed = 7814
    rng = np.random.default_rng(seed)
    bins = np.sort(rng.choice(len(phases), 240, replace=False))
    sigma = 0.002
    observations = flux[bins] + rng.normal(0, sigma, len(bins))
    dataset = dict(
        name="Non-eclipsing binary (30°)", synthetic=True, x_kind="phase", y_kind="flux",
        description="At 30° the stars miss each other. Switch tidal distortion off to compare the brightness modulation.",
        x=phases[bins].tolist(), y=observations.round(9).tolist(), sigma=[sigma] * len(bins), truth=params,
        provenance=dict(phoebe=model.phoebe.__version__, mesh_triangles_per_star=1500, passband="Johnson:V",
                        normalization="median of the model over 512 uniform phases", phases=512, seed=seed,
                        roche_peak_to_peak=float(np.ptp(flux)), spherical_peak_to_peak=float(np.ptp(spherical))),
    )
    (examples / "non-eclipsing.json").write_text(json.dumps(dataset, separators=(",", ":"), allow_nan=False) + "\n")


if __name__ == "__main__":
    generate()
