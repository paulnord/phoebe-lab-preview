import {bindAdvanced} from './advanced.js?v=6e6a2f6ebc7d6f09';
// Native documents have their own PHOEBE worker and never enter the fitting or preview cache.
export function bindNativeFiles(labSnapshot) {
  const el=id=>document.getElementById('native-'+id);
  const dialog=el('dialog');
  const names={period:'Period (days)',incl:'Inclination (°)',ecc:'Eccentricity',per0:'Periastron angle (°)'};
  let worker=null, loading=null, pending=null, busy=false, id=0;
  let doc=null, series=[], fileName='', attach=false;
  let backup=null,restore=null;
  const advanced=bindAdvanced(call,action,meta=>render(meta,fileName));
  function status(text,error=false) {
    el('status').textContent=text;
    el('status').setAttribute('aria-invalid',String(error));
  }
  function controls() {
    for(const control of dialog.querySelectorAll('button:not(.close-dialog), select, input, textarea')) control.disabled=busy;
    advanced.controls(busy);
    el('run').disabled=busy||!doc?.computes.length;
    el('save-model').disabled=busy||!doc?.models.length;
    for(const input of el('orbit-fields').querySelectorAll('input')) input.disabled=busy||input.dataset.editable!=='true';
  }
  function engine() {
    if(loading)return loading;
    const w=new Worker(new URL('./engine.worker.js?v=e43073184c605efc',import.meta.url),{type:'module'});
    worker=w;
    loading=new Promise((resolve,reject)=>{
      function failed(message) {
        if(worker!==w)return;
        worker=null;loading=null;
        reject(Error(message));pending?.reject(Error(message));pending=null;
        w.terminate();doc=null;series=[];el('document').hidden=true;
      }
      w.onerror=e=>failed(e.message||'The file worker stopped.');
      w.onmessage=({data})=>{
        if(data.type==='ready')resolve();
        if(data.type==='status')status(data.title);
        if(data.type==='fatal')failed(data.error);
        if(!pending||data.id!==pending.id)return;
        if(data.type==='native_result'){pending.resolve(data.value);pending=null;}
        if(data.type==='error'){pending.reject(Error(data.error));pending=null;}
      };
      w.postMessage({type:'initialize',nativeFiles:true});
    });
    return loading;
  }
  function send(operation,payload) {
    return new Promise((resolve,reject)=>{
      pending={id:++id,resolve,reject};worker.postMessage({type:'native',id,operation,payload});
    });
  }
  async function call(operation,payload={}) {
    await engine();
    if(restore){
      await send('open',{text:restore});
      restore=null;
    }
    if(operation!=='compute' && operation!=='solve')return send(operation,payload);
    backup=await send('save_bundle',{});
    el('cancel').hidden=false;el('cancel').disabled=false;
    try{return await send(operation,payload);}
    finally{el('cancel').hidden=true;backup=null;}
  }
  el('cancel').onclick=()=>{
    if(!backup||!pending)return;
    restore=backup;
    worker.terminate();worker=null;loading=null;
    pending.reject(Error('Stopped. The previous bundle is available.'));pending=null;
  };
  async function action(message,fn) {
    if(busy)return;
    busy=true;controls();status(message);
    try {await fn();}
    catch(error){status(String(error.message||error).trim().split('\n').at(-1),true);}
    finally{busy=false;controls();}
  }
  function options(select,values) {
    select.replaceChildren(...values.map(v=>new Option(v,v)));
  }
  function orbitFields() {
    el('orbit-fields').replaceChildren();
    for(const [key,field] of Object.entries(doc?.orbits[el('orbit').value]||{})) {
      const label=document.createElement('label');
      label.textContent=names[key];
      const input=document.createElement('input');
      Object.assign(input,{type:'number',step:'any',value:field.value});
      input.dataset.key=key;input.dataset.editable=String(field.editable);
      input.setAttribute('aria-label',names[key]);label.append(input);el('orbit-fields').append(label);
    }
    controls();
  }
  function plot() {
    const selected=series[el('series').selectedIndex];
    const canvas=el('plot');canvas.hidden=!selected;
    el('units').textContent=selected ? `Time (days) · ${selected.label} (${selected.unit||'dimensionless'}) · ${selected.times.length} points` :
      (doc?.models.length ? 'This model has no plottable light curve or radial velocities.' : 'Calculate a model or attach an existing model file.');
    if(!selected||!dialog.open)return;
    const dpr=Math.min(devicePixelRatio||1,2),w=canvas.clientWidth,h=canvas.clientHeight;
    if(!w||!h)return;
    canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);
    const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);
    const x=selected.times,y=selected.values;
    let ymin=Infinity,ymax=-Infinity;
    for(const value of y){ymin=Math.min(ymin,value);ymax=Math.max(ymax,value);}
    const xmin=x[0],xmax=x.at(-1),L=55,R=12,T=12,B=30;
    const pad=(ymax-ymin||Math.abs(ymin)||1)*.06;
    const px=v=>L+(v-xmin)/(xmax-xmin||1)*(w-L-R);
    const py=v=>h-B-(v-ymin+pad)/(ymax-ymin+2*pad)*(h-T-B);
    ctx.font='11px system-ui';ctx.lineWidth=1;ctx.fillStyle='#57536b';ctx.textAlign='right';
    for(let i=0;i<4;i++){const v=ymin+(ymax-ymin)*i/3;
      ctx.fillText(Number(v.toPrecision(4)),L-5,py(v)+4);ctx.strokeStyle='#e5e2eb';ctx.beginPath();ctx.moveTo(L,py(v));ctx.lineTo(w-R,py(v));ctx.stroke();}
    ctx.textAlign='left';ctx.fillText(xmin.toPrecision(7),L,h-8);
    ctx.textAlign='right';ctx.fillText(xmax.toPrecision(7),w-R,h-8);
    ctx.lineWidth=2;ctx.strokeStyle='#6655c8';ctx.beginPath();
    for(let i=0;i<x.length;i++){if(i)ctx.lineTo(px(x[i]),py(y[i]));else ctx.moveTo(px(x[i]),py(y[i]));}
    ctx.stroke();
    if(x.length===1){ctx.fillStyle='#6655c8';ctx.beginPath();ctx.arc(px(x[0]),py(y[0]),2,0,Math.PI*2);ctx.fill();}
  }
  async function loadSeries() {
    series=doc?.models.length ? await call('series',{label:el('model').value}) : [];
    options(el('series'),series.map(s=>s.label));plot();
  }
  async function render(meta,title) {
    doc=meta;fileName=title;const bundle=doc.kind==='bundle';
    el('document').hidden=false;el('title').textContent=title;
    el('summary').textContent=`${bundle?'PHOEBE '+doc.version+' bundle':'PHOEBE model ParameterSet'} · ${doc.datasets.length} dataset(s) · ${doc.models.length} model(s)`;
    el('controls').hidden=!bundle;el('save-bundle').hidden=!bundle;el('attach').hidden=!bundle;
    el('model-row').hidden=!doc.models.length;
    options(el('compute'),doc.computes);options(el('orbit'),Object.keys(doc.orbits));orbitFields();
    options(el('model'),doc.models);if(meta.selected)el('model').value=meta.selected;
    await advanced.refresh(meta);await loadSeries();status(bundle?'Bundle open in the native file workspace.':'Native model open.');
  }
  function show() {if(!dialog.open)dialog.showModal();plot();}
  async function openFile(file,isAttachment=false) {
    show();
    await action('Opening native file…',async()=>{
      const text=await file.text();
      const meta=await call(isAttachment?'attach':'open',{text});
      await render(meta,isAttachment?fileName:file.name);
    });
  }
  function choose(isAttachment) {attach=isAttachment;el('file').value='';el('file').click();}
  function download(text,filename) {
    const href=URL.createObjectURL(new Blob([text],{type:'application/json'}));
    const a=document.createElement('a');a.href=href;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(href),15000);
  }
  el('new').onclick=()=>action('Creating native binary…',async()=>{
    await render(await call('new',{template:el('template').value}),'new-binary.phoebe');
  });
  el('button').onclick=show;el('open').onclick=()=>choose(false);el('attach').onclick=()=>choose(true);
  el('file').onchange=e=>{if(e.target.files[0])openFile(e.target.files[0],attach);};
  el('lab').onclick=()=>action('Building an exact bundle with the current observations…',async()=>{
    await render(await call('lab',labSnapshot()),'lab-system.phoebe');
  });
  el('run').onclick=()=>action('Computing with this bundle’s PHOEBE settings…',async()=>{
    const orbit=el('orbit').value,edits={};
    for(const input of el('orbit-fields').querySelectorAll('input')) {
      const key=input.dataset.key;
      if(input.dataset.editable==='true'){
        if(!Number.isFinite(input.valueAsNumber))throw Error('Enter a finite '+names[key]+'.');
        if(input.valueAsNumber!==doc.orbits[orbit][key].value)edits[key]=input.valueAsNumber;
      }
    }
    await render(await call('compute',{compute:el('compute').value,orbit,edits}),fileName);
  });
  el('save-bundle').onclick=()=>action('Saving native bundle…',async()=>{
    download(await call('save_bundle'),fileName.replace(/\.[^.]+$/,'')+'.phoebe');status('Bundle downloaded.');
  });
  el('save-model').onclick=()=>action('Saving native model…',async()=>{
    const label=el('model').value;download(await call('save_model',{label}),label+'.model');status('Model downloaded.');
  });
  el('orbit').onchange=orbitFields;
  el('model').onchange=()=>action('Reading model…',async()=>{await loadSeries();status('Model loaded.');});
  el('series').onchange=plot;
  return {openFile};
}
