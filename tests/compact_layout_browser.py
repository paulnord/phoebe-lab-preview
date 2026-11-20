"""Layout-only browser smoke test; engine is stubbed, not scientific validation.
Run against a local site server: python tests/compact_layout_browser.py URL
Optional CHROMIUM_PATH selects a system browser. Screenshots go to LAYOUT_SCREENSHOTS.
"""
import json, os, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 b=p.chromium.launch(**({'executable_path':os.environ['CHROMIUM_PATH']} if os.environ.get('CHROMIUM_PATH') else {}),args=['--no-sandbox'])
 page=b.new_page()
 # Layout/interaction checks only; do not download the scientific engine for CSS testing.
 page.route('**/engine.worker.js*',lambda r:r.fulfill(body='self.onmessage=()=>{}',content_type='application/javascript'))
 errs=[];page.on('pageerror',lambda e:errs.append(str(e)))
 page.goto(sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8878/')
 page.wait_for_selector('#range-inclination')
 for w,h in [(1710,950),(1440,800),(1280,800),(1000,800),(760,800),(390,844)]:
  page.set_viewport_size({'width':w,'height':h});page.wait_for_timeout(200)
  sizes=page.evaluate('''() => {const rect=s=>{const r=document.querySelector(s).getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}};return {viewport:innerWidth,scroll:document.documentElement.scrollWidth,plot:rect('#light-curve'),wrap:rect('.plot-wrap'),rail:rect('.fit-rail'),controls:rect('#parameter-controls'),bannerPosition:getComputedStyle(document.querySelector('.engine-banner')).position}}''')
  assert sizes['scroll']==w,sizes
  assert abs(sizes['plot']['w']-sizes['wrap']['w'])<1,sizes
  assert abs(sizes['plot']['h']-sizes['wrap']['h'])<1,sizes
  assert sizes['bannerPosition']=='static'
  if os.environ.get('LAYOUT_SCREENSHOTS'):
   out=Path(os.environ['LAYOUT_SCREENSHOTS']);out.mkdir(parents=True,exist_ok=True)
   page.screenshot(path=str(out/f'phoebe-layout-{w}.png'),full_page=True)
  print(w,h,json.dumps(sizes))
 page.locator('#guide-button').click();assert page.locator('#guide-dialog').is_visible();page.keyboard.press('Escape')
 page.locator('#number-inclination').fill('75');page.locator('#number-inclination').dispatch_event('change');assert page.locator('#range-inclination').input_value()=='75'
 assert not errs,errs
 print('UI smoke PASS; no page errors')
 b.close()
