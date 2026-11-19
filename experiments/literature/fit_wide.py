"""Train disc residuals with an eclipse-aligned head and phase-sampled/Fourier heads."""

import json
import sys
from common import OUT, OLD, KEYS, save, status
from archive import study_rows
from collections import Counter
import numpy as np

from pathlib import Path

GATES = json.loads(Path(__file__).with_name("gates.json").read_text())
N = 256


def coordinates():
    coords = json.loads((OUT / "coordinates.json").read_text())
    p = np.array([[r["parameters"][k] for k in KEYS] for r in coords])
    return coords, p, np.memmap(OUT / "disc.f64", dtype="<f8", mode="r", shape=(len(p), N))


def orbital_coordinates(p):
    inc, r, s, t, q, period, e, w = p.T
    w = np.deg2rad(w)[:, None]
    e = e[:, None]
    nu = np.pi / 2 - w
    E = 2 * np.arctan2(np.sqrt(1 - e) * np.sin(nu / 2), np.sqrt(1 + e) * np.cos(nu / 2))
    mean = E - e * np.sin(E) + 2 * np.pi * (np.arange(N) / N - 0.5)
    E = mean.copy()
    for _ in range(6):
        E -= (E - e * np.sin(E) - mean) / (1 - e * np.cos(E))
    x = np.cos(E) - e
    y = np.sqrt(1 - e * e) * np.sin(E)
    across = x * np.sin(w) + y * np.cos(w)
    return x * np.cos(w) - y * np.sin(w), across, 1 - e * np.cos(E)


def orbit(p):
    along, across, _ = orbital_coordinates(p)
    return np.hypot(along, across * np.cos(np.radians(p[:, 0]))[:, None]), across >= 0


def profiles(p, disc):
    _, front = orbit(p)
    depth = 1 - disc

    def part(mask):
        d = depth * mask
        return d / np.maximum(0.02, d.max(axis=1, keepdims=True))

    a, b = part(front), part(~front)
    return np.stack((a, a * (1 - a), b, b * (1 - b)), axis=-1)


def features(p, disc):
    inc, r, s, t, q, days, e, w = p.T
    sep, fore = orbit(p)
    z = np.column_stack(
        (
            np.cos(np.radians(inc)),
            r,
            s,
            t,
            np.log(q),
            np.log(days),
            e * np.cos(np.radians(w)),
            e * np.sin(np.radians(w)),
            s / r,
            *[np.min(np.where(mask, sep, 2), axis=1) / (r + s) for mask in (fore, ~fore)],
            1 - disc.min(1),
        )
    )
    scale = np.array([0.4, 0.12, 0.10, 0.32, 0.8, 2, 0.35, 0.35, 1.0, 1.0, 1.0, 0.18])
    mean = np.array([0.35, 0.18, 0.16, 0.95, -0.1, 1.5, 0, 0, 1.0, 0.85, 0.85, 0.12])
    z = np.clip((z - mean) / scale, -5, 5)
    rng = np.random.default_rng(14985)
    return np.column_stack(
        (
            np.ones(len(z)),
            z,
            np.tanh(z @ rng.normal(size=(z.shape[1], 144)) / 2 + rng.normal(size=144)),
        )
    )


def targets(p, disc, y):
    a = profiles(p, disc)
    at = a.transpose(0, 2, 1)
    return np.linalg.solve(at @ a + 0.006 * np.eye(4), at @ (y - disc)[:, :, None])[:, :, 0]


def fit(x, y, weight):
    w = x.T * weight
    return np.linalg.solve(w @ x + 0.12 * np.eye(x.shape[1]), w @ y)


def harmonic(y, h):
    f = np.fft.rfft(y, axis=-1)
    f[:, h + 1 :] = 0
    return np.fft.irfft(f, n=N, axis=-1)


def score(d):
    r = np.sqrt((d * d).mean(1))
    m = abs(d).max(1)
    return dict(
        n=len(r),
        rms=float(np.mean(d * d) ** 0.5),
        maximum=float(m.max()),
        p50=float(np.median(r)),
        p95=float(np.quantile(r, 0.95)),
        p95_max=float(np.quantile(m, 0.95)),
        passed=int(((r <= GATES["curve_rms"]) & (m <= GATES["point_max"])).sum()),
    )


