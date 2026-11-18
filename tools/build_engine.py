#!/usr/bin/env python3
"""Build the genuine PHOEBE C/C++ extensions for Pyodide, then static assets.

Requires Python 3.14, git, and a C/C++ host toolchain. No root privileges.
All generated files live in .build/ or site/; no system Python is modified.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import venv

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / ".build"
RUNTIME = "314.0.8"
PHOEBE_COMMIT = "cbbd79cee12296b1fe7eeb0662898450a9567cfd"
NDPOLATOR_URL = "https://files.pythonhosted.org/packages/1e/73/82542bd4ee5465f806fd0d565f644e1808af0028b04d3253c2c5dc74b365/ndpolator-1.3.1.tar.gz"
NDPOLATOR_SHA = "f11ca82adb0ded292048f4e5ef61c63f1e07346ecd68fb874958d0268bdba869"

def run(*args):
    print("+", *map(str, args), flush=True)
    subprocess.run(list(map(str, args)), cwd=ROOT, check=True)

def download(url, path, expected=None):
    if not path.exists():
        with urllib.request.urlopen(url, timeout=180) as response:
            data = response.read()
        path.with_suffix(path.suffix + ".tmp").write_bytes(data)
        path.with_suffix(path.suffix + ".tmp").replace(path)
    if expected and hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError(f"Source checksum mismatch: {path.name}")

def unpack(archive, destination):
    if destination.exists():
        return
    with tarfile.open(archive) as reader:
        reader.extractall(BUILD, filter="data")

def main():
    if sys.version_info[:2] != (3, 14):
        raise SystemExit("Run this build with Python 3.14 to match the browser interpreter.")
    BUILD.mkdir(exist_ok=True)
    env = BUILD / "venv"
    if not env.exists():
        venv.create(env, with_pip=True)
    python = env / "bin/python"
    pyodide = env / "bin/pyodide"
    run(python, "-m", "pip", "install", "pyodide-build==0.39.3")
    xbuild = BUILD / "xbuildenv"
    if not (xbuild / RUNTIME).exists():
        run(pyodide, "xbuildenv", "install", RUNTIME, "--path", xbuild)
    source = BUILD / "phoebe2-source.tar.gz"
    download(f"https://codeload.github.com/phoebe-project/phoebe2/tar.gz/{PHOEBE_COMMIT}", source,
             "562c22f11664fa13833052da4bc3f71c10e2a639aad5eabab6416d7df167afc3")
    phoebe = BUILD / f"phoebe2-{PHOEBE_COMMIT}"
    unpack(source, phoebe)
    project = phoebe / "pyproject.toml"
    text = project.read_text()
    if '"numpy>=1.26,<2.3"' in text:
        project.write_text(text.replace('"numpy>=1.26,<2.3"', '"numpy>=2.4,<2.5"'))
    elif '"numpy>=2.4,<2.5"' not in text:
        raise RuntimeError("The expected upstream NumPy build constraint changed.")
    ndsource = BUILD / "ndpolator-1.3.1.tar.gz"
    download(NDPOLATOR_URL, ndsource, NDPOLATOR_SHA)
    ndpolator = BUILD / "ndpolator-1.3.1"
    unpack(ndsource, ndpolator)
    dest = ROOT / "site/engine"
    dest.mkdir(parents=True, exist_ok=True)
    # Rebuild rather than silently keeping a wheel from different build scripts.
    for wheel in dest.glob("*.whl"):
        wheel.unlink()
    for package in (ndpolator, phoebe):
        run(pyodide, "build", package, "--outdir", dest, "--xbuildenv-path", xbuild)
    run(python, ROOT / "tools/package_browser_wheel.py")
    run(python, ROOT / "tools/vendor_runtime.py")
    sources = ROOT / "site/source"
    sources.mkdir(exist_ok=True)
    shutil.copy2(source, sources / "phoebe-2.5.4.tar.gz")
    shutil.copy2(ndsource, sources / ndsource.name)
    for name in ("build_engine.py", "package_browser_wheel.py", "vendor_runtime.py"):
        shutil.copy2(ROOT / "tools" / name, sources / name)
    shutil.copy2(ROOT / "LICENSE", ROOT / "site/LICENSE.txt")
    shutil.copy2(ROOT / "NOTICE.txt", ROOT / "site/NOTICE.txt")
    shutil.copy2(ROOT / "README.md", sources / "README.md")
    (ROOT / "site/.nojekyll").touch()
    print("Browser engine and complete static site are ready.", flush=True)

if __name__ == "__main__":
    main()
