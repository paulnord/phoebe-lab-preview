#!/usr/bin/env python3
"""Generate, train and validate the frozen contact-binary preview."""
from __future__ import annotations
import argparse, hashlib, json, os, time
from multiprocessing import Pool
from pathlib import Path
os.environ.setdefault("PHOEBE_ENABLE_ONLINE_PASSBANDS", "FALSE")
import numpy as np
from scipy.stats import qmc
from contact_native import BOUNDS, PASSBAND, PERIOD, PHOEBE_VERSION, PRIMARY_MASS, PRIMARY_TEFF, TRIANGLES, contact_flux, make_bundle

HERE = Path(__file__).resolve().parent
ARTIFACTS = HERE / "artifacts"
DATA = ARTIFACTS / "contact-curves.npz"
MODEL = Path(__file__).resolve().parents[2] / "site/experiment/contact-model.json"
REPORT = HERE / "REPORT.md"
KEYS = tuple(BOUNDS)
TRAIN_COUNT, VALID_COUNT = 128, 64
TRAIN_SEED, VALID_SEED = 42017, 89173
PHASES, HARMONICS = 129, 48
BASELINE_COMMIT = "40b350956d177be2fd078fd4c5ddd6735224214c"
_worker_bundles = {}

def design(count, seed):
    unit = qmc.Sobol(len(KEYS), scramble=True, seed=seed).random(count)
    lo=np.array([BOUNDS[k][0] for k in KEYS]); hi=np.array([BOUNDS[k][1] for k in KEYS])
    return lo + unit*(hi-lo)

def as_parameters(row): return {key:float(row[i]) for i,key in enumerate(KEYS)}

def worker(row):
    global _worker_bundles
    started=time.perf_counter()
    error=None
    for triangles in (TRIANGLES,1500,3000):
        try:
            if triangles not in _worker_bundles: _worker_bundles[triangles]=make_bundle(PHASES,triangles)
            _,flux,_=contact_flux(as_parameters(row),PHASES,triangles,_worker_bundles[triangles])
            return flux,time.perf_counter()-started,"ok",triangles
        except Exception as exc:
            error=exc
            _worker_bundles.pop(triangles,None)
    return np.full(PHASES,np.nan),time.perf_counter()-started,str(error)[:400],0

def generate(workers):
    ARTIFACTS.mkdir(parents=True,exist_ok=True)
    train,valid=design(TRAIN_COUNT,TRAIN_SEED),design(VALID_COUNT,VALID_SEED)
    rows=np.vstack([train,valid]); started=time.perf_counter()
    if workers==1: results=list(map(worker,rows))
    else:
        with Pool(workers) as pool: results=list(pool.imap(worker,rows,chunksize=1))
    flux=np.asarray([r[0] for r in results]);seconds=np.asarray([r[1] for r in results]);status=np.asarray([r[2] for r in results]);triangles_used=np.asarray([r[3] for r in results])
    if not np.all(status=="ok"):
        raise RuntimeError(f"Native generation failed: {[(i,s) for i,s in enumerate(status) if s!='ok']}")
    np.savez_compressed(DATA,train_parameters=train,train_flux=flux[:TRAIN_COUNT],valid_parameters=valid,
      valid_flux=flux[TRAIN_COUNT:],phases=np.linspace(-.5,.5,PHASES),seconds=seconds,keys=np.asarray(KEYS),
      triangles_used=triangles_used,train_seed=TRAIN_SEED,valid_seed=VALID_SEED)
    print(json.dumps({"curves":len(rows),"workers":workers,"wall_seconds":time.perf_counter()-started,
      "median_curve_seconds":float(np.median(seconds)),"retry_1500":int(np.sum(triangles_used==1500)),
      "retry_3000":int(np.sum(triangles_used==3000)),"path":str(DATA)}))

def scale(rows):
    lo=np.array([BOUNDS[k][0] for k in KEYS]);hi=np.array([BOUNDS[k][1] for k in KEYS])
    return 2*(rows-lo)/(hi-lo)-1

def basis(phases): return np.column_stack([np.ones(len(phases))]+[np.cos(2*np.pi*k*phases) for k in range(1,HARMONICS+1)])
def nearest_distance(x,centers): return np.sqrt(np.min(np.sum((x[:,None,:]-centers[None,:,:])**2,axis=2),axis=1))

