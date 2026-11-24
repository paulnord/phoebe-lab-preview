import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import threading
import urllib.request

import nbformat

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("phoebe_lab_colab", ROOT / "notebooks" / "phoebe_lab_colab.py")
launcher = importlib.util.module_from_spec(spec); spec.loader.exec_module(launcher)


def test_geometry_is_visible_first_class_model_choice():
    html = (ROOT / "site" / "index.html").read_text()
    assert html.count('id="geometry-detached"') == 1
    assert html.count('id="geometry-semi"') == 1
    assert html.count('id="geometry-contact"') == 1
    assert html.index('class="geometry-picker"') < html.index('id="parameter-controls"') < html.index('id="effects"')
    assert "Surface physics and compute" in html
    assert 'id="donor-row"' in html and 'id="geometry-explanation"' in html


def test_launcher_serves_the_actual_workbench():
    server = launcher.start_lab(ROOT / "site")
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        index = urllib.request.urlopen(base + "/", timeout=5).read().decode()
        app = urllib.request.urlopen(base + "/assets/app.js", timeout=5).read().decode()
        semi = json.load(urllib.request.urlopen(base + "/experiment/semi-model.json", timeout=5))
        contact = json.load(urllib.request.urlopen(base + "/experiment/contact-model.json", timeout=5))
        assert "PHOEBE Lab" in index and 'id="light-curve"' in index and 'id="fit-button"' in index
        assert "setGeometryMode" in app and semi["accepted"] and contact["accepted"]
    finally:
        launcher.stop_lab()


def test_missing_runtime_files_are_proxied_from_published_origin(tmp_path):
    origin = tmp_path / "origin"; origin.mkdir(); (origin / "runtime.bin").write_bytes(b"runtime")
    quiet = type("Quiet", (SimpleHTTPRequestHandler,), {"log_message": lambda *args: None})
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(quiet, directory=str(origin)))
    thread = threading.Thread(target=upstream.serve_forever, daemon=True); thread.start()
    local = tmp_path / "local"; local.mkdir(); (local / "index.html").write_text("local")
    prior = launcher.LabOverlayHandler.published_base
    launcher.LabOverlayHandler.published_base = f"http://127.0.0.1:{upstream.server_address[1]}/"
    server = launcher.start_lab(local)
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        assert urllib.request.urlopen(base + "/index.html").read() == b"local"
        assert urllib.request.urlopen(base + "/runtime.bin").read() == b"runtime"
    finally:
        launcher.stop_lab(); upstream.shutdown(); upstream.server_close()
        launcher.LabOverlayHandler.published_base = prior


def test_generated_notebook_is_the_familiar_lab_not_widget_replacement():
    notebook = nbformat.read(ROOT / "notebooks" / "PHOEBE_Semi_Detached_Binary_Colab.ipynb", as_version=4)
    source = "\n".join(cell.source for cell in notebook.cells)
    assert "same PHOEBE Lab workbench" in source
    assert "show_lab(height=1050)" in source
    assert "LabOverlayHandler" in source
    assert "BinaryFitterApp" not in source and "ToggleButtons" not in source


def test_commit_pinned_preview_reuses_only_generated_public_runtime():
    worker = (ROOT / "site" / "assets" / "engine.worker.js").read_text()
    assert 'self.location.hostname === "raw.githack.com"' in worker
    assert 'new URL("runtime/",PUBLISHED_SITE)' in worker
    assert 'new URL("engine/manifest.json",PUBLISHED_SITE)' in worker
    # Model and wrapper source must remain the reviewed branch files.
    assert 'new URL("../engine/model.py", self.location.href)' in worker
    assert "../engine/advanced.py" in worker and "../engine/native_files.py" in worker


def test_geometry_switches_coalesce_worker_restarts():
    app = (ROOT / "site" / "assets" / "app.js").read_text()
    assert "engineRestartTimer=setTimeout" in app
    assert "},500);" in app
    assert "if(interrupt)startEngine()" not in app
    assert "current.mode!==modeOf(state.parameters)" in app
    assert "Geometry changed · safely stopping the previous PHOEBE model" in app
