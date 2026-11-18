import json
from common import TREE, OUT, save


def main():
    accepted = []
    for fam in ("surface", "eccentric"):
        spec = json.loads((OUT / (fam + "-candidate.json")).read_text())
        if spec["accepted"]:
            accepted.append(spec)
    if not accepted:
        raise SystemExit("No surface candidate accepted")
    save(TREE / "site/experiment/surface.json", accepted)


if __name__ == "__main__":
    main()
