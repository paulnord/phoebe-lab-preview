#!/usr/bin/env python3
"""Reproduce the held-out published radial-velocity checks."""
from __future__ import annotations

import csv
from pathlib import Path
import numpy as np


HERE = Path(__file__).resolve().parent
DATA = HERE / "data"


def read_csv(name):
    with (DATA / name).open(newline="") as stream:
        return list(csv.DictReader(stream))


def circular_fit(samples, *, weighted):
    """Fit shared gamma and positive K1/K2 for V1=gamma-K1*sin(phi)."""
    design, values, weights = [], [], []
    for phase, rv1, rv2, err1, err2 in samples:
        sine = np.sin(2 * np.pi * phase)
        if rv1 is not None:
            design.append((1., -sine, 0.)); values.append(rv1)
            weights.append(1. / err1**2 if weighted else 1.)
        if rv2 is not None:
            design.append((1., 0., sine)); values.append(rv2)
            weights.append(1. / err2**2 if weighted else 1.)
    matrix, values, weights = np.asarray(design), np.asarray(values), np.asarray(weights)
    root_weight = np.sqrt(weights)
    gamma, k1, k2 = np.linalg.lstsq(matrix * root_weight[:, None], values * root_weight, rcond=None)[0]
    residual = values - matrix @ np.array((gamma, k1, k2))
    return {"gamma": gamma, "k1": k1, "k2": k2, "q": k1 / k2,
            "rms": np.sqrt(np.mean(residual**2)),
            "weighted_rms": np.sqrt(np.sum(weights * residual**2) / np.sum(weights)),
            "measurements": len(values)}


def v1128_result():
    t0, period = 2453864.7026, .3053707
    rows = read_csv("v1128_tau_ddo_all.csv")
    samples = []
    for row in rows:
        if float(row["hjd"]) < 2453711:
            continue
        phase = ((float(row["hjd"]) - t0) / period) % 1
        rv1 = float(row["rv1_km_s"]) if float(row["weight_rv1"]) > 0 else None
        rv2 = float(row["rv2_km_s"]) if float(row["weight_rv2"]) > 0 else None
        samples.append((phase, rv1, rv2, 1., 1.))
    fit = circular_fit(samples, weighted=False)
    # Compare the shared workbench's fixed-M1 dynamical RV overlay without
    # changing q or fitting the published velocities as training targets.
    q, inclination, app_period, app_epoch = .534, 86., .305371, 2454842.4996855
    solar_gm = 1.3271244e20
    speed = np.cbrt(2 * np.pi * solar_gm * 1.2 * (1 + q) / (app_period * 86400)) / 1000
    app_k2 = speed * np.sin(np.deg2rad(inclination)) / (1 + q)
    app_k1 = q * app_k2
    observed, zero_gamma = [], []
    for row in rows:
        if float(row["hjd"]) < 2453711:
            continue
        sine = np.sin(2 * np.pi * (float(row["hjd"]) - app_epoch) / app_period)
        if float(row["weight_rv1"]) > 0:
            observed.append(float(row["rv1_km_s"])); zero_gamma.append(-app_k1 * sine)
        if float(row["weight_rv2"]) > 0:
            observed.append(float(row["rv2_km_s"])); zero_gamma.append(app_k2 * sine)
    observed, zero_gamma = np.asarray(observed), np.asarray(zero_gamma)
    app_gamma = float(np.mean(observed - zero_gamma))
    app_residual = observed - zero_gamma - app_gamma
    fit.update({"catalog_rows": len(rows),
                "recent_full_weight_pairs": sum(a is not None and b is not None for _, a, b, _, _ in samples),
                "published_deep_epoch_spectroscopic_phase": ((2454842.3470 - t0) / period) % 1,
                "model_epoch_spectroscopic_phase": ((2454842.4996855 - t0) / period) % 1,
                "workbench_fixed_mass_overlay": {"gamma": app_gamma, "k1": app_k1, "k2": app_k2,
                  "q": app_k1 / app_k2, "pooled_rms": float(np.sqrt(np.mean(app_residual**2)))}})
    return fit


def bo_result():
    rows = read_csv("bo_cvn_rv.csv")
    samples = [(float(r["published_phase"]), float(r["rv1_km_s"]), float(r["rv2_km_s"]),
                float(r["err1_km_s"]), float(r["err2_km_s"])) for r in rows]
    return circular_fit(samples, weighted=True)


def at_results():
    epoch, period = 2452500.9285, 1.146065
    current = read_csv("at_peg_zola_rv.csv")
    samples = []
    for row in current:
        phase = ((float(row["hjd"]) - epoch) / period) % 1
        samples.append((phase, float(row["rv1_gamma_corrected_km_s"]),
                        float(row["rv2_gamma_corrected_km_s"]),
                        float(row["err1_km_s"]), float(row["err2_km_s"])))
    old = read_csv("at_peg_maxted_caleb.csv")
    old_samples = [(float(r["published_phase"]), float(r["rv1_corrected_km_s"]),
                    float(r["rv2_corrected_km_s"]) if r["rv2_corrected_km_s"] else None, 1., 1.) for r in old]
    return circular_fit(samples, weighted=True), circular_fit(old_samples, weighted=False)


def main():
    import json
    current, old = at_results()
    print(json.dumps({"v1128_tau": v1128_result(), "bo_cvn": bo_result(),
                      "at_peg_zola": current, "at_peg_maxted_caleb": old}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
