"""Exercise published examples, cross-mode switching and stale-result rejection."""
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

URL=sys.argv[1] if len(sys.argv)>1 else "http://127.0.0.1:8765/"

FAKE_WORKER=r"""
window.fakePosts=[];window.fakeResults=[];window.fakeDelay=5;
window.Worker=class {
  constructor(){this.terminated=false;}
  terminate(){this.terminated=true;}
  postMessage(message){
    window.fakePosts.push(structuredClone(message));
    if(message.type==='initialize'){
      setTimeout(()=>{if(!this.terminated)this.onmessage?.({data:{type:'ready',supported_workers:1}})},0);return;
    }
    if(!['compute','fit'].includes(message.type))return;
    const delay=window.fakeDelay;
    setTimeout(()=>{
      if(this.terminated)return;
      const {parameters,dataset,quality,workers}=message.payload;
      const phases=Array.from({length:9},(_,i)=>-.5+i/8),model=phases.map(()=>1);
      const observed=dataset.x.map((x,i)=>({phase:dataset.x_kind==='time'?((x-parameters.epoch)/parameters.period+.5)%1-.5:x,index:i})).sort((a,b)=>a.phase-b.phase);
      const comparison={phase:observed.map(row=>row.phase),flux:observed.map(()=>1),sigma:null,
        model_at_data:observed.map(()=>1),residual:observed.map(()=>0),scale:1,rms:0,reduced_chi2:null};
      const result={parameters,quality,phases,model,comparison,seconds:.01,surface_workers:workers,
        native_python:true,runtime:'Test native bridge'};
      window.fakeResults.push({id:message.id,mode:parameters.contact?'contact':parameters.semidetached?'semi':'detached'});
      this.onmessage?.({data:{type:'result',id:message.id,operation:message.type,result}});
    },delay);
  }
};
"""

with sync_playwright() as pw:
    configured=os.environ.get('PLAYWRIGHT_CHROMIUM')
    executable=configured if configured and Path(configured).is_file() else None
    browser=pw.chromium.launch(headless=True,executable_path=executable,
                               args=["--no-sandbox","--disable-dev-shm-usage"])
    page=browser.new_page(viewport={"width":1440,"height":1000})
    page.add_init_script(FAKE_WORKER)
    page.goto(URL)
    expect(page.locator('#export-button')).to_be_enabled(timeout=30000)
    choice=page.locator('#example-choice');load=page.locator('#example-button')

    page.evaluate('window.fakeDelay=180')
    choice.select_option('observed-sz-her');load.click()
    expect(page.locator('#geometry-semi')).to_be_checked()
    expect(page.locator('#donor')).to_have_value('secondary')
    expect(page.locator('#dataset-name')).to_contain_text('SZ Herculis')
    expect(page.locator('#number-period')).to_have_value('0.8180837')
    expect(page.locator('#number-epoch')).to_have_value('2454588.1679970')
    expect(page.locator('#export-button')).to_be_disabled()
    expect(page.locator('#rms-stat')).to_have_text('—')

    # Supersede the still-pending semi-detached result with a contact example.
    choice.select_option('observed-v1128-tau');load.click()
    expect(page.locator('#geometry-contact')).to_be_checked()
    expect(page.locator('#dataset-name')).to_contain_text('V1128 Tauri')
    expect(page.locator('#number-period')).to_have_value('0.3053710')
    expect(page.locator('#number-epoch')).to_have_value('2454842.4996855')
    expect(page.locator('#number-mass_ratio')).to_have_value('0.53')
    expect(page.locator('#number-fillout_factor')).to_have_value('0.134')
    expect(page.locator('#export-button')).to_be_enabled(timeout=30000)
    expect(page.locator('#rms-stat')).to_have_text('0.0000')
    page.wait_for_function("Boolean(document.querySelector('#light-curve').chart)")
    assert page.evaluate("document.querySelector('#light-curve').chart.data.phase.length")==690

    payloads=page.evaluate("window.fakePosts.filter(p=>p.type==='compute').map(p=>p.payload)")
    assert any(p['parameters']['semidetached'] and p['parameters']['donor']=='secondary' for p in payloads)
    contact=next(p for p in reversed(payloads) if p['parameters']['contact'])
    assert len(contact['dataset']['x'])==690 and 'sigma' not in contact['dataset']
    assert contact['parameters']['mass_ratio']==.534
    assert not any(post['type']=='fit' for post in page.evaluate('window.fakePosts'))

    # The same picker remains available from Contact and Detached.
    page.evaluate('window.fakeDelay=5')
    choice.select_option('example.json');load.click()
    expect(page.locator('#geometry-detached')).to_be_checked()
    expect(page.locator('#dataset-name')).to_have_text('Example binary')
    expect(page.locator('#export-button')).to_be_enabled(timeout=30000)
    choice.select_option('observed-sz-her');load.click()
    expect(page.locator('#geometry-semi')).to_be_checked()
    expect(page.locator('#export-button')).to_be_enabled(timeout=30000)
    assert page.evaluate("document.querySelector('#light-curve').chart.data.phase.length")==437
    print('Published picker passed cross-mode load, plot, ephemeris, no-error, no-fit and stale-result checks.')
    browser.close()
