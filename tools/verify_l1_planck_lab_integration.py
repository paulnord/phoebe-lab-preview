"""Exercise the validated Planck path through the native Colab Lab kernel."""
import csv
import importlib.util
import json
from pathlib import Path

import numpy as np


ROOT=Path(__file__).resolve().parents[1]
launcher_spec=importlib.util.spec_from_file_location(
    "phoebe_lab_l1_integration_verify",ROOT/"notebooks"/"phoebe_lab_colab.py")
launcher=importlib.util.module_from_spec(launcher_spec);launcher_spec.loader.exec_module(launcher)

DEFAULTS={"contact":False,"semidetached":False,"donor":"primary","inclination":84.5,
          "radius_primary":.21,"radius_secondary":.17,"fillout_factor":.25,
          "temperature_ratio":.84,"mass_ratio":.75,"eccentricity":0,"omega":90,
          "period":1.8,"epoch":0,"distortion":False,"irradiation":False}
SZ={**DEFAULTS,"semidetached":True,"donor":"secondary","inclination":87.566,
    "radius_primary":.318,"temperature_ratio":4881/7262,"mass_ratio":.4715,
    "period":.8180837,"epoch":2454588.167997}


def observations():
    path=ROOT/"site"/"examples"/"observed-sz-her-johnson-v.csv"
    with path.open(newline="") as handle:rows=list(csv.reader(handle))[1:]
    return {"name":"SZ Herculis - Johnson V","synthetic":False,
            "x_kind":"time","y_kind":"magnitude",
            "x":[float(row[0]) for row in rows],"y":[float(row[1]) for row in rows],
            "period":SZ["period"],"epoch":SZ["epoch"],"time_system":"HJD"}


def run(kernel,name,parameters,quality,phases,workers,data):
    kernel.model._last_complete=None
    payload={"parameters":parameters,"dataset":data,"quality":quality,
             "plot_phases":phases,"fit_phases":65,"workers":workers,"fit":[]}
    partials=[];result=None
    for update in kernel.stream(name,"compute",payload):
        if update["type"]=="partial":partials.append(len(update["phases"]))
        elif update["type"]=="result":result=update["result"]
    assert result and result["native_python"] and len(result["phases"])==phases
    assert np.all(np.isfinite(result["model"])) and np.all(np.asarray(result["model"])>0)
    return result,partials


def main():
    data=observations();kernel=launcher.NativeKernel(ROOT/"site")
    report={"backend":kernel.status(),"sz_her":[],"controls":{}}
    try:
        widths=sorted(set([1,kernel.supported_workers]))
        reference={}
        for quality,phases in (("preview",129),("refined",513)):
            for workers in widths:
                result,partials=run(kernel,f"sz-{quality}-{workers}",SZ,quality,phases,workers,data)
                curve=np.asarray(result["model"])
                if quality in reference:
                    np.testing.assert_allclose(curve,reference[quality],rtol=2e-13,atol=2e-13)
                else:reference[quality]=curve
                report["sz_her"].append({
                    "quality":quality,"workers":workers,"phases":len(curve),
                    "partials":partials,"rms":result["comparison"]["rms"],
                    "native_planck_activations":result["native_planck_activations"],
                    "warning_summary":result.get("native_warning_summary"),
                })
        for name,parameters in (
            ("detached",DEFAULTS),
            ("contact",{**DEFAULTS,"contact":True}),
        ):
            first,_=run(kernel,name+"-a",parameters,"preview",129,1,data)
            second,_=run(kernel,name+"-b",parameters,"preview",129,1,data)
            np.testing.assert_array_equal(first["model"],second["model"])
            assert first["native_planck_activations"]==second["native_planck_activations"]==0
            report["controls"][name]={"samples":129,"repeat_array_equal":True,
                                      "planck_activations":0}
    finally:kernel.close()
    print(json.dumps(report,indent=2))


if __name__=="__main__":main()
