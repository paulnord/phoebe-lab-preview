import json
from pathlib import Path
import subprocess
import sys

import nbformat
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments/contact"))
from contact_native import BOUNDS  # noqa: E402
from train_contact_v2 import basis  # noqa: E402


MODEL_PATH = ROOT / "site/experiment/contact-model.json"
DATA_PATH = ROOT / "experiments/contact/artifacts/contact-curves-v2.npz"
V1_PATH = ROOT / "experiments/contact/artifacts/contact-model-v1.json"


def scaled(parameters, keys):
    return np.array([2 * (parameters[key] - BOUNDS[key][0]) /
                     (BOUNDS[key][1] - BOUNDS[key][0]) - 1 for key in keys])


def python_prediction(spec, parameters):
    x = scaled(parameters, spec["keys"])
    centers = np.asarray(spec["centers"])
    kernel = np.exp(-spec["gamma"] * np.sum((centers - x) ** 2, axis=1))
    coefficients = kernel @ np.asarray(spec["weights"])
    phases = np.linspace(-.5, .5, spec["phases"] + 1)
    model = np.cos(2 * np.pi * np.outer(phases, np.arange(spec["harmonics"] + 1))) @ coefficients
    return model / np.median(model[:-1])


def test_frozen_coefficients_reproduce_from_native_targets():
    spec = json.loads(MODEL_PATH.read_text())
    data = np.load(DATA_PATH, allow_pickle=False)
    matrix = basis(data["phases"])
    coefficients = np.linalg.lstsq(matrix, data["train_flux"].T, rcond=None)[0].T
    centers = np.asarray(spec["centers"])
    kernel = np.exp(-spec["gamma"] * np.sum((centers[:, None, :] - centers[None, :, :]) ** 2, axis=2))
    weights = np.linalg.solve(kernel + spec["ridge"] * np.eye(len(centers)), coefficients)
    np.testing.assert_allclose(weights, spec["weights"], rtol=2e-13, atol=2e-13)


def test_javascript_uses_expanded_frozen_artifact_and_existing_notebook_stays_v1():
    spec = json.loads(MODEL_PATH.read_text())
    parameters = dict(inclination=83.25, mass_ratio=.73, fillout_factor=.27,
                      temperature_ratio=.91, period=1.8, eccentricity=0.,
                      irradiation=False, contact=True)
    code = f"""
      import fs from 'node:fs';
      import {{makeContactPredictor}} from './site/experiment/contact-predict.mjs';
      const spec=JSON.parse(fs.readFileSync('./site/experiment/contact-model.json'));
      const curve=makeContactPredictor(spec)({json.dumps(parameters)});
      console.log(JSON.stringify(curve.model));
    """
    js = np.asarray(json.loads(subprocess.check_output(
        ["node", "--input-type=module", "-e", code], cwd=ROOT, text=True)))
    np.testing.assert_allclose(js, python_prediction(spec, parameters), rtol=2e-12, atol=2e-12)

    notebook = nbformat.read(ROOT / "notebooks/PHOEBE_Contact_Binary_Colab.ipynb", as_version=4)
    embedded = next(cell.source for cell in notebook.cells if cell.cell_type == "code" and
                    cell.source.startswith("CONTACT_MODEL = json.loads"))
    notebook_spec = json.loads(embedded.split("r'''", 1)[1].rsplit("'''", 1)[0])
    assert notebook_spec == json.loads(V1_PATH.read_text())
