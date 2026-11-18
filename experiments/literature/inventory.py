import json
from common import OUT, KEYS, save
from archive import study_rows
from collections import Counter, defaultdict
import csv
import numpy as np


def main():
    rows = study_rows()
    counts = defaultdict(Counter)
    times = defaultdict(list)
    recent = {}
    training = []
    results = {}
    ids = set()
    with (OUT / "exact-index.csv").open("w") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "id",
                "system",
                "family",
                "split",
                "mode",
                "nphase",
                "triangles",
                "status",
                "seconds",
                *KEYS,
            ]
        )
        for r in rows:
            assert r["id"] not in ids
            ids.add(r["id"])
            fpath = OUT / "curves" / (r["id"] + ".json")
            rec = json.loads(fpath.read_text())
            p = [r["parameters"][k] for k in KEYS]
            writer.writerow(
                [r[k] for k in ["id", "system", "family", "split", "mode", "phases", "triangles"]]
                + [rec["status"], rec["seconds"], *p]
            )
            group = (r["family"], r["split"], r["mode"])
            counts[group][rec["status"]] += 1
            times[r["mode"]].append(rec["seconds"])
            if (
                r["family"] == "wide"
                and r["split"] == "train"
                and r["mode"] == "sphere"
                and rec["status"] == "ok"
            ):
                training.append(p)
            if rec["status"] == "ok" and r["family"] == "surface" and r["split"] == "probe":
                results[r["id"]] = np.array(rec["flux"])
    resolution = []
    for r in rows:
        if r["triangles"] <= 400:
            continue
        i = r["system"] + "-" + r["mode"]
        if i not in results or r["id"] not in results:
            continue
        coarse = results[i]
        dense = np.interp(np.arange(512) / 512, np.arange(256) / 256, coarse, period=1)
        delta = dense - results[r["id"]]
        resolution.append(
            dict(id=i, rms=float(np.mean(delta**2) ** 0.5), maximum=float(abs(delta).max()))
        )
    # Inspect every checkpoint and its sibling relationships once more.
    batches = [json.loads(line) for line in (OUT / "scheduling.jsonl").read_text().splitlines()]
    assert all(b["after"] > b["before"] for b in batches)
    extra = set(p.stem for p in (OUT / "curves").glob("*.json")) - ids
    assert not extra
    p = np.array(training)
    total = Counter()
    for c in counts.values():
        total.update(c)
    strict_rows = [json.loads(f.read_text()) for f in (OUT / "strict").glob("*.json")]
    strict_counts = Counter(r["status"] for r in strict_rows)
    strict_delta = []
    for rec in strict_rows:
        if rec["status"] == "ok":
            original = json.loads((OUT / "curves" / (rec["id"] + ".json")).read_text())
            strict_delta.append(float(abs(np.array(rec["flux"]) - original["flux"]).max()))
    slice_errors = [
        r["id"] for r in strict_rows if r["status"] != "ok" and not r["id"].startswith("wide-")
    ]
    if slice_errors:
        raise ValueError(f"Slice atmosphere audit failed: {slice_errors}")
    save(
        OUT / "inventory.json",
        dict(
            strict_audit=dict(
                counts=dict(strict_counts), max_flux_change=max(strict_delta, default=0)
            ),
            attempted=len(rows),
            totals=dict(total),
            counts={"/".join(k): dict(v) for k, v in counts.items()},
            seconds_quantiles={
                k: np.quantile(v, [0.5, 0.95, 1]).tolist() for k, v in times.items()
            },
            resolution=resolution,
            batches=len(batches),
            batch_seconds=sum(b["elapsed"] for b in batches),
            durable_first=batches[0]["before"],
            durable_last=batches[-1]["after"],
            training_limits={
                k: np.quantile(col, [0, 0.05, 0.5, 0.95, 1]).tolist() for k, col in zip(KEYS, p.T)
            },
            spherical_valid_train=len(p),
        ),
    )


if __name__ == "__main__":
    main()
