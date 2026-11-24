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

Run both cells. Colab uses a free CPU runtime. The interface runs in an iframe served by this notebook kernel, while PHOEBE 2.5.4 runs in the interface's browser worker. Uploaded observations stay in that browser session."""),
    nbf.v4.new_code_cell(LAUNCHER),
    nbf.v4.new_code_cell("""# Re-run this cell to restart a clean copy of the same PHOEBE Lab interface.
lab_server = show_lab(height=1050)
"""),
    nbf.v4.new_markdown_cell("""## Runtime notes

- **Colab:** supported on the free CPU runtime. The source is read from the `semi-detached` feature branch; large WebAssembly runtime files are proxied from the published PHOEBE Lab build.
- **Local Jupyter/classic:** supported when the browser and kernel share the same computer. Run the notebook from a repository checkout to use its local `site/` files.
- **Remote JupyterLab:** direct loopback iframes may be blocked by the deployment. Use Colab or the standalone page unless that server provides a loopback proxy.
- The separate `PHOEBE_Semi_Detached_Validation.ipynb` remains the reproducibility report; it is not the fitting interface.
"""),
]
out = ROOT / "notebooks" / "PHOEBE_Semi_Detached_Binary_Colab.ipynb"
nbf.write(nb, out)
print(out)
