"""Build the isolated native PHOEBE L1 Planck candidate test notebook."""
from pathlib import Path
import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = (ROOT / "experiments" / "l1_planck" / "candidate.py").read_text()
VALIDATION = (ROOT / "experiments" / "l1_planck" / "validation.py").read_text()
VALIDATION = VALIDATION.replace(
    "from experiments.l1_planck.candidate import (\n"
    "    direct_blackbody_passband,\n"
    "    low_temperature_planck_candidate,\n"
    ")\n",
    "",
)
VALIDATION = VALIDATION.split('\nif __name__ == "__main__":', 1)[0]


def collapsed(title, source):
    cell = nbf.v4.new_code_cell(f"#@title {title}\n{source}")
    cell["metadata"] = {"cellView": "form", "colab": {}}
    return cell


notebook = nbf.v4.new_notebook()
notebook["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3"},
    "colab": {"name": "PHOEBE L1 Planck Candidate Test.ipynb", "provenance": []},
}
notebook["cells"] = [
    nbf.v4.new_markdown_cell("""# PHOEBE L1 Planck candidate — isolated Colab test

This notebook tests a narrow, **opt-in** candidate for the exact Roche-lobe L1 vertex found in the SZ Herculis semi-detached model. It does not modify PHOEBE Lab, the published app, or the installed PHOEBE package on disk.

The candidate retains PHOEBE's CK2004 atmosphere and existing CK2004→blackbody blending. Only a finite, positive blackbody temperature below the table floor is evaluated directly from the Planck function over the Johnson V passband. Non-positive, non-finite, and high out-of-range inputs retain PHOEBE's failure behavior. The temporary method is always restored.

Choose **Runtime → Run all** once. The final cell performs the complete test and prints one JSON report:

- reproduces the original five-phase NaN failure on the exact-axis L1 topology;
- computes SZ Her Preview (129 phases, 800 triangles) and Refined (513 phases, 1500 triangles);
- reports finite flux, passband luminosities, published-data residuals, and resolution convergence;
- enforces continuity where the direct quadrature meets the native blackbody table;
- proves ordinary detached and contact 129-phase outputs are bit-for-bit unchanged.

This is a scientific validation notebook, not the PHOEBE Lab fitting workbench. Do not use its candidate as an authoritative result until the hosted checks pass and the change is separately reviewed."""),
    collapsed("1 · Install native PHOEBE", """import importlib.metadata, os, subprocess, sys
os.environ.update(PHOEBE_ENABLE_ONLINE_PASSBANDS="FALSE", PHOEBE_ENABLE_MPI="FALSE",
                  PHOEBE_MULTIPROC_NPROCS="0", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
try:
    installed = importlib.metadata.version("phoebe")
except importlib.metadata.PackageNotFoundError:
    installed = None
if installed != "2.5.4":
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "phoebe==2.5.4", "scipy"])
import phoebe
assert phoebe.__version__ == "2.5.4", phoebe.__version__
print("Native PHOEBE", phoebe.__version__, "·", sys.executable)
"""),
    collapsed("2 · Load the opt-in candidate", f"""# Source embedded by the repository generator; no installed file is edited.
CANDIDATE_SOURCE = {CANDIDATE!r}
exec(compile(CANDIDATE_SOURCE, "l1_planck_candidate.py", "exec"), globals())
import hashlib
print("Candidate SHA-256", hashlib.sha256(CANDIDATE_SOURCE.encode()).hexdigest())
"""),
    collapsed("3 · Run complete native validation", f"""VALIDATION_SOURCE = {VALIDATION!r}
exec(compile(VALIDATION_SOURCE, "l1_planck_validation.py", "exec"), globals())
validation_results = run_validation()
print(printable_results(validation_results))
assert validation_results["status"] == "PASS"
"""),
    nbf.v4.new_markdown_cell("""## Reading the result

`status: PASS` means the candidate completed the exact-axis Preview and Refined runs, returned finite positive native curves, computed finite luminosities and residuals, and left the detached/contact controls exactly unchanged in this runtime.

The residuals compare the fixed PHOEBE Lab assumptions to published SZ Her Johnson V photometry. They are a regression check, not a new scientific fit and not evidence that the parameters are unique. The notebook downloads that unchanged CSV from immutable source revision `fe9e3684eef2ba5ab7ab2aafee448a1f26abda98` and verifies SHA-256 before use.

If any assertion fails, copy the final cell output together with the environment and native-library hashes printed in the report. No app or package state remains patched after the cell finishes."""),
]

output = ROOT / "notebooks" / "PHOEBE_L1_Planck_Colab_Test.ipynb"
nbf.write(notebook, output)
print(output)
