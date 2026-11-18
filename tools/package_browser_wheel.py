#!/usr/bin/env python3
"""Remove unused trained KNN datasets; preserve all PHOEBE numerical code."""
import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "site/engine"
source = next(iter(DEST.glob("phoebe-2.5.4-*.whl")), None)
if source is None:
    existing = next(DEST.glob("phoebe-2.5.4+browser.1-*.whl"))
    source = existing.with_suffix(".input.whl")
    source.write_bytes(existing.read_bytes())
    existing.unlink()
output = source.with_name(source.name.replace("phoebe-2.5.4-", "phoebe-2.5.4+browser.1-"))
output = output.with_name(output.name.replace(".input.whl", ".whl"))
old_info = "phoebe-2.5.4.dist-info"
new_info = "phoebe-2.5.4+browser.1.dist-info"
records = []
with zipfile.ZipFile(source) as reader, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as writer:
    for item in reader.infolist():
        if item.filename.startswith("phoebe/solverbackends/knn/") and item.filename.endswith(".knn"):
            continue
        name = item.filename.replace(old_info, new_info)
        if name.endswith(".dist-info/RECORD"):
            continue
        data = reader.read(item.filename)
        if name == "phoebe/parameters/parameters.py":
            if b"readline = None" not in data:
                data = data.replace(b"import readline\n", b"try:\n    import readline\nexcept ImportError:\n    readline = None  # Terminal completion is unavailable in the browser.\n", 1)
            if b"        # set tab completer\n        readline." in data:
                data = data.replace(b"        # set tab completer\n        readline.set_completer(tabcomplete.Completer().complete)\n        readline.set_completer_delims(_twig_delims)\n        readline.parse_and_bind(\"tab: complete\")", b"        # Terminal completion is optional on WebAssembly.\n        if readline is not None:\n            readline.set_completer(tabcomplete.Completer().complete)\n            readline.set_completer_delims(_twig_delims)\n            readline.parse_and_bind(\"tab: complete\")")
        if name.endswith(".dist-info/BROWSER-BUILD.txt"):
            continue
        if name == "phoebe/dependencies/crimpl/__init__.py":
            data = data.replace(b'_run_cmd("ls {}".format(directory), log_cmd=False).split()', b'[_os.path.join(directory, entry) for entry in _os.listdir(directory)]')
            data = data.replace(b'except _subprocess.CalledProcessError:', b'except (_subprocess.CalledProcessError, FileNotFoundError):')
        if name.endswith(".dist-info/METADATA"):
            data = data.replace(b"Version: 2.5.4\n", b"Version: 2.5.4+browser.1\n", 1)
        writer.writestr(name, data)
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")
        records.append([name, "sha256=" + digest, str(len(data))])
    note_name = new_info + "/BROWSER-BUILD.txt"
    note = b"PHOEBE 2.5.4 browser build. Numerical source is unchanged. Built for Pyodide 314.0.8 with NumPy 2.4.6. The terminal-only readline import is optional. Large trained KNN estimator datasets are omitted; that estimator is not exposed by this app. The source build requirement for NumPy was adjusted for this target. Remote/process execution is not used. See project tools and README for reproduction.\n"
    writer.writestr(note_name, note)
    digest = base64.urlsafe_b64encode(hashlib.sha256(note).digest()).decode().rstrip("=")
    records.append([note_name, "sha256=" + digest, str(len(note))])
    records.append([new_info + "/RECORD", "", ""])
    stream = io.StringIO()
    csv.writer(stream, lineterminator="\n").writerows(records)
    writer.writestr(new_info + "/RECORD", stream.getvalue())
source.unlink()
wheels = sorted(DEST.glob("*.whl"))
(DEST / "manifest.json").write_text(json.dumps({
    "runtime": "314.0.8", "python": "3.14.2", "phoebe": "2.5.4",
    "wheels": [p.name for p in wheels],
    "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in wheels},
}, indent=2) + "\n")
print(f"Browser PHOEBE wheel: {output.stat().st_size/1048576:.1f} MiB")
