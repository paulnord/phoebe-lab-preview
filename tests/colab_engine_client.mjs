import assert from 'node:assert/strict';

globalThis.PHOEBE_COLAB_NATIVE={endpoint:'http://127.0.0.1:9999/_phoebe_native/'};
const calls=[];let failStatus=false,unreachableStatus=false,htmlStatus=false,htmlOperation=null,emptyOperation=null;
const streamResponse=lines=>{
  const bytes=new TextEncoder().encode(lines.join('\n')+'\n');
  return {ok:true,status:200,body:new ReadableStream({start(controller){controller.enqueue(bytes);controller.close();}})};
};
globalThis.fetch=async(url,options={})=>{
  const path=new URL(url).pathname;const body=options.body?JSON.parse(options.body):null;
  calls.push({path,body});
  if(path.endsWith('/status')&&unreachableStatus)throw new TypeError('Failed to fetch');
  if(path.endsWith('/status')&&failStatus)return {ok:false,status:503,json:async()=>({error:'native startup failed'})};
  if(path.endsWith('/stream')&&body?.operation===htmlOperation)return streamResponse(['<html>not json</html>']);
  if(path.endsWith('/status')&&htmlStatus)
    return {ok:true,status:200,json:async()=>{throw new SyntaxError('Unexpected token <');}};
  if(body?.operation===emptyOperation)return {ok:true,status:200,json:async()=>({})};
  if(path.endsWith('/stream')){
    const result={parameters:{inclination:85},phases:[-.5,.5],model:[1,1],native_python:true};
    if(body.payload?.cached)return streamResponse([JSON.stringify({type:'result',result})]);
    if(body.operation==='fit')return streamResponse([
      JSON.stringify({type:'fit_parameters',parameters:{inclination:85}}),
      JSON.stringify({type:'partial',phases:[-.5,.5],model:[1,1],target:2}),
      JSON.stringify({type:'result',result:{...result,fit:{parameters:['inclination']}}}),
    ]);
    return streamResponse([
      JSON.stringify({type:'partial',phases:[-.5,.5],model:[1,1],target:2}),
      JSON.stringify({type:'result',result}),
    ]);
  }
  let value;
  if(path.endsWith('/status'))value={backend:'native-python',version:'2.5.4',runtime:'test-python',
    cpu_capacity:{affinity_cpus:4,cgroup_quota_cpus:2,usable_cpu_equivalents:2},supported_workers:1};
  else if(path.endsWith('/cancel'))value={cancelled:true};
  else if(body.operation==='surface')value={value:{source:'native PHOEBE 2.5.4',geometry:'contact',neck:.1,components:[{name:'primary'},{name:'secondary'}]}};
  else value={result:{parameters:{inclination:85},phases:[-.5,.5],model:[1,1],native_python:true,
    ...(body.operation==='fit'?{fit:{parameters:['inclination']}}:{})}};
  return {ok:true,status:200,json:async()=>value};
};

const {createScientificEngine,nativeKernelConfig}=await import('../site/assets/engine-client.mjs?test=1');
assert.equal(nativeKernelConfig.endpoint,globalThis.PHOEBE_COLAB_NATIVE.endpoint);
const engine=createScientificEngine(new URL('file:///unused-worker.js'));
const messages=[];engine.onmessage=event=>messages.push(event.data);
const flush=()=>new Promise(resolve=>setTimeout(resolve,0));

engine.postMessage({type:'initialize'});await flush();await flush();
assert.equal(messages.at(-1).type,'ready');assert.equal(messages.at(-1).location,'colab-native');
assert.equal(messages.at(-1).cpu_capacity.usable_cpu_equivalents,2);assert.equal(messages.at(-1).supported_workers,1);

engine.postMessage({type:'compute',id:'c1',payload:{mode:'detached'}});await flush();await flush();
assert.equal(messages.at(-1).type,'partial');
engine.postMessage({type:'continue',id:'c1'});await flush();await flush();
assert.equal(messages.at(-1).type,'result');assert.equal(messages.at(-1).result.native_python,true);

engine.postMessage({type:'compute',id:'cached',payload:{cached:true}});await flush();await flush();
assert.equal(messages.at(-1).type,'result');assert.equal(messages.at(-1).id,'cached');

engine.postMessage({type:'fit',id:'f1',payload:{fit:['inclination']}});await flush();await flush();
assert.equal(messages.at(-1).type,'fit_parameters');
engine.postMessage({type:'continue',id:'f1'});await flush();await flush();
assert.equal(messages.at(-1).type,'partial');
engine.postMessage({type:'continue',id:'f1'});await flush();await flush();
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

failStatus=false;unreachableStatus=true;
const unreachable=createScientificEngine(new URL('file:///unused-worker.js'));const unreachableMessages=[];
unreachable.onmessage=event=>unreachableMessages.push(event.data);unreachable.postMessage({type:'initialize'});
await flush();await flush();
assert.equal(unreachableMessages.at(-1).type,'fatal');assert.match(unreachableMessages.at(-1).error,/Failed to fetch/);

unreachableStatus=false;htmlStatus=true;
const htmlStartup=createScientificEngine(new URL('file:///unused-worker.js'));const htmlStartupMessages=[];
htmlStartup.onmessage=event=>htmlStartupMessages.push(event.data);htmlStartup.postMessage({type:'initialize'});
await flush();await flush();
assert.equal(htmlStartupMessages.at(-1).type,'fatal');assert.match(htmlStartupMessages.at(-1).error,/valid JSON/);

htmlStatus=false;htmlOperation='compute';
const malformed=createScientificEngine(new URL('file:///unused-worker.js'));const malformedMessages=[];
malformed.onmessage=event=>malformedMessages.push(event.data);
malformed.postMessage({type:'compute',id:'bad-compute',payload:{mode:'contact'}});
await flush();await flush();
assert.equal(malformedMessages.at(-1).type,'error');assert.match(malformedMessages.at(-1).error,/malformed progressive JSON/);
assert(!malformedMessages.some(message=>message.type==='result'));

htmlOperation=null;emptyOperation='surface';
const incomplete=createScientificEngine(new URL('file:///unused-worker.js'));const incompleteMessages=[];
incomplete.onmessage=event=>incompleteMessages.push(event.data);
incomplete.postMessage({type:'surface',id:'bad-surface',payload:{mode:'contact'}});
await flush();await flush();
assert.equal(incompleteMessages.at(-1).type,'surface_error');assert.match(incompleteMessages.at(-1).error,/invalid surface mesh/);
assert(!incompleteMessages.some(message=>message.type==='surface_result'));

console.log('Colab native engine client: normal flows plus HTTP-error and malformed-success rejection passed');
