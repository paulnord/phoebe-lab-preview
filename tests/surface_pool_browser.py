"""Change physics and stop a custom Roche calculation after helper workers join."""
import sys
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page()
    page.goto(sys.argv[1])
    export = page.locator('#export-button')
    expect(export).to_be_enabled(timeout=150000)
    inclination = page.locator('#number-inclination')
    inclination.fill('83.7')
    inclination.press('Tab')
    expect(export).to_be_enabled(timeout=120000)
    def csv():
        with page.expect_download() as saved:
            export.click()
        return saved.value.path().read_bytes()
    spherical = csv()
    page.locator('#effects summary').click()
    page.locator('#surface-workers').select_option('2')
    tides = page.locator('#distortion')
    for stop in (False, True):
        tides.check()
        # A nine-point update has used at least one wave of two workers.
        page.wait_for_function(r"""()=>{
          const match=document.querySelector('.chart-legend').textContent.match(/(\d+) points/);
          return match && Number(match[1])>=9;
        }""", timeout=120000)
        expect(export).to_be_disabled()
        if stop:
            page.locator('#stop-button').click()
            expect(page.locator('#model-status')).to_contain_text('Stopped')
        tides.uncheck()
        expect(export).to_be_enabled(timeout=3000)
        assert csv() == spherical
        expect(page.locator('#fit-button')).to_be_enabled(timeout=150000)
    print('Verified parallel cancellation, Stop, cached CSV recovery and fit re-enable.')
    browser.close()
