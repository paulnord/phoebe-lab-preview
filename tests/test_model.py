"""Checks for data-format mistakes that would invalidate a fit.

Run in an environment with native PHOEBE: python -m unittest discover -s tests
The end-to-end browser tests separately exercise the WebAssembly build.
"""
import os
os.environ.update(PHOEBE_ENABLE_PLOTTING="FALSE", PHOEBE_ENABLE_ONLINE_PASSBANDS="FALSE",
                  PHOEBE_MULTIPROC_NPROCS="0", PHOEBE_ENABLE_MPI="FALSE")
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "site/engine"))
import model

class ObservationTests(unittest.TestCase):
    def test_magnitude_and_flux_are_equivalent(self):
        phase = np.linspace(-.45, .45, 15)
        magnitude = 11 + .15 * np.cos(2 * np.pi * phase)
        mag_sigma = np.full(15, .004)
        flux = 10 ** (-.4 * (magnitude - np.median(magnitude)))
        flux_sigma = .4 * np.log(10) * flux * mag_sigma
        mag = model.observations(dict(x=phase, y=magnitude, sigma=mag_sigma, y_kind="magnitude"), model.DEFAULTS)
        linear = model.observations(dict(x=phase, y=flux, sigma=flux_sigma, y_kind="flux"), model.DEFAULTS)
        for a, b in zip(mag, linear):
            np.testing.assert_allclose(a, b, atol=1e-13)

    def test_time_folding_uses_epoch_and_period(self):
        phase = np.linspace(-.45, .45, 15)
        p = dict(model.DEFAULTS, period=2.3, epoch=2459001.2)
        actual, _, _ = model.observations(dict(x=p["epoch"] + phase*p["period"], y=np.ones(15), x_kind="time"), p)
        np.testing.assert_allclose(actual, phase, atol=1e-9)

    def test_invalid_uncertainties_and_boolean_parameters(self):
        with self.assertRaises(ValueError):
            model.observations(dict(x=list(range(8)), y=[1]*8, sigma=[0]*8), model.DEFAULTS)
        with self.assertRaises(ValueError):
            model.parameters(dict(distortion="false"))

    def test_invalid_cached_semi_curve_rebuilds_once(self):
        class FakeBundle:
            def __init__(self, flux):self.flux=np.asarray(flux,dtype=float)
            def flip_constraint(self,*args,**kwargs):pass
            def add_dataset(self,*args,**kwargs):pass
            def set_value(self,*args,**kwargs):pass
            def set_value_all(self,*args,**kwargs):pass
            def run_compute(self,*args,**kwargs):pass
            def get_value(self,name,*args,**kwargs):
                return 1.0 if name=="sma" else self.flux
        phases=np.linspace(-.5,.5,5)
        bundles=[FakeBundle([1.,np.nan,1.,1.,1.]),FakeBundle([1.,.8,.7,.8,1.])]
        old=dict(model._semi_bundles)
        model._semi_bundles.clear()
        try:
            with patch.object(model.phoebe,"default_binary",side_effect=bundles) as build:
                actual_phases,flux=model._physical_flux(
                    dict(model.DEFAULTS,semidetached=True,donor="secondary",radius_primary=.318),
                    "preview",phases=phases)
            np.testing.assert_array_equal(actual_phases,phases)
            np.testing.assert_array_equal(flux,bundles[1].flux)
            self.assertEqual(build.call_count,2)
        finally:
            model._semi_bundles.clear();model._semi_bundles.update(old)

    def test_second_invalid_curve_reports_runtime_and_bad_phases(self):
        phases=np.linspace(-.5,.5,5)
        with patch.object(model,"runtime_diagnostic",return_value={
            "python":"3.12.0","phoebe":"2.5.4","numpy":"2.0.2","scipy":"1.15.3",
            "astropy":"7.1.0","matplotlib":"3.11.2","passband":"Johnson:V",
            "passband_sha256":"abc123","passband_bytes":14719680,
            "platform":"Linux-test","machine":"x86_64","libc":"glibc 2.35",
            "libphoebe_sha256":"lib123","ceclipse_sha256":"eclipse123",
        }):
            message=model._invalid_curve_diagnostic(phases,np.array([1.,np.nan,0.,.8,1.]))
        self.assertIn("invalid=2",message)
        self.assertIn("invalid phases=[-0.25, 0.0]",message)
        self.assertIn("PHOEBE 2.5.4",message)
        self.assertIn("Johnson:V abc123 (14719680 bytes)",message)
        self.assertIn("libphoebe=lib123",message)

    def test_blackbody_probe_is_finite_without_mutating_authoritative_bundle(self):
        phases=np.linspace(-.5,.5,5)
        p=dict(model.DEFAULTS,semidetached=True,donor="secondary",inclination=87.566,
               radius_primary=.318,temperature_ratio=4881/7262,mass_ratio=.4715,
               period=.8180837,epoch=2454588.167997,irradiation=False)
        old=dict(model._semi_bundles)
        model._semi_bundles.clear()
        try:
            _,flux=model._physical_flux(p,"preview",phases=phases)
            bundle=model._semi_bundles["secondary"]
            before=model._compute_option_diagnostic(bundle)
            probe=model._diagnostic_blackbody_probe(bundle,phases)
            after=model._compute_option_diagnostic(bundle)
            self.assertEqual(probe["settings"],"blackbody/manual-linear")
            self.assertEqual(probe["invalid"],0)
            self.assertEqual(probe["samples"],"5/5")
            self.assertTrue(np.all(np.isfinite(flux) & (flux>0)))
            self.assertEqual(before,after)
            self.assertEqual(before["atm_primary"],"ck2004")
            self.assertEqual(before["ld_primary"],"interp")
            self.assertEqual(before["irrad_method"],"none")
            self.assertEqual(before["triangles_primary"],800)
            message=model._invalid_curve_diagnostic(
                phases,np.full(5,np.nan),bundle=bundle,parameters_used=p,quality="preview")
            self.assertIn('"semidetached": true',message)
            self.assertIn('"donor": "secondary"',message)
            self.assertIn('"irradiation": false',message)
            self.assertIn('"irrad_method": "none"',message)
            self.assertIn('"atm_primary": "ck2004"',message)
            self.assertIn('"invalid": 0',message)  # diagnostic blackbody probe only
        finally:
            model._semi_bundles.clear();model._semi_bundles.update(old)

if __name__ == "__main__":
    unittest.main()
