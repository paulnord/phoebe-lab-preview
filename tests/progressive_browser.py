"""Run against an isolated, served build with the WebAssembly wheels installed."""
import json
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright,expect


def run(url,out):
    with sync_playwright() as pw:
        expect.set_options(timeout=120000)
        browser=pw.chromium.launch()
        page=browser.new_page(accept_downloads=True)
        page.set_default_timeout(100000)
        page.add_init_script("""{const W=Worker;window.events=[];window.results=[];
        window.Worker=class extends W{constructor(...args){super(...args);this.addEventListener('message',({data:d})=>{
        if(d.type==='partial'||d.type==='result'){
           const n=d.phases?.length||d.result.phases.length;
           events.push({id:d.id,type:d.type,n,t:performance.now()});
           if(d.result)results.push(d.result);
        } });}postMessage(d,...args){if(d.type==='compute')events.push({id:d.id,type:'start',t:performance.now()});super.postMessage(d,...args);}};}""")
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('console',lambda msg:print(msg.text,flush=True) if msg.type=='error' else None)
        page.goto(url)
        page.wait_for_function("events.some(e=>e.type==='partial')")
        expect(page.locator('#export-button')).to_be_disabled()
        expect(page.locator('#rms-stat')).to_have_text('—')
        expect(page.locator('#export-button')).to_be_enabled()
        first=page.evaluate('events.slice()')
        assert [e['n'] for e in first if 'n' in e]==[65,129,193,257,321,385,449,513],first
        slider=page.locator('#range-mass_ratio')
        def edit(value,release):
            slider.dispatch_event('pointerdown')
            slider.evaluate("(e,v)=>{e.value=v;e.dispatchEvent(new Event('input'));}",value)
            if release: slider.dispatch_event('pointerup')
        edit(.81,True)
        page.wait_for_function("events.some(e=>e.id===2&&e.type==='partial')")
        edit(1.05,False)
        expect(page.locator('.chart-legend')).to_contain_text('eight-slider')
        page.wait_for_timeout(1800)
        expect(page.locator('#export-button')).to_be_disabled()
        expect(page.locator('.chart-legend')).to_contain_text('eight-slider')
        slider.dispatch_event('pointerup')
        expect(page.locator('#export-button')).to_be_enabled()
        latest=page.evaluate('results.at(-1)')
        assert latest['parameters']['mass_ratio']==1.05 and len(latest['phases'])==513
        assert not page.evaluate("events.some(e=>e.id===2&&e.type==='result')")
        with page.expect_download() as dl:page.locator('#export-button').click()
        assert len(dl.value.path().read_text().splitlines())==514
        print('Progressive UI, guarded handoff and 513-point export passed.',flush=True)
        page.locator('#native-button').click()
        page.locator('#native-new').click()
        expect(page.locator('#adv-parameters')).to_be_enabled()
        page.wait_for_function("document.querySelector('#adv-parameters').options.length>0")
        search=page.locator('#adv-search')
        search.fill('teff@primary')
        opt=page.locator('#adv-parameters option').first
        page.locator('#adv-parameters').select_option(opt.get_attribute('value'))
        field=page.locator('#adv-value')
        expect(field).to_be_enabled()
        field.fill('7070')
        page.locator('#adv-apply').click()
        expect(page.locator('#adv-apply')).to_be_enabled()
        expect(field).to_have_value('7070')
        page.get_by_text('Datasets, physics and solvers',exact=True).click()
        page.locator('#adv-category').select_option('feature')
        page.locator('#adv-kind').select_option('spot')
        page.locator('#adv-add').click()
        expect(page.locator('#adv-add')).to_be_enabled()
        page.locator('#adv-category').select_option('dataset')
        page.locator('#adv-kind').select_option('rv')
        page.locator('#adv-add').click()
        expect(page.locator('#native-summary')).to_contain_text('2 dataset')
        print('Advanced edit, spot and RV dataset passed.',flush=True)
        page.locator('#native-run').click()
        expect(page.locator('#native-save-model')).to_be_enabled()
        assert page.locator('#native-series option').count()>=3
        with page.expect_download() as dl:page.locator('#native-save-bundle').click()
        rows=json.loads(dl.value.path().read_text())
        assert any(r.get('value')==7070 and r.get('qualifier')=='teff' for r in rows)
        assert any(r.get('kind')=='spot' for r in rows)
        assert not errors,errors
        (out/'browser.json').write_text(json.dumps(dict(stages=first,engine=latest['engine'],browser=browser.version,
            exact_export_samples=len(latest['phases']),advanced_series=page.locator('#native-series option').all_text_contents()),indent=2))
        browser.close()


if __name__=='__main__':
    run(sys.argv[1],Path(sys.argv[2]))
