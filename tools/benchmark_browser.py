"""Benchmark the browser worker without starting the graphical interface."""
import asyncio
import json
from pathlib import Path
import sys
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
async def main():
    payload = json.loads((ROOT / 'tests/native-reference.json').read_text())['parameters']
    if '--sphere' in sys.argv:
        payload['distortion'] = False
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=['--no-sandbox','--disable-dev-shm-usage'])
        page = await browser.new_page()
        await page.route('http://127.0.0.1:8765/bench', lambda route: route.fulfill(body='<html><body>Worker benchmark</body></html>', content_type='text/html'))
        await page.goto('http://127.0.0.1:8765/bench')
        await page.evaluate('''()=>{
          window.messages=[];
          window.worker=new Worker('/assets/engine.worker.js',{type:'module'});
          worker.onmessage=({data})=>messages.push(data);
          worker.postMessage({type:'initialize'});
        }''')
        await page.wait_for_function("messages.some(m=>['ready','fatal'].includes(m.type))", timeout=120000)
        messages=await page.evaluate('messages')
        if messages[-1]['type']=='fatal': raise RuntimeError(messages[-1]['error'])
        await page.evaluate('(payload)=>worker.postMessage({type:"compute",id:1,payload,profile:true})',dict(parameters=payload,dataset=json.loads((ROOT/'site/example.json').read_text()),quality='preview'))
        await page.wait_for_function("messages.some(m=>['result','error'].includes(m.type))",timeout=600000)
        result=(await page.evaluate('messages'))[-1]
        print(json.dumps(result),flush=True)
        await browser.close()
asyncio.run(main())
