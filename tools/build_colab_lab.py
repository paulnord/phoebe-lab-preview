"""Build the Colab launcher for the actual PHOEBE Lab web interface."""
from pathlib import Path
import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = (ROOT / "notebooks" / "phoebe_lab_colab.py").read_text()

nb = nbf.v4.new_notebook()
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3"},
    "colab": {"name": "PHOEBE Lab.ipynb", "provenance": []},
}
nb["cells"] = [
    nbf.v4.new_markdown_cell("""# PHOEBE Lab — Colab

This is the familiar PHOEBE Lab workbench, not a second widget interface. It has the same observation loader, light curve and residual plots, radial-velocity view, model controls, bounded native fit, authoritative export, and orbit viewer as the standalone page.

Choose **Detached**, **Semi-detached**, or **Contact** at the top of the model panel. Semi-detached exposes the donor choice and one free-star radius; contact exposes the shared-envelope fill-out factor. Trained curves remain display-only. Explicit compute and fit actions use PHOEBE and invalidate stale statistics/export whenever the data, geometry, donor, or parameters change.

Run all three cells. Colab uses a free CPU runtime. The interface runs in an iframe served by this notebook kernel. Instant trained previews and orbit playback stay in the browser, but exact curves, fits, and native surface meshes are sent to **native PHOEBE 2.5.4 in this Colab Python runtime**—never silently to browser WebAssembly. Uploaded observations stay within this notebook/browser session."""),
    nbf.v4.new_code_cell("""# Install the authoritative native engine in this Colab/Jupyter kernel.
import importlib.metadata, subprocess, sys
try:
    installed_phoebe = importlib.metadata.version("phoebe")
except importlib.metadata.PackageNotFoundError:
    installed_phoebe = None
if installed_phoebe != "2.5.4":
    subprocess.check_call([sys.executable,"-m","pip","install","-q","phoebe==2.5.4","scipy"])
import phoebe
assert phoebe.__version__ == "2.5.4", phoebe.__version__
print("Native PHOEBE",phoebe.__version__,"·",sys.executable)
"""),
    nbf.v4.new_code_cell(LAUNCHER),
    nbf.v4.new_code_cell("""# Re-run this cell to restart a clean copy of the same PHOEBE Lab interface.
lab_server = show_lab(height=1050)
"""),
    nbf.v4.new_markdown_cell("""## Runtime notes

- **Colab:** supported on the free CPU runtime. Exact curves, bounded fits, residual/export results, and native orbit meshes run in the notebook's native Python process. The top status pill and result provenance say `Colab native`.
- **Local Jupyter/classic:** supported when the browser and kernel share the same computer. Run the notebook from a repository checkout to use its local `site/` files.
- **Remote JupyterLab:** direct loopback iframes may be blocked by the deployment. Use Colab or the standalone page unless that server provides a loopback proxy.
- **Standalone preview:** continues to use PHOEBE WebAssembly in its browser worker; this notebook transport does not alter it.
- The separate `PHOEBE_Semi_Detached_Validation.ipynb` remains the reproducibility report; it is not the fitting interface.
"""),
]
out = ROOT / "notebooks" / "PHOEBE_Semi_Detached_Binary_Colab.ipynb"
nbf.write(nb, out)
print(out)
