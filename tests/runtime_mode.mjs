import assert from 'node:assert/strict';
import {applyColabRuntimeUI,canOpenAdvancedWorkspace,isNativeProjectJson,NATIVE_PROJECT_ERROR} from '../site/assets/runtime-mode.mjs';

const elements=new Map([
  ['engine-pill',{}],['model-status-text',{}],['engine-title',{}],['engine-detail',{}],
  ['engine-runtime',{}],['native-button',{disabled:false,title:''}],['data-file',{accept:'.phoebe'}],
]);
const footer={textContent:'browser'};const formats={textContent:'native files'};
const guide={textContent:'What is actually running? Browser WebAssembly.',innerHTML:''};
const doc={
  getElementById:id=>elements.get(id),
  querySelector:selector=>selector==='footer span:last-child'?footer:formats,
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

const untouched={getElementById:()=>{throw Error('standalone DOM must remain untouched');}};
assert.equal(applyColabRuntimeUI(untouched,null),false);
assert.equal(canOpenAdvancedWorkspace(null),true);
assert.equal(canOpenAdvancedWorkspace({endpoint:'native'}),false);
assert.equal(isNativeProjectJson([]),true);
assert.equal(isNativeProjectJson({schema:'phoebe-lab-session-v1'}),false);
assert.match(NATIVE_PROJECT_ERROR,/disabled in Colab/);
console.log('Runtime mode: immediate Colab UI, failed-safe imports, standalone branch passed');
