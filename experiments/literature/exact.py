import os
import json
import sys
from pathlib import Path
from common import OUT, sha, save
import time, multiprocessing
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import model

# Keep the app's forward model intact. For strict checks, tighten only PHOEBE's
# limit on the fraction of off-grid surface elements.
default_binary = model.phoebe.default_binary


def strict_binary(*args, **kwargs):
    bundle = default_binary(*args, **kwargs)
    bundle.set_value_all("extrapolation_max_frac", value=0.0)
    return bundle


def run(row):
    audit = os.environ.get("PHOEBE_AUDIT") == "1"
    # The first 38 broad training systems used the original app settings, then
    # received separate strict verification. Keep that provenance reproducible.
    strict_from = 38 if row["split"] == "train" else 2
    strict = audit or (
        row["family"] == "wide"
        and row["mode"] != "sphere"
        and int(row["system"].split("-")[-1]) >= strict_from
    )
    factory = strict_binary if strict else default_binary
    if model.phoebe.default_binary is not factory:
        model._bundle = None
        model.phoebe.default_binary = factory
    start = time.monotonic()
    try:
        _, y = model._raw_model(
            row["parameters"],
            "preview",
            phases=np.arange(row["phases"]) / row["phases"] - 0.5,
            ntriangles=row["triangles"],
        )
        if len(y) != row["phases"] or not np.isclose(np.median(y), 1):
            raise ValueError("bad flux/grid")
        result = dict(status="ok", flux=y.tolist())
    except Exception as exc:
        model._bundle = None
        err = f"{exc} | {exc.__cause__}"
        reason = (
            "roche"
            if "Roche-lobe limit" in err
            else ("atmosphere" if "atmosphere" in err.lower() else "other")
        )
        result = dict(status=reason, error=err)
    save(
        OUT / ("strict" if audit else "curves") / (row["id"] + ".json"),
        dict(id=row["id"], strict_atmosphere=strict, seconds=time.monotonic() - start, **result),
    )


if __name__ == "__main__":
    spec = json.loads((OUT / "manifest.json").read_text())
    assert (
        model.phoebe.__version__ == spec["phoebe"]
        and sha(Path(model.__file__)) == spec["engine_sha256"]
    )
    assert (
        sha(Path(model.phoebe.list_installed_passbands(full_dict=True)["Johnson:V"]["fname"]))
        == spec["passband_sha256"]
    )
    if (OUT / "supplement.json").exists():
        spec["cases"] += json.loads((OUT / "supplement.json").read_text())
    if (OUT / "enrich.json").exists():
        spec["cases"] += json.loads((OUT / "enrich.json").read_text())
    if (OUT / "paired-extension.json").exists():
        spec["cases"] += json.loads((OUT / "paired-extension.json").read_text())
    ids = set(sys.argv[2:])
    with ProcessPoolExecutor(
        int(sys.argv[1]), mp_context=multiprocessing.get_context("fork")
    ) as pool:
        list(pool.map(run, [r for r in spec["cases"] if r["id"] in ids]))
