/* Select the scientific transport without changing the shared PHOEBE Lab UI. */
export const nativeKernelConfig = globalThis.PHOEBE_COLAB_NATIVE || null;

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
    this.config=config;this.onmessage=null;this.onerror=null;this.controllers=new Map();this.fitResults=new Map();
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
    this.controllers.get(id)?.abort();this.controllers.delete(id);this.fitResults.delete(id);
    this.request('cancel',{id}).catch(()=>{});
  }
  terminate(){for(const id of [...this.controllers.keys()])this.cancel(id);}
  postMessage(data){
    if(data.type==='initialize'){
      this.emit({type:'status',title:'Connecting to Colab Python',detail:'Exact PHOEBE work runs in this notebook runtime, not in browser WebAssembly.'});
      this.request('status').then(validateStatus).then(info=>this.emit({type:'ready',version:info.version,location:'colab-native',runtime:info.runtime}))
        .catch(error=>this.emit({type:'fatal',error:String(error)}));return;
    }
    if(data.type==='release'){this.cancel(data.id);return;}
    if(data.type==='continue'){
      const result=this.fitResults.get(data.id);if(!result)return;
      this.fitResults.delete(data.id);this.emit({type:'result',id:data.id,operation:'fit',result});return;
    }
    if(!['compute','fit','surface'].includes(data.type))return;
    const controller=new AbortController();this.controllers.set(data.id,controller);
    this.emit({type:'progress',id:data.id,stage:data.type==='fit'?'Fitting with native PHOEBE in Colab…':'Running native PHOEBE in Colab…'});
    this.request('run',{id:data.id,operation:data.type,payload:data.payload},controller).then(answer=>{
      this.controllers.delete(data.id);
      if(data.type==='surface')this.emit({type:'surface_result',id:data.id,value:validateSurface(answer)});
      else if(data.type==='fit'){
        const result=validateCurve(answer,'fit');this.fitResults.set(data.id,result);
        this.emit({type:'fit_parameters',id:data.id,parameters:result.parameters});
      }else this.emit({type:'result',id:data.id,operation:'compute',result:validateCurve(answer,'compute')});
    }).catch(error=>{
      this.controllers.delete(data.id);
      if(error?.name==='AbortError')return;
      this.emit({type:data.type==='surface'?'surface_error':'error',id:data.id,error:String(error)});
    });
  }
}

export function createScientificEngine(workerURL){
  return nativeKernelConfig ? new ColabNativeEngine(nativeKernelConfig) : new Worker(workerURL,{type:'module'});
}
