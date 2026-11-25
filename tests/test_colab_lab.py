import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import sys
import threading
import types
import urllib.error
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


def test_high_surface_detail_is_the_fresh_viewer_default():
    html=(ROOT/"site"/"index.html").read_text()
    app=(ROOT/"site"/"assets"/"app.js").read_text()
    assert '<option value="high" selected>High detail</option>' in html
    assert "let orbitDetail='high'" in app
    assert "detail:'high',displayDetail:null,status:'idle'" in app
    assert "orbitDetail==='high'?1500:500" in app


def test_launcher_serves_the_actual_workbench():
    server = launcher.start_lab(ROOT / "site",kernel=False)
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        index = urllib.request.urlopen(base + "/", timeout=5).read().decode()
        app = urllib.request.urlopen(base + "/assets/app.js", timeout=5).read().decode()
        semi = json.load(urllib.request.urlopen(base + "/experiment/semi-model.json", timeout=5))
        contact = json.load(urllib.request.urlopen(base + "/experiment/contact-model.json", timeout=5))
        assert "PHOEBE Lab" in index and 'id="light-curve"' in index and 'id="fit-button"' in index
        assert "setGeometryMode" in app and semi["accepted"] and contact["accepted"]
        assert "PHOEBE_COLAB_NATIVE" not in index
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
    server = launcher.start_lab(local,kernel=False)
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        assert urllib.request.urlopen(base + "/index.html").read() == b"local"
        assert urllib.request.urlopen(base + "/runtime.bin").read() == b"runtime"
    finally:
        launcher.stop_lab(); upstream.shutdown(); upstream.server_close()
        launcher.LabOverlayHandler.published_base = prior


def test_generated_notebook_exposes_full_lab_and_native_runtime():
    notebook = nbformat.read(ROOT / "notebooks" / "PHOEBE_Semi_Detached_Binary_Colab.ipynb", as_version=4)
    source = "\n".join(cell.source for cell in notebook.cells)
    assert "observation loading" in source and "bounded native fitting" in source
    assert "show_lab(height=1050)" in source
    assert "LabOverlayHandler" in source
    assert 'phoebe==2.5.4' in source
    assert "Colab native Python" in source
    assert "exact curves, fits, and native surface meshes" in source
    assert "Run PHOEBE Lab Compute and Fit in this notebook's native Python PHOEBE runtime" in source
    assert "never fall back to browser WebAssembly" in source
    assert "asset proxy never handles scientific Compute or Fit requests" in source
    assert "BinaryFitterApp" not in source and "ToggleButtons" not in source
    code_cells=[cell for cell in notebook.cells if cell.cell_type=="code"]
    assert len(code_cells)==3
    assert all(cell.metadata.get("cellView")=="form" for cell in code_cells)
    assert all(cell.metadata.get("colab")=={} for cell in code_cells)
    assert all(cell.source.startswith("#@title ") for cell in code_cells)
    assert "Runtime → Run all" in source


def test_colab_launch_uses_supported_kernel_port_iframe(monkeypatch):
    calls=[]
    server=types.SimpleNamespace(server_address=("127.0.0.1",43210))
    monkeypatch.setattr(launcher,"start_lab",lambda site=None: server)
    output=types.SimpleNamespace(
        serve_kernel_port_as_iframe=lambda port, *, height: calls.append((port,height)))
    google=types.ModuleType("google")
    colab=types.ModuleType("google.colab")
    colab.output=output;google.colab=colab
    monkeypatch.setitem(sys.modules,"google",google)
    monkeypatch.setitem(sys.modules,"google.colab",colab)

    assert launcher.show_lab(height=777,site=ROOT/"site") is server
    assert calls==[(43210,777)]


def test_colab_reports_affinity_quota_and_bounded_process_workers(monkeypatch):
    monkeypatch.setattr(launcher.os,"sched_getaffinity",lambda pid:set(range(6)))
    monkeypatch.setattr(launcher,"_cgroup_cpu_quota",lambda:2.5)
    assert launcher.detected_cpu_capacity()=={
        "affinity_cpus":6,"cgroup_quota_cpus":2.5,"usable_cpu_equivalents":2.5}
    assert launcher.supported_native_workers()==2
    monkeypatch.setattr(launcher,"detected_cpu_capacity",lambda:{
        "affinity_cpus":16,"cgroup_quota_cpus":None,"usable_cpu_equivalents":16.})
    assert launcher.supported_native_workers()==4
    source=(ROOT/"notebooks"/"phoebe_lab_colab.py").read_text()
    assert '"worker_backend":"persistent-python-processes"' in source
    assert "NativePhaseWorkers" in source and "multiprocessing.get_context(\"fork\")" in source
    assert "PHOEBE_ENABLE_MPI=\"FALSE\"" in source


