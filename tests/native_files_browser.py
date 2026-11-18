"""Check the local WebAssembly app with a desktop-produced .phoebe and .model pair.

Pass the assembled site directory and a disposable directory containing desktop.phoebe
and desktop.model, the four-point survey_v (or lc01) LC fixtures. Browser downloads
are saved there for independent desktop PHOEBE checks.
"""
import argparse
import functools
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright,expect


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass


def run(page,url,out):
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.add_init_script("""{const original=CanvasRenderingContext2D.prototype.stroke;
    CanvasRenderingContext2D.prototype.stroke=function(...args){
      if(this.canvas.id==='light-curve' && ['#b56a08','#6a59da'].includes(this.strokeStyle))
        window.lastCurve={color:this.strokeStyle,width:this.lineWidth,alpha:this.globalAlpha};
      return original.apply(this,args);};}""")
    page.goto(url)
    export=page.locator('#export-button')
    expect(export).to_be_enabled(timeout=180000)
    mass=page.locator('#range-mass_ratio')
    mass.dispatch_event('pointerdown')
    update=lambda k,v:page.locator('#range-'+k).evaluate("(s,v)=>{s.value=v;s.dispatchEvent(new Event('input'));}",v)
    legend=page.locator('.chart-legend span').last
    update('eccentricity',.18);update('omega',240);update('inclination',76)
    expect(legend).to_contain_text('Approximate')
    assert page.evaluate('lastCurve.color')=='#6a59da'
    update('mass_ratio',.90)
    expect(legend).to_contain_text('eight-slider neural preview')
    assert page.evaluate('lastCurve.color')=='#b56a08' and page.evaluate('lastCurve.width')==14
    page.locator('#light-curve').screenshot(path=out/'amber.png')
    expect(export).to_be_disabled();expect(page.locator('#fit-button')).to_be_disabled()
    expect(page.locator('#rms-stat')).to_have_text('—')
    update('period',.1);expect(legend).to_contain_text('atmosphere clamped')
    update('period',1.8);expect(legend).not_to_contain_text('clamped')
    mass.dispatch_event('pointerup')
    expect(export).to_be_enabled(timeout=120000);expect(legend).to_have_text('PHOEBE model')
    assert page.evaluate('lastCurve.color')=='#6a59da' and page.evaluate('lastCurve.alpha')==1

    page.locator('#native-button').click()
    page.locator('#native-lab').click()
    expect(page.locator('#native-title')).to_have_text('lab-system.phoebe',timeout=180000)
    expect(page.locator('#native-units')).to_contain_text('513 points')
    def save(button,name):
        with page.expect_download() as event:page.locator(button).click()
        event.value.save_as(out/name)
    save('#native-save-bundle','browser-lab.phoebe')
    save('#native-save-model','browser-lab.model')
    def upload(button,path):
        with page.expect_file_chooser() as fc:page.locator(button).click()
        fc.value.set_files(path)
    upload('#native-open',out/'desktop.phoebe')
    expect(page.locator('#native-title')).to_have_text('desktop.phoebe')
    expect(page.locator('#native-save-model')).to_be_disabled()
    upload('#native-attach',out/'desktop.model')
    expect(page.locator('#native-units')).to_contain_text('4 points')
    page.locator('#native-orbit-fields input[data-key="incl"]').fill('86')
    page.locator('#native-run').click()
    expect(page.locator('#native-model')).to_have_value('lab_native',timeout=120000)
    save('#native-save-bundle','browser-desktop.phoebe')
    save('#native-save-model','browser-desktop.model')
    page.locator('#native-dialog .close-dialog').click()
    page.locator('#import-button').click()
    page.locator('#data-file').set_input_files(out/'browser-desktop.model')
    expect(page.locator('#native-units')).to_contain_text('4 points')
    expect(page.locator('#native-title')).to_have_text('browser-desktop.model')
    expect(page.locator('#native-save-bundle')).to_be_hidden()
    upload('#native-open',dict(name='broken.phoebe',mimeType='application/json',buffer=b'{}'))
    expect(page.locator('#native-status')).to_have_attribute('aria-invalid','true')
    expect(page.locator('#native-title')).to_have_text('browser-desktop.model')
    page.locator('#native-dialog .close-dialog').click()
    page.locator('#reset-button').click()
    expect(export).to_be_enabled(timeout=120000)
    period=page.locator('#range-period')
    period.dispatch_event('pointerdown');update('period',.1)
    expect(legend).to_contain_text('atmosphere clamped')
    period.dispatch_event('pointerup')
    expect(legend).to_contain_text('exact PHOEBE calculation failed',timeout=120000)
    expect(export).to_be_disabled()
    expect(page.locator('#fit-button')).to_be_disabled()
    expect(page.locator('#rms-stat')).to_have_text('—')
    assert page.evaluate('lastCurve.color')=='#b56a08'
    assert not errors,errors


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('site',type=Path);p.add_argument('out',type=Path)
    a=p.parse_args()
    with ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=a.site)) as s,sync_playwright() as pw:
        threading.Thread(target=s.serve_forever,daemon=True).start()
        b=pw.chromium.launch()
        try:run(b.new_page(viewport={'width':1280,'height':900}),f'http://127.0.0.1:{s.server_port}/',a.out)
        finally:b.close();s.shutdown()
    print('Real Chromium native file round trips and validated/exploratory/exact transitions passed.')
