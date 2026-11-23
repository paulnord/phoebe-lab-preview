#!/usr/bin/env python3
"""Expand contact training and compare v2 with frozen v1 on a new test split."""
from __future__ import annotations
import argparse, hashlib, json, os, time
from multiprocessing import Pool
from pathlib import Path
os.environ.setdefault("PHOEBE_ENABLE_ONLINE_PASSBANDS", "FALSE")
import numpy as np
from scipy.stats import qmc
from contact_native import (BOUNDS, PASSBAND, PERIOD, PHOEBE_VERSION, PRIMARY_MASS,
                            PRIMARY_TEFF, TRIANGLES, contact_flux, make_bundle)

HERE=Path(__file__).resolve().parent; ARTIFACTS=HERE/"artifacts"
DATA=ARTIFACTS/"contact-curves-v2.npz"; OLD_MODEL=ARTIFACTS/"contact-model-v1.json"
MODEL=Path(__file__).resolve().parents[2]/"site/experiment/contact-model.json"; REPORT=HERE/"REPORT_V2.md"
KEYS=tuple(BOUNDS); TRAIN_COUNT,TUNE_COUNT,TEST_COUNT=384,96,128
SEEDS={"train":142017,"tune":189173,"test":231119}; PHASES,HARMONICS=129,48
BASELINE_COMMIT="b7ce074c8231cc8db9bc2e4016b667071daaa845"; _bundles={}

