"""Stage the study locally using the previously built PHOEBE 2.5.4 browser runtime."""

import json
from common import TREE, SCRATCH, OUT, sha, save
import shutil


def main():
    dest = OUT / "demo"
    assets = SCRATCH / "phoebe-progressive-results-20261118/preview"
    shutil.copytree(
        TREE / "site",
        dest,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("*.whl", "runtime", "__pycache__"),
    )
    runtime = dest / "runtime"
    if not runtime.exists():
        runtime.symlink_to((assets / "runtime").resolve(), target_is_directory=True)
    f = dest / "engine/manifest.json"
    manifest = json.loads(f.read_text())
    for wheel in manifest["wheels"]:
        path = dest / "engine" / wheel
        if not path.exists():
            path.symlink_to((assets / "engine" / wheel).resolve())
        manifest["sha256"][wheel] = sha(path)
    save(f, manifest)


if __name__ == "__main__":
    main()
