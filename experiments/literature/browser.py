"""Benchmark the exported predictor and test drag, stale requests and exact CSV in Chromium."""

import json
import sys
from common import TREE, OUT, save, status
import time
import numpy as np
from playwright.sync_api import sync_playwright, expect, TimeoutError as PlaywrightTimeout
from archive import study_rows


def main(url):
    rows = {r["system"]: r for r in study_rows()}
    inputs = []
    expected = []
    specs = json.loads((TREE / "site/experiment/surface.json").read_text())
    for family in ("surface", "eccentric"):
        if not json.loads((OUT / (family + "-test.json")).read_text())["accepted"]:
            continue
        d = np.load(OUT / (family + "-predictions.npz"))
        for i, key in enumerate(d["ids"]):
            for j, mode in enumerate(["tides", "heat", "both"]):
                p = dict(
                    rows[str(key)]["parameters"],
                    distortion=mode != "heat",
                    irradiation=mode != "tides",
                )
                inputs.append(p)
                expected.append(d["pred"][i, j].tolist())
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 980}, accept_downloads=True)
        page.add_init_script("""{ const WorkerClass=Worker;
          window.sends=[];window.results=[];window.partial=[];
          window.Worker=class extends WorkerClass {
            constructor(...a){super(...a);this.addEventListener('message',({data})=>{
              if(data.type==='result')results.push(data.result);
              if(data.type==='partial')partial.push(data.id);
            });}
            postMessage(d,...a){if(d.type==='compute')sends.push(d.id);super.postMessage(d,...a);}
          };
          const stroke=CanvasRenderingContext2D.prototype.stroke;
          CanvasRenderingContext2D.prototype.stroke=function(...a){
            if(this.canvas.id==='light-curve' && this.lineWidth===14)window.fuzzy={color:this.strokeStyle,alpha:this.globalAlpha};
            return stroke.apply(this,a);
          };
        }""")
        page.goto(url)
        bench = page.evaluate(
            """async ([inputs,expected])=>{
          const {makeDiscModel}=await import('./experiment/discs.mjs');
          const {makeSurfacePredictor}=await import('./experiment/surface_predict.mjs');
          const get=async n=>(await fetch('./experiment/'+n+'.json')).json();
          const s=await get('display-model');
          const predict=makeSurfacePredictor(await get('surface'),makeDiscModel(s.table,s.n,s.fixed));
          let max=0,sum=0;
          inputs.forEach((p,i)=>{
            const c=predict(p);
            if(!c?.surfaceMode || c.model[0]!==c.model[256])throw Error('prediction or seam');
            expected[i].forEach((y,j)=>max=Math.max(max,Math.abs(y-c.model[j])));
          });
          if(!(max<1e-6))throw Error('parity '+max);
          const p=inputs[0];
          for(const change of [{period:p.period+.01},{epoch:1},{distortion:false,irradiation:false},{inclination:-.1}])
            if(predict({...p,...change})!==null)throw Error('unsupported input produced a curve');
          const times=[];
          for(let k=-5;k<40;k++){
            const t=performance.now();
            for(let j=0;j<40;j++)sum+=predict(inputs[((k+5)*40+j)%inputs.length]).model[120];
            if(k>=0)times.push((performance.now()-t)/40);
          }
          times.sort((a,b)=>a-b);
          return {n:inputs.length,parity:max,median_ms:times[20],p95_ms:times[37],checksum:sum};
        }""",
            [inputs, expected],
        )
        export = page.locator("#export-button")
        expect(export).to_be_enabled(timeout=180000)
        page.locator("#effects summary").click()
        # Put the measured eccentric slice or the tested circular slice on the main lab.
        prefer = next((s for s in specs if s["dims"] == ["inclination"]), specs[0])
        fixed = prefer["fixed"]
        inc = page.locator("#range-inclination")

        def set_slider(key, v):
            page.locator("#range-" + key).evaluate(
                "(s,v)=>{s.value=v;s.dispatchEvent(new Event('input'));}", v
            )

        inc.dispatch_event("pointerdown")
        for k, v in fixed.items():
            set_slider(k, v)
        if "radius_primary" not in fixed:
            set_slider("radius_primary", 0.21)
        first = 30.0
        set_slider("inclination", first)
        for toggle in ("distortion", "irradiation"):
            page.locator("#" + toggle).evaluate(
                "el=>{el.checked=true;el.dispatchEvent(new Event('change'));}"
            )
        legend = page.locator(".chart-legend")
        expect(legend).to_contain_text("Approximate surface preview · tides and heating")
        expect(page.locator("#rms-stat")).to_have_text("—")
        expect(page.locator("#fit-button")).to_be_disabled()
        expect(export).to_be_disabled()
        assert page.evaluate("fuzzy.color==='#b56a08' && fuzzy.alpha<.5")
        count = page.evaluate("sends.length")
        page.wait_for_timeout(650)
        assert page.evaluate("sends.length") == count
        page.locator("#light-curve").screenshot(path=OUT / "fuzzy.png")
        inc.dispatch_event("pointerup")
        page.wait_for_function("n=>sends.length>n", arg=count, timeout=10000)
        # A newer drag must invalidate the first request.
        inc.dispatch_event("pointerdown")
        set_slider("inclination", first + 1.2)
        expect(export).to_be_disabled()
        inc.dispatch_event("pointerup")
        start = time.monotonic()
        # Surface wall time depends strongly on host load. Keep the last exact
        # phase count available if the browser stalls during a long release.
        while not export.is_enabled():
            elapsed = time.monotonic() - start
            print(round(elapsed, 1), page.locator("#model-status").inner_text(), flush=True)
            if elapsed > 900:
                raise TimeoutError("Exact surface release exceeded 15 minutes")
            try:
                page.wait_for_function(
                    "!document.querySelector('#export-button').disabled", timeout=3000
                )
            except PlaywrightTimeout:
                pass

        expect(legend).to_contain_text("PHOEBE model")
        last = page.evaluate("results.at(-1)")
        assert last["parameters"]["inclination"] == first + 1.2
        assert all(last["parameters"][k] for k in ("distortion", "irradiation"))
        with page.expect_download() as download:
            export.click()
        data = download.value.path().read_text().splitlines()
        assert [float(line.split(",")[1]) for line in data[1:]] == last["model"]
        bench.update(
            browser=browser.version,
            engine=last["engine"],
            release_seconds=time.monotonic() - start,
            phases=len(last["model"]),
            fuzzy=page.evaluate("fuzzy"),
            held_requests=0,
            stale_guard=True,
            csv_parity=True,
        )
        save(OUT / "browser.json", bench)
        example = browser.new_page(viewport={"width": 1370, "height": 960})
        example.goto(url.rstrip("/") + "/?example=non-eclipsing")
        expect(example.locator("#dataset-name")).to_contain_text("Non-eclipsing")
        slider = example.locator("#range-inclination")
        slider.dispatch_event("pointerdown")
        slider.evaluate("s=>{s.value=30;s.dispatchEvent(new Event('input'));}")
        example.locator("#irradiation").evaluate(
            "s=>{s.checked=true;s.dispatchEvent(new Event('change'));}"
        )
        expect(example.locator(".chart-legend")).to_contain_text(
            "Approximate surface preview · tides and heating"
        )
        example.locator("#light-curve").screenshot(path=OUT / "example-preview.png")
        example.close()
        status(
            "Chromium parity, fuzzy line, held drag, superseded request and exact CSV verified."
        )


if __name__ == "__main__":
    main(sys.argv[1])
