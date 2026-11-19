"""Paired broad sample and an interpolation slice through the shipped eccentric example."""

import json
from common import TREE, OUT, save
import numpy as np
from scipy.stats import qmc


def extra(spec):
    rows = []
    example = json.loads((TREE / "site/examples/non-eclipsing.json").read_text())["truth"]
    for split, values in [
        ("train", [18, 22, 26, 29, 33, 37, 41, 46]),
        ("val", [19, 27, 35, 43]),
        ("blind", [20.8, 23.1, 30, 33.3, 36.9, 40.2, 45.4]),
    ]:
        for j, a in enumerate(values):
            p = dict(example, inclination=a)
            rows.extend(siblings("eccentric", split, j, p))
    for split, n in [("train", 128), ("val", 32), ("blind", 64)]:
        for j in range(n):
            p = next(
                r["parameters"] for r in spec["cases"] if r["id"] == f"wide-{split}-{j:04d}-sphere"
            )
            # The pilot already generated the first two families.
            if split == "train" and j < 2:
                continue
            rows.extend(siblings("wide", split, j, p)[1:])
    return rows


def siblings(family, split, j, p):
    system = f"{family}-{split}-{j:04d}"
    return [
        dict(
            id=system + "-" + m,
            system=system,
            family=family,
            split=split,
            mode=m,
            parameters=dict(
                p, distortion=m in ("tides", "both"), irradiation=m in ("heat", "both")
            ),
            phases=256,
            triangles=400,
        )
        for m in ["sphere", "tides", "heat", "both"]
    ]


if __name__ == "__main__":
    spec = json.loads((OUT / "manifest.json").read_text())
    save(OUT / "supplement.json", extra(spec))
