"""Build the self-contained interactive Colab/Jupyter fitting utility."""
from pathlib import Path
import json
import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
DETACHED = json.loads((ROOT / "site/experiment/display-model.json").read_text())
SEMI = json.loads((ROOT / "site/experiment/semi-model.json").read_text())
CONTACT = json.loads((ROOT / "site/experiment/contact-model.json").read_text())
CORE = (ROOT / "notebooks/phoebe_colab_fitter.py").read_text()

nb = nbf.v4.new_notebook()
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3"},
    "colab": {"name": "PHOEBE Binary Fitter.ipynb", "provenance": []},
}
cells = []
cells.append(nbf.v4.new_markdown_cell("""# PHOEBE Binary Fitting Utility

Use a built-in sample or upload a CSV, adjust the geometry-specific controls, inspect the trained live preview, then explicitly run native PHOEBE compute or a bounded fit. Supported geometries are detached, semi-detached with either Roche-lobe donor, and contact.

**Scientific contract**

- Trained previews are display-only and run in the notebook kernel. Colab/Jupyter widget changes therefore make a kernel round trip; this is not the browser-local JavaScript panel from the standalone app.
- Only native PHOEBE 2.5.4 results populate final residual statistics or exports. The final native curve always uses 513 phases and 1,500 triangles; the separately displayed fit phase budget applies only to optimizer trials.
- Semi-detached/contact modes build and cache a native PHOEBE phase-zero mesh. Play, speed, phase, and Earth/overhead controls rotate that existing co-rotating mesh; constrained shape changes rebuild it.
- Photometry alone may not uniquely identify mass ratio, especially for partial/grazing eclipses. This utility does not perform joint radial-velocity fitting, uncertainty estimation, disks, streams, or spots.
- Input CSV headers: `phase,flux[,sigma]`, `time,flux[,sigma]`, or magnitude equivalents. Time input uses the period and epoch controls.

Run the cells in order. Re-running the final launch cell safely closes the previous callbacks before registering a new interface."""))
cells.append(nbf.v4.new_code_cell("""# Colab installs into its free CPU runtime; local Jupyter reuses the selected environment.
import importlib.util, subprocess, sys
required = {"phoebe":"phoebe==2.5.4", "ipywidgets":"ipywidgets>=8,<9", "scipy":"scipy", "matplotlib":"matplotlib"}
missing = [package for module, package in required.items() if importlib.util.find_spec(module) is None]
if missing:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *missing])
"""))
cells.append(nbf.v4.new_code_cell("""import json
import numpy as np
import phoebe, ipywidgets
print("PHOEBE", phoebe.__version__, "· ipywidgets", ipywidgets.__version__)
"""))
cells.append(nbf.v4.new_code_cell(
    "DETACHED_MODEL=json.loads(r'''" + json.dumps(DETACHED, separators=(",", ":")) + "''')\n" +
    "SEMI_MODEL=json.loads(r'''" + json.dumps(SEMI, separators=(",", ":")) + "''')\n" +
    "CONTACT_MODEL=json.loads(r'''" + json.dumps(CONTACT, separators=(",", ":")) + "''')"
))
cells.append(nbf.v4.new_code_cell(CORE))
cells.append(nbf.v4.new_code_cell("""MODELS = PreviewModels(DETACHED_MODEL, SEMI_MODEL, CONTACT_MODEL)
print("Embedded preview artifacts:", DETACHED_MODEL["label"], SEMI_MODEL["name"], CONTACT_MODEL["name"])
"""))
cells.append(nbf.v4.new_code_cell("""# Re-run this cell after a notebook restart or whenever you want a clean interface.
app = launch_fitter(MODELS)
"""))
cells.append(nbf.v4.new_markdown_cell("""## Reading the output

The plot is marked as a trained preview until an explicit native action completes. After a native compute or fit, changing any parameter, donor, geometry, or observation file invalidates the statistics and disables export. Export produces a ZIP containing the authoritative 513-phase native curve, model-at-data residual table, and JSON fit summary.

For model training reproduction, independent holdouts, boundary sweeps, and response-direction validation, see `PHOEBE_Semi_Detached_Validation.ipynb` and the committed experiment reports."""))
nb["cells"] = cells
out = ROOT / "notebooks/PHOEBE_Semi_Detached_Binary_Colab.ipynb"
nbf.write(nb, out)
print(out)
