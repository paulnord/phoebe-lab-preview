import assert from 'node:assert/strict';

globalThis.PHOEBE_COLAB_NATIVE_REQUIRED=true;
let workerConstructions=0;
globalThis.Worker=class {constructor(){workerConstructions++;}};

const {createScientificEngine,nativeKernelConfig,nativeKernelRequired}=await import('../site/assets/engine-client.mjs?missing-bridge=1');
assert.equal(nativeKernelConfig,null);
assert.equal(nativeKernelRequired,true);
const engine=createScientificEngine(new URL('file:///browser-worker-must-not-start.js'));
const messages=[];engine.onmessage=event=>messages.push(event.data);
const flush=()=>new Promise(resolve=>setTimeout(resolve,0));

engine.postMessage({type:'initialize'});await flush();
assert.equal(messages.at(-1).type,'fatal');
assert.match(messages.at(-1).error,/fallback is forbidden/);
engine.postMessage({type:'compute',id:'compute-denied',payload:{}});await flush();
assert.equal(messages.at(-1).type,'error');
engine.postMessage({type:'fit',id:'fit-denied',payload:{}});await flush();
assert.equal(messages.at(-1).type,'error');
assert.equal(workerConstructions,0,'Colab-required mode must never construct a browser Worker');
assert(!messages.some(message=>message.type==='ready'||message.type==='result'));
console.log('Colab missing bridge fails closed for compute and fit without constructing browser WebAssembly');
