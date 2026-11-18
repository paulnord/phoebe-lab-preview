"""Test the exact phased curve on the same grid and mesh as a single PHOEBE call."""
from test_model import model, np, unittest


class ProgressiveTests(unittest.TestCase):
    def test_nested_grids_and_absolute_flux(self):
        payload = dict(parameters=dict(model.DEFAULTS, eccentricity=.18, omega=132, period=3.2),
                       dataset=dict(x=np.linspace(-.45,.45,11), y=np.linspace(.84,1.,11), x_kind='phase'))
        updates = list(model.progressive_curve(payload))
        self.assertEqual([len(u.get('result', u)['phases']) for u in updates],
                         [65, 129, 193, 257, 321, 385, 449, 513])
        previous = set()
        for update in updates:
            phases = update.get('result', update)['phases']
            self.assertEqual(sorted(set(phases)), phases)
            self.assertTrue(previous.issubset(phases))
            previous = set(phases)
            if len(phases) in (65, 129, 257, 513):
                np.testing.assert_array_equal(phases, np.linspace(-.5, .5, len(phases)))
        result = updates[-1]['result']
        phases, flux = model._raw_model(payload['parameters'], 'preview', phases=np.linspace(-.5, .5, 513))
        cmp = model._comparison(phases, flux, payload['dataset'], payload['parameters'])
        np.testing.assert_allclose(result['model'], flux * cmp['normalization'], atol=1e-10, rtol=0)
        np.testing.assert_allclose(result['comparison']['residual'], cmp['residual'], atol=1e-10, rtol=0)
        self.assertEqual(len({i for _, indices in model._phase_batches() for i in indices}), 513)
        self.assertEqual(sum(len(indices) for _, indices in model._phase_batches()), 513)

    def test_surface_batches_and_references(self):
        batches = [indices for _, indices in model._phase_batches(surface=True)]
        self.assertEqual(len(batches[0]), 5)
        self.assertLessEqual(max(map(len, batches)), 8)
        self.assertEqual(sorted(i for batch in batches for i in batch), list(range(513)))
        for tides, heating in ((True, False), (False, True), (True, True)):
            p = dict(model.DEFAULTS, distortion=tides, irradiation=heating)
            dataset = dict(x=np.linspace(-.4,.4,11), y=np.ones(11))
            result = next(model.progressive_curve(dict(parameters=p, dataset=dataset)))['result']
            self.assertEqual(result.get('source'), 'stored_exact')
            self.assertEqual(len(result['phases']), 513)

    def test_local_fit_uses_selected_mesh_and_fitted_degrees_of_freedom(self):
        from unittest.mock import patch
        best = dict(model.DEFAULTS, inclination=83.8)
        data = dict(x=np.linspace(-.4,.4,25), y=np.linspace(.85,1,25), sigma=[.01]*25)
        info = dict(parameters=['inclination'], objective_phases=81)
        with patch.object(model, '_fit_parameters', return_value=(best, info)):
            steps = list(model.progressive_fit(dict(parameters=model.DEFAULTS, dataset=data, quality='refined')))
        self.assertEqual(steps[0], dict(type='fit_parameters', parameters=best))
        final = steps[-1]['result']
        self.assertEqual(final['quality'], 'refined')
        self.assertEqual(final['fit'], info)
        grid, flux = model._raw_model(best, 'refined', phases=np.linspace(-.5,.5,513))
        reference = model._comparison(grid, flux, data, best, fitted_count=1)
        np.testing.assert_array_equal(final['phases'], grid)
        np.testing.assert_allclose(final['model'], flux * reference['normalization'], rtol=0, atol=1e-10)
        self.assertAlmostEqual(final['comparison']['reduced_chi2'], reference['reduced_chi2'], places=9)

    def test_surface_worker_protocol_for_all_widths_and_fit(self):
        from unittest.mock import patch
        self.addCleanup(setattr, model, '_last_complete', None)
        p = dict(model.DEFAULTS, inclination=83.7, distortion=True)
        data = dict(x=np.linspace(-.42,.42,20), y=np.ones(20), sigma=[.01]*20)
        payload = dict(parameters=p, dataset=data)
        def sample(values, quality, indices):
            return 2.8+.01*np.cos(np.asarray(indices)*np.pi/256)
        def finish(curve):
            model._last_complete = None  # Exercise each independent worker run from a cold geometry cache.
            message = next(curve)
            widths = []
            while message['type'] != 'result':
                response = None
                if message['type'] == 'work':
                    groups = message['groups']
                    widths.append(len(groups))
                    response = [model.worker_flux(dict(message, indices=group)) for group in groups]
                message = curve.send(response)
            return message['result'], widths
        with patch.object(model, '_phase_flux', side_effect=sample):
            serial, _ = finish(model.progressive_curve(payload))
            for count in range(2,9):
                parallel, widths = finish(model.progressive_curve(dict(payload, workers=count)))
                self.assertEqual(max(widths), count)
                self.assertEqual(parallel['model'], serial['model'])
                self.assertEqual(parallel['comparison'], serial['comparison'])
            info = dict(parameters=['inclination'])
            with patch.object(model, '_fit_parameters', return_value=(p, info)):
                fitted, widths = finish(model.progressive_fit(dict(payload, workers=4)))
                self.assertEqual(max(widths), 4)
                self.assertEqual(fitted['fit'], info)
                self.assertEqual(fitted['model'], serial['model'])

    def test_epoch_reuses_only_complete_geometry_and_recomputes_statistics(self):
        from unittest.mock import patch
        p = dict(model.DEFAULTS, inclination=84, epoch=2450000.)
        x = p['epoch'] + np.linspace(0.,10.,25)
        y = np.linspace(.85,1.,len(x))
        data = dict(x_kind='time', x=x, y=y, sigma=[.003]*len(x))
        grid = np.linspace(-.5,.5,513)
        flux = 1.-.3*np.exp(-(grid/.05)**2)
        with patch.object(model, '_last_complete', None), patch.object(model, '_phase_flux',
                side_effect=lambda values,quality,indices: flux[list(indices)]) as calculate:
            initial = list(model.progressive_curve(dict(parameters=p, dataset=data)))[-1]['result']
            calculate.reset_mock()
            shifted = dict(p, epoch=p['epoch']+.01)
            actual = list(model.progressive_curve(dict(parameters=shifted, dataset=data)))[0]['result']
            self.assertEqual(actual['source'], 'reused_geometry')
            calculate.assert_not_called()
            reference = model._comparison(grid, flux/np.median(flux), data, shifted)
            self.assertEqual(actual['comparison'], reference)
            self.assertNotEqual(initial['comparison']['rms'], actual['comparison']['rms'])
            next(model.progressive_curve(dict(parameters=shifted,dataset=data,quality='refined')))
            calculate.assert_called_once()
