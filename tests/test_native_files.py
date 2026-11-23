import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'site/engine'))
from native_files import Workspace,records,serialize
import model
import phoebe


class NativeFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        b=phoebe.default_binary()
        b.add_dataset('lc',dataset='survey_v',times=[0.,.2,.4,.6],fluxes=[1,.9,1,1],sigmas=[.01]*4)
        b.set_value_all('distortion_method',value='sphere');b.set_value('irrad_method',value='none')
        b.set_value_all('ntriangles',value=400)
        cls.bundle=serialize(b)
        b.run_compute(model='desktop',progressbar=False)
        cls.file=serialize(b.get_model('desktop'))

    def test_attach_compute_export(self):
        w=Workspace()
        w.act('open',{'text':self.bundle})
        self.assertEqual(w.act('attach',{'text':self.file})['selected'],'desktop')
        new=w.act('compute',{'compute':'phoebe01','orbit':'binary','edits':{'incl':86.}})
        self.assertEqual(new['models'],['desktop',new['selected']])
        reopened=phoebe.open(json.loads(w.act('save_bundle',{})))
        self.assertEqual(reopened.get_value('incl@binary@component',unit='deg'),86.)
        np.testing.assert_array_equal(reopened.get_value('fluxes',dataset='survey_v',context='dataset'),[1,.9,1,1])
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/'result.model'
            file.write_text(w.act('save_model',{'label':new['selected']}))
            fresh=phoebe.open(json.loads(self.bundle))
            fresh.import_model(str(file),model='reloaded')
            np.testing.assert_allclose(fresh.get_value('fluxes',model='reloaded'),w.series(new['selected'])[0]['values'])
        w.act('open',{'text':self.file})
        self.assertEqual(w.series('desktop')[0]['times'],[0,.2,.4,.6])
        with self.assertRaises(ValueError):w.act('open',{'text':'{}'})
        self.assertEqual(w.metadata()['models'],['desktop'])

    def test_lab_epoch_and_exact_flux(self):
        w=Workspace()
        p=dict(model.DEFAULTS,epoch=12.,period=2.,eccentricity=.12)
        data=dict(name='photometry',x_kind='time',y_kind='magnitude',x=np.linspace(12.,13.4,8).tolist(),y=[11.2,11.,11.,11.]*2,sigma=[.01]*8)
        w.act('lab',dict(parameters=p,quality='preview',dataset=data))
        b=phoebe.open(json.loads(w.act('save_bundle',{})))
        np.testing.assert_allclose(b.get_value('times',context='dataset',dataset='observed_lc'),data['x'])
        self.assertEqual(b.get_value('t0_supconj@binary@component'),12.)
        series=w.series('ui_model')[0]
        self.assertEqual(len(series['times']),81)
        np.testing.assert_allclose((np.array(series['times'])-12)/2,np.linspace(-.5,.5,81),atol=1e-10)
        fitted=model.compute(dict(parameters=p,quality='preview',dataset=data))
        y=np.array(series['values'])
        np.testing.assert_allclose(y/np.median(y),np.asarray(fitted['model'])/np.median(fitted['model']),atol=1e-7)

    def test_unsupported_inputs(self):
        for text in ('phoebe legacy', '{}', '[{"Class":"JobParameter"}]'):
            with self.assertRaises(ValueError):records(text)

    def test_contact_lab_bundle_uses_contact_hierarchy(self):
        w=Workspace()
        p=dict(model.DEFAULTS,contact=True,fillout_factor=.25,mass_ratio=.75,
               inclination=84.5,eccentricity=0.,distortion=False,irradiation=False)
        phases=np.linspace(-.5,.5,9)
        data=dict(name='contact photometry',x_kind='phase',y_kind='flux',
                  x=phases.tolist(),y=np.ones(len(phases)).tolist(),sigma=None)
        w.act('lab',dict(parameters=p,quality='preview',dataset=data,phases=phases.tolist()))
        b=phoebe.open(json.loads(w.act('save_bundle',{})))
        self.assertIn('contact_envelope',b.components)
        self.assertEqual(b.get_value('fillout_factor@contact_envelope@component'),.25)
        self.assertEqual(len(w.series('ui_model')[0]['times']),9)

    def test_semi_detached_lab_bundle_preserves_donor_constraint(self):
        for donor in ('primary','secondary'):
            w=Workspace()
            p=dict(model.DEFAULTS,contact=False,semidetached=True,donor=donor,
                   mass_ratio=.75,inclination=84.5,eccentricity=0.,distortion=False,irradiation=False)
            phases=np.linspace(-.5,.5,9)
            data=dict(name='semi photometry',x_kind='phase',y_kind='flux',x=phases.tolist(),y=np.ones(9).tolist(),sigma=None)
            w.act('lab',dict(parameters=p,quality='preview',dataset=data,phases=phases.tolist()))
            b=phoebe.open(json.loads(w.act('save_bundle',{})))
            constrained=b.get_parameter(qualifier='requiv',component=donor,context='constraint')
            self.assertIn('requiv_max',str(constrained))
            self.assertEqual(len(w.series('ui_model')[0]['times']),9)
