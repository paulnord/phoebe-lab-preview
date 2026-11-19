import sys
from common import OUT, save, status
from playwright.sync_api import sync_playwright


def main(url):
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto(url)
        page.wait_for_function("document.querySelector('#stat').textContent.length>0")
        result = page.evaluate("""async ()=>{
          const {makeWide}=await import('./wide_predict.mjs');
          const [spec,table,rows]=await Promise.all(['model','table','cases'].map(async n=>(await fetch(n+'.json')).json()));
          const predict=makeWide(spec,table,rows);
          let max=0,sum=0;
          for(const r of rows){
            const y=predict(r.id);
            r.expected.forEach((v,j)=>max=Math.max(max,Math.abs(v-y[j])));
          }
          if(predict('unscored')!==null || !(max<1e-6))throw Error('wide parity '+max);
          const ms=[];
          for(let k=-4;k<30;k++){
            const t=performance.now();
            for(let j=0;j<32;j++)sum+=predict(rows[((k+4)*32+j)%rows.length].id)[123];
            if(k>=0)ms.push((performance.now()-t)/32);
          }
          ms.sort((a,b)=>a-b);
          return {n:rows.length,max,median_ms:ms[15],p95_ms:ms[28],sum};
        }""")
        result["browser"] = browser.version
        save(OUT / "wide-browser.json", result)
        status("Wider browser viewer verified against held-out Python predictions.")


if __name__ == "__main__":
    main(sys.argv[1])
