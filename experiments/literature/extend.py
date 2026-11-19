"""Enrich physically plausible detached systems after the unconstrained pilot."""

import json
from common import OUT, KEYS, save
from supplement import siblings
from scipy.stats import qmc
import numpy as np


def main():
    spec = json.loads((OUT / "manifest.json").read_text())
    rows = []
    for si, (split, count) in enumerate([("train", 896), ("enriched", 128)]):
        n = 0
        for u in qmc.Sobol(10, seed=20261188 + si).random_base2(14):
            lo, hi = np.array(spec["bounds"]).T
            v = lo + (hi - lo) * u[:8]
            i, r, s, t, q, _, e, w = v
            days = 0.3 * 1000 ** u[5]
            a = 4.2083 * (1.2 * (1 + q) * days**2) ** (1 / 3)

            def lobe(mu):
                z = mu ** (1 / 3)
                return 0.49 * z * z / (0.6 * z * z + np.log1p(z))

            if max(r / lobe(1 / q), s / lobe(q)) > 0.88 * (1 - e):
                continue
            g1 = 4.438 + np.log10(1.2 / (a * r) ** 2)
            g2 = 4.438 + np.log10(1.2 * q / (a * s) ** 2)
            if not 1.7 < min(g1, g2) <= max(g1, g2) < 4.9:
                continue
            # Mostly eclipsing; include the cool and grazing portions deliberately.
            t = 0.56 + 0.1 * u[3] if n % 5 == 0 else t
            contact = (r + s) * (1 + e * np.sin(np.radians(w))) / (1 - e * e)
            i = np.degrees(np.arccos(min(0.999, contact) * u[0])) if n % 4 else i
            if n % 7 == 0:
                i = np.clip(np.degrees(np.arccos(min(0.999, contact))) + 3 * (u[9] - 0.5), 0, 90)
            p = dict(spec["defaults"], **dict(zip(KEYS, [i, r, s, t, q, days, e, w])))
            rows.extend(siblings("wide", split, 2000 + n, p)[:1])
            n += 1
            if n == count:
                break
        assert n == count
    save(OUT / "enrich.json", rows)


if __name__ == "__main__":
    main()
