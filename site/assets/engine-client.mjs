/* Select the scientific transport without changing the shared PHOEBE Lab UI. */
export const nativeKernelConfig = globalThis.PHOEBE_COLAB_NATIVE || null;

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
    const value=await response.json().catch(()=>({error:`Native kernel returned HTTP ${response.status}.`}));
    if(!response.ok)throw Error(value.error||`Native kernel returned HTTP ${response.status}.`);
    return value;
  }
  cancel(id){
    this.controllers.get(id)?.abort();this.controllers.delete(id);this.fitResults.delete(id);
    this.request('cancel',{id}).catch(()=>{});
  }
  terminate(){for(const id of [...this.controllers.keys()])this.cancel(id);}
  postMessage(data){
    if(data.type==='initialize'){
      this.emit({type:'status',title:'Connecting to Colab Python',detail:'Exact PHOEBE work runs in this notebook runtime, not in browser WebAssembly.'});
      this.request('status').then(info=>this.emit({type:'ready',version:info.version,location:'colab-native',runtime:info.runtime}))
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
      if(data.type==='surface')this.emit({type:'surface_result',id:data.id,value:answer.value});
      else if(data.type==='fit'){
        this.fitResults.set(data.id,answer.result);
        this.emit({type:'fit_parameters',id:data.id,parameters:answer.result.parameters});
      }else this.emit({type:'result',id:data.id,operation:'compute',result:answer.result});
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
