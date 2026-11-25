"""Run PHOEBE Lab Compute and Fit in this notebook's native Python PHOEBE runtime.

The browser renders the workbench controls, trained previews, and orbit playback.
Exact curves, bounded fits, residual statistics, exports, and native surface meshes
use the notebook's Python bridge and never fall back to browser WebAssembly.

The feature branch supplies the interface and geometry-specific models. Static support
files omitted from git may be proxied from the published site for display or download
compatibility; that asset proxy never handles scientific Compute or Fit requests.
"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
import importlib.util
import json
import multiprocessing
import os
import queue
import sys
import threading
import tempfile
import traceback
import urllib.error
import urllib.parse
import urllib.request
import zipfile

SOURCE_REVISION = "5b3ceaefae369c56734984ec82d22df26aeaf00f"
SOURCE_ARCHIVE = f"https://github.com/paulnord/phoebe-lab-preview/archive/{SOURCE_REVISION}.zip"
PUBLISHED_BASE = "https://paulnord.github.io/phoebe-lab-preview/"
_server = None
_thread = None
_download_root = None
_kernel = None


def _cgroup_cpu_quota():
    """Return the cgroup CPU quota as CPU equivalents, when one is configured."""
    try:
        v2=Path("/sys/fs/cgroup/cpu.max")
        if v2.is_file():
            quota,period=v2.read_text().split()[:2]
            if quota!="max" and float(period)>0:return float(quota)/float(period)
        quota_path=Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us")
        period_path=Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us")
        if quota_path.is_file() and period_path.is_file():
            quota=float(quota_path.read_text());period=float(period_path.read_text())
            if quota>0 and period>0:return quota/period
    except (OSError,ValueError,IndexError):
        pass
    return None


def detected_cpu_capacity():
    """Report scheduling capacity separately from native-engine worker support."""
    affinity=len(os.sched_getaffinity(0)) if hasattr(os,"sched_getaffinity") else int(os.cpu_count() or 1)
    quota=_cgroup_cpu_quota()
    usable=min(float(affinity),quota) if quota is not None else float(affinity)
    return {"affinity_cpus":affinity,"cgroup_quota_cpus":None if quota is None else round(quota,3),
            "usable_cpu_equivalents":round(max(0.001,usable),3)}


def supported_native_workers(capacity=None):
    """Return the truthful phase-worker limit for this Python runtime."""
    capacity=capacity or detected_cpu_capacity()
    if "fork" not in multiprocessing.get_all_start_methods():return 1
    return max(1,min(4,int(capacity["usable_cpu_equivalents"])))


def _phase_worker_loop(model_path,tasks,results,slot):
    """Keep one independent native PHOEBE model warm for exact phase batches."""
    try:
        os.environ.update(PHOEBE_ENABLE_ONLINE_PASSBANDS="FALSE",PHOEBE_ENABLE_MPI="FALSE",
                          PHOEBE_MULTIPROC_NPROCS="0",OMP_NUM_THREADS="1",OPENBLAS_NUM_THREADS="1")
        spec=importlib.util.spec_from_file_location(f"phoebe_lab_phase_worker_{slot}",model_path)
        model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)
        results.put(("ready",slot,os.getpid()))
        while True:
            task=tasks.get()
            if task is None:return
            task_id,payload=task
            try:results.put(("result",task_id,model.worker_flux(payload)))
            except BaseException as error:
                results.put(("error",task_id,f"{type(error).__name__}: {error}",traceback.format_exc()))
    except BaseException as error:
        results.put(("startup_error",slot,f"{type(error).__name__}: {error}",traceback.format_exc()))


class NativePhaseWorkers:
    """Persistent forked PHOEBE helpers; the notebook process remains worker one."""
    def __init__(self,model_path):
        self.model_path=str(model_path);self.context=multiprocessing.get_context("fork")
        self.tasks=None;self.results=None;self.processes=[];self.pids=[];self.sequence=0

    def _start(self,count):
        self.close();self.tasks=self.context.Queue();self.results=self.context.Queue();self.pids=[]
        self.processes=[self.context.Process(target=_phase_worker_loop,
                           args=(self.model_path,self.tasks,self.results,slot),daemon=True)
                        for slot in range(count)]
        for process in self.processes:process.start()

    def close(self):
        for process in self.processes:
            if process.is_alive():process.terminate()
        for process in self.processes:process.join(timeout=2)
        for channel in (self.tasks,self.results):
            if channel is not None:
                try:channel.close()
                except Exception:pass
        self.tasks=None;self.results=None;self.processes=[];self.pids=[]

    def calculate(self,payloads,local_flux,cancelled):
        """Compute one wave, preserving generator order and stopping stale helpers."""
        helper_count=max(0,len(payloads)-1)
        if helper_count<1:return [local_flux(payloads[0])]
        if len(self.processes)<helper_count:self._start(helper_count)
        task_ids=[]
        for payload in payloads[1:]:
            self.sequence+=1;task_ids.append(self.sequence);self.tasks.put((self.sequence,payload))
        local=local_flux(payloads[0])
        if cancelled.is_set():self.close();raise RuntimeError("Cancelled.")
        pending=set(task_ids);answers={}
        while pending:
            if cancelled.is_set():self.close();raise RuntimeError("Cancelled.")
            if any(not process.is_alive() for process in self.processes):
                self.close();raise RuntimeError("A native PHOEBE phase worker stopped unexpectedly.")
            try:message=self.results.get(timeout=.05)
            except queue.Empty:continue
            kind=message[0]
            if kind=="ready":
                self.pids.append(message[2]);continue
            if kind in ("startup_error","error"):
                self.close();raise RuntimeError(f"Native PHOEBE phase worker failed: {message[2]}")
            _,task_id,value=message
            if task_id in pending:answers[task_id]=value;pending.remove(task_id)
        return [local]+[answers[task_id] for task_id in task_ids]


class NativeKernel:
    """Serialize the shared UI's heavy work through native PHOEBE in Python."""
    def __init__(self, site):
        os.environ.update(PHOEBE_ENABLE_ONLINE_PASSBANDS="FALSE", PHOEBE_ENABLE_MPI="FALSE",
                          PHOEBE_MULTIPROC_NPROCS="0", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
        path = Path(site) / "engine" / "model.py"
        spec = importlib.util.spec_from_file_location("phoebe_lab_native_model", path)
        self.model = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.model)
        self.model_path=path;self.capacity=detected_cpu_capacity()
        self.supported_workers=supported_native_workers(self.capacity)
        self.phase_workers=NativePhaseWorkers(path)
        self.lock = threading.Lock(); self.jobs = {}; self.jobs_lock = threading.Lock()

    def close(self):self.phase_workers.close()

    def _worker_count(self,payload):
        value=payload.get("workers",1)
        if type(value) is not int or not 1<=value<=self.supported_workers:
            raise ValueError(f"Choose between 1 and {self.supported_workers} native phase workers.")
        return value

    def status(self):
        return {"backend":"native-python", "version":self.model.phoebe.__version__,
                "runtime":f"{sys.executable} · Python {sys.version.split()[0]}", "pid":os.getpid(),
                "environment":self.model.runtime_diagnostic(),
                "cpu_capacity":self.capacity,"supported_workers":self.supported_workers,
                "recommended_workers":self.supported_workers,
                "worker_backend":"persistent-python-processes",
                "worker_pids":[process.pid for process in self.phase_workers.processes if process.is_alive()]}

    def cancel(self, job_id):
        with self.jobs_lock:
            event = self.jobs.get(str(job_id))
        if event is not None: event.set()

    def stream(self, job_id, operation, payload):
        """Yield native progressive updates for the Colab iframe transport."""
        job_id=str(job_id);cancelled=threading.Event()
        with self.jobs_lock:self.jobs[job_id]=cancelled
        try:
            with self.lock:
                if operation not in ("compute","fit"):raise ValueError("Unknown streamed native operation.")
                workers=self._worker_count(payload)
                steps=(self.model.progressive_fit if operation=="fit" else self.model.progressive_curve)(dict(payload,workers=workers))
                response=None
                while True:
                    if cancelled.is_set():raise RuntimeError("Cancelled.")
                    try:update=next(steps) if response is None else steps.send(response)
                    except StopIteration:return
                    response=None
                    if update["type"]=="work":
                        payloads=[{"parameters":update["parameters"],"quality":update["quality"],"indices":indices}
                                  for indices in update["groups"]]
                        response=self.phase_workers.calculate(payloads,self.model.worker_flux,cancelled)
                        continue
                    if update["type"]=="result":
                        update["result"]["runtime"]="Colab native Python"
                        update["result"]["native_python"]=True
                        parameters=update["result"].get("parameters",{})
                        surface=any(parameters.get(key) for key in ("contact","semidetached","distortion","irradiation"))
                        update["result"]["surface_workers"]=workers if surface else 1
                    yield update
        finally:
            with self.jobs_lock:self.jobs.pop(job_id,None)

    def run(self, job_id, operation, payload):
        job_id=str(job_id);cancelled=threading.Event()
        with self.jobs_lock:self.jobs[job_id]=cancelled
        try:
            with self.lock:
                if cancelled.is_set(): raise RuntimeError("Cancelled.")
                if operation == "surface":
                    value=self.model.surface_mesh(payload)
                    return {"value":value,"runtime":self.status()}
                if operation == "fit":
                    result=self.model.fit(dict(payload,workers=self._worker_count(payload)))
                elif operation == "compute":
                    result=None
                    for update in self.model.progressive_curve(dict(payload,workers=self._worker_count(payload))):
                        if cancelled.is_set(): raise RuntimeError("Cancelled.")
                        if update["type"]=="work":raise RuntimeError("Non-streaming parallel compute is unavailable.")
                        if update["type"] == "result":result=update["result"]
                    if result is None:raise RuntimeError("Native PHOEBE did not return a complete curve.")
                else:raise ValueError("Unknown native operation.")
                result["runtime"]="Colab native Python"
                result["native_python"]=True
                return {"result":result,"runtime":self.status()}
        finally:
            with self.jobs_lock:self.jobs.pop(job_id,None)


