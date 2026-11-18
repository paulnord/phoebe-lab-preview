"""Generate the labeled synthetic observations and native reference with PHOEBE.

Run using native PHOEBE 2.5.4, NumPy, SciPy and Astropy (not a browser build).
"""
import os
os.environ.update(PHOEBE_ENABLE_PLOTTING="FALSE", PHOEBE_ENABLE_ONLINE_PASSBANDS="FALSE",
                  PHOEBE_MULTIPROC_NPROCS="0", PHOEBE_ENABLE_MPI="FALSE")
from pathlib import Path
import sys
import json
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'site/engine'))
import model

truth = dict(model.DEFAULTS, inclination=86.7, radius_primary=.225,
             radius_secondary=.16, temperature_ratio=.79)
phases, flux = model._raw_model(truth, 'refined')
rng = np.random.default_rng(26017)
x = np.sort(rng.uniform(-.5, .5, 180))
sigma = np.full(len(x), .003)
y = np.interp(x, phases, flux) + rng.normal(0, sigma)
dataset = dict(name='Example binary', synthetic=True, x_kind='phase', y_kind='flux',
               x=x.tolist(), y=y.tolist(), sigma=sigma.tolist(), truth=truth,
               description='Synthetic PHOEBE observations with independent Gaussian noise.')
(ROOT / 'site/example.json').write_text(json.dumps(dataset, indent=2)+'\n')
reference = model.compute(dict(parameters=model.DEFAULTS, dataset=dataset, quality='preview'))
(ROOT / 'tests/native-reference.json').write_text(json.dumps(reference, indent=2)+'\n')
print('Generated PHOEBE example and native reference:', reference['seconds'], 'seconds')
