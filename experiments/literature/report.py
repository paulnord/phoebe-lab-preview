"""Write the review report from frozen selections and completed checkpoints."""

import json
from common import OUT
from collections import Counter
from archive import study_rows
import numpy as np


def read(name):
    return json.loads((OUT / (name + ".json")).read_text())


def main():
    inv = read("inventory")
    w = read("wide-test")
    sel = read("wide-selection")
    mix = read("mixed-test")
    circular = read("surface-test")
    ecc = read("eccentric-test")
    browser = read("browser")
    wb = read("wide-browser")
    groups = ["tides", "heat", "both"]
    names = ["Roche tides", "Horvat heating", "Both"]
    lines = []

    def line(s=""):
        lines.append(s)

    def table(headers, rows):
        line()
        line("| " + " | ".join(headers) + " |")
        line("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in rows:
            line("| " + " | ".join(map(str, row)) + " |")
        line()

    def num(x):
        return f"{x:.6f}"

    def sci(k):
        return f"{k:.4g}"

    line("# Detached-binary light curves and surface drag previews")
    line()
    line(
        f"PHOEBE 2.5.4 returned **{inv['totals']['ok']:,} finite exact curves in {inv['attempted']:,} new design attempts**. The selected wider spherical fit trained on {sel['train']['ok']:,} new geometries. The circular inclination–radius slice recovered tides plus heating on {circular['both']['candidate']['n']} held-out systems with RMS **{num(circular['both']['candidate']['rms'])}**, compared with **{num(circular['both']['spherical']['rms'])}** for the spherical disc prediction. All flux errors below use median-normalized Johnson V flux before scaling to observations."
    )
    line()
    line("## What the catalog supports")
    line()
    line(
        "The 2017-10-10 CDS edition of DEBCat contains 195 detached eclipsing systems. For each system we exponentiated the catalog base-10 masses, radii and temperatures, and computed a³ = G(M₁ + M₂)P²/(4π²). Each fractional radius is the component radius divided by this semimajor axis. Ratios preserve the catalog component labels. Quantiles are unweighted system quantiles over finite entries, with missing values excluded. [Southworth, DEBCat](https://arxiv.org/abs/1411.1219) · [CDS table and field definitions](https://cdsarc.cds.unistra.fr/viz-bin/ReadMe/V/152?format=html)"
    )
    cat = read("catalog")
    table(
        ["Quantity", "N", "Min", "5%", "Median", "95%", "Max"],
        [[k, v["n"], *map(sci, v["p0_05_50_95_100"])] for k, v in cat.items()],
    )
    line(
        "DEBCat emphasizes detached eclipses with precise masses and radii. Eclipse geometry, brightness, spectroscopy and the precision requirement select which systems enter. The fixed 6,300 K primary is close to the catalog median. It excludes large parts of the absolute temperature distribution. A mass ratio up to 2 and a hotter secondary up to 1.50 are simulation challenges beyond the upper catalog quantiles. Long periods and small fractional radii are present in the catalog. This table has no inclination, eccentricity or periastron-angle column. Their bounds and the non-eclipsing sampling fraction are experimental choices. [Southworth](https://arxiv.org/abs/1411.1219)"
    )
    line()
    line(
        "Prša et al. parameterize detached light curves using temperature ratio, summed fractional radii, inclination and the eccentricity-vector components. We use that geometry for grazing stresses and periodic features e cos ω and e sin ω. Their first Kepler release covered 44 days and had a different passband and selection function. It supplies geometric motivation, while Johnson V targets come from PHOEBE. [Prša et al., Kepler eclipsing binaries](https://arxiv.org/abs/1006.2815)"
    )
    line()
    line("## Exact design and split integrity")
    line()
    line(
        "The old joint domain spanned i = 65–90°, r₁ = 0.10–0.32, r₂ = 0.08–0.29, T₂/T₁ = 0.58–1.10, q = 0.20–1.50, P = 0.1–100 d, e = 0–0.35 and all periastron angles. The wider design sampled i = 0–90°, r₁ = 0.025–0.36, r₂ = 0.02–0.33, T₂/T₁ = 0.56–1.50, q = 0.15–2, log-period from 0.3 to 300 d, e = 0–0.65 and ω = 0–360°. These are sampling bounds. Independently varying mass ratio, radius and temperature does not enforce coeval stellar evolution. Each row still requires a detached solution and valid local atmosphere interpolation."
    )
    line()
    line(
        "Scrambled Sobol designs use separate split seeds. The first sample mixes isotropic and eclipse-favoured inclinations. Separate held-out designs traverse a correlated track, hit faces and perturb external contact. The first 1,280 spherical training draws gave 560 exact successes. We added 896 training and 128 independent challenge geometries with surface gravities of 1.7–4.9 and fractional radii below 88% of an estimated periastron Roche-lobe radius. This enrichment favours eclipses and deliberately samples cool secondaries and grazing contact. The periastron scaling is a proposal filter. PHOEBE evaluates the eccentric geometry. [Eggleton, effective Roche-lobe radii](https://doi.org/10.1086/160960)"
    )
    line()
    line(
        "The forward model fixes primary mass at 1.2 M☉, primary temperature at 6,300 K, synchronous rotation, solar abundance, gravity brightening at 0.32 and reflected bolometric fraction at 0.6 on both stars. These surface coefficients limit physical interpretation for hotter radiative stars. The ordinary targets use 256 phases on [−0.5, 0.5), 400 triangles per star, interpolated ck2004 limb intensities and energy weighting. T₂ begins at 3,528 K, just above the 3,500 K table boundary. A ratio of 0.55 would put the secondary at 3,465 K and was excluded. An average temperature inside the table does not guarantee every Roche surface element has covered temperature and gravity. The spherical predictor requires valid atmosphere corners at both stars, including gravity. The exact engine records Roche and atmosphere failures. [PHOEBE surface model](https://doi.org/10.3847/1538-4365/227/2/29) · [Horvat et al., irradiation](https://arxiv.org/abs/1809.07963)"
    )
    line()
    line(
        f"Every physical system and all of its surface/mesh variants share a split. Canonical identities fold ω at 360° and ignore ω on circular orbits. The audit checked {read('audit')['reserved_geometries']:,} historical reserved geometries. The compatible archive contains {sel['historical_used']:,} training curves with the same mass, passband, exact settings, phase grid and sample-median normalization. The pooled candidates used all eligible historical curves. Validation selected the new-only fit. The eight-slider release keeps its original guardrails in the main lab."
    )
    line()
    table(
        [
            "Quantity",
            "Minimum successful training value",
            "Median",
            "Maximum successful training value",
        ],
        [[k, sci(v[0]), sci(v[2]), sci(v[4])] for k, v in inv["training_limits"].items()],
    )
    line("## Wider spherical fit")
    line()
    line(
        "We tabulated Johnson V intensities over valid ck2004 cells, used the eccentric orbit and limb-darkened annuli to compute spherical flux, then fit residuals with ridge regression on physical coordinates and deterministic tanh features. Heads predict phase samples, 16 Fourier harmonics, or four eclipse-aligned profile coefficients. Pooled fits give the historical archive and new training group equal total weight. Each candidate sees exactly the same validation cases. We select by per-curve flux pass count (RMS ≤ 0.005 and pointwise maximum ≤ 0.035), then pooled RMS. The tables give sample error, with each valid curve weighted equally."
    )
    line()
    line(
        f"Validation selected **{sel['winner']}**. The initial fit on 560 wider curves selected {read('initial-selection')['winner']}. Learning-curve rows below give the best validation candidate at each nested new-data size."
    )
    vals = sel["validation"]
    ns = sorted({int(k.split("-")[-1]) for k in vals})
    rows = []
    for n in ns:
        for group in ["new", "pooled"]:
            opts = {k: v for k, v in vals.items() if k.endswith(f"-{group}-{n}")}
            z = min(opts, key=lambda k: (-opts[k]["passed"], opts[k]["rms"]))
            v = opts[z]
            rows.append([n, group, z.split("-")[0], num(v["rms"]), num(v["maximum"])])
    table(
        ["New training", "History weighting", "Best head", "Validation RMS", "Worst point"], rows
    )
    table(
        [
            "Held-out group",
            "Scored",
            "Exact/disc exclusions",
            "Disc RMS",
            "Fit RMS",
            "95% curve RMS",
            "Worst point",
            "Flux passes",
        ],
        [
            [
                k,
                v["selected"]["n"],
                sum(c for s, c in v["counts"].items() if s != "ok"),
                num(v["disc"]["rms"]),
                num(v["selected"]["rms"]),
                num(v["selected"]["p95"]),
                num(v["selected"]["maximum"]),
                v["selected"]["passed"],
            ]
            for k, v in w.items()
        ],
    )
    for k in ["legacy-ordinary", "legacy-stress"]:
        v = w[k]
        m = v["matched"]
        line(
            f"On {m['selected']['n']} matched {k} curves, the actual existing eight-slider browser predictor gave RMS {num(m['deployed']['rms'])} and worst {num(m['deployed']['maximum'])}. The wider fit gave RMS {num(m['selected']['rms'])} and worst {num(m['selected']['maximum'])}."
        )
        line()
    table(
        ["New blind subset", "N", "Fit RMS", "Worst point"],
        [[k, v["n"], num(v["rms"]), num(v["maximum"])] for k, v in w["blind"]["subsets"].items()],
    )
    line(
        "The browser comparison recomputes the wider fit at held-out physical vectors with measured exact curves. Free dragging in the main lab continues to use its existing spherical predictors. The comparison viewer provides access to weak and strong fits across the wider sample without asserting validity everywhere inside the sampling bounds."
    )
    line()
    line("![Successful wider training geometries and blind error distributions](wider.png)")
    line()
    line("## Paired surface corrections")
    line()
    line(
        "At each paired geometry, PHOEBE evaluated spheres with irradiation off, both stars Roche-distorted with irradiation off, spheres with Horvat irradiation, and Roche surfaces with Horvat irradiation. Each mode has its own median normalization. Mode differences therefore include the normalization response. The interaction is both − tides − heating + sphere. On the slices we interpolate paired surface-minus-sphere targets and add the current disc flux at the requested inclination and radius. Candidate heads use direct phase samples or 4, 12 and 32 harmonics, with separate combined-mode fits compared to adding the individual effects."
    )
    line()
    sr = read("surface-selection")
    er = read("eccentric-selection")
    mr = read("mixed-selection")
    line(
        f"The circular grid has 14 inclinations and five primary radii at fixed r₂ = 0.17, T₂/T₁ = 0.845, q = 0.77, P = 1.83 d, e = 0 and ω = 90°. It varies inclination from 0° to 90° and r₁ from 0.14 to 0.28. The eccentric slice varies inclination from 18° to 46° at the shipped eccentric example’s other coordinates. Its exact 30° example stayed blind. The broad experiment compared models using all eight physical inputs, with {mr['systems'][0]} complete eligible four-mode training systems available and selection on {mr['systems'][1]} independent sets. It compares a phase-dependent tidal and illumination fit with direct and Fourier residuals. The selections were {sr['winner']}, {er['winner']} and {mr['winner']}, respectively. A slice label gives training knots, harmonic count (0 means direct samples) and whether the combined correction uses its own mode. A broad label gives training systems and the residual head."
    )
    table(
        [
            "Study",
            "Mode",
            "Held-out N",
            "Spherical RMS",
            "Surface RMS",
            "95% curve RMS",
            "Worst point",
            "Flux passes",
        ],
        [
            [
                label,
                name,
                v[m]["candidate"]["n"],
                num(v[m][b]["rms"]),
                num(v[m]["candidate"]["rms"]),
                num(v[m]["candidate"]["p95"]),
                num(v[m]["candidate"]["maximum"]),
                v[m]["candidate"]["passed"],
            ]
            for label, v, b in [
                ("Circular", circular, "spherical"),
                ("Eccentric", ecc, "spherical"),
                ("Eight sliders", mix, "sphere"),
            ]
            for m, name in zip(groups, names)
        ],
    )
    line(
        f"Slice acceptance also requires eclipse-depth error ≤ 0.03, width error ≤ 0.005 cycles, and lower pooled RMS than the spherical baseline in every mode. The eccentric slice additionally requires recovery of the 30° modulation amplitude to within 20% in each mode. Both sampled slices passed those checks. The unrestricted eight-slider surface fit is withheld from drag use. Its largest combined-mode error was {num(mix['both']['candidate']['maximum'])} at {mix['both']['worst']}."
    )
    line()
    line(
        "On the circular grid each of the 52 blind systems and two additional in-slice probes entered the reported scores. The nominal 30° probe uses different q, period and temperature ratio, so the guard declines it. On the eccentric slice seven geometries entered blind scoring. The 30° system has r₁ = 0.312, r₂ = 0.134, T₂/T₁ = 0.845, q = 0.47, P = 11.39 d, e = 0.18 and ω = 27°."
    )
    line()
    transfer = read("mixed-transfer")
    line(
        f"All 168 broad held-out mode targets passed the absolute flux limits. The 148-system fit had worse validation RMS than the 53-system fit, so the latter supplied the frozen broad predictions. On the separately sampled eccentric inclination slice the general model's heating-only RMS was {num(transfer['eccentric']['heat']['rms'])}, compared with {num(ecc['heat']['spherical']['rms'])} for spherical discs and {num(ecc['heat']['candidate']['rms'])} for the slice model. We rejected unrestricted broad dragging because heating improvement did not transfer to that slice and only 11 geometries were available for broad validation."
    )
    line()
    e30 = [r for r in read("eccentric-errors") if r["id"] == "eccentric-blind-0002"]
    table(
        ["30° example", "Exact peak-to-peak", "Predicted peak-to-peak", "RMS"],
        [[r["mode"], num(r["ooe_actual"]), num(r["ooe_predicted"]), num(r["rms"])] for r in e30],
    )
    line(
        "The following maximum errors use geometric contact to identify eclipses. Each curve’s local continuum is interpolated across the occulted interval. Half-depth width, midpoint and 10–90% ingress/egress require depth ≥ 0.01 in both curves. Minimum phase can be ambiguous in shallow or flat-bottomed eclipses. Before/after errors cover the four phase samples immediately outside geometric contact. Strong distortion can move actual contact relative to this spherical geometric mask."
    )
    rows = []
    for label, v in [
        ("Wide blind", w["blind"]["shape"]),
        ("Circular both", circular["both"]["shape"]),
        ("Eight-slider both", mix["both"]["diagnostics"]),
    ]:
        rows.append(
            [
                label,
                *[
                    num(v[k]["max"]) if k in v else "—"
                    for k in [
                        "depth",
                        "width",
                        "midpoint",
                        "minimum",
                        "ingress",
                        "egress",
                        "before",
                        "after",
                        "ooe_max",
                    ]
                ],
            ]
        )
    table(
        [
            "Group",
            "Depth",
            "Width",
            "Midpoint",
            "Minimum phase",
            "Ingress",
            "Egress",
            "Before",
            "After",
            "Outside",
        ],
        rows,
    )
    for name, v in [("circular", circular), ("eccentric", ecc), ("eight-slider", mix)]:
        u = v["interaction"]
        d = u.get("prediction_error", u.get("error"))
        line(
            f"On the {name} systems the exact interaction had RMS {num(u['exact_rms'])}. Interaction prediction error was {num(d['rms'])}."
        )
        line()
    line("![Surface modulation, eclipse shapes and held-out errors](surfaces.png)")
    line()
    table(
        ["Broad surface benchmark", "Mode", "Scored", "RMS", "Worst point", "Flux passes"],
        [
            [
                split,
                m,
                mix[m][split]["n"],
                num(mix[m][split]["rms"]),
                num(mix[m][split]["maximum"]),
                mix[m][split]["passed"],
            ]
            for split in ("ordinary", "enriched")
            for m in groups
        ],
    )
    line(
        "The preliminary broad fit used 53 complete training systems and 11 complete validation systems. Its 4-harmonic fit passed all 33 validation targets with RMS 0.001915. The small number of geometries motivated adding three surface siblings to 96 existing enriched training systems and 32 independent challenges before broad blind scoring. The final selection compared both training sizes on the original validation systems. The enriched challenges had already been scored for spherical flux."
    )
    line()
    line("## Where the largest combined-mode errors occurred")
    look = {r["system"]: r["parameters"] for r in study_rows()}
    outliers = []
    for label, family, result in [
        ("Circular", "surface", circular),
        ("Eccentric", "eccentric", ecc),
        ("Eight sliders", "mixed", mix),
    ]:
        item = result["both"]
        key = item["worst"]
        p = look[key]
        with np.load(OUT / (family + "-predictions.npz")) as arr:
            i = list(arr["ids"]).index(key)
            y = arr["truth"][i, -1]
            z = arr["pred"][i, -1]
            k = int(abs(y - z).argmax())
        outliers.append(
            [
                label,
                key,
                sci(p["inclination"]),
                sci(p["radius_primary"]),
                sci(p["radius_secondary"]),
                sci(p["temperature_ratio"]),
                sci(p["mass_ratio"]),
                sci(p["period"]),
                sci(p["eccentricity"]),
                sci(p["omega"]),
                f"{k/256-.5:.4f}",
                num(y[k]),
                num(z[k]),
            ]
        )
    table(
        [
            "Study",
            "System",
            "i°",
            "r₁",
            "r₂",
            "T₂/T₁",
            "q",
            "P (d)",
            "e",
            "ω°",
            "Phase",
            "Exact",
            "Predicted",
        ],
        outliers,
    )
    line("## Surface learning curves")
    line()
    line(
        "Validation RMS pools the three surface modes at identical held-out parameters. Direct predicts all 256 corrections. Fourier retains the indicated number of harmonics. The additive column uses independently fitted tides and heating to form the combined curve."
    )
    for label, selection in [("Circular slice", sr), ("Eccentric slice", er)]:
        val = selection["validation"]
        counts = sorted({int(key.split("-")[0]) for key in val})
        table(
            [
                label + " training systems",
                "Direct",
                "4 harmonics",
                "12 harmonics",
                "32 harmonics",
                "Best additive",
            ],
            [
                [
                    n,
                    *[num(val[f"{n}-{h}-mode"]["rms"]) for h in (0, 4, 12, 32)],
                    num(
                        min(
                            v["rms"]
                            for key, v in val.items()
                            if key.startswith(f"{n}-") and key.endswith("-sum")
                        )
                    ),
                ]
                for n in counts
            ],
        )
    val = mr["validation"]
    table(
        [
            "Broad training systems",
            "Spherical",
            "Phase-dependent physics",
            "Direct residual",
            "4 harmonics",
            "12 harmonics",
        ],
        [
            [
                n,
                *[
                    num(val[f"{n}-{kind}"]["rms"])
                    for kind in ("disc", "physics", "direct", "fourier4", "fourier12")
                ],
            ]
            for n in sorted({int(k.split("-")[0]) for k in val})
        ],
    )
    line("## Exact failures, resolution and operation")
    line()
    line(
        f"Across all attempted modes and resolutions the engine returned {inv['totals']['ok']:,} finite curves, rejected {inv['totals']['roche']:,} for Roche geometry and rejected {inv['totals']['atmosphere']:,} for atmosphere coverage. Failures remain in the denominator here. The separate per-attempt index records the system, mode, coordinates and status. Regional errors above are conditional on the exact solution and supported disc atmosphere."
    )
    by_split = {}
    for key, counts in inv["counts"].items():
        family, split, mode = key.split("/")
        by_split.setdefault((family, split), Counter()).update(counts)
    table(
        ["Family", "Split", "Exact attempts", "Successful", "Roche", "Atmosphere", "Other"],
        [
            [
                family,
                split,
                sum(cnt.values()),
                cnt["ok"],
                cnt["roche"],
                cnt["atmosphere"],
                cnt["other"],
            ]
            for (family, split), cnt in by_split.items()
        ],
    )
    audit = inv["strict_audit"]
    line()
    line(
        f"The app ordinarily permits a fraction of elements outside the atmosphere grid. The broad surface benchmark required zero off-grid elements for each successful surface-mode sibling. Earlier successful surface runs received a second exact check at zero tolerance. The extra audit also sampled the circular grid edges, eclipse and 30° probes, and the eccentric inclination endpoints. The strict audit returned {audit['counts']['ok']} successful repeats. Among accepted repeats, the largest change in flux was {audit['max_flux_change']:.3g}. Sphere-only wide scoring required valid disc atmosphere cells. These restrictions and the fixed atmosphere coefficients matter especially for cool, distorted components."
    )
    line()
    table(
        ["Resolution probe", "RMS", "Maximum"],
        [[r["id"], num(r["rms"]), num(r["maximum"])] for r in inv["resolution"]],
    )
    line(
        "Resolution differences compare 400 triangles and 256 phases against 1,500 triangles and 512 phases. Periodic interpolation and independent sample medians contribute along with the mesh. These spot checks constrain the numerical reference only at the listed geometries."
    )
    line()
    line(
        f"The 16-run pilot used four workers. Twelve curves succeeded in 20.67 s including startup and the fifth42 progress check. Production used up to twelve single-threaded workers, a checkpoint per attempt, a 125 s batch process deadline and a separate systemd thaw timer. All {inv['batches']} recorded batches verified durable fifth42 progress after thaw. Their measured wall intervals sum to {inv['batch_seconds']/60:.2f} minutes, including recovery waits. Training and browser tests ran at low priority."
    )
    line()
    line(
        f"Chromium {browser['browser']} tested {browser['n']} surface predictions against Python. Maximum parity difference was {browser['parity']:.3g}, and p95 latency was {browser['p95_ms']:.3f} ms per curve (40-curve batch averages). The wider viewer tested {wb['n']} held-out geometries with parity {wb['max']:.3g} and p95 {wb['p95_ms']:.3f} ms (32-curve averages). The surface line used the amber 14-pixel fuzzy stroke. Dragging held the exact request, a subsequent update superseded an in-flight request, and the final {browser['phases']}-phase exact CSV matched the worker. Release through CSV verification took {browser['release_seconds']:.2f} s on this host. Exact flux remains the source for fitting, RMS, χ² and exports."
    )
    line()
    line(
        "The amber line below previews both effects at 30°. The points are the shipped synthetic observations generated with tides and measurement noise. The exact paired validation uses noiseless PHOEBE outputs for each mode."
    )
    line()
    line("![Fuzzy surface preview for the 30-degree eccentric binary](example-preview.png)")
    line()
    line("## Reproduce on cabbage")
    line()
    line(
        "Run from the review checkout. The script uses the PHOEBE 2.5.4 native environment, the historical eight-slider training archive and reserved manifests, and the locally built browser wheels. The CDS snapshot can be supplied as the second argument. Each scheduled batch thaws fifth42 and verifies progress before continuing."
    )
    line()
    line("""```tcsh
set scratch = /home/pnord/scratch
set tree = "$scratch/phoebe-literature-20261118"
set out = "$scratch/phoebe-literature-results-20261118"
cd "$tree"
tcsh -ef experiments/literature/Reproduce.tcsh "$scratch/phoebe-literature-repeat" "$out/cds.tsv"
```""")
    line()
    line(
        "The repeat script contains the individual design, scheduling, training, evaluation and browser commands. The 21 native regression tests passed. The existing browser fallback test passed for the original surface references, spherical omission label, stop and recovery. The local demo uses the installed 2.5.4 browser wheels with their measured hashes in its isolated manifest. The PR retains the preview release build workflow. The original run’s complete manifests, exact checkpoints, frozen selections, per-case errors, figures, browser timings and scheduling log are in the results directory. The review includes compact artifacts. Raw training and blind targets remain in the local results and previous training archives."
    )
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