def find_local_site(start=None):
    """Return a checkout's site directory when the notebook runs locally."""
    here = Path(start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        site = candidate / "site"
        if (site / "index.html").is_file() and (site / "assets" / "app.js").is_file():
            return site
    return None


def download_feature_site(url=SOURCE_ARCHIVE):
    """Download the feature-branch site when no local checkout is available."""
    global _download_root
    request = urllib.request.Request(url, headers={"User-Agent": "PHOEBE-Lab-Colab"})
    with urllib.request.urlopen(request, timeout=120) as response:
        archive = response.read()
    root = Path(tempfile.mkdtemp(prefix="phoebe-lab-colab-"))
    with zipfile.ZipFile(BytesIO(archive)) as bundle:
        bundle.extractall(root)
    matches = list(root.glob("*/site/index.html"))
    if len(matches) != 1:
        raise RuntimeError("The PHOEBE Lab source archive did not contain one site directory.")
    _download_root = root
    return matches[0].parent


class LabOverlayHandler(SimpleHTTPRequestHandler):
    """Serve the branch UI and native bridge, proxying only omitted static assets."""
    published_base = PUBLISHED_BASE
    native_kernel = None

    def log_message(self, format, *args):
        pass

    def _local_path(self):
        relative = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path).lstrip("/")
        candidate = (Path(self.directory) / relative).resolve()
        root = Path(self.directory).resolve()
        return candidate if candidate == root or root in candidate.parents else None

    def _proxy(self, head=False):
        path = urllib.parse.urlsplit(self.path)
        remote = urllib.parse.urljoin(self.published_base, path.path.lstrip("/"))
        if path.query:
            remote += "?" + path.query
        headers = {"User-Agent": "PHOEBE-Lab-Colab"}
        if self.headers.get("Range"):
            headers["Range"] = self.headers["Range"]
        try:
            with urllib.request.urlopen(urllib.request.Request(remote, headers=headers), timeout=120) as response:
                self.send_response(response.status)
                for name in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges", "Cache-Control", "ETag"):
                    if response.headers.get(name):
                        self.send_header(name, response.headers[name])
                self.end_headers()
                if not head:
                    while chunk := response.read(1024 * 256):
                        self.wfile.write(chunk)
        except urllib.error.HTTPError as error:
            self.send_error(error.code, f"Published runtime asset unavailable: {path.path}")
        except Exception as error:
            self.send_error(502, f"Could not load published runtime asset: {error}")

    def _json(self, value, status=200):
        data=json.dumps(value,allow_nan=False).encode()
        self.send_response(status);self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(data)));self.send_header("Cache-Control","no-store")
        self.end_headers();self.wfile.write(data)

    def _stream(self, job_id, operation, payload):
        self.send_response(200);self.send_header("Content-Type","application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control","no-store");self.send_header("X-Content-Type-Options","nosniff")
        self.end_headers()
        try:
            for update in self.native_kernel.stream(job_id,operation,payload):
                self.wfile.write(json.dumps(update,allow_nan=False).encode()+b"\n");self.wfile.flush()
        except (BrokenPipeError,ConnectionResetError):return
        except Exception as error:
            try:self.wfile.write(json.dumps({"type":"error","error":str(error)[:900]}).encode()+b"\n");self.wfile.flush()
            except (BrokenPipeError,ConnectionResetError):return

    def _serve_colab_index(self):
        text=(Path(self.directory)/"index.html").read_text()
        config='<meta name="phoebe-compute-backend" content="colab-native-required"><script>globalThis.PHOEBE_COLAB_NATIVE_REQUIRED=true;globalThis.PHOEBE_COLAB_NATIVE={endpoint:new URL("./_phoebe_native/",location.href).href};</script>'
        data=text.replace("</head>",config+"\n</head>").encode()
        self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8")
        self.send_header("Content-Length",str(len(data)));self.send_header("Cache-Control","no-store")
        self.end_headers();self.wfile.write(data)

    def do_GET(self):
        path=urllib.parse.urlsplit(self.path).path
        if path == "/_phoebe_native/status" and self.native_kernel:return self._json(self.native_kernel.status())
        if path in ("/","/index.html") and self.native_kernel:return self._serve_colab_index()
        local = self._local_path()
        if local is not None and local.exists():
            return super().do_GET()
        return self._proxy(False)

    def do_POST(self):
        path=urllib.parse.urlsplit(self.path).path
        if not self.native_kernel or path not in ("/_phoebe_native/run","/_phoebe_native/stream","/_phoebe_native/cancel"):
            return self._json({"error":"Native Colab backend is unavailable."},404)
        try:
            length=int(self.headers.get("Content-Length","0"))
            if length<2 or length>10_000_000:raise ValueError("Invalid request size.")
            message=json.loads(self.rfile.read(length))
            if path.endswith("/cancel"):
                self.native_kernel.cancel(message.get("id"));return self._json({"cancelled":True})
            if path.endswith("/stream"):
                return self._stream(message.get("id"),message.get("operation"),message.get("payload",{}))
            value=self.native_kernel.run(message.get("id"),message.get("operation"),message.get("payload",{}))
            try:return self._json(value)
            except (BrokenPipeError,ConnectionResetError):return
        except Exception as error:
            try:return self._json({"error":str(error)[:900]},409 if "Cancelled" in str(error) else 400)
            except (BrokenPipeError,ConnectionResetError):return

    def do_HEAD(self):
        local = self._local_path()
        if local is not None and local.exists():
            return super().do_HEAD()
        return self._proxy(True)


