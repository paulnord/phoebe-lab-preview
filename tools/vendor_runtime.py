#!/usr/bin/env python3
"""Vendor a pinned Pyodide runtime and scientific wheels for static hosting."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import re
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VERSION = "314.0.8"
BASE = f"https://cdn.jsdelivr.net/pyodide/v{VERSION}/full/"
DEST = ROOT / "site/runtime"
DEST.mkdir(parents=True, exist_ok=True)

def get(name, expected=None):
    path = DEST / name
    if path.is_file() and (expected is None or hashlib.sha256(path.read_bytes()).hexdigest() == expected):
        return
    with urllib.request.urlopen(BASE + name, timeout=120) as response:
        data = response.read()
    if expected and hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError(f"Checksum mismatch for {name}")
    path.write_bytes(data)
    print(f"Vendored {name}: {len(data)/1048576:.1f} MiB", flush=True)

get("pyodide-lock.json")
lock = json.loads((DEST / "pyodide-lock.json").read_text())
needed = set()
def include(name):
    name = re.sub(r"[-_.]+", "-", name).lower()
    if name in needed:
        return
    needed.add(name)
    for child in lock["packages"][name].get("depends", []):
        include(child)
for name in ("numpy", "scipy", "astropy", "micropip", "tqdm", "requests"):
    include(name)
downloads = [(name, None) for name in ("pyodide.mjs", "pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip")]
downloads += [(lock["packages"][name]["file_name"], lock["packages"][name].get("sha256")) for name in sorted(needed)]
with ThreadPoolExecutor(max_workers=4) as pool:
    list(pool.map(lambda item: get(*item), downloads))
print(f"Static runtime ready: {sum(p.stat().st_size for p in DEST.iterdir())/1048576:.1f} MiB", flush=True)
