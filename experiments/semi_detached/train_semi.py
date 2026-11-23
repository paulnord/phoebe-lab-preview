#!/usr/bin/env python3
"""Generate, train, and independently validate the semi-detached preview."""
from __future__ import annotations
import argparse, hashlib, json, os, time
from multiprocessing import Pool
from pathlib import Path
os.environ.setdefault("PHOEBE_ENABLE_ONLINE_PASSBANDS", "FALSE")
import numpy as np
from scipy.stats import qmc
from semi_native import (BOUNDS, DONORS, KEYS, PASSBAND, PERIOD, PHOEBE_VERSION,
                         PRIMARY_MASS, PRIMARY_TEFF, TRIANGLES, make_bundle, semi_flux)

HERE=Path(__file__).resolve().parent; ARTIFACTS=HERE/"artifacts"
DATA=ARTIFACTS/"semi-curves.npz"; MODEL=Path(__file__).resolve().parents[2]/"site/experiment/semi-model.json"; REPORT=HERE/"REPORT.md"
TRAIN_COUNT,TUNE_COUNT,TEST_COUNT=192,48,64
SEEDS={"train":53117,"tune":84191,"test":116731}
PHASES,HARMONICS=129,48
BASELINE_COMMIT="b7ce074c8231cc8db9bc2e4016b667071daaa845"
_bundles={}

