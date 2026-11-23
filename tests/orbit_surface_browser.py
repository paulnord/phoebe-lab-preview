"""Browser wiring check for native constrained orbit surfaces with a deterministic worker.

Usage: CHROMIUM_PATH=/usr/bin/chromium python tests/orbit_surface_browser.py http://127.0.0.1:8765/
The worker double exercises pending, stale, ready, and error messages; native mesh
physics is covered independently by the PHOEBE Python tests.
"""
import os
import sys
from playwright.sync_api import expect, sync_playwright


url=sys.argv[1]
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH","/usr/bin/chromium"),args=["--no-sandbox"])
    page=browser.new_page(viewport={"width":1440,"height":900},reduced_motion="reduce")
    errors=[];page.on("pageerror",lambda error:errors.append(str(error)))
    page.add_init_script(r"""
window.surfaceRequests=[];window.surfaceMeshes=[];window.failNextSurface=false;
const semi=(donor)=>({schema:1,source:'native PHOEBE 2.5.4',geometry:'semi',donor,frame:'component_local',phase:0,triangles_requested:500,triangles_actual:500,components:[
 {name:'primary',triangles:[[[.45,-.08,0],[.45,.08,0],[-.32,0,.16]],[[.45,-.08,0],[-.32,0,-.16],[-.32,0,.16]]]},
 {name:'secondary',triangles:[[[.18,-.05,0],[.18,.05,0],[-.16,0,.1]],[[.18,-.05,0],[-.16,0,-.1],[-.16,0,.1]]]}
]});
const contact=()=>({schema:1,source:'native PHOEBE 2.5.4',geometry:'contact',donor:'primary',frame:'primary_origin',neck:.5,phase:0,triangles_requested:500,triangles_actual:500,components:[
 {name:'primary',triangles:[[[0,-.2,0],[.5,-.08,.08],[.5,.08,.08]],[[0,-.2,0],[.5,.08,.08],[0,.2,0]]]},
 {name:'secondary',triangles:[[[.5,-.08,.08],[1,-.2,0],[1,.2,0]],[[.5,-.08,.08],[1,.2,0],[.5,.08,.08]]]}
]});
class DeterministicWorker {
 constructor(){this.onmessage=null;this.onerror=null;}
 emit(data,delay=0){setTimeout(()=>this.onmessage?.({data}),delay);}
 postMessage(message){
  if(message.type==='initialize'){this.emit({type:'ready',version:'2.5.4'});return;}
  if(message.type==='release'||message.type==='continue')return;
  if(message.type==='surface'){
   const p=message.payload.parameters;window.surfaceRequests.push({id:message.id,donor:p.donor,contact:p.contact});
   if(window.failNextSurface){window.failNextSurface=false;this.emit({type:'surface_error',id:message.id,error:'synthetic mesh failure'},40);return;}
   const mesh=p.contact?contact():semi(p.donor);window.surfaceMeshes.push(mesh);
   this.emit({type:'surface_result',id:message.id,value:mesh},p.donor==='primary'&&!p.contact?220:70);return;
  }
  if(message.type==='compute'||message.type==='fit'){
   const p=message.payload.parameters,n=p.contact||p.semidetached?129:513;
   const phases=Array.from({length:n},(_,i)=>i/(n-1)-.5),model=phases.map(x=>1-.18*Math.exp(-900*x*x));
   const d=message.payload.dataset,obs=d.y.map(Number),op=d.x.map(x=>((x+.5)%1+1)%1-.5),at=op.map(x=>1-.18*Math.exp(-900*x*x)),res=obs.map((v,i)=>v-at[i]);
   const result={parameters:p,quality:'preview',phases,model,comparison:{phase:op,flux:obs,sigma:d.sigma,model_at_data:at,residual:res,rms:Math.sqrt(res.reduce((s,v)=>s+v*v,0)/res.length),reduced_chi2:null,normalization:1},seconds:.01,engine:'PHOEBE 2.5.4'};
   this.emit({type:'result',id:message.id,operation:message.type,result},20);return;
  }
 }
 terminate(){}
}
window.Worker=DeterministicWorker;
""")
    page.goto(url)
    expect(page.locator("#fit-button")).to_be_enabled(timeout=15000)
    page.locator("#effects summary").click()
    page.locator("#geometry-semi").check()
    page.locator(".orbit-launch").click()
    expect(page.locator("#orbit-shape-note")).to_contain_text("Building the native PHOEBE",timeout=4000)
    page.locator("#orbit-close").click()
    # Change donor before the delayed primary result; the stale mesh must not win.
    page.locator("#donor").select_option("secondary")
    page.locator(".orbit-launch").click()
    expect(page.locator("#orbit-shape-note")).to_contain_text("secondary donor",timeout=12000)
    canvas=page.locator("#orbit-sky")
    before=canvas.evaluate("el=>Array.from(el.getContext('2d').getImageData(0,0,el.width,el.height).data).reduce((s,v)=>s+v,0)")
    page.locator("#orbit-view").select_option("above")
    expect(page.locator("#orbit-inclination")).to_contain_text("Earth direction")
    page.locator("#orbit-phase").evaluate("el=>{el.value='.25';el.dispatchEvent(new Event('input',{bubbles:true}))}")
    after=canvas.evaluate("el=>Array.from(el.getContext('2d').getImageData(0,0,el.width,el.height).data).reduce((s,v)=>s+v,0)")
    assert before!=after
    page.locator("#orbit-close").click()
    page.locator("#geometry-contact").check()
    page.locator(".orbit-launch").click()
    expect(page.locator("#orbit-shape-note")).to_contain_text("connected common-envelope",timeout=12000)
    assert page.evaluate("surfaceMeshes.at(-1).neck") == .5
    page.locator("#orbit-close").click()
    # A relevant contact control rebuilds and exposes an honest error state.
    page.evaluate("failNextSurface=true")
    page.locator('[data-parameter="fillout_factor"] input[type="number"]').fill("0.3")
    page.locator('[data-parameter="fillout_factor"] input[type="number"]').press("Enter")
    page.locator(".orbit-launch").click()
    expect(page.locator("#orbit-shape-note")).to_contain_text("synthetic mesh failure",timeout=12000)
    page.locator("#orbit-close").click()
    assert len(page.evaluate("surfaceRequests"))>=4
    assert not errors,errors
    print("PASS: browser pending/stale/ready/error surfaces, both donors, contact neck, phase/view wiring")
    browser.close()