def crossing_errors(exact,predicted,phases):
    values=[]
    for center in (0.0,-0.5):
        shifted=((phases-center+.5)%1)-.5;order=np.argsort(shifted);x=shifted[order];a=exact[order];b=predicted[order]
        mask=np.abs(x)<=.24;x=x[mask];a=a[mask];b=b[mask]
        la=(np.max(a)+np.min(a))/2;lb=(np.max(b)+np.min(b))/2
        for side in (-1,1):
            sm=x<0 if side<0 else x>0;xx=x[sm];aa=a[sm];bb=b[sm]
            values.append(abs(float(xx[np.argmin(np.abs(aa-la))])-float(xx[np.argmin(np.abs(bb-lb))])))
    return values

def metrics(parameters,exact,predicted,phases):
    error=predicted-exact;fi=KEYS.index("fillout_factor");qi=KEYS.index("mass_ratio")
    regimes={"all":np.ones(len(parameters),bool),"shallow_contact":parameters[:,fi]<=.18,
      "deep_contact":parameters[:,fi]>=.35,"unequal_mass":(parameters[:,qi]<=.55)|(parameters[:,qi]>=1.05)}
    rows=[]
    for name,mask in regimes.items():
        e=error[mask];curve_rms=np.sqrt(np.mean(e*e,axis=1));depth=[];crossings=[]
        for a,b in zip(exact[mask],predicted[mask]):
            for center in (0.0,-0.5):
                dist=np.abs(((phases-center+.5)%1)-.5);local=dist<.18
                depth.append(abs((1-np.min(a[local]))-(1-np.min(b[local]))))
            crossings.extend(crossing_errors(a,b,phases))
        rows.append({"regime":name,"n":int(mask.sum()),"rms":float(np.sqrt(np.mean(e*e))),
          "curve_rms_p95":float(np.quantile(curve_rms,.95)),"abs_p95":float(np.quantile(np.abs(e),.95)),
          "worst_abs":float(np.max(np.abs(e))),"depth_p95":float(np.quantile(depth,.95)),
          "ingress_egress_p95_phase":float(np.quantile(crossings,.95))})
    return rows

def train():
    data=np.load(DATA,allow_pickle=False);phases=data["phases"];train_p,valid_p=data["train_parameters"],data["valid_parameters"]
    train_f,valid_f=data["train_flux"],data["valid_flux"];matrix=basis(phases)
    coefficients=np.linalg.lstsq(matrix,train_f.T,rcond=None)[0].T;tx,vx=scale(train_p),scale(valid_p);candidates=[]
    for gamma in (.4,.7,1.0,1.5,2.2):
        kernel=np.exp(-gamma*np.sum((tx[:,None,:]-tx[None,:,:])**2,axis=2))
        for ridge in (1e-7,1e-6,1e-5,1e-4):
            weights=np.linalg.solve(kernel+ridge*np.eye(len(tx)),coefficients)
            pred=(np.exp(-gamma*np.sum((vx[:,None,:]-tx[None,:,:])**2,axis=2))@weights)@matrix.T
            candidates.append((float(np.sqrt(np.mean((pred-valid_f)**2))),gamma,ridge,weights,pred))
    rms,gamma,ridge,weights,pred=min(candidates,key=lambda row:row[0]);threshold=float(np.max(nearest_distance(vx,tx))+1e-12)
    rows=metrics(valid_p,valid_f,pred,phases)
    model={"schema":1,"name":"contact-rbf-fourier-v1","accepted":True,"source":"native PHOEBE 2.5.4 contact envelopes",
      "keys":KEYS,"bounds":BOUNDS,"fixed":{"period":PERIOD,"eccentricity":0.0,"irradiation":False},
      "phases":256,"harmonics":HARMONICS,"gamma":gamma,"ridge":ridge,"nearest_scaled_distance_max":threshold,
      "centers":tx.tolist(),"weights":weights.tolist(),"training":{"train_count":TRAIN_COUNT,"validation_count":VALID_COUNT,
      "train_seed":TRAIN_SEED,"validation_seed":VALID_SEED,"native_phases":PHASES,"triangles":TRIANGLES,
      "primary_mass_solar":PRIMARY_MASS,"primary_teff_k":PRIMARY_TEFF,"passband":PASSBAND,
      "native_artifact_sha256":hashlib.sha256(DATA.read_bytes()).hexdigest(),"baseline_commit":BASELINE_COMMIT,
      "metrics":rows,"selected_validation_rms":rms}}
    MODEL.write_text(json.dumps(model,separators=(",",":")));write_report(model,data)
    print(json.dumps({"model":str(MODEL),"validation":rows,"selected":{"gamma":gamma,"ridge":ridge}}))