def design(count,seed):
    unit=qmc.Sobol(len(KEYS),scramble=True,seed=seed).random(count)
    # Reserve one quarter for deterministic near-boundary coverage, cycling all axes.
    for i in range(count//4):
        axis=i%len(KEYS); unit[i,axis]=.015 if (i//len(KEYS))%2==0 else .985
    lo=np.array([BOUNDS[k][0] for k in KEYS]); hi=np.array([BOUNDS[k][1] for k in KEYS])
    return lo+unit*(hi-lo)

def sweep_design():
    anchors=np.array([[68.,.46,.78,.80],[87.,1.22,.80,1.10],[84.,.44,.42,.96],[76.,.92,.60,.88]])
    rows=[]; meta=[]
    steps=np.array([1.0,.04,.035,.025])
    for ai,base in enumerate(anchors):
        rows.append(base); base_index=len(rows)-1
        for ki,key in enumerate(KEYS):
            changed=base.copy(); changed[ki]=np.clip(changed[ki]+steps[ki],*BOUNDS[key])
            rows.append(changed); meta.append((ai,ki,base_index,len(rows)-1))
    return np.asarray(rows),np.asarray(meta,int)

def as_parameters(row,donor): return {**{key:float(row[i]) for i,key in enumerate(KEYS)},"donor":donor}

def worker(task):
    donor,row=task; started=time.perf_counter(); error=None
    for triangles in (TRIANGLES,1500,3000):
        try:
            key=(donor,triangles)
            if key not in _bundles:_bundles[key]=make_bundle(donor,PHASES,triangles)
            _,flux,p=semi_flux(as_parameters(row,donor),PHASES,triangles,_bundles[key])
            return flux,time.perf_counter()-started,"ok",triangles,p["radius_primary"],p["radius_secondary"]
        except Exception as exc:
            error=exc; _bundles.pop((donor,triangles),None)
    return np.full(PHASES,np.nan),time.perf_counter()-started,str(error)[:400],0,np.nan,np.nan

def generate(workers):
    ARTIFACTS.mkdir(parents=True,exist_ok=True); sweep,sweep_meta=sweep_design(); arrays={}; tasks=[]; slices={}; start=0
    for donor in DONORS:
        for split,count in (("train",TRAIN_COUNT),("tune",TUNE_COUNT),("test",TEST_COUNT)):
            rows=design(count,SEEDS[split]+(0 if donor=="primary" else 1009)); arrays[f"{donor}_{split}_parameters"]=rows
            tasks.extend((donor,row) for row in rows); slices[(donor,split)]=slice(start,start+count); start+=count
        arrays[f"{donor}_sweep_parameters"]=sweep.copy(); tasks.extend((donor,row) for row in sweep); slices[(donor,"sweep")]=slice(start,start+len(sweep)); start+=len(sweep)
    began=time.perf_counter()
    with Pool(max(1,workers)) as pool: results=list(pool.imap(worker,tasks,chunksize=1))
    flux=np.asarray([r[0] for r in results]); seconds=np.asarray([r[1] for r in results]); status=np.asarray([r[2] for r in results]); triangles=np.asarray([r[3] for r in results]); radii=np.asarray([[r[4],r[5]] for r in results])
    if not np.all(status=="ok"): raise RuntimeError(f"Native generation failed: {[(i,s) for i,s in enumerate(status) if s!='ok']}")
    for donor in DONORS:
        for split in ("train","tune","test","sweep"):
            sl=slices[(donor,split)]; arrays[f"{donor}_{split}_flux"]=flux[sl]; arrays[f"{donor}_{split}_radii"]=radii[sl]
    arrays.update(phases=np.linspace(-.5,.5,PHASES),keys=np.asarray(KEYS),sweep_meta=sweep_meta,seconds=seconds,triangles_used=triangles)
    np.savez_compressed(DATA,**arrays)
    print(json.dumps({"systems":len(tasks),"workers":workers,"wall_seconds":time.perf_counter()-began,"median_curve_seconds":float(np.median(seconds)),"p95_curve_seconds":float(np.quantile(seconds,.95)),"retry_1500":int(np.sum(triangles==1500)),"retry_3000":int(np.sum(triangles==3000)),"path":str(DATA)}))

def scale(rows):
    lo=np.array([BOUNDS[k][0] for k in KEYS]);hi=np.array([BOUNDS[k][1] for k in KEYS]);return 2*(rows-lo)/(hi-lo)-1
def basis(phases):return np.column_stack([np.ones(len(phases))]+[np.cos(2*np.pi*k*phases) for k in range(1,HARMONICS+1)])
def kernel(x,c,g):return np.exp(-g*np.sum((x[:,None,:]-c[None,:,:])**2,axis=2))
def predict(spec,rows,matrix):
    curves=(kernel(scale(rows),np.asarray(spec["centers"]),spec["gamma"])@np.asarray(spec["weights"]))@matrix.T
    return curves/np.median(curves,axis=1)[:,None]

def curve_metrics(parameters,exact,predicted):
    error=predicted-exact; inc=parameters[:,0]; fill=parameters[:,2]
    regimes={"all":np.ones(len(parameters),bool),"grazing":inc<=72.,"near_free_lobe":fill>=.72,"unequal_mass":(parameters[:,1]<=.55)|(parameters[:,1]>=1.15)}
    rows=[]
    for name,mask in regimes.items():
        e=error[mask]; cr=np.sqrt(np.mean(e*e,axis=1)); rows.append(dict(regime=name,n=int(mask.sum()),rms=float(np.sqrt(np.mean(e*e))),curve_rms_p95=float(np.quantile(cr,.95)),abs_p95=float(np.quantile(np.abs(e),.95)),worst_abs=float(np.max(np.abs(e)))))
    return rows

def response_metrics(spec,sweep,exact,matrix,meta):
    predicted=predict(spec,sweep,matrix); rows=[]
    for ai,ki,bi,pi in meta:
        native=exact[pi]-exact[bi]; model=predicted[pi]-predicted[bi]
        nn=float(np.linalg.norm(native)); mn=float(np.linalg.norm(model)); denom=max(nn*mn,1e-15)
        rows.append(dict(anchor=int(ai),parameter=KEYS[int(ki)],native_response_rms=float(np.sqrt(np.mean(native*native))),difference_rms=float(np.sqrt(np.mean((model-native)**2))),cosine=float(np.dot(native,model)/denom),relative_norm_error=float(abs(mn-nn)/max(nn,1e-15))))
    return rows

def fit_one(data,donor,matrix):
    tp=data[f"{donor}_train_parameters"]; tune=data[f"{donor}_tune_parameters"]; test=data[f"{donor}_test_parameters"]
    tf=data[f"{donor}_train_flux"]; tunef=data[f"{donor}_tune_flux"]; testf=data[f"{donor}_test_flux"]
    coeff=np.linalg.lstsq(matrix,tf.T,rcond=None)[0].T; centers=scale(tp); candidates=[]
    for gamma in (.25,.4,.65,1.0,1.5):
        k=kernel(centers,centers,gamma)
        for ridge in (1e-7,1e-6,1e-5,1e-4):
            weights=np.linalg.solve(k+ridge*np.eye(len(centers)),coeff); pred=(kernel(scale(tune),centers,gamma)@weights)@matrix.T; pred=pred/np.median(pred,axis=1)[:,None]
            candidates.append((float(np.sqrt(np.mean((pred-tunef)**2))),gamma,ridge,weights))
    tune_rms,gamma,ridge,weights=min(candidates,key=lambda x:x[0])
    distances=np.sqrt(np.min(np.sum((scale(test)[:,None,:]-centers[None,:,:])**2,axis=2),axis=1))
    spec={"gamma":gamma,"ridge":ridge,"centers":centers.tolist(),"weights":weights.tolist(),"nearest_scaled_distance_max":float(np.max(distances)+1e-12)}
    test_pred=predict(spec,test,matrix); spec["tune_rms"]=tune_rms; spec["test_metrics"]=curve_metrics(test,testf,test_pred)
    spec["response_metrics"]=response_metrics(spec,data[f"{donor}_sweep_parameters"],data[f"{donor}_sweep_flux"],matrix,data["sweep_meta"])
    return spec

def train():
    data=np.load(DATA,allow_pickle=False); matrix=basis(data["phases"]); donor_models={d:fit_one(data,d,matrix) for d in DONORS}
    for donor in DONORS:
        parameters=np.vstack([data[f"{donor}_{s}_parameters"] for s in ("train","tune","test")]);radii=np.vstack([data[f"{donor}_{s}_radii"] for s in ("train","tune","test")]);free=radii[:,1] if donor=="primary" else radii[:,0];order=np.argsort(parameters[:,1]);donor_models[donor]["lobe_q"]=parameters[order,1].tolist();donor_models[donor]["lobe_fraction"]=(free[order]/parameters[order,2]).tolist()
    model={"schema":1,"name":"semi-detached-rbf-fourier-v1","accepted":True,"source":f"native PHOEBE {PHOEBE_VERSION} semi-detached constraints","keys":list(KEYS),"bounds":BOUNDS,"fixed":{"period":PERIOD,"eccentricity":0.,"irradiation":False},"phases":256,"harmonics":HARMONICS,"donors":donor_models,"training":{"train_count_per_donor":TRAIN_COUNT,"tune_count_per_donor":TUNE_COUNT,"test_count_per_donor":TEST_COUNT,"seeds":SEEDS,"native_phases":PHASES,"triangles":TRIANGLES,"primary_mass_solar":PRIMARY_MASS,"primary_teff_k":PRIMARY_TEFF,"passband":PASSBAND,"native_artifact_sha256":hashlib.sha256(DATA.read_bytes()).hexdigest(),"baseline_commit":BASELINE_COMMIT}}
    MODEL.write_text(json.dumps(model,separators=(",",":"))); write_report(model,data); print(json.dumps({"model":str(MODEL),"donors":{d:{"tune_rms":donor_models[d]["tune_rms"],"test":donor_models[d]["test_metrics"]} for d in DONORS}}))

def write_report(model,data):
    lines=["# Semi-detached preview training report","",f"Native source: PHOEBE {PHOEBE_VERSION} `default_binary(semidetached=donor)` constraints",f"Baseline: `{BASELINE_COMMIT}`",f"Artifact SHA-256: `{model['training']['native_artifact_sha256']}`","",f"Each donor: {TRAIN_COUNT} train / {TUNE_COUNT} tune / {TEST_COUNT} untouched test physical systems; splits use independent seeds and never share phase samples.","", "Domain: inclination 65–90°, q 0.40–1.30, free-star Roche-fill fraction 0.25–0.82, T2/T1 0.76–1.14. Fixed P=1.8 d, M1=1.2 solar masses, T1=6300 K, Johnson:V, circular synchronous orbit, irradiation off.","",f"Native timing: median {np.median(data['seconds']):.3f} s, p95 {np.quantile(data['seconds'],.95):.3f} s per curve; {int(np.sum(data['triangles_used']==1500))} retries at 1,500 and {int(np.sum(data['triangles_used']==3000))} at 3,000 triangles."]
    for donor in DONORS:
        spec=model["donors"][donor]; lines += ["",f"## {donor.title()} donor","",f"Tune RMS used for model selection: {spec['tune_rms']:.6f}","","| Regime | N | pooled RMS | p95 curve RMS | p95 absolute | worst absolute |","| --- | ---: | ---: | ---: | ---: | ---: |"]
        for r in spec["test_metrics"]:lines.append(f"| {r['regime']} | {r['n']} | {r['rms']:.6f} | {r['curve_rms_p95']:.6f} | {r['abs_p95']:.6f} | {r['worst_abs']:.6f} |")
        lines += ["","Slider-response validation compares native and surrogate difference vectors; cosine measures shape/direction agreement rather than pointwise curve RMS.","","| Anchor | Parameter | native response RMS | difference RMS | cosine | relative norm error |","| ---: | --- | ---: | ---: | ---: | ---: |"]
        for r in spec["response_metrics"]:lines.append(f"| {r['anchor']} | {r['parameter']} | {r['native_response_rms']:.6f} | {r['difference_rms']:.6f} | {r['cosine']:.4f} | {r['relative_norm_error']:.4f} |")
    lines += ["","## Limits","","Display-only preview. Native PHOEBE is authoritative for fitting, statistics, and exports. Photometric q can remain degenerate, especially for grazing/partial eclipses; RV curves provide complementary constraints. No disks, streams, spots, eccentric semi-detached systems, irradiation preview, or joint photometry/RV inference is included."]
    REPORT.write_text("\n".join(lines)+"\n")

def main():
    p=argparse.ArgumentParser();p.add_argument("action",choices=("generate","train","all"));p.add_argument("--workers",type=int,default=4);a=p.parse_args()
    if a.action in ("generate","all"):generate(a.workers)
    if a.action in ("train","all"):train()
if __name__=="__main__":main()
