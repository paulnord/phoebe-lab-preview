"""Prove the shared browser UI routes Compute and Fit through the Colab Python bridge.

This is a fast transport test.  The Python-side kernel returns deterministic
native-shaped results; separate native-PHOEBE tests validate the scientific
wrapper itself.  Browser Worker construction is made fatal so any fallback is
observable.
"""
from __future__ import annotations

import importlib.util
import math
import os
from pathlib import Path
import sys
import threading

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("phoebe_lab_colab", ROOT / "notebooks" / "phoebe_lab_colab.py")
launcher = importlib.util.module_from_spec(spec); spec.loader.exec_module(launcher)


class ProbeKernel:
    def __init__(self): self.calls=[]
    def status(self): return {"backend":"native-python","version":"2.5.4","runtime":"probe Python","pid":123}
    def cancel(self,job_id): self.calls.append(("cancel",job_id))
    def run(self,job_id,operation,payload):
        if operation!="surface":raise AssertionError(f"unexpected non-stream operation {operation}")
        p=payload["parameters"];triangles=payload["triangles"]
        if p["contact"]:
            mesh={"schema":1,"source":"native PHOEBE 2.5.4 probe","geometry":"contact","donor":"primary",
                  "frame":"primary_origin","neck":.5,"phase":0,"triangles_requested":triangles,"triangles_actual":triangles,
                  "components":[
                    {"name":"primary","triangles":[[[0,-.2,0],[.5,-.08,.08],[.5,.08,.08]],[[0,-.2,0],[.5,.08,.08],[0,.2,0]]]},
                    {"name":"secondary","triangles":[[[.5,-.08,.08],[1,-.2,0],[1,.2,0]],[[.5,-.08,.08],[1,.2,0],[.5,.08,.08]]]}]}
        else:
            mesh={"schema":1,"source":"native PHOEBE 2.5.4 probe","geometry":"semi","donor":p["donor"],
                  "frame":"component_local","phase":0,"triangles_requested":triangles,"triangles_actual":triangles,
                  "components":[
                    {"name":"primary","triangles":[[[.45,-.08,0],[.45,.08,0],[-.32,0,.16]],[[.45,-.08,0],[-.32,0,-.16],[-.32,0,.16]]]},
                    {"name":"secondary","triangles":[[[.18,-.05,0],[.18,.05,0],[-.16,0,.1]],[[.18,-.05,0],[-.16,0,-.1],[-.16,0,.1]]]}]}
        self.calls.append((job_id,operation,triangles))
        return {"value":mesh,"runtime":self.status()}

    @staticmethod
    def result(payload,fit=False):
        phases=[-.5+i/64 for i in range(65)]
        model=[1-.25*math.exp(-((phase/.055)**2))-.08*math.exp(-(((abs(phase)-.5)/.07)**2)) for phase in phases]
        dataset=payload["dataset"];observed=list(dataset["y"]);data_phase=list(dataset["x"])
        parameters=dict(payload["parameters"])
        comparison={"phase":data_phase,"flux":observed,"model_at_data":observed,
                    "residual":[0.0]*len(observed),"rms":0.0,"reduced_chi2":0.0}
        answer={"parameters":parameters,"phases":phases,"model":model,"comparison":comparison,
                "quality":payload.get("quality","preview"),"seconds":.01,
                "runtime":"Colab native Python","native_python":True}
        if fit:answer["fit"]={"parameters":list(payload["fit"]),"objective_phases":payload["fit_phases"],
                              "evaluations":1,"converged":True}
        return answer

    def stream(self,job_id,operation,payload):
        self.calls.append((job_id,operation))
        print(f"PYTHON_BRIDGE operation={operation} job={job_id}",flush=True)
        result=self.result(payload,operation=="fit")
        if operation=="fit":yield {"type":"fit_parameters","parameters":result["parameters"]}
        yield {"type":"partial","phases":result["phases"],"model":result["model"],"target":65}
        yield {"type":"result","result":result}


def main():
    kernel=ProbeKernel();server=launcher.start_lab(ROOT / "site",kernel=kernel)
    url=f"http://127.0.0.1:{server.server_address[1]}/"
    try:
        with sync_playwright() as pw:
            launch={"headless":True,"args":["--no-sandbox","--disable-dev-shm-usage"]}
            if os.environ.get("PHOEBE_CHROMIUM"):launch["executable_path"]=os.environ["PHOEBE_CHROMIUM"]
            browser=pw.chromium.launch(**launch)
            page=browser.new_page(viewport={"width":1280,"height":900})
            page.add_init_script("window.Worker=class {constructor(){throw Error('browser Worker fallback forbidden by probe')}};")
            errors=[];page.on("pageerror",lambda error:errors.append(str(error)))
            page.goto(url)
            page.locator("#engine-pill").get_by_text("Colab native engine ready").wait_for(timeout=15000)
            page.locator("#export-button").wait_for(state="visible")
            assert page.locator("#export-button").is_enabled()
            assert any(operation=="compute" for _,operation in kernel.calls if operation!="cancel")
            assert "Colab Python runtime" in page.locator("#engine-runtime").inner_text()
            assert "browser WebAssembly" not in page.locator("#engine-detail").inner_text()
            assert page.locator("#window-button").is_disabled()
            assert "no longer provides a reliable" in page.locator("#window-button").get_attribute("title")

            # A denied iframe fullscreen request is reported and cannot alter routing.
            page.evaluate("Object.defineProperty(document.documentElement,'requestFullscreen',{configurable:true,value:()=>Promise.reject(new Error('denied'))})")
            page.locator("#fullscreen-button").click()
            page.get_by_text("Fullscreen was blocked",exact=False).wait_for(timeout=5000)
            assert any(operation=="compute" for _,operation in kernel.calls if operation!="cancel")

            page.locator("#fit-button").click()
            page.locator("#fit-form button[type=submit]").click()
            page.get_by_text("Local fit complete",exact=False).wait_for(timeout=15000)
            assert any(operation=="fit" for _,operation in kernel.calls if operation!="cancel")
            assert "Colab native engine ready" in page.locator("#engine-pill").inner_text()
            assert not errors,errors
            browser.close()
    finally: launcher.stop_lab()
    print("Real Chromium shared UI routed Compute and Fit to the Python bridge; browser Worker fallback was impossible.")


def serve_probe(native=False):
    server=launcher.start_lab(ROOT / "site",kernel=None if native else ProbeKernel())
    label="PHOEBE_COLAB_NATIVE" if native else "PHOEBE_COLAB_PROBE"
    print(f"{label}=http://127.0.0.1:{server.server_address[1]}/",flush=True)
    try:threading.Event().wait()
    finally:launcher.stop_lab()


if __name__=="__main__":
    if "--serve-native" in sys.argv:serve_probe(True)
    elif "--serve" in sys.argv:serve_probe(False)
    else:main()
