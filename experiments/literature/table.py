"""Expand the existing disc intensity table using the installed exact passband."""

import json
from common import TREE, OUT, save
import base64
import model
import numpy as np
from phoebe.atmospheres import passbands


def main():
    old = json.loads((TREE / "site/experiment/display-model.json").read_text())
    table = old["table"]
    radii = np.array(table["radii"])
    mus = np.sqrt(1 - (radii[:-1] ** 2 + radii[1:] ** 2) / 2)
    teffs = np.unique(np.r_[3528.0, np.arange(3625, 9450, 125), table["teffs"], 9450.0])
    gravities = np.arange(0, 5.01, 0.25)
    pb = model.phoebe.get_passband("Johnson:V")
    values = np.empty((len(teffs), len(gravities), len(mus)))
    valid = np.zeros(values.shape[:2], bool)
    for i, t in enumerate(teffs):
        for j, g in enumerate(gravities):
            query = passbands.InterpQuery(
                cols=["teffs", "loggs", "abuns", "mus"],
                pts=np.column_stack(
                    (np.full_like(mus, t), np.full_like(mus, g), np.zeros_like(mus), mus)
                ),
            )
            try:
                intens = (
                    pb.interpolate_imus(query, intens_weighting="energy")
                    .get_interpolated_values()
                    .ravel()
                )
                if np.all(np.isfinite(intens) & (intens > 0)):
                    values[i, j] = np.log(intens)
                    valid[i, j] = True
            except ValueError:
                pass
    values[~valid] = 0
    table.update(
        teffs=teffs.tolist(),
        gravities=gravities.tolist(),
        valid=valid.tolist(),
        log_intensity_f32le=base64.b64encode(values.astype("<f4").tobytes()).decode(),
    )
    save(OUT / "table.json", dict(table=table, n=old["n"], fixed=old["fixed"]))


if __name__ == "__main__":
    main()
