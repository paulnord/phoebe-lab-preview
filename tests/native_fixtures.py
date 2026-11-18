"""Create desktop PHOEBE interchange fixtures or verify the browser's downloads."""
import argparse
from pathlib import Path
import numpy as np
import phoebe
from phoebe.parameters import ParameterSet


def generate(out):
    out.mkdir(exist_ok=True,parents=True)
    b=phoebe.default_binary()
    b.add_dataset('lc',times=[0.,.2,.4,.6],fluxes=[1,.9,1,1],sigmas=[.01]*4)
    b.set_value_all('distortion_method',value='sphere')
    b.set_value('irrad_method',value='none')
    b.set_value_all('ntriangles',value=400)
    b.save(str(out/'desktop.phoebe'),compact=True)
    b.run_compute(model='desktop',progressbar=False)
    b.get_model(model='desktop').save(str(out/'desktop.model'),compact=True)


def verify(out):
    b=phoebe.open(str(out/'browser-desktop.phoebe'))
    assert b.get_value('incl@binary@component',unit='deg')==86
    assert {'desktop','lab_native'}<=set(b.models) and b.datasets==['lc01']
    np.testing.assert_allclose(b.get_value('fluxes@lc01@dataset'),[1,.9,1,1])
    param=dict(qualifier='fluxes',dataset='lc01',context='model')
    independent=phoebe.open(str(out/'desktop.phoebe'))
    independent.set_value('incl@binary@component',unit='deg',value=86)
    independent.run_compute(model='reference',progressbar=False)
    matching=b.get_value(**param,model='lab_native')
    np.testing.assert_allclose(matching,independent.get_value(**param,model='reference'),atol=1e-7,rtol=0)
    independent.import_model(str(out/'browser-desktop.model'),model='readback')
    np.testing.assert_array_equal(matching,independent.get_value(**param,model='readback'))
    b=phoebe.open(str(out/'browser-lab.phoebe'))
    assert b.get_value('ecc@binary@component')==.18 and b.get_value('q@binary@component')==.9
    assert len(b.get_value('fluxes',context='dataset',dataset='observed_lc'))>=8
    ps=ParameterSet.open(str(out/'browser-lab.model'))
    np.testing.assert_array_equal(ps.get_value('fluxes'),b.get_value('fluxes',model='ui_model'))
    print('Browser files opened and imported by native PHOEBE',phoebe.__version__)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['generate','verify']);p.add_argument('out',type=Path)
    a=p.parse_args();(generate if a.action=='generate' else verify)(a.out)
