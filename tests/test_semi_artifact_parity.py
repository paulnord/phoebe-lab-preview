import json, subprocess, sys
from pathlib import Path
import nbformat, numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"experiments/semi_detached"))
from semi_native import BOUNDS,KEYS  # noqa:E402
from train_semi import basis  # noqa:E402
MODEL=ROOT/"site/experiment/semi-model.json";DATA=ROOT/"experiments/semi_detached/artifacts/semi-curves.npz"
def scale(rows):
    lo=np.array([BOUNDS[k][0] for k in KEYS]);hi=np.array([BOUNDS[k][1] for k in KEYS]);return 2*(rows-lo)/(hi-lo)-1
def predict(spec,donor,row):
    m=spec["donors"][donor];x=scale(np.asarray([row]))[0];centers=np.asarray(m["centers"]);coeff=np.exp(-m["gamma"]*np.sum((centers-x)**2,axis=1))@np.asarray(m["weights"]);phase=np.linspace(-.5,.5,spec["phases"]+1);flux=np.cos(2*np.pi*np.outer(phase,np.arange(spec["harmonics"]+1)))@coeff;return flux/np.median(flux[:-1])
def test_coefficients_reproduce_for_both_donors():
    spec=json.loads(MODEL.read_text());data=np.load(DATA,allow_pickle=False);matrix=basis(data["phases"])
    for donor in ("primary","secondary"):
        m=spec["donors"][donor];coeff=np.linalg.lstsq(matrix,data[f"{donor}_train_flux"].T,rcond=None)[0].T;centers=np.asarray(m["centers"]);kernel=np.exp(-m["gamma"]*np.sum((centers[:,None,:]-centers[None,:,:])**2,axis=2));weights=np.linalg.solve(kernel+m["ridge"]*np.eye(len(centers)),coeff);np.testing.assert_allclose(weights,m["weights"],rtol=2e-12,atol=2e-12)
def test_javascript_python_and_validation_notebook_parity():
    spec=json.loads(MODEL.read_text());row=np.array([83.25,.73,.55,.91]);q=row[1]
    for donor in ("primary","secondary"):
        m=spec["donors"][donor];rl=np.interp(q,m["lobe_q"],m["lobe_fraction"]);p=dict(semidetached=True,contact=False,donor=donor,inclination=row[0],mass_ratio=q,radius_primary=.21,radius_secondary=.17,temperature_ratio=row[3],period=1.8,eccentricity=0.,irradiation=False);p["radius_secondary" if donor=="primary" else "radius_primary"]=row[2]*rl
        code=f"""import fs from 'node:fs';import{{makeSemiPredictor}}from'./site/experiment/semi-predict.mjs';const s=JSON.parse(fs.readFileSync('./site/experiment/semi-model.json'));console.log(JSON.stringify(makeSemiPredictor(s)({json.dumps(p)}).model));""";js=np.asarray(json.loads(subprocess.check_output(["node","--input-type=module","-e",code],cwd=ROOT,text=True)));np.testing.assert_allclose(js,predict(spec,donor,row),rtol=3e-12,atol=3e-12)
    nb=nbformat.read(ROOT/"notebooks/PHOEBE_Semi_Detached_Validation.ipynb",as_version=4);source=next(c.source for c in nb.cells if c.cell_type=="code" and c.source.startswith("SEMI_MODEL=json.loads"));assert json.loads(source.split("r'''",1)[1].rsplit("'''",1)[0])==spec
