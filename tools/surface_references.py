"""Compute the three surface-physics references for the unchanged lab starting binary."""
import inspect
import hashlib
import json
import os
from pathlib import Path
import sys
os.environ.update(PHOEBE_ENABLE_PLOTTING='FALSE',PHOEBE_ENABLE_ONLINE_PASSBANDS='FALSE',
                  PHOEBE_MULTIPROC_NPROCS='0',PHOEBE_ENABLE_MPI='FALSE')
import numpy as np
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'site/engine'))
import model

def generate():
    phases=np.linspace(-.5,.5,513)
    references=[]
    for tides,heating in ((True,False),(False,True),(True,True)):
        p=dict(model.DEFAULTS,distortion=tides,irradiation=heating)
        _,flux=model._raw_model(p,'preview',phases=phases,ntriangles=400)
        assert len(flux)==513 and np.isfinite(flux).all() and np.min(flux)>0
        references.append(dict(parameters=p,flux=flux.tolist()))
        print(f'Calculated tides={tides}, heating={heating}',flush=True)
    passband=Path(model.phoebe.list_installed_passbands(full_dict=True)['Johnson:V']['fname'])
    data=dict(physics_sha256=hashlib.sha256(inspect.getsource(model._physical_flux).encode()).hexdigest(),
              version=model.phoebe.__version__,triangles=400,passband='Johnson:V',
              passband_sha256=hashlib.sha256(passband.read_bytes()).hexdigest(),
              phases=phases.tolist(),normalization='sample median',references=references)
    (root/'site/engine/surface-references.json').write_text(json.dumps(data,separators=(',',':'),allow_nan=False)+'\n')

if __name__=='__main__':generate()