def predict(kind, w, x, a, disc):
    if kind == "disc":
        return disc
    y = x @ w
    if kind == "profile":
        y = np.einsum("ijk,ik->ij", a, y)
    elif kind == "fourier":
        y = harmonic(y, 16)
    return disc + y


def gather(split, original_only=False):
    c, p, base = coordinates()
    idx = {r["id"]: i for i, r in enumerate(c)}
    rows = [
        r
        for r in study_rows()
        if r["family"] == "wide"
        and r["mode"] == "sphere"
        and r["split"] in split
        and (not original_only or int(r["system"].split("-")[-1]) < 2000)
    ]
    ii = []
    ys = []
    rs = []
    counts = Counter()
    for r in rows:
        rec = json.loads((OUT / "curves" / (r["id"] + ".json")).read_text())
        j = idx[r["system"]]
        state = rec["status"]
        if state == "ok" and not np.isfinite(base[j]).all():
            state = "disc_unsupported"
        counts[state] += 1
        if state == "ok":
            ii.append(j)
            ys.append(rec["flux"])
            rs.append(r)
    return p[ii], base[ii], np.array(ys), rs, dict(counts)


def fit_all(original_only=False):
    status(
        "Starting wider fit. Selection uses validation flux pass count, then pooled RMS. Held-out shape checks follow the frozen selection."
    )
    p, b, y, rows, counts = gather({"train"}, original_only)
    v, vb, vy, _, vc = gather({"val"})
    coords, pp, db = coordinates()
    hist = np.load(OLD / "share/training.npz")
    history_flux = hist["flux"]
    hi = [
        j for j, r in enumerate(coords) if r["id"].startswith("hist-") and np.isfinite(db[j]).all()
    ]
    hids = [int(coords[j]["id"][5:]) for j in hi]

    def prep(pp, bb, yy):
        return features(pp, bb), targets(pp, bb, yy), yy - bb

    hx = []
    ht = []
    hr = []
    for j in range(0, len(hi), 256):
        ix = hi[j : j + 256]
        a, c, d = prep(pp[ix], db[ix], history_flux[hids[j : j + 256]])
        hx.extend(a)
        ht.extend(c)
        hr.extend(d)
    hx, ht, hr = map(np.array, (hx, ht, hr))
    x, t, res = prep(p, b, y)
    vx = features(v, vb)
    va = profiles(v, vb)
    scores = {}
    weights = {}
    for n in sorted(set([min(192, len(x)), min(512, len(x)), len(x)])):
        for label in ("new", "pooled"):
            X = x[:n]
            T = t[:n]
            R = res[:n]
            w = np.ones(n)
            if label == "pooled":
                X = np.vstack((X, hx))
                T = np.vstack((T, ht))
                R = np.vstack((R, hr))
                w = np.r_[w, np.full(len(hx), n / len(hx))]
            pw = fit(X, T, w)
            rw = fit(X, R, w)
            for kind, W in [("disc", None), ("profile", pw), ("direct", rw), ("fourier", rw)]:
                name = f"{kind}-{label}-{n}"
                scores[name] = score(predict(kind, W, vx, va, vb) - vy)
                if n == len(x) and W is not None:
                    weights[name] = W
    finalists = [k for k in scores if k.endswith("-" + str(len(x)))]
    winner = min(finalists, key=lambda k: (-scores[k]["passed"], scores[k]["rms"]))
    prefix = "initial" if original_only else "wide"
    save(
        OUT / (prefix + "-selection.json"),
        dict(winner=winner, validation=scores, train=counts, val=vc, historical_used=len(hi)),
    )
    np.savez_compressed(OUT / (prefix + "-weights.npz"), **weights)
    status(
        f"Wider fit frozen. {len(x)} wider and {len(hi)} historical eligible targets. Validation chose {winner}."
    )


if __name__ == "__main__":
    fit_all("--initial" in sys.argv)
