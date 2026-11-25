"""Bounded native PHOEBE smoke for the two published picker presets."""
import csv
import importlib.util
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("phoebe_lab_observed_verify",ROOT/"notebooks"/"phoebe_lab_colab.py")
launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)

DEFAULTS={"contact":False,"semidetached":False,"donor":"primary","inclination":84.5,
          "radius_primary":.21,"radius_secondary":.17,"fillout_factor":.25,
          "temperature_ratio":.84,"mass_ratio":.75,"eccentricity":0,"omega":90,
          "period":1.8,"epoch":0,"distortion":False,"irradiation":False}
PRESETS={
    "sz-her":("observed-sz-her-johnson-v.csv",{**DEFAULTS,"semidetached":True,"donor":"secondary",
        "inclination":87.566,"radius_primary":.318,"temperature_ratio":4881/7262,"mass_ratio":.4715,
        "period":.8180837,"epoch":2454588.167997}),
    "v1128-tau":("observed-v1128-tau-johnson-v.csv",{**DEFAULTS,"contact":True,"inclination":86,
        "fillout_factor":.134,"temperature_ratio":6400/6200,"mass_ratio":.534,
        "period":.305371,"epoch":2454842.3470}),
}

def dataset(filename,parameters):
    with (ROOT/"site"/"examples"/filename).open(newline="") as handle:
        rows=list(csv.reader(handle))[1:]
    return {"name":filename,"synthetic":False,"x_kind":"time","y_kind":"magnitude",
            "x":[float(row[0]) for row in rows],"y":[float(row[1]) for row in rows],
            "period":parameters["period"],"epoch":parameters["epoch"],"time_system":"HJD"}

def main():
    kernel=launcher.NativeKernel(ROOT/"site")
    report={"backend":kernel.status(),"checks":[]}
    workers=kernel.supported_workers
    try:
        for name,(filename,parameters) in PRESETS.items():
            result=None;partials=[]
            payload={"parameters":parameters,"dataset":dataset(filename,parameters),"quality":"preview",
                     "plot_phases":129,"fit_phases":65,"workers":workers,"fit":[]}
            for update in kernel.stream("observed-"+name,"compute",payload):
                if update["type"]=="partial":partials.append(len(update["phases"]))
                elif update["type"]=="result":result=update["result"]
            assert result and result["native_python"] and len(result["phases"])==129
            assert len(result["comparison"]["phase"])==len(payload["dataset"]["x"])
            assert all(math.isfinite(value) for value in result["model"])
            assert min(result["model"])<.99
            report["checks"].append({"name":name,"observations":len(payload["dataset"]["x"]),
                "mode":"contact" if parameters["contact"] else "semi-secondary",
                "period":parameters["period"],"epoch":parameters["epoch"],"partials":partials,
                "phases":len(result["phases"]),"surface_workers":result["surface_workers"],
                "rms":result["comparison"]["rms"]})
    finally:kernel.close()
    print(json.dumps(report,indent=2))

if __name__=="__main__":main()
