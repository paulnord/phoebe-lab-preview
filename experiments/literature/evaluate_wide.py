import json
from common import OUT, OLD, save, status
from collections import Counter
import numpy as np
from fit_wide import coordinates, gather, predict, features, profiles, score, orbit
from diagnostics import details, summarize


def main():
    selection = json.loads((OUT / "wide-selection.json").read_text())
    name = selection["winner"]
    kind = name.split("-")[0]
    weights = np.load(OUT / "wide-weights.npz")
    w = weights[name] if name in weights else None
    c, allp, base = coordinates()
    index = {r["id"]: i for i, r in enumerate(c)}
    prev = np.memmap(OUT / "deployed.f64", mode="r", dtype="<f8", shape=base.shape)
    holdouts = json.loads((OLD / "manifest.json").read_text())["cases"]
    report = {}
    cases = []
    for split in [
        "blind",
        "boundary",
        "grazing",
        "track",
        "enriched",
        "legacy-ordinary",
        "legacy-stress",
    ]:
        if split.startswith("legacy"):
            groups = (
                ["blind_ui", "blind_short"]
                if split == "legacy-ordinary"
                else ["faces", "grazing", "path"]
            )
            rows = []
            ys = []
            indices = []
            counts = Counter()
            all_old = []
            all_truth = []
            for r in holdouts:
                if r["group"] not in groups:
                    continue
                rec = json.loads((OLD / "curves" / (r["id"] + ".json")).read_text())
                if rec["status"] != "ok":
                    counts["exact_failure"] += 1
                    continue
                ii = index["old-" + r["id"]]
                all_old.append(prev[ii])
                all_truth.append(rec["flux"])
                if not np.isfinite(base[ii]).all():
                    counts["disc_unsupported"] += 1
                    continue
                indices.append(ii)
                ys.append(rec["flux"])
                rows.append(r)
            p, b, y = allp[indices], base[indices], np.array(ys)
            counts["ok"] = len(rows)
        else:
            p, b, y, rows, counts = gather({split})
            indices = [index[r["system"]] for r in rows]
        pred = predict(kind, w, features(p, b), profiles(p, b), b)
        metrics = [
            dict(id=r["id"], split=split, **details(x, a, z))
            for r, x, a, z in zip(rows, p, y, pred)
        ]
        cases.extend(metrics)
        sep, _ = orbit(p)
        eclipsing = np.any(sep < (p[:, 1] + p[:, 2])[:, None], axis=1)
        subsets = {
            "geometric_eclipse": eclipsing,
            "no_eclipse": ~eclipsing,
            "hotter_secondary": p[:, 3] > 1,
            "cool_secondary": p[:, 3] < 0.66,
            "high_eccentricity": p[:, 6] > 0.35,
            "low_inclination": p[:, 0] < 65,
        }
        by_subset = {k: score((pred - y)[mask]) for k, mask in subsets.items() if mask.any()}
        if split in ("blind", "enriched", "boundary", "grazing", "track"):
            np.savez_compressed(
                OUT / ("wide-" + split + "-predictions.npz"),
                ids=[r["id"] for r in rows],
                parameters=p,
                pred=pred,
                exact=y,
                disc=b,
            )
        entry = dict(
            subsets=by_subset,
            counts=dict(counts),
            selected=score(pred - y),
            disc=score(b - y),
            shape=summarize(metrics),
            worst=max(metrics, key=lambda r: r["maximum"])["id"],
        )
        ok = np.isfinite(prev[indices]).all(1)
        if ok.any():
            entry["matched"] = dict(
                deployed=score(prev[np.array(indices)[ok]] - y[ok]),
                selected=score(pred[ok] - y[ok]),
            )
        if split.startswith("legacy"):
            entry["all_deployed"] = score(np.array(all_old) - all_truth)
        report[split] = entry
    save(OUT / "wide-test.json", report)
    save(OUT / "wide-errors.json", cases)
    status(
        "Wider blind and stress evaluation complete. Matched deployed predictions and curve-level diagnostics saved."
    )


if __name__ == "__main__":
    main()