def design(count,seed):
    unit=qmc.Sobol(len(KEYS),scramble=True,seed=seed).random(count)
    for i in range(count//3):
        axis=i%len(KEYS); unit[i,axis]=.01 if (i//len(KEYS))%2==0 else .99
    lo=np.array([BOUNDS[k][0] for k in KEYS]);hi=np.array([BOUNDS[k][1] for k in KEYS]);return lo+unit*(hi-lo)

def sweep_design():
    anchors=np.array([[67.,.48,.12,.80],[88.,1.15,.48,1.08],[84.,.50,.38,.96],[74.,.95,.20,.88]])
    steps=np.array([1.,.04,.025,.025]);rows=[];meta=[]
    for ai,base in enumerate(anchors):
        rows.append(base);bi=len(rows)-1
        for ki,key in enumerate(KEYS):
            changed=base.copy();changed[ki]=np.clip(changed[ki]+steps[ki],*BOUNDS[key]);rows.append(changed);meta.append((ai,ki,bi,len(rows)-1))
    return np.asarray(rows),np.asarray(meta,int)

def as_parameters(row):return {key:float(row[i]) for i,key in enumerate(KEYS)}
def worker(row):
    started=time.perf_counter();error=None
    for triangles in (TRIANGLES,1500,3000):
        try:
            if triangles not in _bundles:_bundles[triangles]=make_bundle(PHASES,triangles)
            _,flux,_=contact_flux(as_parameters(row),PHASES,triangles,_bundles[triangles]);return flux,time.perf_counter()-started,"ok",triangles
        except Exception as exc:error=exc;_bundles.pop(triangles,None)
    return np.full(PHASES,np.nan),time.perf_counter()-started,str(error)[:400],0

def generate(workers):
    ARTIFACTS.mkdir(parents=True,exist_ok=True);splits={name:design(count,SEEDS[name]) for name,count in (("train",TRAIN_COUNT),("tune",TUNE_COUNT),("test",TEST_COUNT))};sweep,meta=sweep_design();rows=np.vstack([splits["train"],splits["tune"],splits["test"],sweep]);began=time.perf_counter()
    with Pool(max(1,workers)) as pool:results=list(pool.imap(worker,rows,chunksize=1))
    flux=np.asarray([r[0] for r in results]);seconds=np.asarray([r[1] for r in results]);status=np.asarray([r[2] for r in results]);triangles=np.asarray([r[3] for r in results])
    if not np.all(status=="ok"):raise RuntimeError(f"Native generation failed: {[(i,s) for i,s in enumerate(status) if s!='ok']}")
    a=TRAIN_COUNT;b=a+TUNE_COUNT;c=b+TEST_COUNT
    np.savez_compressed(DATA,train_parameters=splits["train"],train_flux=flux[:a],tune_parameters=splits["tune"],tune_flux=flux[a:b],test_parameters=splits["test"],test_flux=flux[b:c],sweep_parameters=sweep,sweep_flux=flux[c:],sweep_meta=meta,phases=np.linspace(-.5,.5,PHASES),seconds=seconds,triangles_used=triangles,keys=np.asarray(KEYS))
    print(json.dumps({"systems":len(rows),"workers":workers,"wall_seconds":time.perf_counter()-began,"median_curve_seconds":float(np.median(seconds)),"p95_curve_seconds":float(np.quantile(seconds,.95)),"retry_1500":int(np.sum(triangles==1500)),"retry_3000":int(np.sum(triangles==3000)),"path":str(DATA)}))

def scale(rows):
    lo=np.array([BOUNDS[k][0] for k in KEYS]);hi=np.array([BOUNDS[k][1] for k in KEYS]);return 2*(rows-lo)/(hi-lo)-1
def basis(phases):return np.column_stack([np.ones(len(phases))]+[np.cos(2*np.pi*k*phases) for k in range(1,HARMONICS+1)])
def kernel(x,c,g):return np.exp(-g*np.sum((x[:,None,:]-c[None,:,:])**2,axis=2))
def predict(spec,rows,matrix):
    curves=(kernel(scale(rows),np.asarray(spec["centers"]),spec["gamma"])@np.asarray(spec["weights"]))@matrix.T
    return curves/np.median(curves,axis=1)[:,None]
def metrics(parameters,exact,pred):
    e=pred-exact;inc=parameters[:,0];q=parameters[:,1];fill=parameters[:,2];regimes={"all":np.ones(len(parameters),bool),"grazing":inc<=72.,"shallow_contact":fill<=.16,"deep_contact":fill>=.42,"unequal_mass":(q<=.55)|(q>=1.08)};out=[]
    for name,mask in regimes.items():
        x=e[mask];cr=np.sqrt(np.mean(x*x,axis=1));out.append(dict(regime=name,n=int(mask.sum()),rms=float(np.sqrt(np.mean(x*x))),curve_rms_p95=float(np.quantile(cr,.95)),abs_p95=float(np.quantile(np.abs(x),.95)),worst_abs=float(np.max(np.abs(x)))))
    return out
def responses(spec,parameters,exact,matrix,meta):
    pred=predict(spec,parameters,matrix);out=[]
    for ai,ki,bi,pi in meta:
        n=exact[pi]-exact[bi];m=pred[pi]-pred[bi];nn=np.linalg.norm(n);mn=np.linalg.norm(m)
        out.append(dict(anchor=int(ai),parameter=KEYS[int(ki)],native_response_rms=float(np.sqrt(np.mean(n*n))),difference_rms=float(np.sqrt(np.mean((m-n)**2))),cosine=float(np.dot(n,m)/max(nn*mn,1e-15)),relative_norm_error=float(abs(mn-nn)/max(nn,1e-15))))
    return out
def old_spec(old):return {k:old[k] for k in ("gamma","centers","weights")}

def train():
    data=np.load(DATA,allow_pickle=False);matrix=basis(data["phases"]);tp=data["train_parameters"];tf=data["train_flux"];tune=data["tune_parameters"];tunef=data["tune_flux"];test=data["test_parameters"];testf=data["test_flux"];coeff=np.linalg.lstsq(matrix,tf.T,rcond=None)[0].T;centers=scale(tp);candidates=[]
    for gamma in (.2,.3,.4,.6,.9):
        k=kernel(centers,centers,gamma)
        for ridge in (1e-7,1e-6,1e-5,1e-4):
            weights=np.linalg.solve(k+ridge*np.eye(len(centers)),coeff);pred=(kernel(scale(tune),centers,gamma)@weights)@matrix.T;pred/=np.median(pred,axis=1)[:,None];candidates.append((float(np.sqrt(np.mean((pred-tunef)**2))),gamma,ridge,weights))
    tune_rms,gamma,ridge,weights=min(candidates,key=lambda x:x[0]);dist=np.sqrt(np.min(np.sum((scale(test)[:,None,:]-centers[None,:,:])**2,axis=2),axis=1));spec={"gamma":gamma,"ridge":ridge,"centers":centers.tolist(),"weights":weights.tolist(),"nearest_scaled_distance_max":float(np.max(dist)+1e-12)}
    new_metrics=metrics(test,testf,predict(spec,test,matrix));new_responses=responses(spec,data["sweep_parameters"],data["sweep_flux"],matrix,data["sweep_meta"])
    old=json.loads(OLD_MODEL.read_text());old_metrics=metrics(test,testf,predict(old_spec(old),test,matrix));old_responses=responses(old_spec(old),data["sweep_parameters"],data["sweep_flux"],matrix,data["sweep_meta"])
    model={"schema":2,"name":"contact-rbf-fourier-v2","accepted":True,"source":f"native PHOEBE {PHOEBE_VERSION} contact envelopes","keys":list(KEYS),"bounds":BOUNDS,"fixed":{"period":PERIOD,"eccentricity":0.,"irradiation":False},"phases":256,"harmonics":HARMONICS,**spec,"training":{"train_count":TRAIN_COUNT,"tune_count":TUNE_COUNT,"test_count":TEST_COUNT,"seeds":SEEDS,"native_phases":PHASES,"triangles":TRIANGLES,"primary_mass_solar":PRIMARY_MASS,"primary_teff_k":PRIMARY_TEFF,"passband":PASSBAND,"native_artifact_sha256":hashlib.sha256(DATA.read_bytes()).hexdigest(),"baseline_commit":BASELINE_COMMIT,"tune_rms":tune_rms,"test_metrics":new_metrics,"old_test_metrics":old_metrics,"response_metrics":new_responses,"old_response_metrics":old_responses}}
    MODEL.write_text(json.dumps(model,separators=(",",":")));write_report(model,data);print(json.dumps({"model":str(MODEL),"tune_rms":tune_rms,"new":new_metrics,"old":old_metrics}))

def write_report(model,data):
    t=model["training"];lines=["# Expanded contact preview training report","",f"Baseline: `{BASELINE_COMMIT}`",f"Artifact SHA-256: `{t['native_artifact_sha256']}`",f"Split: {TRAIN_COUNT} train / {TUNE_COUNT} tune / {TEST_COUNT} untouched test systems with independent seeds; boundary-focused systems are included independently in every split.","",f"Native timing: median {np.median(data['seconds']):.3f} s, p95 {np.quantile(data['seconds'],.95):.3f} s; {int(np.sum(data['triangles_used']==1500))} retries at 1,500 and {int(np.sum(data['triangles_used']==3000))} at 3,000 triangles.","","The frozen v1 and expanded v2 models are compared on the same newly generated test systems. Neither model saw this test split during fitting or hyperparameter selection.","","| Model / regime | N | pooled RMS | p95 curve RMS | p95 absolute | worst absolute |","| --- | ---: | ---: | ---: | ---: | ---: |"]
    for label,key in (("v1","old_test_metrics"),("v2","test_metrics")):
        for r in t[key]:lines.append(f"| {label} / {r['regime']} | {r['n']} | {r['rms']:.6f} | {r['curve_rms_p95']:.6f} | {r['abs_p95']:.6f} | {r['worst_abs']:.6f} |")
    lines += ["","## Slider-difference comparison","","Cosine compares the direction/shape of the native and surrogate flux-response vectors; relative norm error compares response amplitude. This is deliberately separate from pointwise curve RMS.","","| Model | Anchor | Parameter | native response RMS | difference RMS | cosine | relative norm error |","| --- | ---: | --- | ---: | ---: | ---: | ---: |"]
    for label,key in (("v1","old_response_metrics"),("v2","response_metrics")):
        for r in t[key]:lines.append(f"| {label} | {r['anchor']} | {r['parameter']} | {r['native_response_rms']:.6f} | {r['difference_rms']:.6f} | {r['cosine']:.4f} | {r['relative_norm_error']:.4f} |")
    lines += ["","## Limits","","Display-only preview in its fixed-physics domain. Native PHOEBE remains authoritative. Pointwise agreement or a photometric response match does not establish unique q; RV curves remain important complementary evidence."]
    REPORT.write_text("\n".join(lines)+"\n")

def main():
    p=argparse.ArgumentParser();p.add_argument("action",choices=("generate","train","all"));p.add_argument("--workers",type=int,default=4);a=p.parse_args()
    if a.action in ("generate","all"):generate(a.workers)
    if a.action in ("train","all"):train()
if __name__=="__main__":main()
