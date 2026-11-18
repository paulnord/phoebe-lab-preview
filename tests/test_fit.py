"""Local-fit grid, selection and timestamp regression checks."""
from unittest.mock import patch

from test_model import model, np, unittest


class FitTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(setattr, model, '_last_complete', None)
        model._last_complete = None

    def test_all_eight_parameters_use_refined_grid_and_reuse_winning_curve(self):
        params = dict(model.DEFAULTS, eccentricity=.13, omega=72.)
        keys = [key for key in model.LIMITS if key != 'epoch']
        grid = np.linspace(-.5,.5,513)
        _, flux = model._raw_model(params, 'refined', phases=grid)
        phase = np.linspace(-.49,.49,90)
        data = dict(x=phase, y=np.interp(phase,grid,flux), x_kind='phase')
        with patch.object(model, '_physical_flux', wraps=model._physical_flux) as calculate:
            result = model.fit(dict(parameters=params,quality='refined',dataset=data,fit=keys,fit_phases=513))
        self.assertGreaterEqual(calculate.call_count, 9)
        self.assertEqual(calculate.call_count, result['fit']['evaluations'])
        for call in calculate.call_args_list:
            self.assertEqual(call.args[1], 'refined')
            np.testing.assert_array_equal(call.kwargs['phases'], grid)
        self.assertEqual(result['fit']['parameters'], keys)
        self.assertEqual(result['fit']['objective_triangles'], 1500)
        self.assertEqual(result['fit']['objective_phases'], 513)
        self.assertLess(result['comparison']['rms'], 1e-10)

    def test_period_fit_on_unsorted_times_with_unequal_errors(self):
        p = dict(model.DEFAULTS, epoch=2451000., period=1.8)
        times = p['epoch'] + np.random.default_rng(28).uniform(0,90,500)
        def geometry(params, quality, *, phases):
            return phases, 1-.3*np.exp(-((phases-.015)/.035)**2)-.1*np.exp(-((phases+.45)/.05)**2)
        grid = np.linspace(-.5,.5,513)
        phase = ((times-p['epoch'])/p['period']+.5)%1-.5
        y = np.interp(phase,grid,geometry(p,'preview',phases=grid)[1])
        data = dict(x=times,y=y,sigma=np.linspace(.001,.03,len(times)),x_kind='time')
        with patch.object(model, '_physical_flux', side_effect=geometry):
            result = model.fit(dict(parameters=dict(p, period=1.8007),dataset=data,fit=['period'],fit_phases=513))
        self.assertAlmostEqual(result['parameters']['period'], p['period'], places=8)
        self.assertLess(result['comparison']['rms'], 1e-8)

    def test_periastron_can_cross_zero(self):
        p = dict(model.DEFAULTS, eccentricity=.1, omega=359.)
        grid = np.linspace(-.5,.5,513)
        def geometry(params, quality, *, phases):
            return phases, 1+.1*np.cos(2*np.pi*phases+np.deg2rad(params['omega']))
        data = dict(x=grid[:-1], y=geometry(dict(p, omega=1.),'preview',phases=grid)[1][:-1])
        with patch.object(model, '_physical_flux', side_effect=geometry):
            result = model.fit(dict(parameters=p,dataset=data,fit=['omega'],fit_phases=513))
        self.assertAlmostEqual(result['parameters']['omega'], 1., places=2)

    def test_nested_search_grids_refine_only_missing_phases(self):
        grid = np.linspace(-.5, .5, 513)
        initial = dict(model.DEFAULTS, distortion=True, inclination=83.)
        def physical(params, quality, *, phases):
            depth = (params['inclination'] - 60.) / 100.
            return phases, 17. * (1. - depth * np.exp(-(phases/.04)**2))
        data = dict(x=grid, y=physical(dict(initial, inclination=85.), 'preview', phases=grid)[1])
        for count in (65, 129):
            with self.subTest(count=count), patch.object(model, '_physical_flux', side_effect=physical) as compute:
                model._phase_flux.cache_clear()
                self.addCleanup(model._phase_flux.cache_clear)
                # Provide the complete initial model in median-normalized units, like the app.
                initial_flux = physical(initial, 'preview', phases=grid)[1]
                values = tuple(sorted((k,v) for k,v in initial.items() if k != 'epoch'))
                model._last_complete = (('preview',values), grid, initial_flux/np.median(initial_flux))
                payload = dict(parameters=initial,dataset=data,fit=['inclination'])
                if count == 65:
                    payload['fit_phases'] = count  # Missing setting defaults to 129.
                stream = model.progressive_fit(payload)
                winner = next(stream)['parameters']
                self.assertNotEqual(initial['inclination'], winner['inclination'])
                for call in compute.call_args_list:
                    np.testing.assert_array_equal(call.kwargs['phases'], grid[::512//(count-1)])
                compute.reset_mock()
                updates = list(stream)
                self.assertEqual(len(updates[0]['phases']), count)
                final = updates[-1]['result']
                self.assertEqual(final['fit']['objective_phases'], count)
                missing = np.setdiff1d(grid, grid[::512//(count-1)])
                calculated = np.concatenate([c.kwargs['phases'] for c in compute.call_args_list])
                np.testing.assert_array_equal(np.sort(calculated), missing)
                flux = physical(winner, 'preview', phases=grid)[1]
                flux /= np.median(flux)
                comparison = model._comparison(grid, flux, data, winner, fitted_count=1)
                np.testing.assert_allclose(final['model'], flux*comparison['normalization'], atol=1e-12, rtol=0)
                np.testing.assert_allclose(final['comparison']['residual'], comparison['residual'], atol=1e-12, rtol=0)

    def test_undefined_periastron(self):
        with self.assertRaisesRegex(ValueError, 'eccentricity'):
            model.fit(dict(parameters=model.DEFAULTS,fit=['omega']))