def start_lab(site=None, kernel=None):
    """Start or restart the loopback server and return it."""
    global _server, _thread, _kernel
    if _server is not None:
        _server.shutdown()
        _server.server_close()
        if hasattr(_kernel,"close"):_kernel.close()
    site = Path(site) if site is not None else find_local_site()
    if site is None:
        site = download_feature_site()
    if kernel is None:kernel=NativeKernel(site)
    _kernel=kernel
    handler_class=type("BoundLabOverlayHandler",(LabOverlayHandler,),{"native_kernel":kernel})
    handler = partial(handler_class, directory=str(site.resolve()))
    _server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    _thread = threading.Thread(target=_server.serve_forever, name="phoebe-lab", daemon=True)
    _thread.start()
    return _server


def show_lab(height=1050, site=None):
    """Display the PHOEBE Lab workbench served by this notebook kernel."""
    server = start_lab(site)
    port = server.server_address[1]
    try:
        from google.colab import output
    except ImportError:
        from IPython.display import IFrame, display
        display(IFrame(src=f"http://127.0.0.1:{port}/", width="100%", height=height))
    else:
        output.serve_kernel_port_as_iframe(port, height=height)
    return server


def stop_lab():
    global _server, _kernel
    if _server is not None:
        _server.shutdown()
        _server.server_close()
        _server = None
    if hasattr(_kernel,"close"):_kernel.close()
    _kernel=None
