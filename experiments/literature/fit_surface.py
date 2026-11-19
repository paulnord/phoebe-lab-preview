"""Learn mode-specific paired corrections on the two regular interpolation slices."""

import json
import sys
from common import OUT, KEYS, save, status
from archive import study_rows
from fit_wide import GATES, score
from diagnostics import details, summarize
from scipy.interpolate import RegularGridInterpolator
from collections import defaultdict
import base64
import numpy as np

MODES = ["sphere", "tides", "heat", "both"]


def groups(family, splits, original_only=False):
    records = defaultdict(dict)
    for r in study_rows():
        if r["family"] != family or r["split"] not in splits or r["triangles"] != 400:
            continue
        if original_only and int(r["system"].split("-")[-1]) >= 2000:
            continue
        rec = json.loads((OUT / "curves" / (r["id"] + ".json")).read_text())
        audit = OUT / "strict" / (r["id"] + ".json")
        if audit.exists() and json.loads(audit.read_text())["status"] != "ok":
            continue
        if rec["status"] == "ok":
            records[r["system"]][r["mode"]] = np.asarray(rec["flux"])
        records[r["system"]]["parameters"] = r["parameters"]
    return {k: v for k, v in records.items() if all(m in v for m in MODES)}


def encoded(v, h):
    if h == 0:
        return v
    ft = np.fft.rfft(v, axis=-1) / 256
    return np.concatenate([ft[..., : h + 1].real, ft[..., 1 : h + 1].imag], axis=-1)


def decoded(z, h):
    if h == 0:
        return z
    return (
        np.fft.irfft(
            np.concatenate([z[..., :1], z[..., 1 : h + 1] + 1j * z[..., h + 1 :]], axis=-1),
            n=256,
            axis=-1,
        )
        * 256
    )


def grid(records, family, reduced=False):
    dims = ["inclination", "radius_primary"] if family == "surface" else ["inclination"]
    axes = [sorted({v["parameters"][k] for v in records.values()}) for k in dims]
    if reduced:
        axes = [sorted(set(a[::2] + a[-1:])) for a in axes]
    shape = tuple(map(len, axes))
    table = np.full((*shape, 3, 256), np.nan)
    for v in records.values():
        p = v["parameters"]
        if any(p[k] not in a for k, a in zip(dims, axes)):
            continue
        index = tuple(a.index(p[k]) for a, k in zip(axes, dims))
        table[index] = [v[m] - v["sphere"] for m in MODES[1:]]
    assert np.isfinite(table).all()
    return dims, axes, table


def arrays(records, bases, dims):
    ids = list(records)
    x = np.array([[records[i]["parameters"][k] for k in dims] for i in ids])
    truth = np.array([[records[i][m] for m in MODES[1:]] for i in ids])
    base = np.array([bases[i] for i in ids])[:, None, :]
    return ids, x, truth, base


def candidate(axes, table, x, h, additive=False):
    z = RegularGridInterpolator(axes, encoded(table, h))(x)
    v = decoded(z, h)
    if additive:
        v[:, 2] = v[:, 0] + v[:, 1]
    return v


def main(family):
    status("Fitting surface corrections for " + family + " using system-grouped validation.")
    tr = groups(family, {"train"})
    val = groups(family, {"val"})
    bases = json.loads((OUT / "slice-disc.json").read_text())
    sel = {}
    best = None
    for reduced in (True, False):
        dims, axes, t = grid(tr, family, reduced)
        _, x, y, b = arrays(val, bases, dims)
        for h in (4, 12, 32, 0):
            for additive in (False, True):
                r = b + candidate(axes, t, x, h, additive) - y
                key = f"{t.size//(3*256)}-{h}-" + ("sum" if additive else "mode")
                sc = score(r.reshape(-1, 256))
                sel[key] = sc
                if not reduced:
                    rank = (-sc["passed"], sc["rms"])
                    if best is None or rank < best[0]:
                        best = (rank, h, additive, key)
    _, h, additive, winner = best
    save(
        OUT / (family + "-selection.json"),
        dict(winner=winner, validation=sel, training=len(tr), validation_systems=len(val)),
    )
    # Selection is frozen before any blind/probe targets are read.
    blind = groups(family, {"blind", "probe"})
    fixed = {k: next(iter(tr.values()))["parameters"][k] for k in KEYS if k not in dims}
    blind = {
        k: v for k, v in blind.items() if all(v["parameters"][j] == z for j, z in fixed.items())
    }
    ids, x, y, b = arrays(blind, bases, dims)
    pr = b + candidate(axes, t, x, h, additive)
    ss = np.array([blind[i]["sphere"] for i in ids])
    interaction = y[:, 2] - y[:, 0] - y[:, 1] + ss
    estimated = pr[:, 2] - pr[:, 0] - pr[:, 1] + b[:, 0]
    report = {}
    cases = []
    ok = True
    for j, m in enumerate(MODES[1:]):
        rec = [
            dict(id=i, mode=m, **details([blind[i]["parameters"][k] for k in KEYS], yy, zz))
            for i, yy, zz in zip(ids, y[:, j], pr[:, j])
        ]
        cases.extend(rec)
        sc = score(pr[:, j] - y[:, j])
        bs = score(b[:, 0] - y[:, j])
        diag = summarize(rec)
        ok = (
            bool(np.all(pr[:, j] > 0))
            and ok
            and sc["passed"] == len(rec)
            and sc["rms"] < bs["rms"]
            and diag["depth"]["max"] <= GATES["depth_max"]
            and diag.get("width", {"max": 0})["max"] <= GATES["width_max_cycles"]
        )
        report[m] = dict(
            candidate=sc,
            spherical=bs,
            shape=diag,
            worst=max(rec, key=lambda r: r["maximum"])["id"],
        )
    if family == "eccentric":
        at30 = [r for r in cases if r["id"] == "eccentric-blind-0002"]
        ok = (
            ok
            and len(at30) == 3
            and all(
                abs(r["ooe_predicted"] - r["ooe_actual"]) < 0.2 * r["ooe_actual"] for r in at30
            )
        )
    report["interaction"] = dict(
        exact_rms=float(np.mean(interaction**2) ** 0.5),
        exact_max=float(abs(interaction).max()),
        prediction_error=score(estimated - interaction),
    )
    report["accepted"] = bool(ok)
    save(OUT / (family + "-test.json"), report)
    save(OUT / (family + "-errors.json"), cases)
    np.savez_compressed(
        OUT / (family + "-predictions.npz"), ids=ids, truth=y, pred=pr, base=b, sphere=ss
    )
    z = encoded(t, h)
    artifact = dict(
        dims=dims,
        axes=axes,
        fixed=fixed,
        harmonics=h,
        additive=additive,
        accepted=bool(ok),
        modes=MODES[1:],
        coefficients=base64.b64encode(z.astype("<f4").tobytes()).decode(),
    )
    save(OUT / (family + "-candidate.json"), artifact)
    status(f"{family} held-out evaluation finished. Winner {winner}, accepted {bool(ok)}.")


if __name__ == "__main__":
    main(sys.argv[1])
