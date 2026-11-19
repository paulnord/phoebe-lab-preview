import json
from pathlib import Path
from common import OUT, KEYS, sha, save
import csv, itertools, math
import numpy as np
from scipy.stats import qmc
from astropy import constants as C, units as U
import model
from scipy import __version__ as scipy_version


def catalog():
    lines = [s for s in (OUT / "cds.tsv").read_text().splitlines() if s and not s.startswith("#")]
    reader = csv.DictReader([lines[0], *lines[3:]], delimiter="\t")
    props = {}
    for row in reader:

        def val(k):
            t = row[k].strip()
            return float(t) if t and float(t) != -9.99 else np.nan

        m1, m2 = 10 ** val("logM1"), 10 ** val("logM2")
        days = val("Per")
        a = (
            (C.G * C.M_sun * (m1 + m2) * (days * U.day) ** 2 / (4 * np.pi**2)) ** (1 / 3)
        ).to_value(U.R_sun)
        for key, v in dict(
            period=days,
            mass_ratio=m2 / m1,
            radius_primary=10 ** val("logR1") / a,
            radius_secondary=10 ** val("logR2") / a,
            temperature_ratio=10 ** (val("logT2") - val("logT1")),
            T1=10 ** val("logT1"),
        ).items():
            if np.isfinite(v):
                props.setdefault(key, []).append(v)
    save(
        OUT / "catalog.json",
        {
            k: dict(n=len(v), p0_05_50_95_100=np.percentile(v, [0, 5, 50, 95, 100]).tolist())
            for k, v in props.items()
        },
    )


def design():
    rows = []
    bounds = [
        [0, 90],
        [0.025, 0.36],
        [0.02, 0.33],
        [0.56, 1.5],
        [0.15, 2],
        [0.3, 300],
        [0, 0.65],
        [0, 360],
    ]
    fixed = dict(model.DEFAULTS, period=1.83, mass_ratio=0.77, temperature_ratio=0.845)
    modes = ["sphere", "tides", "heat", "both"]

    def add(family, split, i, p, modes, mesh=400, n=256):
        group = f"{family}-{split}-{i:04d}"
        for mode in modes:
            pars = dict(
                p, distortion=mode in ("tides", "both"), irradiation=mode in ("heat", "both")
            )
            rows.append(
                dict(
                    id=group + "-" + mode + ("" if mesh == 400 and n == 256 else f"-{mesh}-{n}"),
                    system=group,
                    family=family,
                    split=split,
                    mode=mode,
                    parameters=pars,
                    triangles=mesh,
                    phases=n,
                )
            )

    for si, (split, count) in enumerate(
        [
            ("train", 1280),
            ("val", 128),
            ("blind", 192),
            ("grazing", 32),
            ("boundary", 32),
            ("track", 17),
        ]
    ):
        seq = qmc.Sobol(10, seed=19261118 + si).random_base2(11)
        for i, u in enumerate(seq[:count]):
            if split == "track":
                u[:8] = [
                    0.79 + 0.20 * i / 16,
                    0.36 + 0.36 * i / 16,
                    0.84 - 0.6 * i / 16,
                    0.87 - 0.84 * i / 16,
                    0.23 + 0.59 * i / 16,
                    0.66 - 0.33 * i / 16,
                    0.72 - 0.64 * i / 16,
                    0.2 + 0.75 * i / 16,
                ]
            p = dict(model.DEFAULTS)
            for k, x, (a, b) in zip(KEYS, u, bounds):
                p[k] = a * (b / a) ** x if k == "period" else a + (b - a) * x
            # Deliberately mix eclipse-favoured orientations and isotropic orientations.
            p["inclination"] = 60 + 30 * u[0] if u[8] < 0.65 else math.degrees(math.acos(u[0]))
            if split == "boundary":
                j = (i // 2) % 8
                p[KEYS[j]] = bounds[j][i % 2]
            if split == "grazing":
                e = p["eccentricity"]
                contact = (
                    (p["radius_primary"] + p["radius_secondary"])
                    * (1 + (-1) ** i * e * np.sin(np.deg2rad(p["omega"])))
                    / (1 - e * e)
                )
                p["inclination"] = np.clip(
                    np.degrees(np.arccos(min(1, contact))) + 2 * (u[9] - 0.5), 0, 90
                )
            add("wide", split, i, p, ["sphere"])
    inc = [0, 12, 24, 36, 48, 58, 64, 68, 72, 76, 80, 84, 87, 90]
    rad = [0.14, 0.175, 0.21, 0.245, 0.28]
    for i, (a, r) in enumerate(itertools.product(inc, rad)):
        add("surface", "train", i, dict(fixed, inclination=a, radius_primary=r), modes)
    for si, (split, count) in enumerate([("val", 28), ("blind", 52)]):
        for i, (v, w) in enumerate(qmc.Sobol(2, seed=19261148 + si).random_base2(6)[:count]):
            a = 90 * v if i % 3 == 0 else 60 + 30 * v
            add(
                "surface",
                split,
                i,
                dict(fixed, inclination=round(a, 1), radius_primary=round(0.14 + 0.14 * w, 3)),
                modes,
            )
    for i, p in enumerate(
        [
            dict(fixed, inclination=30),
            dict(model.DEFAULTS, inclination=30),
            dict(fixed, inclination=83.2, radius_primary=0.232),
        ]
    ):
        add("surface", "probe", i, p, modes)
        if i != 1:
            add("surface", "probe", i, p, modes, 1500, 512)
    # Four varied physical systems x four modes are timed in the pilot.
    pilot = [
        ("surface", "train", 36),
        ("surface", "train", 64),
        ("wide", "train", 0),
        ("wide", "train", 1),
    ]
    for i in (0, 1):
        row = next(r for r in rows if r["system"] == f"wide-train-{i:04d}")
        add("wide", "train", i, row["parameters"], modes[1:])
    ids = [r["id"] for fam, sp, i in pilot for r in rows if r["system"] == f"{fam}-{sp}-{i:04d}"]
    pb = Path(model.phoebe.list_installed_passbands(full_dict=True)["Johnson:V"]["fname"])
    spec = dict(
        keys=KEYS,
        bounds=bounds,
        defaults=model.DEFAULTS,
        surface_fixed=fixed,
        inclination_knots=inc,
        radius_knots=rad,
        phase_grid="arange(n)/n - 0.5",
        phoebe=model.phoebe.__version__,
        numpy=np.__version__,
        scipy=scipy_version,
        passband_sha256=sha(pb),
        engine_sha256=sha(Path(model.__file__)),
        catalog_sha256=sha(OUT / "cds.tsv"),
        pilot=ids,
        cases=rows,
    )
    assert spec["phoebe"] == "2.5.4" and len(ids) == 16
    if (OUT / "manifest.json").exists():
        assert json.loads((OUT / "manifest.json").read_text()) == spec
    else:
        save(OUT / "manifest.json", spec)


if __name__ == "__main__":
    catalog()
    design()
