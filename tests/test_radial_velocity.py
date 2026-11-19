"""Compare the displayed center-of-mass velocities with PHOEBE's dynamical RV backend."""
import json
from pathlib import Path
import subprocess
from test_model import model, np, unittest


class VelocityTests(unittest.TestCase):
    def test_both_stars_across_one_orbit(self):
        root = Path(__file__).resolve().parents[1]
        eccentric = json.loads((root/'site/examples/eccentric.json').read_text())['truth']
        cases = [
            model.DEFAULTS,
            eccentric,
            dict(eccentric, inclination=0),
            dict(eccentric, inclination=65, omega=359, eccentricity=.35, period=100, mass_ratio=1.5),
        ]
        script = """
import {radialVelocities} from './site/assets/radial-velocity.mjs';
console.log(JSON.stringify(JSON.parse(process.argv[1]).map(radialVelocities)));
"""
        browser_curves = json.loads(subprocess.check_output(
            ['node','--input-type=module','-e',script,json.dumps(cases)], cwd=root, text=True))
        b = model.phoebe.default_binary()
        b.flip_constraint('mass@primary', solve_for='sma@binary')
        b.set_value('mass', component='primary', value=1.2)
        b.add_dataset('rv', dataset='test_rv')
        b.set_value_all('rv_method', value='dynamical')
        phases = np.linspace(-.5,.5,513)
        for p, curve in zip(cases, browser_curves, strict=True):
            with self.subTest(params=p):
                for name, key in [('period','period'),('incl','inclination'),('ecc','eccentricity'),
                                  ('q','mass_ratio'),('per0','omega')]:
                    b.set_value(name, component='binary', value=p[key])
                b.set_value('compute_times', dataset='test_rv', context='dataset', value=phases*p['period'])
                b.run_compute(model='comparison', overwrite=True, progressbar=False)
                np.testing.assert_array_equal(curve['phases'], phases)
                for star in ['primary','secondary']:
                    actual = b.get_value('rvs',model='comparison',component=star,dataset='test_rv')
                    np.testing.assert_allclose(curve[star], actual, rtol=0, atol=1e-5)
                self.assertAlmostEqual(curve['k1'], p['mass_ratio']*curve['k2'])
                if p['inclination'] == 0:
                    for star in ['primary','secondary']:
                        np.testing.assert_array_equal(curve[star], np.zeros_like(phases))
