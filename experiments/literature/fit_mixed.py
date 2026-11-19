"""Paired eight-slider surface fits. Use complete four-mode systems throughout."""

import sys
from common import OUT, save, status
from fit_surface import MODES, groups
from fit_wide import coordinates, features, harmonic, score, orbital_coordinates
from diagnostics import details, summarize
import numpy as np


def components(p, base):
    inclination, r, s, t, q, _, e, _ = p.T
    _, across, dist = orbital_coordinates(p)
    c = np.clip(across / dist * np.sin(np.radians(inclination))[:, None], -1, 1)

    def lambert(c):
        return (np.sqrt(np.maximum(0, 1 - c * c)) + (np.pi - np.arccos(c)) * c) / np.pi

    # Broad-band luminosity proxy. Regression calibrates these on Johnson V.
    L = r * r / (r * r + s * s * t**4)
    tidal = q * r**3 * L + s**3 / q * (1 - L)
    heatA = L * s**2
    heatB = (1 - L) * r**2
    tidal_scale = tidal[:, None] / dist**3
    heat_scale = (heatA + heatB)[:, None] / dist**2
    basis = np.stack(
        [
            tidal_scale * (1 - 2 * c * c),
            tidal_scale,
            heatA[:, None] * lambert(-c) / dist**2,
            heatB[:, None] * lambert(c) / dist**2,
            heat_scale,
            (1 - base) * tidal_scale,
            (1 - base) * heat_scale,
        ],
        axis=-1,
    )
    basis -= np.median(basis, axis=1, keepdims=True)
    amp = np.stack((tidal, heatA + heatB, tidal + heatA + heatB), axis=1)
    return basis, np.maximum(0.002, amp / (1 - e[:, None]) ** 2)


def data(split, index, p, base, original_only=False, family="wide"):
    records = groups(family, {split}, original_only)
    ids = [k for k in records if np.isfinite(base[index[k]]).all()]
    ii = [index[k] for k in ids]
    pp, bb = p[ii], base[ii]
    y = np.array([[records[k][m] for m in MODES] for k in ids])
    x = features(pp, bb)[:, :49]
    A, amps = components(pp, bb)
    return ids, pp, bb, y, x, A, amps


def fit(d, n):
    _, _, b, y, x, A, amps = d
    y, x, A, amps = y[:n], x[:n], A[:n], amps[:n]
    diff = y[:, 1:] - y[:, :1]
    weights = []
    for j in range(3):
        aj = A / amps[:, j, None, None]
        yj = diff[:, j] / amps[:, j, None]
        a = aj.reshape(-1, aj.shape[-1])
        weights.append(np.linalg.solve(a.T @ a + 0.2 * np.eye(a.shape[-1]), a.T @ yj.ravel()))
    coefficients = np.array(weights)
    ph = np.einsum("npk,mk->nmp", A, coefficients)
    response = (diff - ph) / amps[:, :, None]
    ridge = np.linalg.solve(x.T @ x + 2 * np.eye(x.shape[1]), x.T @ response.reshape(n, -1))
    return coefficients, ridge


def predict(d, co, ridge, kind):
    _, _, b, _, x, A, amps = d
    ph = np.einsum("npk,mk->nmp", A, co)
    if kind == "disc":
        return np.broadcast_to(b[:, None, :], ph.shape)
    if kind != "physics":
        r = (x @ ridge).reshape(-1, 3, 256)
        if kind.startswith("fourier"):
            r = harmonic(r.reshape(-1, 256), int(kind[7:])).reshape(ph.shape)
        ph += r * amps[:, :, None]
    return b[:, None, :] + ph


def main(initial=False):
    c, p, base = coordinates()
    idx = {r["id"]: i for i, r in enumerate(c)}
    # Fitting uses the prescribed paired subset; other spherical rows have no siblings.
    tr = data("train", idx, p, base, initial)
    val = data("val", idx, p, base)
    status(f"Starting broad surface regression on {len(tr[0])} complete supported systems.")
    scores = {}
    original = sum(int(key.split("-")[-1]) < 2000 for key in tr[0])
    fits = {}
    for n in sorted({max(8, original // 2), original, len(tr[0])}):
        co, w = fit(tr, n)
        fits[n] = (co, w)
        for kind in ("disc", "physics", "direct", "fourier4", "fourier12"):
            pred = predict(val, co, w, kind)
            scores[f"{n}-{kind}"] = score((pred - val[3][:, 1:]).reshape(-1, 256))
    choices = list(scores)
    best = min(choices, key=lambda k: (-scores[k]["passed"], scores[k]["rms"]))
    save(
        OUT / ("mixed-initial.json" if initial else "mixed-selection.json"),
        dict(winner=best, validation=scores, systems=[len(tr[0]), len(val[0])]),
    )
    if initial:
        return
    co, w = fits[int(best.split("-")[0])]
    np.savez_compressed(
        OUT / "mixed-weights.npz",
        head=best.split("-")[1],
        physics=co,
        residual=w,
        training_ids=tr[0][: int(best.split("-")[0])],
    )
    blind = data("blind", idx, p, base)
    enriched = data("enriched", idx, p, base)
    tst = (
        blind[0] + enriched[0],
        *[np.concatenate((a, b)) for a, b in zip(blind[1:], enriched[1:])],
    )
    pred = predict(tst, co, w, best.split("-")[1])
    ids, pp, b, y, *_ = tst
    rep = {}
    errors = []
    for j, m in enumerate(MODES[1:]):
        truth = y[:, j + 1]
        rec = [
            dict(id=k, mode=m, **details(q, a, z))
            for k, q, a, z in zip(ids, pp, truth, pred[:, j])
        ]
        errors += rec
        rep[m] = dict(
            candidate=score(pred[:, j] - truth),
            ordinary=score((pred[:, j] - truth)[: len(blind[0])]),
            enriched=score((pred[:, j] - truth)[len(blind[0]) :]),
            sphere=score(b - truth),
            oracle_sphere=score(y[:, 0] - truth),
            diagnostics=summarize(rec),
            worst=max(rec, key=lambda r: r["maximum"])["id"],
        )
    true_inter = y[:, 3] - y[:, 2] - y[:, 1] + y[:, 0]
    pred_inter = pred[:, 2] - pred[:, 1] - pred[:, 0] + b
    rep["interaction"] = dict(
        exact_rms=float(np.mean(true_inter**2) ** 0.5), error=score(pred_inter - true_inter)
    )
    np.savez_compressed(OUT / "mixed-predictions.npz", ids=ids, truth=y, pred=pred, base=b)
    transfers = {}
    for family in ("surface", "eccentric"):
        extra = data("blind", idx, p, base, family=family)
        q = predict(extra, co, w, best.split("-")[1])
        targets = extra[3][:, 1:]
        entry = {m: score(q[:, j] - targets[:, j]) for j, m in enumerate(MODES[1:])}
        if family == "eccentric":
            i = extra[0].index("eccentric-blind-0002")
            entry["at30"] = {
                m: dict(actual=float(np.ptp(targets[i, j])), predicted=float(np.ptp(q[i, j])))
                for j, m in enumerate(MODES[1:])
            }
        transfers[family] = entry
    save(OUT / "mixed-transfer.json", transfers)
    save(OUT / "mixed-test.json", rep)
    save(OUT / "mixed-errors.json", errors)
    status(
        "Broad paired benchmark complete. Frozen validation choice and individual blind errors saved."
    )


if __name__ == "__main__":
    main("--initial" in sys.argv)
