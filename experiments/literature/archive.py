"""Audit the previous training archive against every historical reserved geometry."""

import json
from common import SCRATCH, OUT, OLD, KEYS, sha, save
import numpy as np


def identity(p):
    vals = [p[k] for k in KEYS]
    vals[-1] = vals[-1] % 360 if vals[-2] else 0.0
    return tuple(vals)


def study_rows():
    spec = json.loads((OUT / "manifest.json").read_text())
    extra = OUT / "paired-extension.json"
    return (
        spec["cases"]
        + json.loads((OUT / "supplement.json").read_text())
        + json.loads((OUT / "enrich.json").read_text())
        + (json.loads(extra.read_text()) if extra.exists() else [])
    )


def main():
    spec = json.loads((OUT / "manifest.json").read_text())
    sources = [
        ("surrogate-results-20261118/ten-thousand", {"train"}),
        ("wide-results-20261118", {"train"}),
        ("joint-results-20261118", {"train"}),
        ("slider-sweep-results-20261118", {"nominal", "axis", "orbit_surface"}),
        ("slider-sweep-results-20261118/conditional", {"slice_omega", "slice_inclination"}),
        ("eight-results-20261118", {"train_ui", "train_short"}),
    ]
    reserved = set()
    hashes = {}
    for name, allowed in sources:
        f = SCRATCH / ("phoebe-" + name) / "manifest.json"
        m = json.loads(f.read_text())
        hashes[name] = sha(f)
        reserved.update(identity(r["parameters"]) for r in m["cases"] if r["group"] not in allowed)
    physical = {}
    for r in study_rows():
        sig = identity(r["parameters"])
        if sig in physical:
            assert physical[sig] == r["system"], (physical[sig], r["system"])
        physical[sig] = r["system"]
        if r["split"] == "train":
            assert sig not in reserved, (r["id"], sig)
    archive = OLD / "share/training.npz"
    inputs = []
    with np.load(archive) as z:
        assert list(z["keys"]) == KEYS
        oldp = [dict(zip(KEYS, x)) for x in z["parameters"]]
        keep = [
            i
            for i, p in enumerate(oldp)
            if identity(p) not in reserved and identity(p) not in physical
        ]
        for i in keep:
            inputs.append(dict(id="hist-" + str(i), parameters=oldp[i]))
    manifest = json.loads((OLD / "manifest.json").read_text())
    assert (
        manifest["passband"]["sha256"] == spec["passband_sha256"]
        and manifest["phoebe"] == spec["phoebe"]
    )
    for r in manifest["cases"]:
        if r["group"] in ("blind_ui", "blind_short", "faces", "grazing", "path"):
            inputs.append(dict(id="old-" + r["id"], parameters=r["parameters"]))
    inputs.extend(
        dict(id=r["system"], parameters=r["parameters"])
        for r in study_rows()
        if r["mode"] == "sphere" and r["triangles"] == 400
    )
    save(OUT / "coordinates.json", inputs)
    save(
        OUT / "audit.json",
        dict(
            training_archive_sha256=sha(archive),
            eligible_history=len(keep),
            previous_count=len(oldp),
            reserved_geometries=len(reserved),
            new_systems=len(physical),
            source_hashes=hashes,
        ),
    )


if __name__ == "__main__":
    main()
