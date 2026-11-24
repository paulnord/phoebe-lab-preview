"""Bounded end-to-end check of the Colab HTTP bridge with native PHOEBE.

This is intentionally verification, not training.  It exercises the same loopback
server and JSON requests used by the shared browser UI.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("phoebe_lab_colab", ROOT / "notebooks" / "phoebe_lab_colab.py")
launcher = importlib.util.module_from_spec(spec); spec.loader.exec_module(launcher)

DEFAULTS = {"contact":False,"semidetached":False,"donor":"primary","inclination":84.5,
            "radius_primary":.21,"radius_secondary":.17,"fillout_factor":.25,
            "temperature_ratio":.84,"mass_ratio":.75,"eccentricity":0,"omega":90,
            "period":1.8,"epoch":0,"distortion":False,"irradiation":False}


def post(base, message, timeout=900):
    request=urllib.request.Request(base+"/_phoebe_native/run",data=json.dumps(message).encode(),
                                   headers={"Content-Type":"application/json"})
    return json.load(urllib.request.urlopen(request,timeout=timeout))


def main():
    server=launcher.start_lab(ROOT / "site")
    base=f"http://127.0.0.1:{server.server_address[1]}"
    dataset=json.loads((ROOT / "site" / "example.json").read_text())
    report={"status":json.load(urllib.request.urlopen(base+"/_phoebe_native/status")),"checks":[]}
    try:
        def run(name,operation,payload):
            started=time.perf_counter();answer=post(base,{"id":name,"operation":operation,"payload":payload})
            elapsed=time.perf_counter()-started
            report["checks"].append({"name":name,"operation":operation,"seconds":elapsed,
                                      "runtime":answer.get("runtime"),
                                      "phases":len(answer.get("result",{}).get("phases",[])),
                                      "native_python":answer.get("result",{}).get("native_python"),
                                      "surface_geometry":answer.get("value",{}).get("geometry"),
                                      "has_neck":answer.get("value",{}).get("neck") is not None})
            return answer

        base_payload={"parameters":DEFAULTS,"dataset":dataset,"quality":"preview","plot_phases":513,
                      "fit_phases":65,"workers":1,"fit":[]}
        curve=run("detached-513","compute",base_payload)
        assert len(curve["result"]["phases"])==513 and curve["result"]["native_python"]

        fit_payload={**base_payload,"fit":["inclination"]}
        fitted=run("detached-fit","fit",fit_payload)
        assert fitted["result"]["fit"]["parameters"]==["inclination"]
        assert len(fitted["result"]["phases"])==513 and fitted["result"]["native_python"]

        geometries=[
            ("semi-primary",{**DEFAULTS,"semidetached":True,"donor":"primary","radius_secondary":.195}),
            ("semi-secondary",{**DEFAULTS,"semidetached":True,"donor":"secondary","radius_primary":.222}),
            ("contact",{**DEFAULTS,"contact":True,"fillout_factor":.25}),
        ]
        for name,parameters in geometries:
            surface=run(name+"-surface","surface",{"parameters":parameters,"triangles":300})
            assert surface["value"]["geometry"] in ("semi","contact")
            if name=="contact":assert surface["value"]["neck"] is not None
            model=run(name+"-129","compute",{**base_payload,"parameters":parameters,"plot_phases":129})
            assert len(model["result"]["phases"])==129 and model["result"]["native_python"]
        print(json.dumps(report,indent=2))
    finally: launcher.stop_lab()


if __name__=="__main__":main()
