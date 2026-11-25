#!/usr/bin/env python3
"""Train target-neighborhood display surrogates from native PHOEBE curves."""
from __future__ import annotations
import argparse, hashlib, json, os, time
from multiprocessing import Pool
from pathlib import Path
os.environ.setdefault("PHOEBE_ENABLE_ONLINE_PASSBANDS", "FALSE")
import numpy as np
from scipy.stats import qmc

ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent;ARTIFACTS=HERE/"artifacts"
DATA=ARTIFACTS/"literature-local-curves.npz";MODEL=ROOT/"site"/"experiment"/"literature-local-model.json";REPORT=HERE/"REPORT.md"
PHASES,HARMONICS=129,48;TRAIN_COUNT,TUNE_COUNT,TEST_COUNT=96,24,32
SEEDS={"train":91427,"tune":118621,"test":143777};BASELINE_COMMIT="c5364d1714c5c4ca7ba4aa003031ae1c2929c6a8"
KEYS=("inclination","mass_ratio","shape","temperature_ratio","log_period")
BOUNDS={"contact":{"inclination":(78.,90.),"mass_ratio":(.45,.65),"shape":(.10,.23),"temperature_ratio":(.94,1.10),"period":(.22,.45)},
        "semi_secondary":{"inclination":(82.,90.),"mass_ratio":(.40,.58),"shape":(.55,.82),"temperature_ratio":(.62,.74),"period":(.60,1.05)}}
PRESETS={"contact":{"inclination":86.,"mass_ratio":.534,"shape":.134,"temperature_ratio":6400/6200,"period":.305371},
         "semi_secondary":{"inclination":87.566,"mass_ratio":.4715,"radius_primary":.318,"temperature_ratio":4881/7262,"period":.8180837}}
_bundles={}

def feature_row(p):return np.array([p["inclination"],p["mass_ratio"],p["shape"],p["temperature_ratio"],np.log(p["period"])])
def feature_bounds(mode):
    b=BOUNDS[mode];return np.array([[*b["inclination"]],[*b["mass_ratio"]],[*b["shape"]],[*b["temperature_ratio"]],[np.log(b["period"][0]),np.log(b["period"][1])]])
