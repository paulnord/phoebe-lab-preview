import json
import subprocess
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]

def test_local_artifact_split_and_metrics():
    model=json.loads((ROOT/"site/experiment/literature-local-model.json").read_text())
    data=np.load(ROOT/"experiments/literature_local/artifacts/literature-local-curves.npz",allow_pickle=False)
    assert model["accepted"] is True and model["training"]["native_phases"]==129
    for mode in ("contact","semi_secondary"):
        assert data[f"{mode}_train_parameters"].shape==(96,5)
        assert data[f"{mode}_tune_parameters"].shape==(24,5)
        assert data[f"{mode}_test_parameters"].shape==(32,5)
        assert data[f"{mode}_preset_parameters"].shape==(1,5)
        assert model["modes"][mode]["test_metrics"]["pooled_rms"]<.002
        assert model["modes"][mode]["preset_metrics"]["pooled_rms"]<.001
    assert model["modes"]["contact"]["preset_metrics"]["max_abs"]<.002
    assert model["modes"]["semi_secondary"]["preset_metrics"]["max_abs"]<.005
    assert np.isclose(np.exp(data["contact_preset_parameters"][0,4]),.305371)
    assert np.isclose(np.exp(data["semi_secondary_preset_parameters"][0,4]),.8180837)

def test_browser_predictor_matches_frozen_coefficients_at_presets():
    model=json.loads((ROOT/"site/experiment/literature-local-model.json").read_text())
    data=np.load(ROOT/"experiments/literature_local/artifacts/literature-local-curves.npz",allow_pickle=False)
    phases=np.linspace(-.5,.5,257)
    matrix=np.column_stack([np.ones(len(phases))]+[np.cos(2*np.pi*k*phases) for k in range(1,49)])
    expected=[]
    for mode in ("contact","semi_secondary"):
        spec=model["modes"][mode];row=data[f"{mode}_preset_parameters"][0]
        bounds=model["bounds"][mode]
        lo=np.array([bounds["inclination"][0],bounds["mass_ratio"][0],bounds["shape"][0],bounds["temperature_ratio"][0],np.log(bounds["period"][0])])
        hi=np.array([bounds["inclination"][1],bounds["mass_ratio"][1],bounds["shape"][1],bounds["temperature_ratio"][1],np.log(bounds["period"][1])])
        x=2*(row-lo)/(hi-lo)-1;centers=np.asarray(spec["centers"])
        kernel=np.exp(-spec["gamma"]*np.sum((centers-x)**2,axis=1))
        curve=(kernel@np.asarray(spec["weights"]))@matrix.T;curve/=np.median(curve[:-1]);expected.append(curve)
    code="""import fs from'node:fs';import{makeLiteratureLocalPredictor}from'./site/experiment/literature-local-predict.mjs';const s=JSON.parse(fs.readFileSync('./site/experiment/literature-local-model.json'));const p=makeLiteratureLocalPredictor(s);console.log(JSON.stringify([p({contact:true,semidetached:false,donor:'primary',inclination:86,mass_ratio:.534,fillout_factor:.134,temperature_ratio:6400/6200,period:.305371,eccentricity:0,irradiation:false}).model,p({contact:false,semidetached:true,donor:'secondary',inclination:87.566,mass_ratio:.4715,radius_primary:.318,radius_secondary:.17,temperature_ratio:4881/7262,period:.8180837,eccentricity:0,irradiation:false}).model]));"""
    actual=json.loads(subprocess.check_output(["node","--input-type=module","-e",code],cwd=ROOT,text=True))
    np.testing.assert_allclose(actual,expected,rtol=3e-12,atol=3e-12)

def test_previous_period_curve_is_not_labeled_as_trained_preview():
    source=(ROOT/"site/assets/app.js").read_text()
    assert "if(dragView?.prior)return 'Previous-period PHOEBE curve · current period awaiting native calculation';" in source
