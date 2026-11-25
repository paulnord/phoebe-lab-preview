"""Reproduce the standard semi-detached load and fit through the Colab native bridge."""
import csv
import importlib.util
import json
from pathlib import Path
import time

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("phoebe_lab_semi_standard",ROOT/"notebooks"/"phoebe_lab_colab.py")
launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)

DEFAULTS={"contact":False,"semidetached":False,"donor":"primary","inclination":84.5,
          "radius_primary":.21,"radius_secondary":.17,"fillout_factor":.25,
          "temperature_ratio":.84,"mass_ratio":.75,"eccentricity":0,"omega":90,
          "period":.8180837,"epoch":2454588.167997,"distortion":False,"irradiation":False}
SZ={**DEFAULTS,"semidetached":True,"donor":"secondary","inclination":87.566,
    "radius_primary":.318,"temperature_ratio":4881/7262,"mass_ratio":.4715}


def observations():
    with (ROOT/"site/examples/observed-sz-her-johnson-v.csv").open(newline="") as handle:
        rows=list(csv.reader(handle))[1:]
    return {"name":"SZ Herculis - Johnson V","synthetic":False,"x_kind":"time","y_kind":"magnitude",
            "x":[float(row[0]) for row in rows],"y":[float(row[1]) for row in rows],
            "period":SZ["period"],"epoch":SZ["epoch"],"time_system":"HJD"}


def main():
    kernel=launcher.NativeKernel(ROOT/"site");data=observations();checks=[]
    def run(name,parameters,operation="compute",fit=None):
        payload={"parameters":parameters,"dataset":data,"quality":"preview","plot_phases":129,
                 "fit_phases":65,"workers":kernel.supported_workers,"fit":fit or []}
        started=time.perf_counter();partials=[];result=None
        for update in kernel.stream(name,operation,payload):
            if update["type"]=="partial":partials.append(len(update["phases"]))
            elif update["type"]=="result":result=update["result"]
        assert result and result["native_python"] and len(result["phases"])==(513 if operation=="fit" else 129)
        checks.append({"name":name,"operation":operation,"donor":parameters.get("donor"),
            "phases":len(result["phases"]),"partials":partials,"rms":result["comparison"]["rms"],
            "seconds":time.perf_counter()-started,"fit":result.get("fit")})
        return result
    try:
        fresh=run("sz-standard-fresh",SZ)
        run("semi-primary-default",{**DEFAULTS,"semidetached":True,"donor":"primary","radius_secondary":.195})
        run("contact-default",{**DEFAULTS,"contact":True})
        restored=run("sz-standard-after-switches",SZ)
        assert fresh["model"]==restored["model"]
        run("sz-standard-inclination-fit",SZ,"fit",["inclination"])
    finally:kernel.close()
    print(json.dumps({"backend":"native-python PHOEBE 2.5.4","observations":len(data["x"]),"checks":checks},indent=2))


if __name__=="__main__":main()
