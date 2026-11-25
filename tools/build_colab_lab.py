"""Build the PHOEBE Lab UI whose exact Compute and Fit run in Colab Python."""
from pathlib import Path
import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = (ROOT / "notebooks" / "phoebe_lab_colab.py").read_text()

def collapsed_code(title, source):
    cell = nbf.v4.new_code_cell(f"#@title {title}\n{source}")
    cell["metadata"] = {"cellView": "form", "colab": {}}
    return cell

nb = nbf.v4.new_notebook()
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3"},
    "colab": {"name": "PHOEBE Lab.ipynb", "provenance": []},
}
nb["cells"] = [
    nbf.v4.new_markdown_cell("""# PHOEBE Lab — Colab

The PHOEBE Lab workbench includes observation loading, light-curve and residual plots, a radial-velocity view, geometry controls, bounded native fitting, authoritative export, and an orbit viewer.

Choose **Detached**, **Semi-detached**, or **Contact** at the top of the model panel. Semi-detached exposes the donor choice and one free-star radius; contact exposes the shared-envelope fill-out factor. Trained curves remain display-only. Explicit compute and fit actions use PHOEBE and invalidate stale statistics/export whenever the data, geometry, donor, or parameters change.

Choose **Runtime → Run all**. The three code cells are collapsed by default; each can be expanded if you want to inspect the source, and runtime errors remain in its output. Colab uses a free CPU runtime. The interface runs in an iframe served by this notebook kernel. Instant trained previews and orbit playback stay in the browser, but exact curves, fits, and native surface meshes are sent to **native PHOEBE 2.5.4 in this Colab Python runtime**—never silently to browser WebAssembly. Uploaded observations stay within this notebook/browser session."""),
    collapsed_code("1 · Install native PHOEBE", """# Install the authoritative native engine in this Colab/Jupyter kernel.
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
    collapsed_code("2 · Load the native workbench bridge", LAUNCHER),
    collapsed_code("3 · Launch PHOEBE Lab", """# Re-run this cell to restart the PHOEBE Lab server and interface.
lab_server = show_lab(height=1050)
"""),
    nbf.v4.new_markdown_cell("""## Runtime notes

- **Colab:** supported on the free CPU runtime. Exact curves, bounded fits, residual/export results, and native orbit meshes run in the notebook's native Python process. The top status pill and result provenance say `Colab native`.
- Native Colab curves arrive in genuine PHOEBE phase batches, so the plot fills in progressively before the authoritative final normalization/statistics/export result.
- **Native phase workers:** the notebook reports affinity and CPU quota separately, then offers only the worker counts its persistent native-Python phase pool supports (up to four). The maximum truthful supported count is selected by default, with every lower count still available. This parallelizes exact surface phase batches and the final fitted curve; bounded fit trials remain serial and deterministic.
- **Local Jupyter/classic:** supported when the browser and kernel share the same computer. Run the notebook from a repository checkout to use its local `site/` files.
- **Remote JupyterLab:** direct loopback iframes may be blocked by the deployment. Use Colab or the standalone page unless that server provides a loopback proxy.
- **Standalone preview:** uses PHOEBE WebAssembly in independent browser Web Workers, not MPI, and remains independent of this notebook's native bridge. Browser Web Workers already parallelize eligible exact phase batches without a hosted solver.
- **Fullscreen:** the workbench asks the browser for fullscreen. Colab's supported kernel-port iframe may deny that browser permission; if so, the interface reports the limitation without changing compute backends.
- **Full window:** Colab's direct kernel-port window helper is deprecated because browser security changes can break it, so this notebook does not advertise an unreliable app-only popup. The inline workbench remains connected to this kernel.
- Use `PHOEBE_Semi_Detached_Validation.ipynb` for training reproducibility and this notebook for interactive fitting.
"""),
]
out = ROOT / "notebooks" / "PHOEBE_Semi_Detached_Binary_Colab.ipynb"
nbf.write(nb, out)
print(out)