def test_colab_source_archive_is_commit_pinned_and_notebook_matches_launcher():
    source=(ROOT/"notebooks"/"phoebe_lab_colab.py").read_text()
    notebook=(ROOT/"notebooks"/"PHOEBE_Semi_Detached_Binary_Colab.ipynb").read_text()
    revision="e4694defb02385612999175a429dd12a5e9ccb6b"
    assert f'SOURCE_REVISION = "{revision}"' in source
    assert f'SOURCE_REVISION = \\u0022{revision}\\u0022' in notebook or f'SOURCE_REVISION = \\\"{revision}\\\"' in notebook
    assert "archive/refs/heads/semi-detached.zip" not in source
    assert "archive/refs/heads/semi-detached.zip" not in notebook


def test_colab_kernel_services_parallel_work_protocol_and_provenance():
    class FakeModel:
        phoebe=types.SimpleNamespace(__version__="2.5.4")
        @staticmethod
        def worker_flux(payload):return [float(i) for i in payload["indices"]]
        @staticmethod
        def progressive_curve(payload):
            assert payload["workers"]==2
            yield {"type":"partial","phases":[-.5,.5],"model":[1.,1.],"target":2}
            answer=yield {"type":"work","groups":[(0,2),(1,3)],"parameters":{
                "contact":True},"quality":"preview"}
            assert answer==[[0.,2.],[1.,3.]]
            yield {"type":"result","result":{"parameters":{"contact":True},
                   "phases":[-.5,.5],"model":[1.,1.]}}
    class FakeWorkers:
        processes=[]
        @staticmethod
        def calculate(payloads,local,cancelled):return [local(payload) for payload in payloads]
        @staticmethod
        def close():pass
    kernel=launcher.NativeKernel.__new__(launcher.NativeKernel)
    kernel.model=FakeModel();kernel.supported_workers=2;kernel.phase_workers=FakeWorkers()
    kernel.lock=threading.Lock();kernel.jobs={};kernel.jobs_lock=threading.Lock()
    updates=list(kernel.stream("parallel","compute",{"workers":2}))
    assert [update["type"] for update in updates]==["partial","result"]
    assert updates[-1]["result"]["surface_workers"]==2
    assert updates[-1]["result"]["native_python"] is True


def test_colab_overlay_injects_native_transport_and_routes_requests():
    class FakeKernel:
        def __init__(self): self.calls=[]
        def status(self): return {"backend":"native-python","version":"2.5.4","pid":123,
                                  "environment":{"python":"3.12.0","phoebe":"2.5.4","numpy":"2.0.2","scipy":"1.15.3","astropy":"7.1.0","matplotlib":"3.11.2","passband":"Johnson:V","passband_sha256":"abc123","passband_bytes":14719680},
                                  "cpu_capacity":{"affinity_cpus":4,"cgroup_quota_cpus":2.,"usable_cpu_equivalents":2.},
                                  "supported_workers":1}
        def cancel(self, job_id): self.calls.append(("cancel",job_id))
        def run(self, job_id, operation, payload):
            self.calls.append((job_id,operation,payload))
            return {"result":{"native_python":True,"runtime":"Colab native Python"}}
        def stream(self, job_id, operation, payload):
            self.calls.append((job_id,operation,payload,"stream"))
            yield {"type":"partial","phases":[-.5,.5],"model":[1.,1.],"target":2}
            yield {"type":"result","result":{"parameters":{},"phases":[-.5,.5],"model":[1.,1.],"native_python":True}}
    kernel=FakeKernel();server=launcher.start_lab(ROOT / "site",kernel=kernel)
    try:
        base=f"http://127.0.0.1:{server.server_address[1]}"
        index=urllib.request.urlopen(base+"/",timeout=5).read().decode()
        assert "PHOEBE_COLAB_NATIVE" in index and "PHOEBE_COLAB_NATIVE_REQUIRED" in index
        assert 'content="colab-native-required"' in index and "_phoebe_native/" in index
        status=json.load(urllib.request.urlopen(base+"/_phoebe_native/status",timeout=5))
        assert status["backend"]=="native-python" and status["version"]=="2.5.4"
        assert status["environment"]["passband_sha256"]=="abc123"
        assert status["supported_workers"]==1 and status["cpu_capacity"]["usable_cpu_equivalents"]==2.
        body=json.dumps({"id":"job-7","operation":"compute","payload":{"geometry":"contact"}}).encode()
        request=urllib.request.Request(base+"/_phoebe_native/run",data=body,
                                       headers={"Content-Type":"application/json"})
        answer=json.load(urllib.request.urlopen(request,timeout=5))
        assert answer["result"]["native_python"] is True
        assert kernel.calls==[("job-7","compute",{"geometry":"contact"})]
        stream_body=json.dumps({"id":"job-8","operation":"compute","payload":{"geometry":"semi"}}).encode()
        stream_request=urllib.request.Request(base+"/_phoebe_native/stream",data=stream_body,
                                              headers={"Content-Type":"application/json"})
        updates=[json.loads(line) for line in urllib.request.urlopen(stream_request,timeout=5) if line.strip()]
        assert [update["type"] for update in updates]==["partial","result"]
        assert kernel.calls[-1]==("job-8","compute",{"geometry":"semi"},"stream")
        fit_body=json.dumps({"id":"job-9","operation":"fit","payload":{"fit":["inclination"]}}).encode()
        fit_request=urllib.request.Request(base+"/_phoebe_native/stream",data=fit_body,
                                           headers={"Content-Type":"application/json"})
        fit_updates=[json.loads(line) for line in urllib.request.urlopen(fit_request,timeout=5) if line.strip()]
        assert [update["type"] for update in fit_updates]==["partial","result"]
        assert kernel.calls[-1]==("job-9","fit",{"fit":["inclination"]},"stream")
    finally: launcher.stop_lab()


