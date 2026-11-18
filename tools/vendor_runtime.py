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

def get(name, expected=None, source=None):
    path = DEST / name
    if path.is_file() and (expected is None or hashlib.sha256(path.read_bytes()).hexdigest() == expected):
        return
    with urllib.request.urlopen(source or BASE + name, timeout=120) as response:
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
for name in ("numpy", "scipy", "astropy", "micropip", "tqdm", "requests", "scikit-learn"):
    include(name)
downloads = [(name, None) for name in ("pyodide.mjs", "pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip")]
downloads += [(lock["packages"][name]["file_name"], lock["packages"][name].get("sha256")) for name in sorted(needed)]
with ThreadPoolExecutor(max_workers=4) as pool:
    list(pool.map(lambda item: get(*item), downloads))
print(f"Static runtime ready: {sum(p.stat().st_size for p in DEST.iterdir())/1048576:.1f} MiB", flush=True)

# Optional pure-Python samplers are loaded only by the advanced bundle worker.
samplers = {
    'emcee-3.1.6-py2.py3-none-any.whl': ('f9/ef/2196b9bf88ffa1bde45853c72df021fbd07a8fa91a0f59a22d14a050dc04','f2d63752023bdccf744461450e512a5b417ae7d28f18e12acd76a33de87580cb'),
    'dynesty-2.1.5-py2.py3-none-any.whl': ('c8/01/db367a6adfa49d280cda609ad5d94b9b257058b4499c59633e6d15c5e552','c1d20f300d6e0fb64675f01683d7511b181d2a5ac372295b1fe5f4410670530b'),
}
for filename, (parts, checksum) in samplers.items():
    get(filename, checksum, f'https://files.pythonhosted.org/packages/{parts}/{filename}')
(DEST/'advanced-wheels.json').write_text(json.dumps({name:data[1] for name,data in samplers.items()}))
