"""Exercise the default exact surface references, custom grid and stale-result handling."""
import sys
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page()
    page.add_init_script("""{
      const orig=CanvasRenderingContext2D.prototype.stroke;
      CanvasRenderingContext2D.prototype.stroke=function(...args){
        if(this.canvas.id==='light-curve' && this.lineWidth===14)
          window.fuzzy={color:this.strokeStyle,alpha:this.globalAlpha};
        return orig.apply(this,args);
      };
      window.surfaceBatches=[];
      const WorkerClass=window.Worker;
      window.Worker=class extends WorkerClass {
        constructor(...args){super(...args);this.addEventListener('message',({data})=>{
          if(data.type==='partial')surfaceBatches.push(data.phases.length);
        });}
      };
    }""")
    page.goto(sys.argv[1])
    export = page.locator('#export-button')
    expect(export).to_be_enabled(timeout=120000)

    def csv():
        with page.expect_download() as download:
            export.click()
        return download.value.path().read_bytes()

    original = csv()
    page.locator('#effects summary').click()
    legend = page.locator('.chart-legend')
    status = page.locator('#model-status')
    tidal = page.locator('#distortion')
    heating = page.locator('#irradiation')
    for toggle, label in ((tidal, 'tides'), (heating, 'heating')):
        toggle.check()
        expect(legend).to_contain_text(label + ' omitted')
        assert page.evaluate("fuzzy.color==='#b56a08' && fuzzy.alpha<.5")
        expect(status).to_contain_text('saved reference', timeout=20000)
        expected = 129 if label == 'tides' else 513
        expect(status).to_contain_text(f'{expected} phases')
        assert len(csv().splitlines()) == expected + 1
        if label == 'tides':
            count = page.locator('#tidal-phases')
            count.select_option('513')
            expect(status).to_contain_text('513 phases', timeout=20000)
            assert len(csv().splitlines()) == 514
            count.select_option('129')
            expect(status).to_contain_text('129 phases · restored')
            assert len(csv().splitlines()) == 130
        assert csv() != original
        toggle.uncheck()
        expect(export).to_be_enabled(timeout=2000)
        assert csv() == original
    tidal.check()
    heating.check()
    expect(status).to_contain_text('saved reference', timeout=20000)
    slider = page.locator('#range-inclination')
    slider.dispatch_event('pointerdown')
    slider.evaluate("s=>{s.value=82.1;s.dispatchEvent(new Event('input'));}")
    expect(legend).to_contain_text('tides and heating omitted')
    expect(page.locator('#rms-stat')).to_have_text('—')
    expect(export).to_be_disabled()
    page.evaluate("window.surfaceBatches=[]")
    slider.dispatch_event('pointerup')
    page.wait_for_function("surfaceBatches.includes(5)", timeout=120000)
    expect(export).to_be_disabled()
    page.locator('#stop-button').click()
    expect(status).to_contain_text('Stopped')
    heating.uncheck()
    tidal.uncheck()
    expect(export).to_be_enabled(timeout=120000)
    print('Default surface references, amber drag preview, custom five-phase initial curve and stop/recovery passed.')
    browser.close()
