export const NATIVE_PROJECT_ERROR='Native PHOEBE project files are intentionally disabled in Colab. Import an observation table or PHOEBE Lab session; exact curves, fits, and surfaces run in this notebook’s Python PHOEBE runtime.';

export const canOpenAdvancedWorkspace=config=>!config;
export const isNativeProjectJson=value=>Array.isArray(value);

export function applyColabWorkerStatus(doc,info){
  const workers=doc.getElementById('surface-workers'),workerRow=workers.closest('label');
  const supported=Math.max(1,Math.floor(Number(info?.supported_workers)||1));
  workers.dataset.supportedWorkers=String(supported);workers.replaceChildren();
  for(let value=1;value<=supported;value++){const option=doc.createElement('option');option.value=option.textContent=String(value);workers.append(option);}
  const recommended=Math.max(1,Math.min(supported,Math.floor(Number(info?.recommended_workers)||1)));
  workers.value=String(recommended);workers.hidden=supported===1;workers.disabled=supported===1;
  const workerValue=doc.getElementById('surface-workers-value');workerValue.hidden=supported>1;
  workerValue.textContent=supported===1?'1 native worker':`${supported} native workers available`;
  const capacity=info?.cpu_capacity||{},usable=Number(capacity.usable_cpu_equivalents),affinity=Number(capacity.affinity_cpus),quota=capacity.cgroup_quota_cpus;
  const detected=Number.isFinite(usable)?`${usable} usable CPU equivalent${usable===1?'':'s'} detected`:'runtime CPU capacity unavailable';
  const limit=Number.isFinite(affinity)?` (${affinity} affinity CPU${affinity===1?'':'s'}${quota==null?'':`, ${quota} quota`})`:'';
  workerRow.querySelector('small').textContent=`${detected}${limit}. Native phase streaming supports ${supported} worker${supported===1?'':'s'}; the fit search itself remains serial, then its final exact curve uses this selection.`;
}

export function applyColabRuntimeUI(doc,config){
  if(!config)return false;
  doc.getElementById('engine-pill').innerHTML='<span class="status-dot loading"></span>Connecting to Colab native engine';
  doc.getElementById('model-status-text').textContent='Connecting to native PHOEBE in this Colab runtime…';
  doc.getElementById('engine-title').textContent='Connecting to native PHOEBE in Colab';
  doc.getElementById('engine-detail').textContent='Exact curves, fits, and surfaces use this notebook’s Python process. Browser WebAssembly fallback is disabled.';
  doc.getElementById('engine-runtime').innerHTML='Calculated by <a href="https://phoebe-project.org/" target="_blank" rel="noreferrer">PHOEBE 2.5.4</a> in this Colab Python runtime';
  doc.querySelector('footer span:last-child').textContent='Uploaded observations stay in this Colab session.';
  const nativeButton=doc.getElementById('native-button');
  nativeButton.disabled=true;nativeButton.title='The separate PHOEBE file workspace is available in the standalone browser build.';
  const windowButton=doc.getElementById('window-button');
  windowButton.disabled=true;windowButton.title='Colab no longer provides a reliable app-only kernel-port window. Fullscreen remains available when the host grants iframe permission.';
  const workers=doc.getElementById('surface-workers'),workerRow=workers.closest('label');
  workers.value='1';workers.dataset.supportedWorkers='1';workers.disabled=true;workers.hidden=true;
  workerRow.querySelector('strong').textContent='Native phase workers';
  workerRow.querySelector('small').textContent='Detecting runtime CPU capacity; native phase streaming currently supports one worker.';
  const workerValue=doc.createElement('span');workerValue.id='surface-workers-value';workerValue.className='mono';workerValue.textContent='1 native worker';workerRow.append(workerValue);
  doc.getElementById('data-file').accept='.csv,.tsv,.txt,.dat,.json';
  doc.querySelector('label[for="data-file"] span:last-of-type').textContent='CSV, TSV, TXT, or PHOEBE Lab session JSON';
  const runtimeGuide=[...doc.querySelectorAll('#guide-dialog p')].find(p=>p.textContent.includes('What is actually running?'));
  if(runtimeGuide)runtimeGuide.innerHTML='<strong>What is actually running?</strong> Instant trained previews and orbit playback run in this browser. Exact light curves, bounded fits, residual statistics and native surface meshes run with PHOEBE 2.5.4 in this Colab notebook’s native Python process. Model CSV and SVG/PDF/PNG figures serialize that completed native result; no exact calculation falls back to browser WebAssembly. Changing geometry or donor supersedes in-progress work and invalidates exact statistics/curve exports; parameter JSON/table remains an explicitly unfitted snapshot until native compute finishes. The standalone page uses the reviewed WebAssembly worker.';
  return true;
}
