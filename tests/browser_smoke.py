"""End-to-end checks against real PHOEBE in a browser Web Worker.

Usage: python tests/browser_smoke.py [http://127.0.0.1:8765/]
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
        np.testing.assert_allclose(result["model"], reference["model"], atol=1e-7, rtol=0)
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
        assert len(Path(await csv.path()).read_text().splitlines()) == 82
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
        await page.locator('input[name=fit][value=radius_primary]').check()
        await page.locator('#fit-form button[type=submit]').click()
        assert 'one or two' in await page.locator('#fit-error').inner_text()
        await page.locator('input[name=fit][value=radius_primary]').uncheck()
        await page.locator('input[name=fit][value=temperature_ratio]').uncheck()
        await page.locator('#fit-form button[type=submit]').click()
        await page.wait_for_function("window.engineResults.some(m=>m.operation==='fit')", timeout=180000)
        fitted = await page.evaluate("window.engineResults.find(m=>m.operation==='fit').result")
        assert fitted['fit']['parameters'] == ['inclination']
        assert fitted['comparison']['rms'] <= changed['comparison']['rms'] + 1e-10
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
