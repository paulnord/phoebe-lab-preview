import json
from common import OUT, KEYS
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from archive import study_rows


def main():
    phase = np.arange(256) / 256 - 0.5
    fig, axes = plt.subplots(2, 2, figsize=(11, 6), constrained_layout=True)
    for ax, family, key in [
        (axes[0, 0], "eccentric", "eccentric-blind-0002"),
        (axes[1, 0], "surface", "surface-probe-0002"),
    ]:
        d = np.load(OUT / (family + "-predictions.npz"))
        i = list(d["ids"]).index(key)
        ax.plot(phase, d["sphere"][i], color="#666666", lw=1, label="Spherical exact")
        for j, (color, label) in enumerate(
            zip(["#276A9A", "#DC8800", "#6F4285"], ["Roche", "Horvat", "Both"])
        ):
            ax.plot(phase, d["truth"][i, j], color=color, lw=1.7, label=label + " exact")
            ax.plot(phase[::8], d["pred"][i, j, ::8], ".", color=color, ms=3)
        ax.set(
            title=(
                "30° eccentric example"
                if family == "eccentric"
                else "83.2° circular eclipsing pair"
            ),
            xlabel="Orbital phase",
            ylabel="Normalized Johnson V flux",
        )
        if family == "eccentric":
            ax.legend(ncol=2, fontsize=8)
    for ax, group in [(axes[0, 1], "surface"), (axes[1, 1], "mixed")]:
        d = np.load(OUT / (group + "-predictions.npz"))
        y = d["truth"][:, 1:] if group == "mixed" else d["truth"]
        b = d["base"] if group == "surface" else d["base"][:, None, :]
        for loss, label, color in [
            (d["pred"] - y, "Surface correction", "#6F4285"),
            (b - y, "Spherical discs", "#666666"),
        ]:
            err = np.sqrt(np.mean(loss**2, axis=-1)).ravel()
            ax.plot(
                np.sort(np.maximum(err, 1.0e-8)),
                np.arange(1, len(err) + 1) / len(err),
                color=color,
                label=label,
            )
        ax.set(
            xscale="log",
            xlabel="Per-curve RMS flux error",
            ylabel="Cumulative fraction",
            title=("Circular slice" if group == "surface" else "Eight-slider pairs"),
        )
        ax.legend(fontsize=8)
    fig.savefig(OUT / "surfaces.png", dpi=145)
    plt.close(fig)
    fig, a = plt.subplots(1, 3, figsize=(12, 3.8), constrained_layout=True)
    rows = study_rows()
    for stage, col in [("initial", "#88929B"), ("enriched", "#326974")]:
        part = [
            r
            for r in rows
            if r["mode"] == "sphere"
            and r["family"] == "wide"
            and r["split"] == "train"
            and (int(r["system"].split("-")[-1]) >= 2000) == (stage == "enriched")
            and json.loads((OUT / "curves" / (r["id"] + ".json")).read_text())["status"] == "ok"
        ]
        p = np.array([[r["parameters"][k] for k in KEYS] for r in part])
        for ax, x, y in zip(a[:2], [1, 5], [2, 3]):
            ax.scatter(p[:, x], p[:, y], s=4, alpha=0.45, color=col, label=stage)
    a[0].set(xlabel="Primary radius / a", ylabel="Secondary radius / a")
    a[1].set(xscale="log", xlabel="Period (days)", ylabel="T₂ / T₁")
    a[0].legend(fontsize=8)
    cases = json.loads((OUT / "wide-errors.json").read_text())
    for sp in ("blind", "enriched", "legacy-ordinary"):
        v = sorted(r["rms"] for r in cases if r["split"] == sp)
        a[2].plot(v, np.arange(1, len(v) + 1) / len(v), label=sp)
    a[2].set(xlabel="Per-curve RMS", ylabel="Cumulative fraction")
    a[2].legend(fontsize=8)
    fig.savefig(OUT / "wider.png", dpi=145)
    plt.close(fig)


if __name__ == "__main__":
    main()
