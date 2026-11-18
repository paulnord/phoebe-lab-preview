"""End-to-end checks against real PHOEBE in a browser Web Worker.

Usage: python tests/browser_smoke.py [http://127.0.0.1:8765/] [65|129|513]
Requires playwright and its Chromium browser. No PHOEBE installation on the host.
"""
import asyncio
import json
import os
from pathlib import Path
import sys
import numpy as np
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/"

FIT_PHASES = int(sys.argv[2]) if len(sys.argv) > 2 else 129

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = await browser.new_page(viewport={"width": 1440, "height": 1080})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda message: print("console:", message.text[:1200], flush=True) if message.type == "error" else None)
        page.on("requestfailed", lambda request: print("request failed:", request.url, request.failure, flush=True))
        await page.add_init_script("""
        window.engineMessages=[];window.engineResults=[];
        const OriginalWorker=window.Worker;
        window.Worker=class extends OriginalWorker {
          constructor(...args){super(...args);window.testWorker=this;
            this.addEventListener('message',({data})=>{
              if(data.type==='result')window.engineResults.push(data);
              else window.engineMessages.push(data);
            });
          }
          postMessage(data,...rest){if(window.testProfile&&data.type==='compute')data.profile=true;super.postMessage(data,...rest);}
        };
        """)
        # Use a fresh, single-call PHOEBE evaluation in the same WebAssembly build.
        # The check is injected only into the worker response in this test browser.
        async def instrument_worker(route):
            response = await route.fetch()
            source = await response.text()
            marker = '  if (data.type === "continue"'
            assert source.count(marker) == 1
            hook = """  if (data.type === 'single_check') {
                pyodide.globals.set('_check_payload', JSON.stringify(data.payload));
                const text = await pyodide.runPythonAsync(`
_check = json.loads(_check_payload)
_p = model.parameters(_check['parameters'])
_x, _f = model._raw_model(_p, _check['quality'], phases=model.np.linspace(-.5,.5,513))
json.dumps(model._curve_result(_p,_check['quality'],_x,_f,_check['dataset'],model.time.perf_counter(),_check['fitted_count']))
`);
                self.postMessage({type:'single_check', value:JSON.parse(text)});return;
              }
"""
            await route.fulfill(response=response, body=source.replace(marker, hook+marker))
        await page.context.route('**/engine.worker.js*', instrument_worker)
        dataset = json.loads((ROOT / 'site/example.json').read_text())

        async def verify_single(result, fitted_count=0):
            check = await page.evaluate("""payload => new Promise((resolve,reject)=>{
              const timer=setTimeout(()=>reject(Error("Single-call PHOEBE check timed out")),90000);
              function receive({data}){if(data.type==='single_check'){
                clearTimeout(timer);testWorker.removeEventListener('message',receive);resolve(data.value);}}
              testWorker.addEventListener('message',receive);
              testWorker.postMessage({type:'single_check',payload});
            })""", dict(parameters=result['parameters'], quality=result['quality'],
                        dataset=dataset, fitted_count=fitted_count))
            np.testing.assert_array_equal(result['phases'], check['phases'])
            np.testing.assert_allclose(result['model'], check['model'], atol=1e-10, rtol=0)
            for key in ('residual','model_at_data','reduced_chi2','rms'):
                np.testing.assert_allclose(result['comparison'][key], check['comparison'][key], atol=1e-10, rtol=0)
        await page.goto(URL)
        for _ in range(300):
            messages = await page.evaluate("window.engineMessages")
            fatal = next((m for m in messages if m["type"] in ("fatal", "error")), None)
            if fatal:
                print(json.dumps(fatal), flush=True)
                raise AssertionError("Browser engine failed")
            if await page.evaluate("window.engineResults.length"):
                break
            if _ % 10 == 0:
                print(await page.locator("#engine-title").inner_text(), await page.locator("#model-status").inner_text(), flush=True)
            await asyncio.sleep(1)
        else:
            raise AssertionError("Browser engine timed out")
        result = await page.evaluate("window.engineResults.at(-1).result")
        reference = json.loads((ROOT / "tests/native-reference.json").read_text())
        (ROOT / ".qa").mkdir(exist_ok=True)
        (ROOT / ".qa/browser-result.json").write_text(json.dumps(result))
        await page.screenshot(path=str(ROOT / ".qa/desktop.png"), full_page=True)
        difference = float(np.max(np.abs(np.asarray(result["model"])-reference["model"])))
        print("Native comparison max absolute difference:", difference, "; model seconds:", result["seconds"], flush=True)
        await verify_single(result)
        np.testing.assert_allclose(result["model"], reference["model"], atol=3e-6, rtol=0)
        await page.evaluate("window.testProfile=" + ("true" if os.getenv("PHOEBE_PROFILE") else "false"))
        await page.locator('#number-inclination').fill('87')
        await page.locator('#number-inclination').press('Tab')
        await page.wait_for_function("window.engineResults.length>=2", timeout=300000)
        changed = await page.evaluate("window.engineResults.at(-1).result")
        print('Subsequent model seconds:', changed['seconds'], '\n', changed.get('_profile'), flush=True)
        assert changed['parameters']['inclination'] == 87
        assert np.max(np.abs(np.array(changed['model']) - result['model'])) > .005
        await page.evaluate("window.testProfile=false")
        async with page.expect_download() as session_download:
            await page.locator('#save-button').click()
        saved = await session_download.value
        session_text = Path(await saved.path()).read_text()
        assert json.loads(session_text)['parameters']['inclination'] == 87
        async with page.expect_download() as csv_download:
            await page.locator('#export-button').click()
        csv = await csv_download.value
        assert len(Path(await csv.path()).read_text().splitlines()) == 514
        # Import the same observations as magnitudes; the flux comparison must agree.
        example = json.loads((ROOT / 'site/example.json').read_text())
        rows = ['phase,magnitude,sigma_magnitude']
        for phase, flux, sigma in zip(example['x'], example['y'], example['sigma']):
            rows.append(f'{phase},{11-2.5*np.log10(flux)},{sigma/(.4*np.log(10)*flux)}')
        await page.locator('#import-button').click()
        await page.locator('#data-file').set_input_files({'name':'magnitude-test.csv','mimeType':'text/csv','buffer':'\n'.join(rows).encode()})
        await page.locator('#import-options').wait_for(state='visible')
        assert await page.locator('#y-kind').input_value() == 'magnitude'
        await page.locator('#load-file-button').click()
        await page.wait_for_function('window.engineResults.length>=3', timeout=300000)
        magnitude_result = await page.evaluate('window.engineResults.at(-1).result')
        np.testing.assert_allclose(magnitude_result['comparison']['flux'], changed['comparison']['flux'], atol=1e-12)
        np.testing.assert_allclose(magnitude_result['comparison']['sigma'], changed['comparison']['sigma'], atol=1e-12)
        # Restore a saved session through the same file import control.
        await page.locator('#import-button').click()
        await page.locator('#data-file').set_input_files({'name':'session.json','mimeType':'application/json','buffer':session_text.encode()})
        await page.wait_for_function('window.engineResults.length>=4', timeout=300000)
        assert 'Example binary' in await page.locator('#dataset-name').inner_text()
        await page.locator('#fit-button').click()
        fit_phases = page.locator('#fit-phases')
        assert await fit_phases.input_value() == '129'
        await fit_phases.select_option(str(FIT_PHASES))
        assert await page.locator('input[name=fit]').count() == 8
        await page.locator('input[name=fit][value=inclination]').uncheck()
        await page.locator('input[name=fit][value=temperature_ratio]').uncheck()
        await page.locator('#fit-form button[type=submit]').click()
        assert 'at least one' in await page.locator('#fit-error').inner_text()
        await page.locator('input[name=fit][value=inclination]').check()
        await page.locator('#fit-form button[type=submit]').click()
        await page.wait_for_function("window.engineResults.some(m=>m.operation==='fit')", timeout=300000)
        fitted = await page.evaluate("window.engineResults.find(m=>m.operation==='fit').result")
        assert fitted['fit']['parameters'] == ['inclination']
        assert fitted['comparison']['rms'] <= changed['comparison']['rms'] + 1e-10
        assert fitted['fit']['objective_phases'] == FIT_PHASES and len(fitted['phases']) == 513
        await verify_single(fitted, 1)
        async with page.expect_download() as fitted_download:
            await page.locator('#export-button').click()
        fitted_csv = np.loadtxt(await (await fitted_download.value).path(), delimiter=',', skiprows=1)
        np.testing.assert_array_equal(fitted_csv.T, [fitted['phases'], fitted['model']])
        print('Real browser fit passed:', fitted['fit']['evaluations'], 'evaluations in', fitted['seconds'], 'seconds.', flush=True)
        # Exercise the display layer with an eccentric secondary eclipse, then
        # verify the worker replaces it before fitting or exports become available.
        await page.locator("#example-button").click()
        await page.wait_for_function("document.querySelector('#number-inclination').value==='84.5' && !document.querySelector('#export-button').disabled")
        eccentricity = page.locator("#range-eccentricity")
        await eccentricity.dispatch_event("pointerdown")
        for key, val in [("eccentricity", ".18"), ("omega", "240")]:
            await page.locator("#range-" + key).evaluate(
                "(s,v)=>{s.value=v;s.dispatchEvent(new Event('input',{bubbles:true}));}", val)
        legend = page.locator(".chart-legend span").last
        assert "Approximate" in await legend.inner_text()
        assert await page.locator("#export-button").is_disabled()
        assert await page.locator("#fit-button").is_disabled()
        assert await page.locator("#rms-stat").inner_text() == "—"
        await eccentricity.dispatch_event("pointerup")
        await page.wait_for_function("window.engineResults.at(-1).result.parameters.omega===240 && !document.querySelector('#export-button').disabled", timeout=120000)
        assert await legend.inner_text() == "PHOEBE model"
        await page.set_viewport_size({'width':390,'height':844})
        assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        await page.screenshot(path=str(ROOT / '.qa/mobile.png'), full_page=True)
        print('Slider, magnitude import, session restore, CSV export, fit validation and mobile layout passed.', flush=True)
        assert not errors, errors
        await browser.close()

asyncio.run(main())
