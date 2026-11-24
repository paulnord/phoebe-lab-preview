import assert from 'node:assert/strict';

globalThis.PHOEBE_COLAB_NATIVE={endpoint:'http://127.0.0.1:9999/_phoebe_native/'};
const calls=[];let failStatus=false;
globalThis.fetch=async(url,options={})=>{
  const path=new URL(url).pathname;const body=options.body?JSON.parse(options.body):null;
  calls.push({path,body});
  if(path.endsWith('/status')&&failStatus)return {ok:false,status:503,json:async()=>({error:'native startup failed'})};
  let value;
  if(path.endsWith('/status'))value={version:'2.5.4',runtime:'test-python'};
  else if(path.endsWith('/cancel'))value={cancelled:true};
  else if(body.operation==='surface')value={value:{geometry:'contact',neck:.1}};
  else value={result:{parameters:{inclination:85},phases:[-.5,.5],model:[1,1],native_python:true}};
  return {ok:true,status:200,json:async()=>value};
};

const {createScientificEngine,nativeKernelConfig}=await import('../site/assets/engine-client.mjs?test=1');
assert.equal(nativeKernelConfig.endpoint,globalThis.PHOEBE_COLAB_NATIVE.endpoint);
const engine=createScientificEngine(new URL('file:///unused-worker.js'));
const messages=[];engine.onmessage=event=>messages.push(event.data);
const flush=()=>new Promise(resolve=>setTimeout(resolve,0));

engine.postMessage({type:'initialize'});await flush();await flush();
assert.equal(messages.at(-1).type,'ready');assert.equal(messages.at(-1).location,'colab-native');

engine.postMessage({type:'compute',id:'c1',payload:{mode:'detached'}});await flush();await flush();
assert.equal(messages.at(-1).type,'result');assert.equal(messages.at(-1).result.native_python,true);

engine.postMessage({type:'fit',id:'f1',payload:{fit:['inclination']}});await flush();await flush();
assert.equal(messages.at(-1).type,'fit_parameters');
engine.postMessage({type:'continue',id:'f1'});await flush();
assert.equal(messages.at(-1).type,'result');assert.equal(messages.at(-1).operation,'fit');

engine.postMessage({type:'surface',id:'s1',payload:{mode:'contact'}});await flush();await flush();
assert.equal(messages.at(-1).type,'surface_result');assert.equal(messages.at(-1).value.geometry,'contact');

engine.postMessage({type:'compute',id:'cancel-me',payload:{}});engine.postMessage({type:'release',id:'cancel-me'});
await flush();await flush();
assert(calls.some(call=>call.path.endsWith('/cancel')&&call.body.id==='cancel-me'));

failStatus=true;
const failed=createScientificEngine(new URL('file:///unused-worker.js'));const failedMessages=[];
failed.onmessage=event=>failedMessages.push(event.data);failed.postMessage({type:'initialize'});
await flush();await flush();
assert.equal(failedMessages.at(-1).type,'fatal');assert.match(failedMessages.at(-1).error,/native startup failed/);

console.log('Colab native engine client: initialize, failed startup, compute, fit handshake, surface, cancel passed');
