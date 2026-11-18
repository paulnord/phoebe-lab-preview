"""Checks for data-format mistakes that would invalidate a fit.

Run in an environment with native PHOEBE: python -m unittest discover -s tests
The end-to-end browser tests separately exercise the WebAssembly build.
"""
import os
os.environ.update(PHOEBE_ENABLE_PLOTTING="FALSE", PHOEBE_ENABLE_ONLINE_PASSBANDS="FALSE",
                  PHOEBE_MULTIPROC_NPROCS="0", PHOEBE_ENABLE_MPI="FALSE")
import sys
import unittest
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

if __name__ == "__main__":
    unittest.main()
