import unittest
from test_model import model, np
from native_files import Workspace, records, construct


class AdvancedTests(unittest.TestCase):
    def test_native_settings_compute_and_roundtrip(self):
        w=Workspace()
        doc=w.act('new',{'template':'Detached'})
        p=next(row for row in w.act('catalog',{}) if row['name']=='teff' and 'primary@' in row['twig'])
        self.assertEqual(w.act('field',{'id':p['id']})['unit'],'K')
        w.act('set_field',dict(id=p['id'],value=7040))
        with self.assertRaises(ValueError):
            w.act('set_field',dict(id=p['id'],value=-20))
        w.act('add',dict(category='feature',kind='spot',component='primary'))
        w.act('add',dict(category='dataset',kind='rv'))
        w.act('add',dict(category='solver',kind='estimator.lc_periodogram'))
        w.act('compute',dict(compute=doc['computes'][0],edits={}))
        raw=w.act('save_bundle',{})
        b,_=construct(records(raw))
        self.assertEqual(b.get_value('teff@primary'),7040)
        self.assertEqual(len(b.features),1)
        self.assertEqual(len(b.solvers),1)
        self.assertGreaterEqual(len(w.act('series',dict(label=b.models[-1]))),3)

    def test_distribution_roundtrip_and_constraint_flip(self):
        w=Workspace()
        w.act('new',{'template':'Detached'})
        r=next(r for r in w.act('catalog',{}) if r['name']=='teff' and 'primary@' in r['twig'])
        w.act('distribution',dict(id=r['id'],family='Gaussian',a=6100,b=250,label='temp_prior'))
        w.act('add',dict(category='solver',kind='sampler.emcee'))
        w.act('open',dict(text=w.act('save_bundle',{})))
        self.assertIn('temp_prior',w.bundle.distributions)
        p=w.bundle.get_parameter('mass@primary@component')
        field=w.act('field',dict(id=p.uniqueid))
        self.assertFalse(field['editable'])
        target=next(t for t in field['flip'] if t.startswith('sma@binary'))
        w.act('flip',dict(id=p.uniqueid,target=target))
        self.assertTrue(w.act('field',dict(id=p.uniqueid))['editable'])

    def test_local_periodogram(self):
        w=Workspace()
        w.act('new',{'template':'Detached'})
        for name,values in [('times',np.linspace(0,8,161)),('fluxes',1+.1*np.cos(np.linspace(0,8,161)*2*np.pi))]:
            uid=w.bundle.get_parameter(qualifier=name,context='dataset').uniqueid
            w.act('set_field',dict(id=uid,value=values.tolist()))
        w.act('add',dict(category='solver',kind='estimator.lc_periodogram'))
        result=w.act('solve',dict(solver=w.bundle.solvers[0]))
        self.assertTrue(result['solutions'])
