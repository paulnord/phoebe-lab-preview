"""Build three exact reference examples and a measured Kepler excerpt for the lab."""
import argparse
import hashlib
import io
import json
from pathlib import Path
from urllib.request import urlopen
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
CATALOG='https://keplerebs.villanova.edu/data/?k=4544587.00&cadence=lc&data=data'
DIGEST='8562208590e0365faa45c41f9818b2a47d9bc52f547b86fddbcb7cf0461854d0'
CASES=[
    ('grazing','Grazing eclipses','The stars overlap only at their limbs.','wide','10135',.001),
    ('deep-primary','Deep primary eclipse','Two similarly sized stars have very different surface brightness.','wide','10147',.002),
    ('eccentric','Eccentric eclipse pair','The secondary eclipse falls away from phase 0.5.','eight','04466',.002),
]


def write(name,data):
    (ROOT/'site/examples'/(name+'.json')).write_text(json.dumps(data,separators=(',',':'),allow_nan=False)+'\n')


def generate(archives,kepler):
    for idx,(key,name,note,study,record,sigma) in enumerate(CASES):
        src=archives/f'phoebe-{study}-results-20261118'/'curves'/(record+'.json')
        raw=src.read_bytes()
        r=json.loads(raw)
        assert r['status']=='ok' and r['phases']==512 and r['triangles']==1500 and r['phoebe']=='2.5.4'
        seed=7811+idx
        rng=np.random.default_rng(seed)
        bins=np.sort(rng.choice(512,240,replace=False))
        flux=np.asarray(r['flux'])[bins]+rng.normal(0,sigma,len(bins))
        write(key,dict(name=name,synthetic=True,x_kind='phase',y_kind='flux',description=note,
                       x=(bins/512-.5).tolist(),y=flux.round(9).tolist(),sigma=[sigma]*len(bins),truth=r['parameters'],
                       provenance=dict(study=study,record=record,sha256=hashlib.sha256(raw).hexdigest(),
                                       phoebe=r['phoebe'],settings=r['settings'],phases=512,seed=seed)))
    raw=kepler.read_bytes() if kepler else urlopen(CATALOG,timeout=30).read()
    if hashlib.sha256(raw).hexdigest()!=DIGEST:raise ValueError('Catalog changed; verify the epoch and file format.')
    table=np.genfromtxt(io.BytesIO(raw),names=True)
    clean=np.isfinite(table['phase']) & np.isfinite(table['dtr_flux']) & (table['dtr_flux']>0) & (table['dtr_err']>0)
    subset=table[clean][:432]
    folded = dict(name='Kepler · KIC 4544587',synthetic=False,x_kind='phase',y_kind='flux',
          description='Kepler photometry. The Johnson V overlay uses approximate starting parameters.',
          x=subset['phase'].tolist(),y=subset['dtr_flux'].tolist(),sigma=subset['dtr_err'].tolist(),
          starting_parameters=dict(inclination=87.9,radius_primary=.168,radius_secondary=.146,temperature_ratio=.90,
                                   mass_ratio=.81,period=2.19,eccentricity=.275,omega=329),
          provenance=dict(catalog='Kepler Eclipsing Binary Catalog, third revision',url=CATALOG,sha256=DIGEST,
                          selection='First 432 finite detrended measurements with positive flux and errors, in source order.',
                          columns=['phase','dtr_flux','dtr_err'],catalog_period_days=2.1890973,epoch_bjd_minus_2400000=54954.135787,
                          time_range_bjd_minus_2400000=[float(subset['bjd'][0]),float(subset['bjd'][-1])],
                          starting_model='Hambleton et al. 2013, Table 6, rounded to slider steps. Lab primary temperature and mass use lab defaults.',
                          paper='https://doi.org/10.1093/mnras/stt886'))
    write('kepler-4544587', folded)
    period = folded['provenance']['catalog_period_days']
    epoch = folded['provenance']['epoch_bjd_minus_2400000']
    valid = table[clean & np.isfinite(table['bjd']) & np.isfinite(table['dtr_err'])]
    window = valid[valid['bjd'] < valid['bjd'].min() + 28]
    times = window['bjd']
    phase_error = ((times - epoch) / period - window['phase'] + .5) % 1 - .5
    assert np.max(np.abs(phase_error)) < 2e-7
    write('kepler-4544587-time', dict(folded, name='Kepler · KIC 4544587 (unfolded)', x_kind='time',
        description='28 days of long-cadence observations. Change the period to refold the eclipses.',
        x=times.tolist(), y=window['dtr_flux'].tolist(), sigma=window['dtr_err'].tolist(),
        epoch=epoch, period=period, time_system='BJD − 2400000',
        starting_parameters=dict(folded['starting_parameters'], epoch=epoch, period=period),
        provenance=dict(folded['provenance'], columns=['bjd','dtr_flux','dtr_err'],
                        selection='First 28 days of finite, positive detrended long-cadence photometry.',
                        time_range_bjd_minus_2400000=[float(times.min()), float(times.max())],
                        max_catalog_phase_difference=float(np.max(np.abs(phase_error))))))



if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('archives',type=Path)
    p.add_argument('--kepler-file',type=Path)
    a=p.parse_args()
    generate(a.archives,a.kepler_file)
