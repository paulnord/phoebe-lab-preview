from fit_wide import orbit, score
import numpy as np


def shape(y, window, outside):
    # Reconstruct the local continuum between neighboring non-occulted phase samples.
    j = np.arange(len(y))
    clear = j[outside]
    if len(clear) < 2:
        return None
    continuum = np.interp(j, clear, y[clear], period=len(j))
    deficit = np.where(window & ~outside, continuum - y, 0)
    peak = int(deficit.argmax())
    depth = float(deficit[peak])
    if depth < 0.01:
        return dict(depth=depth)

    def cross(level, step):
        for k in range(1, len(y)):
            a, b = (peak + (k - 1) * step) % len(y), (peak + k * step) % len(y)
            if deficit[b] <= level:
                return (
                    peak + step * (k - 1 + (deficit[a] - level) / (deficit[a] - deficit[b]))
                ) / len(y)
        raise ValueError("missing crossing")

    left, right = cross(0.5 * depth, -1), cross(0.5 * depth, 1)
    return dict(
        depth=depth,
        width=right - left,
        minimum=peak / len(y),
        midpoint=(left + right) / 2,
        ingress=cross(0.9 * depth, -1) - cross(0.1 * depth, -1),
        egress=cross(0.1 * depth, 1) - cross(0.9 * depth, 1),
    )


def details(params, exact, pred):
    sep, fore = orbit(np.array([params]))
    outside = sep[0] > params[1] + params[2]
    error = pred - exact
    a = dict(rms=float(np.mean(error**2) ** 0.5), maximum=float(abs(error).max()))
    if outside.any():
        a.update(
            ooe_max=float(abs(error[outside]).max()),
            ooe_ptp_error=float(abs(np.ptp(exact[outside]) - np.ptp(pred[outside]))),
            ooe_actual=float(np.ptp(exact[outside])),
            ooe_predicted=float(np.ptp(pred[outside])),
        )
    # Compare shoulders separately in orbital order (periodic at the seam).
    for key, shift in [("before", 1), ("after", -1)]:
        mask = outside & np.any([~np.roll(outside, -shift * k) for k in range(1, 5)], axis=0)
        if mask.any():
            a[key] = float(abs(error[mask]).max())
    metrics = {}
    for mask in (fore[0], ~fore[0]):
        x, y = shape(exact, mask, outside), shape(pred, mask, outside)
        if x is None or y is None:
            continue
        if ("width" in x) != ("width" in y):
            a["threshold_disagreement"] = 1
        for k in x.keys() & y.keys():
            v = x[k] - y[k]
            if k in ("midpoint", "minimum"):
                v = (v + 0.5) % 1 - 0.5
            metrics.setdefault(k, []).append(abs(v))
    for k, v in metrics.items():
        a[k] = float(max(v))
    return a


def summarize(records):
    return {
        k: dict(n=len(v), max=float(max(v)), p95=float(np.percentile(v, 95)))
        for k in set().union(*(r.keys() for r in records))
        if (v := [r[k] for r in records if k in r and isinstance(r[k], (float, int))])
    }
