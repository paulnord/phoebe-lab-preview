#!/usr/bin/env python3
"""Bounded, separate boundary retraining pilot for contact and semi-detached previews."""
from __future__ import annotations
import argparse, json, os, sys, time
from multiprocessing import Pool
from pathlib import Path
os.environ.setdefault("PHOEBE_ENABLE_ONLINE_PASSBANDS","FALSE")
import numpy as np
from scipy.stats import qmc

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"experiments/contact"),str(ROOT/"experiments/semi_detached")]
import contact_native, semi_native

OUT=ROOT/"experiments/boundary_pilot"; ART=OUT/"artifacts"; DATA=ART/"boundary-pilot.npz"
REPORT=OUT/"REPORT.md"; CANDIDATE=ART/"candidate-models.json"
PHASES=129; HARMONICS=48; MODES=("contact","semi_primary","semi_secondary")
TRAIN_EDGE=12; TEST_EDGE=8; SEEDS={"train":730241,"test":880301}; _bundles={}

def edge_design(bounds,count,seed,offset):
    keys=tuple(bounds);unit=qmc.Sobol(len(keys),scramble=True,seed=seed+offset).random(count)
    edge=.015 if offset<10 else .04
    for i in range(count):
        axis=i%len(keys);unit[i,axis]=edge if (i//len(keys))%2==0 else 1-edge
        if i%5==0:
            other=(axis+2)%len(keys);unit[i,other]=1-edge if unit[i,axis]<.5 else edge
    lo=np.array([bounds[k][0] for k in keys]);hi=np.array([bounds[k][1] for k in keys])
    return keys,lo+unit*(hi-lo)

def parameters(mode,keys,row):
    p={k:float(row[i]) for i,k in enumerate(keys)}
    if mode.startswith("semi_"):p["donor"]=mode.split("_",1)[1]
    return p

def worker(task):
    mode,keys,row=task;started=time.perf_counter();error=None
    for triangles in (800,1500,3000):
        try:
            key=(mode,triangles)
            if mode=="contact":
                bundle=_bundles.setdefault(key,contact_native.make_bundle(PHASES,triangles))
                _,flux,_=contact_native.contact_flux(parameters(mode,keys,row),PHASES,triangles,bundle)
            else:
                donor=mode.split("_",1)[1];bundle=_bundles.setdefault(key,semi_native.make_bundle(donor,PHASES,triangles))
                _,flux,_=semi_native.semi_flux(parameters(mode,keys,row),PHASES,triangles,bundle)
            return flux,time.perf_counter()-started,"ok"
        except Exception as exc:error=exc;_bundles.pop(key,None)
    return np.full(PHASES,np.nan),time.perf_counter()-started,str(error)[:300]

def generate(workers):
    ART.mkdir(parents=True,exist_ok=True);arrays={};tasks=[];slices={};start=0
    for mi,mode in enumerate(MODES):
        bounds=contact_native.BOUNDS if mode=="contact" else semi_native.BOUNDS
        for split,count,off in (("train",TRAIN_EDGE,mi),("test",TEST_EDGE,20+mi)):
            keys,rows=edge_design(bounds,count,SEEDS[split],off);arrays[f"{mode}_{split}_parameters"]=rows
            tasks += [(mode,keys,row) for row in rows];slices[(mode,split)]=slice(start,start+count);start+=count
    began=time.perf_counter()
    with Pool(max(1,workers)) as pool:results=list(pool.imap(worker,tasks,chunksize=1))
    flux=np.asarray([r[0] for r in results]);seconds=np.asarray([r[1] for r in results]);status=np.asarray([r[2] for r in results])
    if not np.all(status=="ok"):raise RuntimeError([(i,s) for i,s in enumerate(status) if s!="ok"])
    for mode in MODES:
        for split in ("train","test"):arrays[f"{mode}_{split}_flux"]=flux[slices[(mode,split)]]
    summary={"systems":len(tasks),"workers":workers,"wall_seconds":time.perf_counter()-began,
             "median_native_seconds":float(np.median(seconds)),"p95_native_seconds":float(np.quantile(seconds,.95)),"path":str(DATA)}
    arrays.update(phases=np.linspace(-.5,.5,PHASES),seconds=seconds,
                  workers=workers,wall_seconds=summary["wall_seconds"])
    np.savez_compressed(DATA,**arrays)
    print(json.dumps(summary),flush=True);return summary

def basis(phases):return np.column_stack([np.ones(len(phases))]+[np.cos(2*np.pi*k*phases) for k in range(1,HARMONICS+1)])
def scale(rows,bounds,keys):
    lo=np.array([bounds[k][0] for k in keys]);hi=np.array([bounds[k][1] for k in keys]);return 2*(rows-lo)/(hi-lo)-1
def kernel(x,c,g):return np.exp(-g*np.sum((x[:,None,:]-c[None,:,:])**2,axis=2))
def predict(spec,rows,bounds,keys,matrix):
    curves=(kernel(scale(rows,bounds,keys),np.asarray(spec["centers"]),spec["gamma"])@np.asarray(spec["weights"]))@matrix.T
    return curves/np.median(curves,axis=1)[:,None]
def fit(train_x,train_y,tune_x,tune_y,bounds,keys,matrix):
    centers=scale(train_x,bounds,keys);coeff=np.linalg.lstsq(matrix,train_y.T,rcond=None)[0].T;best=None
    for gamma in (.25,.4,.65,1.0):
        k=kernel(centers,centers,gamma)
        for ridge in (1e-7,1e-6,1e-5,1e-4):
            weights=np.linalg.solve(k+ridge*np.eye(len(centers)),coeff);spec={"gamma":gamma,"ridge":ridge,"centers":centers.tolist(),"weights":weights.tolist()}
            error=predict(spec,tune_x,bounds,keys,matrix)-tune_y;rms=float(np.sqrt(np.mean(error*error)))
            if best is None or rms<best[0]:best=(rms,spec)
    return best
def metrics(exact,pred):
    error=pred-exact;curve=np.sqrt(np.mean(error*error,axis=1));depth=np.abs(np.min(pred,axis=1)-np.min(exact,axis=1));ingress=[]
    for truth,delta in zip(exact,error):
        gradient=np.abs(np.gradient(truth));mask=gradient>=np.quantile(gradient,.8);ingress.append(np.sqrt(np.mean(delta[mask]**2)))
    return {"rms":float(np.sqrt(np.mean(error*error))),"curve_rms_p95":float(np.quantile(curve,.95)),
            "worst_abs":float(np.max(np.abs(error))),"eclipse_depth_error_p95":float(np.quantile(depth,.95)),
            "ingress_egress_rms_p95":float(np.quantile(ingress,.95))}
def paired_q_responses(parameters,exact,current_pred,candidate_pred,meta):
    rows=[]
    for anchor,key_index,base_index,probe_index in meta:
        if key_index!=1 or not (parameters[base_index,1]<=.50 or parameters[base_index,1]>=1.15):continue
        native=exact[probe_index]-exact[base_index]
        row={"anchor":int(anchor),"q":float(parameters[base_index,1])}
        for name,pred in (("current",current_pred),("candidate",candidate_pred)):
            response=pred[probe_index]-pred[base_index];nn=np.linalg.norm(native);rn=np.linalg.norm(response)
            row[name]={"difference_rms":float(np.sqrt(np.mean((response-native)**2))),
                       "cosine":float(np.dot(native,response)/max(nn*rn,1e-15)),
                       "relative_norm_error":float(abs(rn-nn)/max(nn,1e-15))}
        rows.append(row)
    return rows

def train(summary):
    pilot=np.load(DATA);matrix=basis(pilot["phases"]);current_contact=json.loads((ROOT/"site/experiment/contact-model.json").read_text());current_semi=json.loads((ROOT/"site/experiment/semi-model.json").read_text())
    old_contact=np.load(ROOT/"experiments/contact/artifacts/contact-curves-v2.npz");old_semi=np.load(ROOT/"experiments/semi_detached/artifacts/semi-curves.npz")
    candidates={};comparisons={}
    for mode in MODES:
        if mode=="contact":
            keys=tuple(contact_native.BOUNDS);bounds=contact_native.BOUNDS;old=old_contact;current=current_contact
            train_x,train_y,tune_x,tune_y,test_x,test_y=[old[k] for k in ("train_parameters","train_flux","tune_parameters","tune_flux","test_parameters","test_flux")]
        else:
            donor=mode.split("_",1)[1];keys=tuple(semi_native.BOUNDS);bounds=semi_native.BOUNDS;old=old_semi;current=current_semi["donors"][donor]
            train_x,train_y,tune_x,tune_y,test_x,test_y=[old[f"{donor}_{k}"] for k in ("train_parameters","train_flux","tune_parameters","tune_flux","test_parameters","test_flux")]
        edge_x=pilot[f"{mode}_train_parameters"];edge_y=pilot[f"{mode}_train_flux"]
        tune_rms,candidate=fit(np.vstack([train_x,edge_x]),np.vstack([train_y,edge_y]),tune_x,tune_y,bounds,keys,matrix);candidate["tune_rms"]=tune_rms
        edge_test_x=pilot[f"{mode}_test_parameters"];edge_test_y=pilot[f"{mode}_test_flux"]
        comparisons[mode]={
            "common_holdout":{"current":metrics(test_y,predict(current,test_x,bounds,keys,matrix)),"candidate":metrics(test_y,predict(candidate,test_x,bounds,keys,matrix))},
            "edge_holdout":{"current":metrics(edge_test_y,predict(current,edge_test_x,bounds,keys,matrix)),"candidate":metrics(edge_test_y,predict(candidate,edge_test_x,bounds,keys,matrix))},
        }
        if mode.startswith("semi_"):
            donor=mode.split("_",1)[1];sweep_x=old[f"{donor}_sweep_parameters"];sweep_y=old[f"{donor}_sweep_flux"]
            comparisons[mode]["paired_edge_q_response"]=paired_q_responses(sweep_x,sweep_y,
                predict(current,sweep_x,bounds,keys,matrix),predict(candidate,sweep_x,bounds,keys,matrix),old["sweep_meta"])
        candidates[mode]=candidate
    payload={"accepted":False,"purpose":"boundary retraining candidate only","training":{"edge_train_per_mode":TRAIN_EDGE,"edge_test_per_mode":TEST_EDGE,"seeds":SEEDS,**summary},"comparisons":comparisons,"models":candidates}
    CANDIDATE.write_text(json.dumps(payload,separators=(",",":")))
    lines=["# Boundary preview retraining pilot","",f"Generated {summary['systems']} new native PHOEBE systems with {summary['workers']} workers in {summary['wall_seconds']:.1f} s (median {summary['median_native_seconds']:.2f} s/curve, p95 {summary['p95_native_seconds']:.2f} s/curve).",f"Each of contact, primary-donor semi-detached, and secondary-donor semi-detached received {TRAIN_EDGE} boundary-focused training systems and {TEST_EDGE} separately seeded edge holdouts.","","The candidate is **not accepted** and the production preview models are unchanged. Current and candidate models use the same untouched original in-domain test systems; edge holdouts are new and absent from both fits except that the candidate sees a separate edge-training split.","","| Mode | Holdout | Model | RMS | p95 curve RMS | worst abs | p95 depth error | p95 ingress/egress RMS |","|---|---|---|---:|---:|---:|---:|---:|"]
    for mode,sets in comparisons.items():
        for holdout,models in sets.items():
            if holdout=="paired_edge_q_response":continue
            for name,m in models.items():lines.append(f"| {mode} | {holdout} | {name} | {m['rms']:.6f} | {m['curve_rms_p95']:.6f} | {m['worst_abs']:.6f} | {m['eclipse_depth_error_p95']:.6f} | {m['ingress_egress_rms_p95']:.6f} |")
    lines += ["","## Paired mass-ratio responses already in the original sweep","","These comparisons use the already-sampled native slider pairs near q edges; no new response sweep was generated. Donors remain separate.","","| Donor | anchor q | model | difference RMS | cosine | relative norm error |","|---|---:|---|---:|---:|---:|"]
    for mode in ("semi_primary","semi_secondary"):
        for row in comparisons[mode]["paired_edge_q_response"]:
            for name,m in (("current",row["current"]),("candidate",row["candidate"])):
                lines.append(f"| {mode.removeprefix('semi_')} | {row['q']:.3f} | {name} | {m['difference_rms']:.6f} | {m['cosine']:.4f} | {m['relative_norm_error']:.4f} |")
    lines += ["","Native PHOEBE remains authoritative for fitting, statistics, and export. Candidate promotion requires reviewing these common and edge holdouts; this pilot never changes fit bounds."]
    REPORT.write_text("\n".join(lines)+"\n");print(json.dumps({"candidate":str(CANDIDATE),"report":str(REPORT),"comparisons":comparisons}))

def main():
    parser=argparse.ArgumentParser();parser.add_argument("action",choices=("generate","train","all"));parser.add_argument("--workers",type=int,default=4);args=parser.parse_args()
    if args.action in ("generate","all"):summary=generate(args.workers)
    else:
        saved=np.load(DATA);seconds=saved["seconds"]
        summary={"systems":3*(TRAIN_EDGE+TEST_EDGE),"workers":int(saved["workers"]),"wall_seconds":float(saved["wall_seconds"]),
                 "median_native_seconds":float(np.median(seconds)),"p95_native_seconds":float(np.quantile(seconds,.95)),"path":str(DATA)}
    if args.action in ("train","all"):train(summary)
if __name__=="__main__":main()