def design(mode,count,seed):
    unit=qmc.Sobol(len(KEYS),scramble=True,seed=seed).random(count)
    for i in range(count//4):unit[i,i%len(KEYS)]=.02 if (i//len(KEYS))%2==0 else .98
    b=feature_bounds(mode);return b[:,0]+unit*(b[:,1]-b[:,0])
def parameters(row):return {"inclination":float(row[0]),"mass_ratio":float(row[1]),"shape":float(row[2]),"temperature_ratio":float(row[3]),"period":float(np.exp(row[4]))}

def bundle(mode,triangles):
    import phoebe
    if phoebe.__version__!="2.5.4":raise RuntimeError(f"Expected PHOEBE 2.5.4, found {phoebe.__version__}")
    if mode=="contact":
        b=phoebe.default_contact_binary();b.flip_constraint("mass@primary",solve_for="sma@binary");b.flip_constraint("pot@contact_envelope",solve_for="requiv@primary");b.flip_constraint("fillout_factor@contact_envelope",solve_for="pot@contact_envelope")
    else:b=phoebe.default_binary(semidetached="secondary");b.flip_constraint("mass@primary",solve_for="sma@binary")
    b.set_value("mass",component="primary",value=1.2);b.add_dataset("lc",compute_phases=np.linspace(-.5,.5,PHASES),dataset="local_lc",passband="Johnson:V")
    b.set_value_all("ntriangles",value=triangles);b.set_value("irrad_method",value="none");return b
def native_curve(mode,row,triangles=800):
    p=parameters(row);key=(mode,triangles)
    if key not in _bundles:_bundles[key]=bundle(mode,triangles)
    b=_bundles[key];b.set_value("period",component="binary",value=p["period"]);b.set_value("q",component="binary",value=p["mass_ratio"])
    if mode=="contact":b.set_value("fillout_factor",component="contact_envelope",context="component",value=p["shape"]);model="local_contact"
    else:
        max_radius=b.get_value("requiv_max",component="primary",context="component");b.set_value("requiv",component="primary",context="component",value=p["shape"]*max_radius);model="local_semi"
    b.set_value("teff",component="primary",value=6300.);b.set_value("teff",component="secondary",value=6300.*p["temperature_ratio"]);b.set_value("incl",component="binary",value=p["inclination"])
    b.set_value("compute_phases",dataset="local_lc",context="dataset",value=np.linspace(-.5,.5,PHASES));b.set_value_all("ntriangles",value=triangles);b.run_compute(model=model,overwrite=True,progressbar=False)
    flux=np.asarray(b.get_value("fluxes",dataset="local_lc",model=model),float)
    if flux.shape!=(PHASES,) or not np.all(np.isfinite(flux)&(flux>0)):raise ValueError("invalid native flux")
    return flux/np.median(flux)
def semi_preset_row():
    import phoebe
    b=phoebe.default_binary(semidetached="secondary");b.flip_constraint("mass@primary",solve_for="sma@binary");p=PRESETS["semi_secondary"]
    b.set_value("mass",component="primary",value=1.2);b.set_value("period",component="binary",value=p["period"]);b.set_value("q",component="binary",value=p["mass_ratio"])
    shape=p["radius_primary"]/(b.get_value("requiv_max",component="primary",context="component")/b.get_value("sma",component="binary",context="component"))
    return feature_row({**p,"shape":shape})
def preset_row(mode):return feature_row(PRESETS[mode]) if mode=="contact" else semi_preset_row()
def worker(task):
    mode,row=task;started=time.perf_counter();error=None
    for triangles in (800,1500,3000):
        try:return native_curve(mode,row,triangles),time.perf_counter()-started,"ok",triangles
        except Exception as exc:error=exc;_bundles.pop((mode,triangles),None)
    return np.full(PHASES,np.nan),time.perf_counter()-started,str(error)[:400],0
def run_tasks(tasks,workers):
    began=time.perf_counter()
    with Pool(max(1,workers)) as pool:results=list(pool.imap(worker,tasks,chunksize=1))
    flux=np.asarray([r[0] for r in results]);seconds=np.asarray([r[1] for r in results]);status=np.asarray([r[2] for r in results]);triangles=np.asarray([r[3] for r in results])
    if not np.all(status=="ok"):raise RuntimeError([(i,s) for i,s in enumerate(status) if s!="ok"])
    return flux,seconds,triangles,time.perf_counter()-began
def pilot(workers):
    tasks=[(mode,row) for mode in BOUNDS for row in design(mode,8,SEEDS["train"])]
    _,seconds,triangles,wall=run_tasks(tasks,workers);estimate=wall*((TRAIN_COUNT+TUNE_COUNT+TEST_COUNT)*2+2)/len(tasks)
    print(json.dumps({"pilot_systems":len(tasks),"workers":workers,"wall_seconds":wall,"median_native_seconds":float(np.median(seconds)),"p95_native_seconds":float(np.quantile(seconds,.95)),"retry_1500":int(np.sum(triangles==1500)),"retry_3000":int(np.sum(triangles==3000)),"estimated_full_wall_seconds":estimate},indent=2))
def generate(workers):
    ARTIFACTS.mkdir(parents=True,exist_ok=True);arrays={};tasks=[];slices={};start=0
    for mode in BOUNDS:
        for split,count in (("train",TRAIN_COUNT),("tune",TUNE_COUNT),("test",TEST_COUNT)):
            rows=design(mode,count,SEEDS[split]+(0 if mode=="contact" else 1009));arrays[f"{mode}_{split}_parameters"]=rows;tasks.extend((mode,row) for row in rows);slices[(mode,split)]=slice(start,start+count);start+=count
        exact=preset_row(mode)[None,:];arrays[f"{mode}_preset_parameters"]=exact;tasks.append((mode,exact[0]));slices[(mode,"preset")]=slice(start,start+1);start+=1
    flux,seconds,triangles,wall=run_tasks(tasks,workers)
    for mode in BOUNDS:
        for split in ("train","tune","test","preset"):arrays[f"{mode}_{split}_flux"]=flux[slices[(mode,split)]]
    arrays.update(phases=np.linspace(-.5,.5,PHASES),seconds=seconds,triangles_used=triangles,keys=np.asarray(KEYS),generation_wall_seconds=np.asarray(wall));np.savez_compressed(DATA,**arrays)
    print(json.dumps({"systems":len(tasks),"workers":workers,"wall_seconds":wall,"median_native_seconds":float(np.median(seconds)),"p95_native_seconds":float(np.quantile(seconds,.95)),"retry_1500":int(np.sum(triangles==1500)),"retry_3000":int(np.sum(triangles==3000)),"path":str(DATA)},indent=2))

def basis(phases):return np.column_stack([np.ones(len(phases))]+[np.cos(2*np.pi*k*phases) for k in range(1,HARMONICS+1)])
def scale(mode,rows):b=feature_bounds(mode);return 2*(rows-b[:,0])/(b[:,1]-b[:,0])-1
def kernel(x,c,g):return np.exp(-g*np.sum((x[:,None,:]-c[None,:,:])**2,axis=2))
def predict(mode,spec,rows,matrix):
    curves=(kernel(scale(mode,rows),np.asarray(spec["centers"]),spec["gamma"])@np.asarray(spec["weights"]))@matrix.T
    return curves/np.median(curves,axis=1)[:,None]
def metrics(exact,pred):
    e=pred-exact;curve=np.sqrt(np.mean(e*e,axis=1));phase=np.linspace(-.5,.5,PHASES)
    primary=np.abs(phase)<.16;secondary=np.abs(phase)>.34
    primary_depth=np.abs(np.min(pred[:,primary],axis=1)-np.min(exact[:,primary],axis=1))
    secondary_depth=np.abs(np.min(pred[:,secondary],axis=1)-np.min(exact[:,secondary],axis=1))
    return {"pooled_rms":float(np.sqrt(np.mean(e*e))),"curve_rms_p95":float(np.quantile(curve,.95)),"max_abs":float(np.max(np.abs(e))),
      "primary_depth_error_p95":float(np.quantile(primary_depth,.95)),"secondary_depth_error_p95":float(np.quantile(secondary_depth,.95)),
      "primary_eclipse_rms":float(np.sqrt(np.mean(e[:,primary]**2))),"secondary_eclipse_rms":float(np.sqrt(np.mean(e[:,secondary]**2)))}
def fit(mode,data,matrix):
    train=data[f"{mode}_train_parameters"];tf=data[f"{mode}_train_flux"];tune=data[f"{mode}_tune_parameters"];tunef=data[f"{mode}_tune_flux"]
    coeff=np.linalg.lstsq(matrix,tf.T,rcond=None)[0].T;centers=scale(mode,train);candidates=[]
    for gamma in (.18,.28,.4,.6,.9,1.3):
        k=kernel(centers,centers,gamma)
        for ridge in (1e-8,1e-7,1e-6,1e-5,1e-4):
            weights=np.linalg.solve(k+ridge*np.eye(len(centers)),coeff);spec={"gamma":gamma,"weights":weights,"centers":centers};pred=predict(mode,spec,tune,matrix);candidates.append((np.sqrt(np.mean((pred-tunef)**2)),gamma,ridge,weights))
    tune_rms,gamma,ridge,weights=min(candidates,key=lambda row:row[0]);test=data[f"{mode}_test_parameters"]
    distances=np.sqrt(np.min(np.sum((scale(mode,test)[:,None,:]-centers[None,:,:])**2,axis=2),axis=1))
    spec={"gamma":gamma,"ridge":ridge,"centers":centers.tolist(),"weights":weights.tolist(),"nearest_scaled_distance_max":float(np.quantile(distances,.95)),"tune_rms":float(tune_rms)}
    spec["test_metrics"]=metrics(data[f"{mode}_test_flux"],predict(mode,spec,test,matrix));spec["preset_metrics"]=metrics(data[f"{mode}_preset_flux"],predict(mode,spec,data[f"{mode}_preset_parameters"],matrix));return spec
def train():
    data=np.load(DATA,allow_pickle=False);matrix=basis(data["phases"]);models={mode:fit(mode,data,matrix) for mode in BOUNDS}
    semi_rows=np.vstack([data[f"semi_secondary_{split}_parameters"] for split in ("train","tune","test","preset")])
    import phoebe
    b=phoebe.default_binary(semidetached="secondary");b.flip_constraint("mass@primary",solve_for="sma@binary");b.set_value("mass",component="primary",value=1.2);lobe=[]
    for row in semi_rows:
        p=parameters(row);b.set_value("period",component="binary",value=p["period"]);b.set_value("q",component="binary",value=p["mass_ratio"]);lobe.append(b.get_value("requiv_max",component="primary",context="component")/b.get_value("sma",component="binary",context="component"))
    order=np.argsort(semi_rows[:,1]);models["semi_secondary"]["lobe_q"]=semi_rows[order,1].tolist();models["semi_secondary"]["lobe_fraction"]=np.asarray(lobe)[order].tolist()
    model={"schema":1,"name":"literature-neighborhood-rbf-fourier-v1","accepted":True,"source":"native PHOEBE 2.5.4; target observations are not training data","keys":list(KEYS),"bounds":BOUNDS,"phases":256,"harmonics":HARMONICS,"modes":models,"fixed":{"eccentricity":0.,"irradiation":False,"primary_mass_solar":1.2,"primary_teff_k":6300.,"passband":"Johnson:V"},"training":{"train_count_per_mode":TRAIN_COUNT,"tune_count_per_mode":TUNE_COUNT,"test_count_per_mode":TEST_COUNT,"preset_holdout_count_per_mode":1,"seeds":SEEDS,"native_phases":PHASES,"triangles":800,"baseline_commit":BASELINE_COMMIT,"native_artifact_sha256":hashlib.sha256(DATA.read_bytes()).hexdigest()}}
    MODEL.write_text(json.dumps(model,separators=(",",":")));write_report(model,data);print(json.dumps({m:{"tune_rms":s["tune_rms"],"test":s["test_metrics"],"preset":s["preset_metrics"]} for m,s in models.items()},indent=2))
def write_report(model,data):
    t=model["training"];wall=float(data["generation_wall_seconds"]) if "generation_wall_seconds" in data else float("nan");lines=["# Literature-neighborhood preview training","",f"Baseline: `{t['baseline_commit']}`",f"Native artifact SHA-256: `{t['native_artifact_sha256']}`","",f"Per mode: {TRAIN_COUNT} train / {TUNE_COUNT} tune / {TEST_COUNT} untouched test systems plus the exact published preset as a separate one-system holdout. Splits use independent Sobol seeds and never share phase samples. The observed photometry is not a training target.","",f"Generation: {len(data['seconds'])} native PHOEBE systems with four local workers in {wall:.1f} s; median {np.median(data['seconds']):.3f} s, p95 {np.quantile(data['seconds'],.95):.3f} s per curve; {int(np.sum(data['triangles_used']==1500))} retries at 1,500 triangles and {int(np.sum(data['triangles_used']==3000))} at 3,000.","","| Mode / holdout | pooled RMS | p95 curve RMS | max abs | primary depth p95 | secondary depth p95 | primary eclipse RMS | secondary eclipse RMS |","|---|---:|---:|---:|---:|---:|---:|---:|"]
    for mode,spec in model["modes"].items():
        for split,key in (("independent test","test_metrics"),("exact preset","preset_metrics")):
            m=spec[key];lines.append(f"| {mode} / {split} | {m['pooled_rms']:.6f} | {m['curve_rms_p95']:.6f} | {m['max_abs']:.6f} | {m['primary_depth_error_p95']:.6f} | {m['secondary_depth_error_p95']:.6f} | {m['primary_eclipse_rms']:.6f} | {m['secondary_eclipse_rms']:.6f} |")
    lines += ["","## Validated display domains","",f"- V1128 Tau contact neighborhood: inclination 78–90°, q 0.45–0.65, fill-out 0.10–0.23, T2/T1 0.94–1.10, P 0.22–0.45 d.",f"- SZ Her secondary-donor neighborhood: inclination 82–90°, q 0.40–0.58, free-primary Roche fill 0.55–0.82, T2/T1 0.62–0.74, P 0.60–1.05 d.","","The browser adapter fails closed outside a small confidence margin and the existing broad contact/semi models remain unchanged at their original P=1.8 d domains. Native PHOEBE remains authoritative for fitting, residual statistics and export. These local previews omit spots and do not establish unique photometric q."]
    REPORT.write_text("\n".join(lines)+"\n")
def main():
    p=argparse.ArgumentParser();p.add_argument("action",choices=("pilot","generate","train","all"));p.add_argument("--workers",type=int,default=4);a=p.parse_args()
    if a.action=="pilot":pilot(a.workers)
    if a.action in ("generate","all"):generate(a.workers)
    if a.action in ("train","all"):train()
if __name__=="__main__":main()
