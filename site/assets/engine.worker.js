/* PHOEBE executes here, inside the browser, with no model-computation API. */
const RUNTIME = new URL("../runtime/", self.location.href).href;
let pyodide;
let initialized = false;
let activeId = null;
let progressiveId = null;
let progressiveOperation;
function status(title, detail = "") { self.postMessage({ type: "status", title, detail }); }
self.modelProgress = (message) => self.postMessage({ type: "progress", id: activeId, ...JSON.parse(message) });

async function initialize(nativeFiles=false) {
  status("Starting Python in your browser", "Downloading the WebAssembly runtime. This is cached after the first visit.");
  const { loadPyodide } = await import(`${RUNTIME}pyodide.mjs`);
  pyodide = await loadPyodide({ indexURL: RUNTIME,
    stdout: () => {}, stderr: (message) => console.debug("PHOEBE:", message) });
  status("Loading scientific libraries", "NumPy, SciPy, and Astropy are being loaded into this browser worker.");
  await pyodide.loadPackage(["numpy", "scipy", "astropy", "micropip", "tqdm", "requests"]);
  status("Loading PHOEBE", "Installing the WebAssembly builds of PHOEBE and its interpolation library.");
  if(nativeFiles){
    await pyodide.loadPackage("scikit-learn");
    const res=await fetch(new URL("advanced-wheels.json",RUNTIME));
    if(!res.ok)throw Error("The local advanced solver packages are missing.");
    const wheels=Object.entries(await res.json()).map(([name,sha])=>new URL(name,RUNTIME).href+"#sha256="+sha);
    pyodide.globals.set("_advanced_wheels",JSON.stringify(wheels));
    await pyodide.runPythonAsync("import json, micropip; await micropip.install(json.loads(_advanced_wheels),deps=False)");
  }
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
  if(!nativeFiles){
    const refs=await fetch(new URL('../engine/surface-references.json',self.location.href));
    if(refs.ok)pyodide.FS.writeFile('/home/pyodide/surface-references.json',await refs.text());
  }
  await pyodide.runPythonAsync("import model; import phoebe; _engine_version = phoebe.__version__");
  if (nativeFiles) {
    const advancedSource=await fetch(new URL('../engine/advanced.py',self.location.href));
    if(!advancedSource.ok)throw Error('The advanced parameter module is missing.');
    pyodide.FS.writeFile('/home/pyodide/advanced.py',await advancedSource.text());
    const nativeSource=await fetch(new URL('../engine/native_files.py',self.location.href));
    if (!nativeSource.ok) throw Error('The native PHOEBE file module is missing.');
    pyodide.FS.writeFile('/home/pyodide/native_files.py',await nativeSource.text());
    await pyodide.runPythonAsync('import native_files');
  }
  initialized = true;
  self.postMessage({ type: "ready", version: pyodide.globals.get("_engine_version") });
}

// The primary worker computes one batch itself. Helpers hold independent PHOEBE bundles.
let helpers = [];
function releaseHelpers() {
  for (const h of helpers) h.worker.terminate();
  helpers = [];
}
function createHelper() {
  const worker = new Worker(self.location.href, {type:"module"});
  let resolve, reject, failure;
  const ready = new Promise((ok, fail)=>{ resolve=ok; reject=fail; });
  const fail = error => {failure=error;reject(error);};
  worker.onmessage = ({data}) => {
    if (data.type === "ready" || data.type === "flux") resolve(data.flux);
    if (data.type === "fatal" || data.type === "error") fail(Error(data.error));
  };
  worker.onerror = event => fail(Error(event.message || "A PHOEBE worker stopped."));
  worker.onmessageerror = () => fail(Error("Could not read a PHOEBE worker response."));
  worker.postMessage({type:"initialize"});
  return {worker, async run(payload) {
    await ready;
    if(failure)throw failure;
    return new Promise((ok, fail)=>{
      resolve=ok; reject=fail;
      worker.postMessage({type:"flux", payload});
    });
  }};
}
const fluxCommand = 'json.dumps(model.worker_flux(json.loads(_flux_payload)), allow_nan=False)';
async function localFlux(payload) {
  pyodide.globals.set("_flux_payload", JSON.stringify(payload));
  return JSON.parse(await pyodide.runPythonAsync(fluxCommand));
}
async function calculateWave({groups, parameters, quality}) {
  while (helpers.length < groups.length - 1) helpers.push(createHelper());
  const payloads = groups.map(indices=>({parameters, quality, indices}));
  const others = payloads.slice(1).map((payload,i)=>helpers[i].run(payload));
  return Promise.all([localFlux(payloads[0]), ...others]);
}

// The host can change settings while helper threads are busy. Serialize access to
// this interpreter and let the UI revision check discard late results.
let messages = Promise.resolve();
self.onmessage = ({data}) => { messages = messages.then(()=>handle(data)).catch(error=>{
  releaseHelpers();
  self.postMessage({type:"error", id:data.id, error:String(error)});
}); };
async function handle(data) {
  if (data.type === "initialize") {
    try { await initialize(data.nativeFiles===true); }
    catch (error) { self.postMessage({ type: "fatal", error: String(error) }); }
    return;
  }
  if (!initialized) { self.postMessage({ type: "error", id: data.id, error: "The scientific engine is still loading." }); return; }
  if (data.type === "continue" && data.id !== progressiveId) return;
  activeId = data.id;
  try {
    if (data.type === "release") {
      if (data.id === progressiveId) { releaseHelpers(); progressiveId=null; }
      return;
    }
    if (data.type === "flux") {
      self.postMessage({type:"flux", flux:await localFlux(data.payload)});
      return;
    }
    if (data.payload) pyodide.globals.set("_model_payload", JSON.stringify(data.payload));
    if (data.type === 'continue' || (data.progressive && ['compute', 'fit'].includes(data.type))) {
      if (data.type !== 'continue') {
        releaseHelpers();
        progressiveOperation = data.type;
        progressiveId = data.id;
        const generator = data.type === 'fit' ? 'progressive_fit' : 'progressive_curve';
        pyodide.runPython(`_curve_steps = model.${generator}(json.loads(_model_payload))`);
      }
      let message = JSON.parse(await pyodide.runPythonAsync('json.dumps(next(_curve_steps), allow_nan=False)'));
      if (message.type === "work") {
        const fluxes = await calculateWave(message);
        pyodide.globals.set("_fluxes", JSON.stringify(fluxes));
        message = JSON.parse(pyodide.runPython('json.dumps(_curve_steps.send(json.loads(_fluxes)), allow_nan=False)'));
      }
      if (message.type === 'result') {
        if(helpers.length)message.result.surface_workers=1+helpers.length;
        releaseHelpers(); progressiveId = null;
      }
      self.postMessage({...message, id:data.id, operation:progressiveOperation});
      return;
    }
    progressiveId = null;
    if (data.type==='native') {
      pyodide.globals.set('_native_op',data.operation);
      const answer=await pyodide.runPythonAsync('json.dumps(native_files.workspace.act(_native_op, json.loads(_model_payload)),allow_nan=False)');
      self.postMessage({type:'native_result',id:data.id,value:JSON.parse(answer)});
      return;
    }
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
    releaseHelpers(); progressiveId = null;
    self.postMessage({ type: "error", id: data.id, error: String(error) });
  }
  activeId = null;
}
