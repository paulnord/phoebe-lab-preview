import importlib.util
import json
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / "experiments/published_validation"
DATA = VALIDATION / "data"


def load_analysis():
    spec = importlib.util.spec_from_file_location("published_validation", VALIDATION / "analyze.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_published_rv_results_and_separate_at_peg_series():
    analysis = load_analysis()
    v1128 = analysis.v1128_result(); bo = analysis.bo_result(); current, old = analysis.at_results()
    assert v1128["catalog_rows"] == 104 and v1128["recent_full_weight_pairs"] == 38
    assert v1128["q"] == pytest.approx(.5343321589)
    assert v1128["published_deep_epoch_spectroscopic_phase"] == pytest.approx(.5003404063)
    assert v1128["model_epoch_spectroscopic_phase"] == pytest.approx(.0003408967)
    assert v1128["workbench_fixed_mass_overlay"]["pooled_rms"] == pytest.approx(8.2076850)
    assert bo["q"] == pytest.approx(.3120756770)
    assert current["q"] == pytest.approx(.4828905108)
    assert old["q"] == pytest.approx(.4774389258)
    assert current["measurements"] == 18 and old["measurements"] == 38


def test_source_row_counts_and_app_velocity_import():
    assert len((DATA / "at_peg_johnson_cousins_v.csv").read_text().splitlines()) == 896
    assert len((DATA / "v1128_tau_ddo_all.csv").read_text().splitlines()) == 105
    script = """
import fs from 'node:fs';
import {parseVelocity} from './site/assets/radial-velocity.mjs';
const text=fs.readFileSync('./experiments/published_validation/data/v1128_tau_ddo_recent_app.csv','utf8');
const data=parseVelocity(text,{x_kind:'time'});
console.log(JSON.stringify(data));
"""
    imported = json.loads(subprocess.check_output(
        ["node", "--input-type=module", "-e", script], cwd=ROOT, text=True))
    assert imported["axis"] == "time" and len(imported["rows"]) == 38
    assert all(row[1] is not None and row[2] is not None and row[3] is None and row[4] is None
               for row in imported["rows"])