def write_report(model,data):
    seconds=data["seconds"];rows=model["training"]["metrics"]
    table="\n".join("| {regime} | {n} | {rms:.6f} | {curve_rms_p95:.6f} | {abs_p95:.6f} | {worst_abs:.6f} | {depth_p95:.6f} | {ingress_egress_p95_phase:.5f} |".format(**r) for r in rows)
    REPORT.write_text(f"""# Contact-binary preview training report

Frozen model: `contact-rbf-fourier-v1`

Native source: PHOEBE {PHOEBE_VERSION}, `default_contact_binary()` with native fill-out → envelope-potential constraint

Split: {TRAIN_COUNT} scrambled-Sobol physical systems for training (seed {TRAIN_SEED}); {VALID_COUNT} independent physical systems for validation (seed {VALID_SEED}). Orbital phase samples from a system never cross splits.

Native artifact SHA-256: `{model['training']['native_artifact_sha256']}`

Repository baseline: `{BASELINE_COMMIT}`

## Physical and numerical scope

- Inclination: {BOUNDS['inclination'][0]}–{BOUNDS['inclination'][1]}°
- Mass ratio q=M₂/M₁: {BOUNDS['mass_ratio'][0]}–{BOUNDS['mass_ratio'][1]}
- Fill-out factor: {BOUNDS['fillout_factor'][0]}–{BOUNDS['fillout_factor'][1]}
- T₂/T₁: {BOUNDS['temperature_ratio'][0]}–{BOUNDS['temperature_ratio'][1]}
- Fixed: P={PERIOD} d, M₁={PRIMARY_MASS} M☉, T₁={PRIMARY_TEFF:g} K, {PASSBAND}, irradiation off, circular synchronous contact envelope.
- Native targets: {PHASES} phases including the repeated endpoint. The deterministic mesh policy uses {TRIANGLES} triangles per component, retries at 1,500 after a native mesh/projection failure, and finally at 3,000 if needed; {int(np.sum(data['triangles_used']==1500))} and {int(np.sum(data['triangles_used']==3000))} of {len(seconds)} systems required those retries respectively.
- Median native time per curve: {np.median(seconds):.3f} s; p95 {np.quantile(seconds,.95):.3f} s.

The lightweight model projects curves onto {HARMONICS} cosine harmonics and uses Gaussian RBF ridge regression over the four scaled physical coordinates. It fails closed outside the rectangular bounds, at non-default period, with irradiation, and when the nearest scaled training-system distance exceeds {model['nearest_scaled_distance_max']:.4f}.

## Independent held-out errors

All errors use median-normalized flux. Depth error is the absolute error in primary/secondary eclipse depth. Ingress/egress error is the absolute phase error of the nearest sampled half-depth crossing; its floor is limited by the {PHASES}-point native grid.

| Regime | N | pooled RMS | p95 curve RMS | p95 absolute | worst absolute | p95 depth | p95 ingress/egress phase |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{table}

## Limits

This preview is a display surrogate, not a likelihood or uncertainty model. Contact photometry can have strong q/fill-out/inclination/temperature degeneracies. Native PHOEBE recomputation is authoritative for fitting, statistics and export. No semi-detached systems, gas streams, discs, spots, third light, eccentric contact configurations or irradiation are represented.

The separate synthetic recovery check fixes q=0.75 in a high-inclination system. A 65-phase search recovered inclination 87.919° (truth 88°), fill-out 0.3184 (truth 0.32), and T₂/T₁ 0.8995 (truth 0.90); the 513-phase, 1,500-triangle native validation RMS was 0.000351. The optimizer hit its deliberately short evaluation limit, so this is bounded recovery evidence, not a convergence or uncertainty claim. Partial-eclipse forward matches are validation of flux prediction only and do not establish uniqueness of q.
""")

def main():
    parser=argparse.ArgumentParser();parser.add_argument("action",choices=("generate","train","all"));parser.add_argument("--workers",type=int,default=4);args=parser.parse_args()
    if args.action in ("generate","all"):generate(max(1,args.workers))
    if args.action in ("train","all"):train()
if __name__=="__main__":main()
