#!/usr/bin/env python3
"""Build the literature-validation CSVs from downloaded source tables.

The inputs are the unmodified VizieR TSV and AAS figure-data files named in
REPORT.md. BO CVn's ten rows are transcribed from Table 1 of the primary PDF;
the values are kept here so the transcription remains reviewable.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import re


BO_CVN = [
    (54569.0244, .255, -56.7, 7.9, 245.9, 11.2),
    (54571.8556, .726, 85.6, 10.7, -226.0, 5.0),
    (54574.6943, .212, -60.2, 9.3, 227.4, 12.9),
    (54574.7383, .297, -52.2, 10.2, 241.2, 16.8),
    (54925.8028, .731, 89.5, 5.4, -220.1, 4.7),
    (54926.8407, .736, 92.8, 3.4, -218.6, 8.1),
    (54928.7197, .368, -25.8, 4.4, 198.8, 11.2),
    (54929.9678, .780, 95.2, 3.2, -215.9, 4.2),
    (55673.8127, .264, -56.1, 3.9, 238.5, 8.8),
    (55677.9635, .285, -48.3, 6.1, 243.6, 4.9),
]


def write_csv(path: Path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def vizier_rows(path: Path):
    lines = path.read_text().splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("recno\t")) + 3
    rows = []
    for line in lines[start:]:
        fields = line.split("\t")
        if len(fields) < 8:
            continue
        rows.append((fields[0].strip(), fields[2].strip(), fields[3].strip(), fields[4].strip(),
                     fields[5].strip(), fields[6].strip(), fields[7].strip()))
    if len(rows) != 104:
        raise ValueError(f"Expected 104 V1128 Tau rows, found {len(rows)}")
    return rows


def aas_rv_rows(path: Path):
    rows = []
    for line in path.read_text().splitlines():
        parts = line.split()
        if line.startswith("AT Peg") and len(parts) == 7:
            rows.append(parts[2:])
    return rows


def aas_light_rows(path: Path):
    rows = []
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0] == "V":
            rows.append(parts[1:])
    return rows


def maxted_rows(path: Path):
    rows = []
    for line in path.read_text().splitlines():
        if not re.match(r"^\d{5}\.\d{4}", line):
            continue
        parts = line.split()
        hjd, phase, rv1_unc, rv2_unc = parts[:4]
        offset = 4
        if rv2_unc == "-":
            rv1_cor, rv2_cor = parts[offset], ""
            offset += 2
        else:
            rv1_cor, rv2_cor = parts[offset:offset + 2]
            offset += 2
        residual1 = parts[offset]
        residual2 = parts[offset + 1] if offset + 1 < len(parts) and parts[offset + 1] != "-" else ""
        rows.append((hjd, phase, rv1_unc, "" if rv2_unc == "-" else rv2_unc,
                     rv1_cor, rv2_cor, residual1, residual2))
    if len(rows) != 21:
        raise ValueError(f"Expected 21 Maxted/CALeb rows, found {len(rows)}")
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vizier", type=Path, required=True)
    parser.add_argument("--at-rv", type=Path, required=True)
    parser.add_argument("--at-light", type=Path, required=True)
    parser.add_argument("--maxted-html", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("data"))
    args = parser.parse_args()

    v1128 = vizier_rows(args.vizier)
    write_csv(args.output / "v1128_tau_ddo_all.csv",
              ("source_row", "hjd", "rv1_km_s", "weight_rv1", "rv2_km_s", "weight_rv2", "published_phase"), v1128)
    recent = [(hjd, rv1, rv2) for _, hjd, rv1, w1, rv2, w2, _ in v1128
              if float(hjd) >= 2453711 and float(w1) > 0 and float(w2) > 0]
    if len(recent) != 38:
        raise ValueError(f"Expected 38 full-weight recent pairs, found {len(recent)}")
    write_csv(args.output / "v1128_tau_ddo_recent_app.csv", ("time", "rv1", "rv2"), recent)
    write_csv(args.output / "bo_cvn_rv.csv",
              ("hjd_minus_2400000", "published_phase", "rv1_km_s", "err1_km_s", "rv2_km_s", "err2_km_s"), BO_CVN)

    at_rv = aas_rv_rows(args.at_rv)
    if len(at_rv) != 9:
        raise ValueError(f"Expected 9 AAS AT Peg RV rows, found {len(at_rv)}")
    write_csv(args.output / "at_peg_zola_rv.csv",
              ("hjd", "rv1_gamma_corrected_km_s", "err1_km_s", "rv2_gamma_corrected_km_s", "err2_km_s"), at_rv)
    at_light = aas_light_rows(args.at_light)
    if len(at_light) != 895:
        raise ValueError(f"Expected 895 AAS AT Peg V rows, found {len(at_light)}")
    write_csv(args.output / "at_peg_johnson_cousins_v.csv", ("time", "magnitude"), at_light)
    write_csv(args.output / "at_peg_maxted_caleb.csv",
              ("hjd_minus_2400000", "published_phase", "rv1_uncorrected_km_s", "rv2_uncorrected_km_s",
               "rv1_corrected_km_s", "rv2_corrected_km_s", "published_residual1_km_s", "published_residual2_km_s"),
              maxted_rows(args.maxted_html))


if __name__ == "__main__":
    main()
