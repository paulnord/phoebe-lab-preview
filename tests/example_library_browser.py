"""Load all packaged examples through their regular UI entry point."""
import sys
from playwright.sync_api import sync_playwright,expect

with sync_playwright() as pw:
    b=pw.chromium.launch()
    page=b.new_page()
    page.goto(sys.argv[1])
    export=page.locator('#export-button')
    expect(export).to_be_enabled(timeout=120000)
    picker=page.locator('#example-choice')
    for name in ('Grazing eclipses','Deep primary eclipse','Eccentric eclipse pair','Kepler · KIC 4544587','Original binary'):
        picker.select_option(label=name)
        page.locator('#example-button').click()
        expected='Example binary' if name=='Original binary' else name
        expect(page.locator('#dataset-name')).to_have_text(expected)
        expect(export).to_be_enabled(timeout=120000)
        if name.startswith('Kepler'):
            expect(page.locator('#dataset-description')).to_contain_text('Kepler observations · 432')
        print('Loaded and computed',name,flush=True)
    b.close()
