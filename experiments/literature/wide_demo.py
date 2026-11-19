"""Package an isolated browser comparison over exact held-out parameter vectors."""

import json
from pathlib import Path
from common import OUT, KEYS, save
import numpy as np
import base64, shutil


def wire(a):
    return base64.b64encode(np.ascontiguousarray(a, dtype="<f8").tobytes()).decode()


def main():
    dest = OUT / "demo/study"
    dest.mkdir(parents=True, exist_ok=True)
    m = json.loads((OUT / "wide-selection.json").read_text())
    name = m["winner"]
    kind = name.split("-")[0]
    rng = np.random.default_rng(14985)
    A = rng.normal(size=(12, 144)) / 2
    bias = rng.normal(size=144)
    if kind == "disc":
        w = np.zeros((157, 0))
    else:
        w = np.load(OUT / "wide-weights.npz")[name]
    if kind == "fourier":
        ft = np.fft.rfft(w, axis=1) / 256
        w = np.c_[ft[:, :17].real, ft[:, 1:17].imag]
    save(
        dest / "model.json",
        dict(
            name=name,
            kind=kind,
            projection=wire(A),
            bias=bias.tolist(),
            w=wire(w),
            columns=w.shape[1],
        ),
    )
    data = []
    for split in ("blind", "enriched", "boundary", "grazing", "track"):
        d = np.load(OUT / ("wide-" + split + "-predictions.npz"))
        for i, key in enumerate(d["ids"]):
            data.append(
                dict(
                    id=str(key),
                    p=dict(zip(KEYS, d["parameters"][i])),
                    expected=d["pred"][i].tolist(),
                    exact=d["exact"][i].tolist(),
                )
            )
    save(dest / "cases.json", data)
    shutil.copy(OUT / "table.json", dest / "table.json")
    for name in ("study.html", "wide_predict.mjs"):
        shutil.copy(Path(__file__).with_name(name), dest / name)


if __name__ == "__main__":
    main()
