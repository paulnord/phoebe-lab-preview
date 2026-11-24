/* Select the scientific transport without changing the shared PHOEBE Lab UI. */
export const nativeKernelConfig = globalThis.PHOEBE_COLAB_NATIVE || null;
export const nativeKernelRequired = Boolean(nativeKernelConfig) || globalThis.PHOEBE_COLAB_NATIVE_REQUIRED===true ||
  globalThis.document?.querySelector?.('meta[name="phoebe-compute-backend"]')?.content==='colab-native-required';

const record=(value,label)=>{
  if(!value || typeof value!=='object' || Array.isArray(value))throw Error(`Native kernel returned an invalid ${label} response.`);
  return value;
};
const finiteArray=value=>Array.isArray(value) && value.length>=2 && value.every(Number.isFinite);
const validateStatus=value=>{
  const info=record(value,'status');
  if(info.backend!=='native-python' || typeof info.version!=='string' || !info.version)throw Error('Native kernel status did not identify the native Python PHOEBE backend.');
  return info;
};
const validateCurve=(value,operation)=>{
  const answer=record(value,operation),result=record(answer.result,`${operation} result`);
  if(result.native_python!==true || !record(result.parameters,`${operation} parameters`) ||
      !finiteArray(result.phases) || !finiteArray(result.model) || result.phases.length!==result.model.length)
    throw Error(`Native kernel returned an incomplete ${operation} result.`);
  if(operation==='fit' && (!result.fit || typeof result.fit!=='object'))throw Error('Native kernel returned a fit result without fit provenance.');
  return result;
};
const validateSurface=value=>{
  const answer=record(value,'surface'),surface=record(answer.value,'surface mesh');
  if(!['semi','contact'].includes(surface.geometry) || !Array.isArray(surface.components) || surface.components.length!==2 ||
      typeof surface.source!=='string' || !surface.source.startsWith('native PHOEBE'))
    throw Error('Native kernel returned an incomplete surface mesh.');
  return surface;
};

class ColabNativeEngine {
  constructor(config) {
    this.config=config;this.onmessage=null;this.onerror=null;this.controllers=new Map();this.gates=new Map();
  }
  emit(data){queueMicrotask(()=>this.onmessage?.({data}));}
  async request(path,body=null,controller=null){
    const response=await fetch(new URL(path,this.config.endpoint),{
      method:body===null?'GET':'POST',headers:body===null?{}:{'Content-Type':'application/json'},
      body:body===null?null:JSON.stringify(body),signal:controller?.signal,
    });
    let value;
    try{value=await response.json();}
    catch{throw Error(`Native kernel returned HTTP ${response.status} without a valid JSON response.`);}
    if(!response.ok)throw Error(value.error||`Native kernel returned HTTP ${response.status}.`);
    return record(value,'JSON');
  }
  cancel(id){
    this.controllers.get(id)?.abort();this.controllers.delete(id);
    this.gates.get(id)?.();this.gates.delete(id);
    this.request('cancel',{id}).catch(()=>{});
  }
  terminate(){for(const id of [...this.controllers.keys()])this.cancel(id);}
  pause(id){return new Promise(resolve=>this.gates.set(id,resolve));}
  continue(id){const resolve=this.gates.get(id);if(resolve){this.gates.delete(id);resolve();}}
  async stream(data,controller){
    const response=await fetch(new URL('stream',this.config.endpoint),{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({id:data.id,operation:data.type,payload:data.payload}),signal:controller.signal,
    });
    if(!response.ok)throw Error(`Native kernel returned HTTP ${response.status}.`);
    if(!response.body?.getReader)throw Error('Native kernel did not provide a progressive response stream.');
    const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='',completed=false;
    const consume=async line=>{
      if(!line.trim())return;
      let update;try{update=JSON.parse(line);}catch{throw Error('Native kernel returned malformed progressive JSON.');}
      record(update,'progressive update');
      if(update.type==='error')throw Error(update.error||'Native progressive calculation failed.');
      if(update.type==='fit_parameters'){
        const parameters=record(update.parameters,'fit parameters');
        this.emit({type:'fit_parameters',id:data.id,parameters});await this.pause(data.id);return;
      }
      if(update.type==='partial'){
        if(!finiteArray(update.phases)||!finiteArray(update.model)||update.phases.length!==update.model.length)
          throw Error('Native kernel returned an incomplete partial curve.');
        this.emit({...update,id:data.id,operation:data.type});await this.pause(data.id);return;
      }
      if(update.type==='progress'){this.emit({...update,id:data.id});return;}
      if(update.type==='result'){
        this.emit({type:'result',id:data.id,operation:data.type,result:validateCurve({result:update.result},data.type)});completed=true;return;
      }
      throw Error(`Native kernel returned an unknown progressive update: ${update.type}.`);
    };
    while(true){
      const {value,done}=await reader.read();buffer+=decoder.decode(value||new Uint8Array(),{stream:!done});
      const lines=buffer.split('\n');buffer=lines.pop();for(const line of lines)await consume(line);
      if(done)break;
    }
    if(buffer.trim())await consume(buffer);
    if(!completed)throw Error('Native progressive response ended without a final result.');
  }
  postMessage(data){
    if(data.type==='initialize'){
      this.emit({type:'status',title:'Connecting to Colab Python',detail:'Exact PHOEBE work runs in this notebook runtime, not in browser WebAssembly.'});
      this.request('status').then(validateStatus).then(info=>this.emit({type:'ready',version:info.version,location:'colab-native',runtime:info.runtime}))
        .catch(error=>this.emit({type:'fatal',error:String(error)}));return;
    }
    if(data.type==='release'){this.cancel(data.id);return;}
    if(data.type==='continue'){this.continue(data.id);return;}
    if(!['compute','fit','surface'].includes(data.type))return;
    const controller=new AbortController();this.controllers.set(data.id,controller);
    this.emit({type:'progress',id:data.id,stage:data.type==='fit'?'Fitting with native PHOEBE in Colab…':'Running native PHOEBE in Colab…'});
    const operation=data.type==='surface'
      ? this.request('run',{id:data.id,operation:data.type,payload:data.payload},controller)
      : this.stream(data,controller);
    operation.then(answer=>{
      this.controllers.delete(data.id);
      if(data.type==='surface')this.emit({type:'surface_result',id:data.id,value:validateSurface(answer)});
    }).catch(error=>{
      this.controllers.delete(data.id);
      if(error?.name==='AbortError')return;
      this.emit({type:data.type==='surface'?'surface_error':'error',id:data.id,error:String(error)});
    });
  }
}

class MissingColabNativeEngine {
  constructor(){this.onmessage=null;this.onerror=null;}
  emit(data){queueMicrotask(()=>this.onmessage?.({data}));}
  postMessage(data){
    const error='The Colab native PHOEBE bridge is missing. Exact compute and fit are disabled; browser WebAssembly fallback is forbidden in Colab.';
    if(data.type==='initialize')this.emit({type:'fatal',error});
    else if(['compute','fit'].includes(data.type))this.emit({type:'error',id:data.id,error});
    else if(data.type==='surface')this.emit({type:'surface_error',id:data.id,error});
  }
  terminate(){}
}

export function createScientificEngine(workerURL){
  if(nativeKernelConfig)return new ColabNativeEngine(nativeKernelConfig);
  if(nativeKernelRequired)return new MissingColabNativeEngine();
  return new Worker(workerURL,{type:'module'});
}
