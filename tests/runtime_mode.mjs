import assert from 'node:assert/strict';
import {applyColabRuntimeUI,applyColabWorkerStatus,canOpenAdvancedWorkspace,isNativeProjectJson,NATIVE_PROJECT_ERROR} from '../site/assets/runtime-mode.mjs';

const workerSmall={textContent:''},workerStrong={textContent:''};
let elements;
const workerRow={querySelector:selector=>selector==='small'?workerSmall:workerStrong,
  append:child=>elements.set(child.id,child)};
const workers={value:'8',disabled:false,hidden:false,dataset:{},children:[],closest:()=>workerRow,
  replaceChildren(){this.children=[];},append(child){this.children.push(child);}};
elements=new Map([
  ['engine-pill',{}],['model-status-text',{}],['engine-title',{}],['engine-detail',{}],
  ['engine-runtime',{}],['engine-environment',{hidden:true,textContent:'',title:''}],['native-button',{disabled:false,title:''}],['window-button',{disabled:false,title:''}],
  ['surface-workers',workers],['data-file',{accept:'.phoebe'}],
]);
const footer={textContent:'browser'};const formats={textContent:'native files'};
const guide={textContent:'What is actually running? Browser WebAssembly.',innerHTML:''};
const doc={
  getElementById:id=>elements.get(id),
  createElement:tag=>({tag,hidden:false,textContent:'',className:'',id:'',value:''}),
  querySelector:selector=>selector==='footer span:last-child'?footer:selector.startsWith('label[')?formats:formats,
  querySelectorAll:selector=>selector==='#guide-dialog p'?[guide]:[],
};

assert.equal(applyColabRuntimeUI(doc,{endpoint:'native'}),true);
assert.match(elements.get('engine-pill').innerHTML,/Colab native engine/);
assert.match(elements.get('model-status-text').textContent,/native PHOEBE/);
assert.match(elements.get('engine-title').textContent,/native PHOEBE in Colab/);
assert.match(elements.get('engine-detail').textContent,/fallback is disabled/);
assert.match(elements.get('engine-runtime').innerHTML,/Colab Python runtime/);
assert.equal(elements.get('native-button').disabled,true);
assert.equal(elements.get('data-file').accept,'.csv,.tsv,.txt,.dat,.json');
assert.match(formats.textContent,/PHOEBE Lab session JSON/);
assert.match(guide.innerHTML,/native Python process/);
assert.equal(footer.textContent,'Uploaded observations stay in this Colab session.');
assert.equal(workers.hidden,true);assert.equal(workers.disabled,true);

const environment={python:'3.12.0',phoebe:'2.5.4',numpy:'2.0.2',scipy:'1.15.3',astropy:'7.1.0',matplotlib:'3.11.2',passband:'Johnson:V',passband_sha256:'abcdef1234567890',passband_bytes:14719680};
applyColabWorkerStatus(doc,{environment,cpu_capacity:{affinity_cpus:8,cgroup_quota_cpus:2.5,usable_cpu_equivalents:2.5},supported_workers:1});
assert.equal(workers.dataset.supportedWorkers,'1');assert.equal(workers.children.length,1);
assert.match(workerSmall.textContent,/2.5 usable CPU equivalents detected/);assert.match(workerSmall.textContent,/supports 1 worker/);
assert.equal(elements.get('engine-environment').hidden,false);assert.match(elements.get('engine-environment').textContent,/NumPy 2.0.2/);
assert.match(elements.get('engine-environment').title,/abcdef1234567890/);
applyColabWorkerStatus(doc,{environment,cpu_capacity:{affinity_cpus:8,cgroup_quota_cpus:4,usable_cpu_equivalents:4},supported_workers:4,recommended_workers:4});
assert.equal(workers.dataset.supportedWorkers,'4');assert.equal(workers.children.length,4);
assert.equal(workers.value,'4');assert.equal(workers.hidden,false);assert.equal(workers.disabled,false);
assert.match(workerSmall.textContent,/fit search itself remains serial/);

const untouched={getElementById:()=>{throw Error('standalone DOM must remain untouched');}};
assert.equal(applyColabRuntimeUI(untouched,null),false);
assert.equal(canOpenAdvancedWorkspace(null),true);
assert.equal(canOpenAdvancedWorkspace({endpoint:'native'}),false);
assert.equal(isNativeProjectJson([]),true);
assert.equal(isNativeProjectJson({schema:'phoebe-lab-session-v1'}),false);
assert.match(NATIVE_PROJECT_ERROR,/disabled in Colab/);
console.log('Runtime mode: immediate Colab UI, failed-safe imports, standalone branch passed');
