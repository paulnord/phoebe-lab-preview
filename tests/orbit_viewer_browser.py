"""Orbit viewer browser checks, against a live app or the offline review fixture.

Usage: python tests/orbit_viewer_browser.py http://127.0.0.1:8765/ [--live]
Requires Playwright and Chromium. CHROMIUM_PATH can select a system browser.
"""
import os
import sys

from playwright.sync_api import expect, sync_playwright


live = '--live' in sys.argv[2:]
with sync_playwright() as pw:
    options = {"args": ["--no-sandbox"]}
    if os.environ.get("CHROMIUM_PATH"):
        options["executable_path"] = os.environ["CHROMIUM_PATH"]
    browser = pw.chromium.launch(**options)
    page = browser.new_page(viewport={"width": 1440, "height": 800}, reduced_motion="reduce")
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.add_init_script("""window.requests = 0;
    const original = Worker.prototype.postMessage;
    Worker.prototype.postMessage = function(message, ...args) {
      if (message.type === 'compute' || message.type === 'fit') window.requests++;
      return original.call(this, message, ...args);
    };""")
    page.goto(sys.argv[1])
    expect(page.locator("#fit-button")).to_be_enabled(timeout=240000 if live else 12000)
    calls = page.evaluate("requests")
    launcher = page.locator(".orbit-launch")
    launcher.focus()
    launcher.press("Enter")
    dialog = page.locator("#orbit-dialog")
    expect(dialog).to_be_visible()
    expect(page.locator("#orbit-play")).to_have_text("Play")
    original_curve = "preview resolution" if live else "81 computed phases"
    expect(page.locator("#orbit-curve-status")).to_contain_text(original_curve)
    page.locator("#orbit-view").select_option("above")
    expect(page.locator("#orbit-inclination")).to_contain_text("part of the Earth direction")
    phase = page.locator("#orbit-phase")
    phase.evaluate("""el => {el.value = '0.25'; el.dispatchEvent(new Event('input', {bubbles:true}));}""")
    expect(page.locator("#orbit-time")).to_contain_text("0.4500 of 1.8 model days")
    assert phase.evaluate("el => el.style.getPropertyValue('--fill')") == "25%"
    page.locator("#orbit-speed").select_option("2")
    page.locator("#orbit-play").click()
    page.wait_for_function("Number(document.getElementById('orbit-phase').value) > .30")
    page.locator("#orbit-play").click()
    held = phase.input_value()
    page.wait_for_timeout(180)
    assert phase.input_value() == held
    page.keyboard.press("Escape")
    expect(dialog).to_be_hidden()
    expect(launcher).to_be_focused()
    assert page.evaluate("requests") == calls
    # Changing quality creates a new revision; the offline worker has no refined result.
    page.get_by_role("button", name="Refined").click()
    launcher.click()
    expect(page.locator("#orbit-curve-status")).not_to_contain_text(original_curve)
    for w, h in [(1710, 950), (1440, 800), (390, 844), (667, 375)]:
        page.set_viewport_size({"width": w, "height": h})
        expect(dialog).to_be_visible()
        box = dialog.bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= w + 1
        assert box["y"] >= 0 and box["y"] + box["height"] <= h + 1
    page.locator("#orbit-close").click()
    expect(dialog).to_be_hidden()
    assert not errors, errors
    print("PASS: current model curve, launch/focus, reduced motion, scrub and play, no new compute, stale-result rejection, responsive dialog")
    browser.close()
