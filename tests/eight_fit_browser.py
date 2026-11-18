"""Exercise all eight fit choices with timestamped photometry from browser PHOEBE."""
import json
import sys
import numpy as np
from playwright.sync_api import sync_playwright, expect


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page()
    page.add_init_script("""{const W=Worker;window.results=[];
        window.Worker=class extends W {constructor(...args){super(...args);
        this.addEventListener('message',({data})=>{if(data.type==='result')results.push(data.result);});}};}""")
    page.goto(sys.argv[1])
    export = page.locator('#export-button')
    expect(export).to_be_enabled(timeout=150000)
    page.locator('#number-eccentricity').fill('0.13')
    page.locator('#number-eccentricity').press('Tab')
    page.wait_for_function('results.at(-1)?.parameters.eccentricity===.13', timeout=150000)
    truth = page.evaluate('results.at(-1)')
    p = truth['parameters']
    times = np.random.default_rng(55).uniform(0, 24, 200)
    phase = (times/p['period']+.5)%1-.5
    flux = np.interp(phase,truth['phases'],truth['model'])
    data = dict(name='Eight-parameter fit check', x_kind='time', y_kind='flux', x=times.tolist(),
                y=flux.tolist(), sigma=np.linspace(.002,.009,len(times)).tolist(), period=p['period'], epoch=p['epoch'])
    session = dict(schema='phoebe-lab-session-v1', parameters=p, dataset=data, quality='preview')
    page.locator('#import-button').click()
    page.locator('#data-file').set_input_files(dict(name='eight.json',mimeType='application/json',
                                                   buffer=json.dumps(session).encode()))
    expect(page.locator('#dataset-name')).to_have_text(data['name'])
    expect(page.locator('#fit-button')).to_be_enabled(timeout=120000)
    page.locator('#fit-button').click()
    page.locator('#fit-phases').select_option('513')
    boxes = page.locator('input[name=fit]')
    assert boxes.count() == 8
    for box in boxes.all():
        box.check()
    page.locator('#fit-form button[type=submit]').click()
    page.wait_for_function("results.at(-1)?.fit?.parameters.length===8",timeout=360000)
    fitted = page.evaluate('results.at(-1)')
    assert fitted['fit']['objective_phases'] == len(fitted['phases']) == 513
    assert fitted['fit']['objective_triangles'] == 400 and fitted['comparison']['rms'] < 1e-10
    expect(export).to_be_enabled()
    print(f"Eight selected, {fitted['fit']['evaluations']} evaluations, {fitted['seconds']:.1f} s; "
          f"RMS {fitted['comparison']['rms']:.2g}.")
    browser.close()
