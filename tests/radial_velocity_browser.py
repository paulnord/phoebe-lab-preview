"""Load the eccentric binary and verify live RV updates, scale and mobile layout."""
import sys
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(sys.argv[1].rstrip('/')+'/?example=eccentric#rv-panel')
    primary, secondary = page.locator('#rv-primary'), page.locator('#rv-secondary')
    expect(primary).to_contain_text('37.2 km/s')
    expect(secondary).to_contain_text('79.1 km/s')
    # Capture the drawn pixels before and after a live change; the photometry worker can still be loading.
    image = lambda: page.locator('#rv-curve').evaluate('c=>c.toDataURL()')
    inclination = page.locator('#number-inclination')
    angle_slider = page.locator('#range-inclination')
    inclination.fill('0')
    inclination.press('Enter')
    expect(angle_slider).to_have_value('0')
    expect(primary).to_contain_text('0.0 km/s')
    expect(secondary).to_contain_text('0.0 km/s')
    page.locator('#rv-rescale').click()
    # Both stroke colors must still be visible on the zero axis after rescaling.
    face_on = page.locator('#rv-curve').evaluate("""canvas => {
        const {width, height} = canvas;
        const {data} = canvas.getContext('2d').getImageData(0, 0, width, height);
        const rows = [[], []];
        for (let y = 0; y < height; y++) {
            const colors = new Set();
            for (let x = 50; x < width - 20; x++) {
                const i = 4 * (y * width + x);
                if (data[i + 3] === 255)
                    colors.add((data[i] << 16) | (data[i + 1] << 8) | data[i + 2]);
            }
            [0x5948bd, 0x087c83].forEach((color, j) => {
                if (colors.has(color)) rows[j].push(y);
            });
        }
        return rows;
    }""")
    assert face_on[0] == face_on[1] and 1 <= len(face_on[0]) <= 2, face_on
    expect(page.locator('#export-button')).to_be_enabled(timeout=150000)
    inclination.fill('-1')
    inclination.press('Tab')
    expect(inclination).to_have_value('0.0')
    expect(page.locator('#toast')).to_contain_text('Using 0.0')
    angle_slider.focus()
    angle_slider.press('End')
    expect(inclination).to_have_value('90.0')
    expect(secondary).to_contain_text('79.1 km/s')
    angle_slider.press('Home')
    expect(primary).to_contain_text('0.0 km/s')
    expect(secondary).to_contain_text('0.0 km/s')
    inclination.fill('89.8')
    inclination.press('Tab')
    first = image()
    slider = page.locator('#range-period')
    slider.dispatch_event('pointerdown')
    for period, k1, k2 in [(.1,'180.1','383.3'), (100,'18.0','38.3')]:
        slider.evaluate("(s,p)=>{s.value=String(p);s.dispatchEvent(new Event('input'));}",period)
        expect(primary).to_contain_text(k1+' km/s')
        expect(secondary).to_contain_text(k2+' km/s')
        assert image() != first
    last = image()
    slider.dispatch_event('pointerup')
    page.locator('#rv-rescale').click()
    assert image() != last
    page.set_viewport_size(dict(width=390,height=844))
    expect(secondary).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.goto(sys.argv[1].rstrip('/')+'/?example=non-eclipsing#rv-panel')
    expect(page.locator('#dataset-name')).to_have_text('Non-eclipsing binary (30°)')
    expect(inclination).to_have_value('30.0')
    expect(primary).to_contain_text('18.6 km/s')
    expect(secondary).to_contain_text('39.5 km/s')
    expect(page.locator('#model-status')).to_contain_text('saved reference', timeout=150000)
    def flux_span(count):
        with page.expect_download() as download:
            page.locator('#export-button').click()
        lines = download.value.path().read_text().splitlines()
        assert len(lines) == count + 1
        flux = [float(line.split(',')[1]) for line in lines[1:]]
        return max(flux) - min(flux)

    distorted_span = flux_span(129)
    page.locator('#effects summary').click()
    expect(page.locator('#distortion')).to_be_checked()
    page.locator('#distortion').uncheck()
    expect(page.locator('#export-button')).to_be_enabled(timeout=150000)
    assert distorted_span > flux_span(513)
    expect(primary).to_contain_text('18.6 km/s')
    expect(secondary).to_contain_text('39.5 km/s')
    assert not errors, errors
    print('Verified face-on drawing, period and inclination controls, mobile layout and non-eclipsing tides.')
    browser.close()
