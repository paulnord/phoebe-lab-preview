"""Benchmark a custom 513-phase Roche curve through the browser UI; resume by count."""
import argparse
import json
import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright


def memory_mib():
    """Whole Chromium process group, including browser libraries, measured as summed PSS."""
    if not Path('/proc/self/smaps_rollup').is_file():
        return None
    parents = {}
    for stat in Path('/proc').glob('[0-9]*/stat'):
        try:
            parents[int(stat.parent.name)] = int(stat.read_text().rsplit(')', 1)[1].split()[1])
        except (OSError, IndexError, ValueError):
            continue
    family = {os.getpid()}
    while True:
        added = {pid for pid, parent in parents.items() if parent in family} - family
        if not added:
            break
        family |= added
    kb = 0
    for pid in family - {os.getpid()}:
        try:
            lines = Path(f'/proc/{pid}/smaps_rollup').read_text().splitlines()
            kb += int(next(s for s in lines if s.startswith('Pss:')).split()[1])
        except (OSError, StopIteration):
            continue
    return round(kb / 1024)


def run(pw, url, count):
    browser = pw.chromium.launch()
    try:
        page = browser.new_page()
        page.goto(url)
        page.locator('#export-button:enabled').wait_for(timeout=180000)
        page.locator('#effects summary').click()
        if count != 1 or page.locator('#surface-workers').count():
            page.locator('#surface-workers').select_option(str(count))
        # Listen to worker messages before the first custom request; the opening curve is excluded.
        page.evaluate("""()=>{
          window.sample={events:[],start:0};
          const original=Worker.prototype.postMessage;
          const watched=new WeakSet();
          Worker.prototype.postMessage=function(d,...rest){
            if(d.type==='compute' && d.payload.parameters.distortion){
              sample.start=performance.now();
              if(!watched.has(this)){
                watched.add(this);
                this.addEventListener('message',({data:m})=>{
                  const t=(performance.now()-sample.start)/1000;
                  if(m.type==='partial')sample.events.push([m.phases.length,t]);
                  if(m.type==='result'){sample.events.push([m.result.phases.length,t]);sample.result=m.result;}
                  if(m.type==='error'||m.type==='fatal')sample.error=m.error;
                });
              }
            }
            return original.call(this,d,...rest);
          };
          const el=document.querySelector('#range-inclination');
          el.value='83.7';el.dispatchEvent(new Event('input'));
          document.querySelector('#distortion').click();
        }""")
        base = peak = memory_mib()
        deadline = time.monotonic() + 2400
        while time.monotonic() < deadline:
            page.wait_for_timeout(3000)
            memory = memory_mib()
            if memory is not None:
                peak = max(peak or 0, memory)
            if page.evaluate('Boolean(sample.result || sample.error)'):
                break
        sample = page.evaluate('sample')
        if 'result' not in sample:
            raise RuntimeError(str(sample))
        assert sample['events'][0][0] == 5 and sample['events'][-1][0] == 513
        assert sample['result']['parameters']['inclination'] == 83.7
        assert sample['result'].get('source') != 'stored_exact'
        assert len(sample['result']['model']) == 513
        if count > 1:
            assert sample['result']['surface_workers'] == count
        assert not page.locator('#export-button').is_disabled()
        return dict(workers=count, browser=browser.version, affinity=sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
                    initial_pss_mib=base, sampled_peak_pss_mib=peak, **sample)
    finally:
        browser.close()


def summarize(output):
    baseline = json.loads((output / 'workers-1.json').read_text())
    reference = baseline['result']
    rows = []
    for path in sorted(output.glob('workers-*.json')):
        record = json.loads(path.read_text())
        result = record['result']
        assert reference['parameters'] == result['parameters'] and reference['quality'] == result['quality']
        assert reference['phases'] == result['phases'] and record['events'][0][0] == 5
        assert reference['engine'] == result['engine'] and baseline['browser'] == record['browser']
        errors = [abs(a-b) for a,b in zip(reference['model'], result['model'], strict=True)]
        residual_errors = [abs(a-b) for a,b in zip(reference['comparison']['residual'],
                                                    result['comparison']['residual'], strict=True)]
        assert max(errors) < 1e-10 and max(residual_errors) < 1e-10
        seconds = record['events'][-1][1]
        rows.append(dict(workers=record['workers'], first_seconds=record['events'][0][1], seconds=seconds,
                         speedup=baseline['events'][-1][1]/seconds, sampled_peak_pss_mib=record['sampled_peak_pss_mib'],
                         maximum_flux_difference=max(errors), rms_flux_difference=(sum(e*e for e in errors)/len(errors))**.5,
                         maximum_residual_difference=max(residual_errors)))
    return dict(chromium=baseline['browser'], engine=reference['engine'], parameters=reference['parameters'],
                quality=reference['quality'], phases=len(reference['phases']), rows=rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url')
    parser.add_argument('output', type=Path)
    parser.add_argument('counts', type=int, choices=range(1,9), nargs='*')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if not args.counts:
        print(json.dumps(summarize(args.output), indent=2))
        raise SystemExit
    with sync_playwright() as pw:
        for count in args.counts:
            dest = args.output / f'workers-{count}.json'
            if dest.exists():
                continue
            print(f'Starting {count} worker(s)', flush=True)
            record = run(pw, args.url, count)
            tmp = dest.with_suffix('.tmp')
            tmp.write_text(json.dumps(record, allow_nan=False))
            tmp.replace(dest)
            print(count, record['events'][0], record['events'][-1], record['sampled_peak_pss_mib'], flush=True)
