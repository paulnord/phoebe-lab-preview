"""Extend paired training using pre-split, detached-enriched spherical draws."""

import json
from common import OUT, save
from supplement import siblings


def main():
    rows = json.loads((OUT / "enrich.json").read_text())
    extra = []
    for split, n in [("train", 96), ("enriched", 32)]:
        for r in [r for r in rows if r["split"] == split][:n]:
            i = int(r["system"].split("-")[-1])
            extra.extend(siblings("wide", split, i, r["parameters"])[1:])
    save(OUT / "paired-extension.json", extra)


if __name__ == "__main__":
    main()
