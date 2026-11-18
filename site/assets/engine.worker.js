/* PHOEBE executes here, inside the browser, with no model-computation API. */
const RUNTIME = new URL("../runtime/", self.location.href).href;
let pyodide;
let initialized = false;
let activeId = null;
function status(title, detail = "") { self.postMessage({ type: "status", title, detail }); }
self.modelProgress = (message) => self.postMessage({ type: "progress", id: activeId, ...JSON.parse(message) });

async function initialize() {
  status("Starting Python in your browser", "Downloading the WebAssembly runtime. This is cached after the first visit.");
  const { loadPyodide } = await import(`${RUNTIME}pyodide.mjs`);
  pyodide = await loadPyodide({ indexURL: RUNTIME,
    stdout: () => {}, stderr: (message) => console.debug("PHOEBE:", message) });
  status("Loading scientific libraries", "NumPy, SciPy, and Astropy are being loaded into this browser worker.");
  await pyodide.loadPackage(["numpy", "scipy", "astropy", "micropip", "tqdm", "requests"]);
  status("Loading PHOEBE", "Installing the WebAssembly builds of PHOEBE and its interpolation library.");
  const manifestURL = new URL("../engine/manifest.json", self.location.href);
  const response = await fetch(manifestURL);
  if (!response.ok) throw new Error("The PHOEBE WebAssembly packages are missing. Build the browser engine first.");
  const manifest = await response.json();
  const wheels = manifest.wheels.map((name) => new URL(name, manifestURL).href + `#sha256=${manifest.sha256[name]}`);
  pyodide.globals.set("_browser_wheels", JSON.stringify(wheels));
  await pyodide.runPythonAsync(`
import os, json
os.environ.update({
    'PHOEBE_ENABLE_PLOTTING': 'FALSE', 'PHOEBE_ENABLE_SYMPY': 'FALSE',
    'PHOEBE_ENABLE_ONLINE_PASSBANDS': 'FALSE', 'PHOEBE_ENABLE_MPI': 'FALSE',
    'PHOEBE_MULTIPROC_NPROCS': '0', 'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1'
})
import micropip
await micropip.install(json.loads(_browser_wheels), deps=False)
`);
  status("Preparing the binary-star model", "PHOEBE's numerical engine is running locally in WebAssembly.");
  const modelURL = new URL("../engine/model.py", self.location.href);
  const sourceResponse = await fetch(modelURL);
  if (!sourceResponse.ok) throw new Error("The model calculation module could not be loaded.");
  pyodide.FS.writeFile("/home/pyodide/model.py", await sourceResponse.text());
  await pyodide.runPythonAsync("import model; import phoebe; _engine_version = phoebe.__version__");
  initialized = true;
  self.postMessage({ type: "ready", version: pyodide.globals.get("_engine_version") });
}

self.onmessage = async ({ data }) => {
  if (data.type === "initialize") {
    try { await initialize(); }
    catch (error) { self.postMessage({ type: "fatal", error: String(error) }); }
    return;
  }
  if (!initialized) { self.postMessage({ type: "error", id: data.id, error: "The scientific engine is still loading." }); return; }
  activeId = data.id;
  try {
    pyodide.globals.set("_model_payload", JSON.stringify(data.payload));
    const operation = data.type === "fit" ? "fit" : "compute";
    let command = `json.dumps(model.${operation}(json.loads(_model_payload)), allow_nan=False)`;
    if (data.profile) command = `
import cProfile, pstats, io
_profile = cProfile.Profile()
_profile.enable()
_answer = model.${operation}(json.loads(_model_payload))
_profile.disable()
_stream = io.StringIO()
pstats.Stats(_profile, stream=_stream).sort_stats('cumulative').print_stats(25)
_answer['_profile'] = _stream.getvalue()
json.dumps(_answer, allow_nan=False)
`;
    const text = await pyodide.runPythonAsync(command);
    self.postMessage({ type: "result", id: data.id, operation, result: JSON.parse(text) });
  } catch (error) {
    self.postMessage({ type: "error", id: data.id, error: String(error) });
  }
  activeId = null;
};
