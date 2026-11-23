import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import nbformat
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "notebooks"))
from phoebe_colab_fitter import (  # noqa: E402
    BinaryFitterApp, NativeBackend, PreviewModels, export_result,
    launch_fitter, parse_csv_bytes,
)


@pytest.fixture(scope="module")
def models():
    return PreviewModels(
        json.loads((ROOT / "site/experiment/display-model.json").read_text()),
        json.loads((ROOT / "site/experiment/semi-model.json").read_text()),
        json.loads((ROOT / "site/experiment/contact-model.json").read_text()),
    )


class PreviewBackend:
    """Fast callback-wiring double; native PHOEBE is covered separately below."""
    def __init__(self, models): self.models = models; self.calls = 0
    def curve(self, parameters, phases, triangles=800):
        self.calls += 1
        x, y = self.models.curve(parameters)
        return np.asarray(phases), np.interp(phases, x, y)


def csv_bytes(models, parameters, count=43):
    phase, flux = models.curve(parameters)
    indices = np.linspace(3, len(phase)-5, count, dtype=int)
    sigma = np.full(count, .0017)
    out = io.StringIO()
    np.savetxt(out, np.c_[phase[indices], flux[indices], sigma], delimiter=",",
               header="phase,flux,sigma", comments="")
    return out.getvalue().encode()


def set_only_fit(app, key):
    for name, checkbox in app.fit_checks.items(): checkbox.value = name == key


@pytest.mark.parametrize("mode,donor", [("detached","primary"),("semi","primary"),("semi","secondary"),("contact","primary")])
def test_uploaded_csv_callbacks_fit_export_and_stale_state(models, tmp_path, mode, donor):
    backend = PreviewBackend(models)
    app = BinaryFitterApp(models, backend=backend, render_plots=False, export_directory=tmp_path)
    app.geometry.value = mode
    if mode == "semi": app.donor.value = donor
    app.controls["inclination"].value = 82.3
    app.controls["mass_ratio"].value = .75 if mode == "detached" else .73
    app.controls["temperature_ratio"].value = .91
    if mode == "semi": app.controls["free_fill"].value = .57
    if mode == "contact": app.controls["fillout_factor"].value = .29
    content = csv_bytes(models, app.parameters())
    # Exercise the real FileUpload observer, including the ipywidgets 8 tuple shape.
    app.upload.value = ({"name": f"{mode}-{donor}.csv", "type": "text/csv", "size": len(content),
                         "content": memoryview(content), "last_modified": datetime.now(timezone.utc)},)
    assert app.observations.name.endswith(".csv")
    set_only_fit(app, "inclination"); app.max_evaluations.value = 4; app.fit_button.click()
    assert app.exact_result is not None
    assert app.exact_result["source"] == "native PHOEBE"
    assert app.exact_result["fit"]["objective_phases"] == 65
    assert not app.export_button.disabled
    app.export_button.click()
    archive = tmp_path / "phoebe_fit_results.zip"
    assert archive.is_file()
    with zipfile.ZipFile(archive) as bundle:
        assert set(bundle.namelist()) == {"native_model.csv", "residuals.csv", "fit_summary.json"}
    app.controls["temperature_ratio"].value = .92
    assert app.exact_result is None and app.export_button.disabled
    app.close()


def test_restart_closes_old_callbacks(models, tmp_path):
    first_backend = PreviewBackend(models); second_backend = PreviewBackend(models)
    first = launch_fitter(models, first_backend, render_plots=False, export_directory=tmp_path)
    second = launch_fitter(models, second_backend, render_plots=False, export_directory=tmp_path)
    before = first_backend.calls
    first.native_button.click()
    assert first_backend.calls == before
    second.native_button.click()
    assert second_backend.calls > 0
    second.close()


def test_detached_settings_restore_after_other_geometry(models):
    app = BinaryFitterApp(models, backend=PreviewBackend(models), render_plots=False)
    app.controls["eccentricity"].value = .12; app.controls["omega"].value = 143.
    app.controls["radius_primary"].value = .24
    app.geometry.value = "semi"
    assert app.controls["eccentricity"].value == 0
    app.geometry.value = "detached"
    assert app.controls["eccentricity"].value == .12
    assert app.controls["omega"].value == 143.
    assert app.controls["radius_primary"].value == .24
    app.close()


def test_csv_parser_rejects_bad_uncertainties():
    with pytest.raises(ValueError, match="Uncertainties"):
        parse_csv_bytes(b"phase,flux,sigma\n" + b"0,1,-1\n" * 8)


def test_generated_notebooks_separate_fitter_from_validation():
    fitter = nbformat.read(ROOT / "notebooks/PHOEBE_Semi_Detached_Binary_Colab.ipynb", as_version=4)
    validation = nbformat.read(ROOT / "notebooks/PHOEBE_Semi_Detached_Validation.ipynb", as_version=4)
    fitter_source = "\n".join(cell.source for cell in fitter.cells)
    validation_source = "\n".join(cell.source for cell in validation.cells)
    assert "class BinaryFitterApp" in fitter_source
    assert "Upload CSV" in fitter_source and "Run bounded native fit" in fitter_source
    assert "Bounded native recovery benchmark" in validation_source
    assert "For observation upload and native fitting" in validation_source


@pytest.mark.parametrize("mode,donor", [("detached","primary"),("semi","primary"),("semi","secondary"),("contact","primary")])
def test_real_native_backend_through_interactive_surface(models, tmp_path, mode, donor):
    """Local equivalent of Colab callbacks with a non-default uploaded native curve."""
    backend = NativeBackend()
    app = BinaryFitterApp(models, backend=backend, render_plots=False, export_directory=tmp_path)
    app.geometry.value = mode
    if mode == "semi": app.donor.value = donor
    app.controls["inclination"].value = 82.3
    app.controls["mass_ratio"].value = .75 if mode == "detached" else .73
    app.controls["temperature_ratio"].value = .91
    if mode == "semi": app.controls["free_fill"].value = .57
    if mode == "contact": app.controls["fillout_factor"].value = .29
    truth = app.parameters(); grid = np.linspace(-.5,.5,65)
    _, flux = backend.curve(truth, grid, 800)
    take = np.r_[2:30:2, 33:63:2]
    out = io.StringIO(); np.savetxt(out, np.c_[grid[take],flux[take],np.full(len(take),.001)],
                                    delimiter=",",header="phase,flux,sigma",comments="")
    content = out.getvalue().encode()
    app.upload.value = ({"name":f"native-{mode}-{donor}.csv","type":"text/csv","size":len(content),
                         "content":memoryview(content),"last_modified":datetime.now(timezone.utc)},)
    set_only_fit(app,"inclination"); app.max_evaluations.value=4; app.fit_button.click()
    assert app.exact_result is not None, app.status.value
    assert len(app.exact_result["phases"]) == 513
    assert app.exact_result["fit"]["objective_triangles"] == (400 if mode == "detached" else 800)
    assert app.exact_result["comparison"]["rms"] < .01
    destination = export_result(app.exact_result, tmp_path/f"native-{mode}-{donor}.zip")
    assert destination.is_file(); app.close()
