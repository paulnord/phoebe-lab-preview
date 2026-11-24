"""Launch the familiar PHOEBE Lab web workbench inside Colab or Jupyter.

The repository source supplies the interface and geometry-specific models. Large
browser-runtime files that are intentionally excluded from git are transparently
proxied from the published PHOEBE Lab site at the same origin as the iframe.
"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
import os
import threading
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile

SOURCE_ARCHIVE = "https://github.com/paulnord/phoebe-lab-preview/archive/refs/heads/semi-detached.zip"
PUBLISHED_BASE = "https://paulnord.github.io/phoebe-lab-preview/"
_server = None
_thread = None
_download_root = None


def find_local_site(start=None):
    """Return a checkout's site directory when the notebook runs locally."""
    here = Path(start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        site = candidate / "site"
        if (site / "index.html").is_file() and (site / "assets" / "app.js").is_file():
            return site
    return None


def download_feature_site(url=SOURCE_ARCHIVE):
    """Download the feature-branch source used by a standalone Colab runtime."""
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
    """Serve branch UI files locally and proxy omitted runtime assets."""
    published_base = PUBLISHED_BASE

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

    def do_GET(self):
        local = self._local_path()
        if local is not None and local.exists():
            return super().do_GET()
        return self._proxy(False)

    def do_HEAD(self):
        local = self._local_path()
        if local is not None and local.exists():
            return super().do_HEAD()
        return self._proxy(True)


def start_lab(site=None):
    """Start or restart the loopback server and return it."""
    global _server, _thread
    if _server is not None:
        _server.shutdown()
        _server.server_close()
    site = Path(site) if site is not None else find_local_site()
    if site is None:
        site = download_feature_site()
    handler = partial(LabOverlayHandler, directory=str(site.resolve()))
    _server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    _thread = threading.Thread(target=_server.serve_forever, name="phoebe-lab", daemon=True)
    _thread.start()
    return _server


def show_lab(height=1050, site=None):
    """Render the same PHOEBE Lab workbench used by the standalone page."""
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
    global _server
    if _server is not None:
        _server.shutdown()
        _server.server_close()
        _server = None
