"""Measure serial and persistent-process phase streaming through the Colab entry point."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import threading
import time

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location("phoebe_lab_parallel_benchmark",ROOT/"notebooks"/"phoebe_lab_colab.py")
launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)

DEFAULTS={"contact":False,"semidetached":False,"donor":"primary","inclination":84.5,
          "radius_primary":.21,"radius_secondary":.17,"fillout_factor":.25,
          "temperature_ratio":.84,"mass_ratio":.75,"eccentricity":0,"omega":90,
          "period":1.8,"epoch":0,"distortion":False,"irradiation":False}


def digest(values):
    return hashlib.sha256(np.asarray(values,dtype="<f8").tobytes()).hexdigest()


def curve(kernel,workers,fillout):
    dataset=json.loads((ROOT/"site"/"example.json").read_text())
    parameters={**DEFAULTS,"contact":True,"fillout_factor":fillout}
    payload={"parameters":parameters,"dataset":dataset,"quality":"preview","plot_phases":129,
             "fit_phases":65,"workers":workers,"fit":[]}
    began=time.perf_counter();first=None;partials=[];result=None
    for update in kernel.stream(f"curve-{workers}-{fillout}","compute",payload):
        if update["type"]=="partial":
            if first is None:first=time.perf_counter()-began
            partials.append(len(update["phases"]))
        elif update["type"]=="result":result=update["result"]
    return {"first_partial_seconds":first,"total_seconds":time.perf_counter()-began,
            "partials":partials,"phases":len(result["phases"]),"flux_sha256":digest(result["model"]),
            "surface_workers":result["surface_workers"]}


def fit(kernel,workers):
    dataset=json.loads((ROOT/"site"/"example.json").read_text())
    parameters={**DEFAULTS,"contact":True,"fillout_factor":.25}
    payload={"parameters":parameters,"dataset":dataset,"quality":"preview","plot_phases":129,
             "fit_phases":65,"workers":workers,"fit":["inclination"]}
    began=time.perf_counter();fit_parameters_at=None;first=None;result=None
    for update in kernel.stream(f"fit-{workers}","fit",payload):
        if update["type"]=="fit_parameters":fit_parameters_at=time.perf_counter()-began
        elif update["type"]=="partial" and first is None:first=time.perf_counter()-began
        elif update["type"]=="result":result=update["result"]
    return {"fit_parameters_seconds":fit_parameters_at,"first_partial_seconds":first,
            "total_seconds":time.perf_counter()-began,"parameters":result["parameters"],
            "evaluations":result["fit"]["evaluations"],"flux_sha256":digest(result["model"]),
            "surface_workers":result["surface_workers"]}


def cancel_restart(kernel):
    dataset=json.loads((ROOT/"site"/"example.json").read_text())
    payload={"parameters":{**DEFAULTS,"contact":True,"fillout_factor":.29},"dataset":dataset,
             "quality":"preview","plot_phases":129,"fit_phases":65,"workers":2,"fit":[]}
    stream=kernel.stream("cancel-probe","compute",payload)
    first=next(stream);assert first["type"]=="partial"
    outcome={}
    def advance():
        try:next(stream)
        except BaseException as error:outcome["error"]=f"{type(error).__name__}: {error}"
    thread=threading.Thread(target=advance);thread.start();time.sleep(.05);kernel.cancel("cancel-probe")
    thread.join(timeout=30);assert not thread.is_alive()
    assert outcome.get("error")=="RuntimeError: Cancelled.",outcome
    helpers_after_cancel=len(kernel.phase_workers.processes)
    restarted=curve(kernel,2,.31)
    return {"cancel_error":outcome["error"],"helpers_after_cancel":helpers_after_cancel,
            "restart_phases":restarted["phases"],"restart_flux_sha256":restarted["flux_sha256"]}


def main():
    report={"capacity":launcher.detected_cpu_capacity(),"supported_workers":launcher.supported_native_workers(),
            "runs":{}}
    worker_counts=sorted({1,min(2,report["supported_workers"]),report["supported_workers"]})
    for workers in worker_counts:
        kernel=launcher.NativeKernel(ROOT/"site")
        try:
            report["runs"][str(workers)]={"cold":curve(kernel,workers,.25),"warm":curve(kernel,workers,.27),
                                           "helper_pids":[p.pid for p in kernel.phase_workers.processes]}
            if "--fit" in sys.argv:report["runs"][str(workers)]["fit"]=fit(kernel,workers)
            if workers==min(2,report["supported_workers"]) and "--cancel" in sys.argv:
                report["cancel_restart"]=cancel_restart(kernel)
        finally:kernel.close()
    for workers in worker_counts[1:]:
        assert report["runs"]["1"]["cold"]["flux_sha256"]==report["runs"][str(workers)]["cold"]["flux_sha256"]
        assert report["runs"]["1"]["warm"]["flux_sha256"]==report["runs"][str(workers)]["warm"]["flux_sha256"]
    if "--fit" in sys.argv:
        for workers in worker_counts[1:]:
            assert report["runs"]["1"]["fit"]["parameters"]==report["runs"][str(workers)]["fit"]["parameters"]
            assert report["runs"]["1"]["fit"]["flux_sha256"]==report["runs"][str(workers)]["fit"]["flux_sha256"]
    print(json.dumps(report,indent=2))


if __name__=="__main__":main()