def test_shared_ui_has_explicit_colab_native_and_standalone_wasm_transports():
    app=(ROOT / "site" / "assets" / "app.js").read_text()
    client=(ROOT / "site" / "assets" / "engine-client.mjs").read_text()
    mode=(ROOT / "site" / "assets" / "runtime-mode.mjs").read_text()
    html=(ROOT / "site" / "index.html").read_text()
    assert "createScientificEngine" in app and "nativeKernelConfig" in app and "nativeKernelRequired" in app
    assert "Colab native engine ready" in app and "Browser engine ready" in app
    assert "engine_runtime" in app and "Colab native Python" in app and "Browser WebAssembly" in app
    assert "applyColabRuntimeUI(document,colabNativeMode)" in app
    assert "canOpenAdvancedWorkspace(colabNativeMode)" in app
    assert "isNativeProjectJson(project)" in app
    assert "Native PHOEBE project files are intentionally disabled in Colab" in mode
    assert "native PHOEBE running" in app and "s elapsed" in app
    assert "calculating first 5 phases" in app  # Standalone progressive worker retains its accurate status.
    assert "without a valid JSON response" in client
    assert "incomplete ${operation} result" in client and "incomplete surface mesh" in client
    assert "if(nativeKernelConfig)return new ColabNativeEngine" in client
    assert "if(nativeKernelRequired)return new MissingColabNativeEngine" in client
    assert "browser WebAssembly fallback is forbidden in Colab" in client
    assert "new Worker(workerURL,{type:'module'})" in client
    assert "PHOEBE_COLAB_NATIVE" not in html
    assert "application/x-ndjson" in (ROOT / "notebooks" / "phoebe_lab_colab.py").read_text()
    assert "type==='partial'" in client and "this.pause(data.id)" in client
    assert "green tested / amber caution / red unvalidated" in app
    assert "!unphysicalReason() && !current" in app
    assert "requestFullscreen" in app and "document.fullscreenElement" in app
    assert "window.open(location.href" in app and "opened.opener=null" in app
    assert "windowButton.disabled=true" in mode
    assert "workers.value='1'" in mode and "workers.hidden=true" in mode
    assert "applyColabWorkerStatus" in mode and "1 native worker" in mode
    assert "usable CPU equivalent" in mode and "Native phase streaming supports" in mode
    assert "fit search itself remains serial" in mode and "recommended_workers" in mode
    assert "independent browser Web Workers" in html
    assert "dataset.supportedWorkers" in app and "applyColabWorkerStatus(document,data)" in app
    assert 'View / orientation <select id="orbit-view"' in html
    launcher=(ROOT / "notebooks" / "phoebe_lab_colab.py").read_text()
    assert "output.serve_kernel_port_as_iframe(port, height=height)" in launcher
    assert "google.colab.kernel.proxyPort" not in launcher
    assert "_display_colab_iframe" not in launcher
    assert "serve_kernel_port_as_window" not in launcher


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
