"""Check that both stars stay visible as a radius slider moves lower in the panel."""
import sys
from playwright.sync_api import sync_playwright, expect


def visible_stars(page):
    return page.locator('.star-guide .star').evaluate_all("""stars => stars.every(star => {
        const r = star.getBoundingClientRect();
        return r.top >= 0 && r.bottom <= innerHeight &&
            document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2) === star;
    })""")


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(reduced_motion='reduce')
    page.goto(sys.argv[1])
    radius = page.locator('#range-radius_primary')
    primary = page.locator('#primary-star')
    expect(radius).to_be_visible()
    for width, height in [(1366, 768), (900, 650), (390, 844), (667, 375)]:
        page.set_viewport_size(dict(width=width, height=height))
        panel = page.locator('.controls-panel')
        panel.evaluate("el => { window.scrollTo(0, 0); el.scrollTop = 0; }")
        column_top = panel.evaluate("el => el.getBoundingClientRect().top + el.clientTop")
        guide = page.locator('.star-guide')
        heading = page.locator('.panel-heading')
        start = guide.bounding_box()
        assert abs(start['y'] - column_top) <= 1, (width, height)
        assert heading.bounding_box()['y'] >= start['y'] + start['height'] - 1
        radius.evaluate("el => el.scrollIntoView({block:'center'})")
        box = radius.bounding_box()
        y = box['y'] + box['height'] / 2
        page.mouse.move(box['x'] + .25 * box['width'], y)
        page.mouse.down()
        before = primary.bounding_box()['width']
        assert visible_stars(page), (width, height)
        page.mouse.move(box['x'] + .8 * box['width'], y, steps=5)
        assert primary.bounding_box()['width'] > before
        assert visible_stars(page), (width, height)
        page.mouse.up()
        page.locator('#range-period').evaluate("el => el.scrollIntoView({block:'center'})")
        assert visible_stars(page), (width, height)
        pinned = guide.bounding_box()
        assert abs(pinned['y'] - max(0, panel.bounding_box()['y'])) <= 1
        title = heading.bounding_box()
        assert title['y'] + title['height'] <= pinned['y'] + 1
        print(f'Both stars visible during radius drag and at period control: {width} x {height}', flush=True)
    browser.close()
