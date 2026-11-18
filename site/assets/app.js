import {bindVelocityPlot} from './radial-velocity.mjs?v=5c40d22026196c51';
import {bindNativeFiles} from './native-files.js?v=b81d3b4d01d31c3f';
const $ = (id) => document.getElementById(id);
const DEFAULTS = {inclination:84.5,radius_primary:.21,radius_secondary:.17,temperature_ratio:.84,mass_ratio:.75,eccentricity:0,omega:90,period:1.8,epoch:0,distortion:false,irradiation:false};
const GROUPS = [
  {name:'Orbit',items:[
    ['inclination','Inclination',0,90,.1,1,'°','0° is face-on. At 90° the orbit is edge-on.'],
    ['eccentricity','Eccentricity',0,.35,.001,4,'','Zero is a circular orbit.'],
    ['omega','Periastron angle',0,360,1,0,'°','The orientation of an eccentric orbit.'],
  ]},
  {name:'The stars',items:[
    ['radius_primary','Primary radius / separation',.10,.32,.002,3,'','Larger stars generally make broader eclipses.'],
    ['radius_secondary','Secondary radius / separation',.08,.29,.002,3,'','Compare the eclipse widths and depths.'],
    ['temperature_ratio','Temperature ratio T₂ / T₁',.58,1.10,.005,3,'','Watch the relative depths of the two eclipses.'],
    ['mass_ratio','Mass ratio M₂ / M₁',.2,1.5,.01,2,'','At fixed fractional radii, changing mass ratio mainly shifts surface gravity in the spherical preview.'],
  ]},
  {name:'Timing',items:[
    ['period','Orbital period',.1,100,.01,7,'d','Use the arrow keys on a zoomed slider to step by 0.0000001 day.'],
    ['epoch','Primary-eclipse epoch',-1e9,1e9,.001,7,'d','Time of phase zero, in the same time system as your observations.'],
  ]},
];
const state = {parameters:{...DEFAULTS},quality:'preview',dataset:null,result:null,revision:0,ready:false,busy:false,fitting:false,queued:false,worker:null,request:0,current:null};
let computeTimer,toastTimer,parsedFile,exampleRequest=0;
const parameterInputs = new Map();
let predictSurface = null, predictDisplay = null, dragView = null, pointerHeld = false;
let timingRevision=-1, liveTiming=null;
let exactPartial = null, previousExact = null, engineFailed = false, elapsedTimer;
const exactHistory = new Map();
const plotPhases=()=>state.parameters.distortion ? Number($('tidal-phases').value) : 513;
const geometryKey=()=>JSON.stringify([state.quality,plotPhases(),...Object.keys(DEFAULTS).map(k=>state.parameters[k])]);

function rememberExact(result) {
  previousExact=result;
  if(result.fit || result.phases.length!==plotPhases())return;
  const key=geometryKey();
  exactHistory.delete(key);
  exactHistory.set(key,result);
  if(exactHistory.size>8)exactHistory.delete(exactHistory.keys().next().value);
}

function restoreExact() {
  const saved=exactHistory.get(geometryKey());
  if(!saved)return false;
  if(state.current)state.worker?.postMessage({type:'release',id:state.current.id});
  clearTimeout(computeTimer);state.queued=false;state.current=null;
  clearDisplay();exactPartial=null;
  state.result={...saved,revision:state.revision};previousExact=state.result;
  setBusy(false);$('export-button').disabled=false;
  $('plot-placeholder').hidden=true;
  status(`Exact PHOEBE · ${saved.phases.length} phases · restored`);drawPlots();updateStats();
  return true;
}
const legend = document.querySelector('.chart-legend span:last-child');

function labelCurve(text) {
  legend.lastChild.textContent = text;
  const swatch=legend.querySelector('i');
  swatch.style.backgroundColor=dragView?.exploratory ? '#b56a08' : '';
  swatch.style.height=dragView ? '8px' : '';
  swatch.style.opacity=dragView ? '.36' : '';
  swatch.style.filter=dragView ? 'blur(1.8px)' : '';
}
function clearDisplay() {
  dragView = null;
  labelCurve('PHOEBE model');
}

function approximateView() {
  const p=state.parameters;
  const omitted=[p.distortion && 'tides',p.irradiation && 'heating'].filter(Boolean);
  if (!state.dataset || !predictDisplay || (state.quality!=='preview' && !omitted.length)) return null;
  // Epoch places observations in phase. The phase-domain geometry uses a relative origin.
  const surface=state.quality==='preview' && predictSurface?.(p);
  const curve=surface || predictDisplay({...p,epoch:0,distortion:false,irradiation:false});
  if (!curve) return null;
  const scaled=compareDisplayCurve(curve, normalizedData());
  return {...curve,...scaled,exploratory:!!(omitted.length||curve.exploratory),omitted:surface ? [] : omitted};
}

// Both lists are sorted in phase. A single pass also handles the uneven grids
// produced while the exact curve is being refined.
function compareDisplayCurve(curve, obs) {
  const x=curve.phases, y=curve.model;
  const predicted=[];
  let j=0, numerator=0, denominator=0;
  for(let i=0;i<obs.phase.length;i++){
    const phase=obs.phase[i];
    while(j<x.length-2 && x[j+1]<phase)j++;
    const fraction=Math.max(0,Math.min(1,(phase-x[j])/(x[j+1]-x[j])));
    const flux=y[j]+fraction*(y[j+1]-y[j]);
    const weight=obs.sigma ? 1/obs.sigma[i]**2 : 1;
    predicted.push(flux);numerator+=weight*obs.flux[i]*flux;denominator+=weight*flux*flux;
  }
  const scale=numerator/denominator;
  return {phases:x,model:y.map(f=>scale*f),
          comparison:{...obs,residual:predicted.map((f,i)=>obs.flux[i]-scale*f)}};
}

function timingDisplay() {
  const sameGeometry=(curve,ignorePeriod)=>curve?.parameters && curve.quality===state.quality && curve.phases.length>=plotPhases() &&
    Object.keys(DEFAULTS).every(k=>k==='epoch'||(ignorePeriod && k==='period')||curve.parameters[k]===state.parameters[k]);
  const candidates=[state.result,previousExact,...Array.from(exactHistory.values()).reverse()];
  const exact=candidates.find(c=>sameGeometry(c,false));
  if(exact){
    return {...compareDisplayCurve(exact,normalizedData()),label:'Live · exact PHOEBE curve'};
  }
  const approximate=approximateView();
  if(approximate)return {...approximate,label:approximate.omitted.length?'Preview · spherical approximation':'Preview · approximate curve'};
  const prior=candidates.find(c=>sameGeometry(c,true));
  if(prior)return {...compareDisplayCurve(prior,normalizedData()),prior:true,label:'Preview · PHOEBE curve at previous period'};
  return null;
}

function releasePointer() {
  if (!pointerHeld) return;
  pointerHeld=false;
  scheduleCompute(80);
}
window.addEventListener('pointerup',releasePointer);
window.addEventListener('pointercancel',releasePointer);
window.addEventListener('blur',releasePointer);

function toast(text) { $('toast').textContent=text; $('toast').hidden=false; clearTimeout(toastTimer); toastTimer=setTimeout(()=>$('toast').hidden=true,6500); }
function status(text,kind='ready') { const el=$('model-status'); el.replaceChildren(); const dot=document.createElement('span');dot.className=`status-dot ${kind==='busy'?'loading':kind==='error'?'error':''}`;const label=document.createElement('span');label.textContent=text;el.append(dot,label); }
function cleanError(error) { return String(error).trim().split('\n').filter(Boolean).slice(-1)[0].replace(/^(ValueError|RuntimeError|PythonError):\s*/,''); }
function median(values) { const x=[...values].sort((a,b)=>a-b);const i=Math.floor(x.length/2);return x.length%2?x[i]:(x[i-1]+x[i])/2; }
function wrapPhase(value) { return ((value+.5)%1+1)%1-.5; }

// Fine sliders use integer ticks so sub-second changes survive range-input rounding.
const timeSpans=['0.00001','0.001','0.01','0.1','1'];
const zoomOptions={
  period:{spans:[...timeSpans,'full'],digits:7,unit:' d',fullStep:.01},
  epoch:{spans:timeSpans,digits:7,unit:' d'},
  eccentricity:{spans:['0.01','full'],digits:4,unit:'',fullStep:.001},
};
const zoomCenters={...DEFAULTS};
function centerSlider(key) {
  const {range,min,max}=parameterInputs.get(key);
  const span=$(key+'-span').value, options=zoomOptions[key];
  const center=state.parameters[key];
  zoomCenters[key]=center;
  if(span==='full'){
    Object.assign(range,{min,max,step:options.fullStep});
  }else{
    const scale=10**options.digits, ticks=Math.round(Number(span)*scale);
    Object.assign(range,{min:Math.max(-ticks,Math.round((min-center)*scale)),
                         max:Math.min(ticks,Math.round((max-center)*scale)),step:1});
  }
}
function addZoom(row,key,title) {
  const label=document.createElement('label');
  label.className='slider-zoom';
  label.append('Drag range ');
  const select=document.createElement('select');
  select.id=key+'-span';
  select.setAttribute('aria-label',title+' drag range');
  const options=zoomOptions[key];
  for(const span of options.spans)select.add(new Option(span==='full'?'Full range':'±'+span+options.unit,span));
  select.value=key==='epoch'?'0.001':'full';
  select.onchange=()=>{centerSlider(key);updateControlValues();};
  label.append(select);row.append(label);
}

function renderControls() {
  for (const group of GROUPS) {
    const section=document.createElement('section');section.className='parameter-group';
    const heading=document.createElement('h3');heading.textContent=group.name;section.append(heading);
    if(group.name==='Timing') { section.classList.add('timing-group');heading.title='Timing values are in days.'; }
    for(const [key,label,min,max,step,digits,unit,help] of group.items) {
      const row=document.createElement('div');row.className='parameter';
      const top=document.createElement('div');top.className='parameter-label';
      const title=document.createElement('label');title.htmlFor=`number-${key}`;title.textContent=label;
      const box=document.createElement('span');box.className='value-box';
      const number=document.createElement('input');Object.assign(number,{type:'number',id:`number-${key}`,min,max,step,value:state.parameters[key]});number.setAttribute('aria-label',label);
      const suffix=document.createElement('span');suffix.textContent=unit;box.append(number,suffix);top.append(title,box);row.append(top);
      const range=document.createElement('input');
      Object.assign(range,{type:'range',id:`range-${key}`,min,max,step,value:state.parameters[key]});
      range.setAttribute('aria-label',`${label} slider`);row.append(range);
      const zoom=zoomOptions[key];
      if(zoom)addZoom(row,key,label);
      const hint=document.createElement('small');hint.className='parameter-help';hint.textContent=help;row.append(hint);section.append(row);
      parameterInputs.set(key,{number,range,digits,min,max});
      const update=(source)=>{
        const inTicks=zoom && source===range && $(key+'-span').value!=='full';
        const entered=source.valueAsNumber;
        const value=inTicks ? Number((zoomCenters[key]+entered/10**zoom.digits).toFixed(zoom.digits)) : entered;
        if(!Number.isFinite(value)||value<min||value>max) {
          updateControlValues();
          toast(`${label} must be between ${min} and ${max}. Using ${number.value}${unit}.`);
          return;
        }
        state.parameters[key]=value;
        if(zoom && source===number)centerSlider(key);
        updateControlValues();parametersChanged(source===range,false,key);
      };
      number.addEventListener('change',()=>update(number));
      if(range) {range.addEventListener('pointerdown',()=>{pointerHeld=true;clearTimeout(computeTimer);});range.addEventListener('input',()=>update(range));range.addEventListener('change',()=>scheduleCompute(80));}
    }
    $('parameter-controls').append(section);
  }
  for(const key of ['distortion','irradiation']) $(key).addEventListener('change',()=>{state.parameters[key]=$(key).checked;parametersChanged(false,true);});
  updateControlValues();
}

function updateControlValues() {
  for(const [key,{number,range,digits,min,max}] of parameterInputs) {
    const zoom=zoomOptions[key];
    const value=state.parameters[key];
    number.value=zoom && Number(value.toFixed(digits))!==value ? String(value) : value.toFixed(digits);
    if(zoom){
      number.step=10**-zoom.digits;
      if(zoom.unit)number.classList.add('time-value');
      range.setAttribute('aria-valuetext',number.value+zoom.unit);
      if(key==='epoch'){
        range.hidden=state.dataset?.x_kind!=='time';
        $('epoch-span').parentElement.hidden=range.hidden;
      }
    }
    range.value=zoom && $(key+'-span').value!=='full'
      ? Math.round((value-zoomCenters[key])*10**zoom.digits) : value;
    range.style.setProperty('--fill',100*(Number(range.value)-Number(range.min))/(Number(range.max)-Number(range.min))+'%');
  }
  $('distortion').checked=state.parameters.distortion;$('irradiation').checked=state.parameters.irradiation;
  const a=56*state.parameters.radius_primary/.21,b=56*state.parameters.radius_secondary/.21;
  Object.assign($('primary-star').style,{width:`${a}px`,height:`${a}px`});Object.assign($('secondary-star').style,{width:`${b}px`,height:`${b}px`});
}

function unavailableReason() {
  if (state.quality!=='preview') return 'Drag preview unavailable · choose Preview quality';
  if (artifact.pairs && (state.parameters.eccentricity!==0 || state.parameters.omega!==90))
    return 'Drag preview unavailable for this combination · release for PHOEBE';
  const fixedLabel={eccentricity:'eccentricity',mass_ratio:'mass ratio',period:'period',
    omega:'periastron angle',epoch:'epoch',distortion:'tidal distortion',irradiation:'irradiation'};
  for (const [k,v] of Object.entries(artifact.fixed)) {
    if(state.parameters[k]!==v) return `Drag preview unavailable · requires ${fixedLabel[k]} ${v===false?'off':v}`;
  }
  return 'Drag preview unavailable · waiting for PHOEBE';
}
function parametersChanged(slider=false,physics=false,key=null) {
  const interrupt=physics && state.current?.type==='compute' &&
    ((state.current.tides && !state.parameters.distortion) || (state.current.heating && !state.parameters.irradiation));
  if(interrupt)startEngine();
  exactPartial=null;
  state.revision++;
  $('export-button').disabled=true;
  $('fit-button').disabled=true;
  timingRevision=key==='epoch'||key==='period' ? state.revision : -1;
  liveTiming=timingRevision===state.revision ? timingDisplay() : null;
  if(timingRevision===state.revision)dragView=liveTiming?.omitted ? liveTiming : null;
  else dragView=slider || physics || state.parameters.distortion || state.parameters.irradiation ? approximateView() : null;
  const dragLabel=dragView?.surfaceMode ? 'Approximate surface preview · '+dragView.surfaceMode : dragView?.omitted?.length
    ? 'Approximate spherical curve · '+dragView.omitted.join(' and ')+' omitted'+(dragView.atEdge?' · atmosphere clamped':'')
    : dragView?.exploratory
    ? ['Approximate · eight-slider neural preview', dragView.periodOutside ? 'outside joint training periods' : '', dragView.atEdge ? 'atmosphere clamped' : ''].filter(Boolean).join(' · ')
    : 'Approximate · drag preview';
  labelCurve(dragView ? dragLabel : liveTiming ? (liveTiming.prior?'Previous-period PHOEBE curve':'Exact PHOEBE curve · updated phases') : previousExact ? 'Previous PHOEBE curve · awaiting recalculation' :
    slider ? unavailableReason() : 'Waiting for PHOEBE');
  if(dragView) $('plot-placeholder').hidden=true;
  status('Parameters changed · waiting for PHOEBE','busy');
  drawPlots();updateStats();
  if(!pointerHeld){
    if(!slider && restoreExact()){
      if(engineFailed){startEngine();restoreExact();}
      return;
    }
    if(engineFailed){startEngine();return;}
    scheduleCompute();
  }
}
function scheduleCompute(delay=450) {clearTimeout(computeTimer);computeTimer=setTimeout(()=>requestModel('compute'),delay);}
function setBusy(busy,fitting=false) {
  state.busy=busy;state.fitting=fitting;
  $('fit-button').disabled=!state.ready||busy||state.result?.revision!==state.revision;
  $('stop-button').hidden=!busy;
  document.querySelectorAll('.quality').forEach(button=>{button.disabled=fitting;});
  $('tidal-phases').disabled=fitting;
  $('surface-workers').disabled=fitting;Object.keys(zoomOptions).forEach(key=>{$(key+'-span').disabled=fitting;});
  $('example-choice').disabled=fitting;
  $('import-button').disabled=fitting;$('example-button').disabled=fitting;$('reset-button').disabled=fitting;
  for(const {number,range} of parameterInputs.values()) {number.disabled=fitting;if(range)range.disabled=fitting;}
  $('distortion').disabled=fitting;$('irradiation').disabled=fitting;
}

function startEngine() {
  clearDisplay();exactPartial=null;engineFailed=false;
  clearInterval(elapsedTimer);
  if(state.worker)state.worker.terminate();
  state.ready=false;setBusy(false);state.queued=false;state.current=null;
  $('engine-banner').hidden=false;$('engine-retry').hidden=true;
  $('engine-pill').innerHTML='<span class="status-dot loading"></span>Loading engine';
  status('Starting the browser engine…','busy');
  state.worker=new Worker(new URL('./engine.worker.js?v=fb346b55717006fd',import.meta.url),{type:'module'});
  const worker=state.worker;
  state.worker.onmessage=({data})=>{
    if(worker!==state.worker)return;
    if(data.type==='status') {$('engine-title').textContent=data.title;$('engine-detail').textContent=data.detail;return;}
    if(data.type==='ready') {
      state.ready=true;$('engine-banner').hidden=true;$('engine-pill').innerHTML='<span class="status-dot"></span>Browser engine ready';
      requestModel('compute');return;
    }
    if(data.type==='fatal') {
      engineFailed=true;state.ready=false;setBusy(false);$('engine-title').textContent='The scientific engine could not start';$('engine-detail').textContent=cleanError(data.error);$('engine-retry').hidden=false;
      $('engine-pill').innerHTML='<span class="status-dot error"></span>Engine unavailable';status(cleanError(data.error),'error');return;
    }
    if(data.id!==state.current?.id)return;
    if(data.type==='fit_parameters') {
      const current=state.current;
      if(current.revision!==state.revision || current.stopped){
        state.current=null;setBusy(false);requestModel('compute');return;
      }
      state.parameters={...data.parameters};
      current.revision=++state.revision;
      Object.keys(zoomOptions).forEach(centerSlider);
      updateControlValues();clearDisplay();
      if(previousExact)labelCurve('Previous PHOEBE curve · drawing fitted parameters');
      drawPlots();updateStats();
      status('Fit search complete · drawing the fitted PHOEBE curve','busy');
      state.worker.postMessage({type:'continue',id:current.id});
      return;
    }
    if(data.type==='partial') {
      const current=state.current;
      const advance=()=>{
        if(current!==state.current)return;
        if(current.revision!==state.revision || pointerHeld || state.queued || current.stopped) {
          state.worker.postMessage({type:'release',id:current.id});
          state.current=null;setBusy(false);
          if(current.stopped && current.revision===state.revision) {
            status('Refinement stopped · change a parameter to recalculate');
          } else if(state.queued && !pointerHeld) {
            state.queued=false;requestModel('compute');
          }
          return;
        }
        state.worker.postMessage({type:'continue',id:current.id});
      };
      if(current.revision===state.revision && !pointerHeld && !current.stopped) {
        clearDisplay();
        exactPartial={revision:current.revision,phases:data.phases,model:data.model};
        previousExact=exactPartial;
        if(timingRevision===state.revision){
          liveTiming={...compareDisplayCurve(exactPartial,normalizedData()),label:`Preview · ${data.phases.length}-point PHOEBE curve`};
        }
        $('plot-placeholder').hidden=true;
        labelCurve(`PHOEBE model · ${data.phases.length} points`);
        status(`Exact PHOEBE · ${data.phases.length} of ${current.plotCount} phase points`,'busy');
        drawPlots();updateStats();
      }
      setTimeout(advance,35);
      return;
    }
    if(data.type==='progress' && (state.current.revision!==state.revision || exactPartial || state.current.stopped))return;
    if(data.type==='progress') {status(data.stage||`Fitting · model evaluation ${data.evaluation} · RMS ${Number(data.rms).toFixed(4)}`,'busy');return;}
    if(data.type==='result') {
      const current=state.current;
      const matches=!current.stopped && current.revision===state.revision;
      state.current=null;
      setBusy(false);
      if(matches) {
        clearDisplay();exactPartial=null;state.result=data.result;state.result.revision=state.revision;
        rememberExact(state.result);
        $('plot-placeholder').hidden=true;$('export-button').disabled=false;$('fit-button').disabled=false;
        let text=`${data.result.quality==='refined'?'Refined':'Preview'} model · ${data.result.phases.length} phases · ${data.result.seconds.toFixed(1)} s`;
        if(data.result.surface_workers>1)text+= ' · '+data.result.surface_workers+' workers';
        if(data.result.source==='reused_geometry')text=`Exact PHOEBE · ${data.result.phases.length} phases · updated observation comparison`;
        if(data.result.source==='stored_exact')text=`Exact PHOEBE · ${data.result.phases.length} phases · saved reference for these settings`;
        if(data.result.fit) {text=`Local fit complete · ${data.result.fit.objective_phases}-phase search · ${data.result.phases.length}-point curve · ${data.result.fit.evaluations} model evaluations · ${data.result.seconds.toFixed(1)} s`;toast(data.result.fit.converged?'Local fit completed. Inspect the residuals before accepting the model.':'The short fit reached its stopping limit. Inspect the residuals and starting values.');}
        status(text);drawPlots();updateStats();
      }
      if(state.queued) {state.queued=false;requestModel('compute');}
      else if(current.stopped && current.revision===state.revision)status('Refinement stopped · change a parameter to recalculate');
      return;
    }
    if(data.type==='error') {
      const outdated=state.current.revision!==state.revision;
      state.current=null;
      setBusy(false);
      if(state.queued) {state.queued=false;requestModel('compute');return;}
      if(outdated)return;
      if(dragView?.exploratory)labelCurve((dragView.omitted?.length ? 'Spherical estimate · '+dragView.omitted.join(' and ')+' omitted' : 'Exploratory only')+' · exact PHOEBE calculation failed');
      if(!dragView && previousExact)labelCurve('Previous PHOEBE curve · current calculation failed');
      if(/out of memory|memory access out of bounds|wasm trap|aborted\(/i.test(data.error)) {
        engineFailed=true;state.ready=false;$('engine-banner').hidden=false;$('engine-retry').hidden=false;
        $('engine-title').textContent='The numerical engine needs to restart';$('engine-detail').textContent=cleanError(data.error);
      }
      status(cleanError(data.error),'error');toast(cleanError(data.error));
      if(!state.result){$('plot-placeholder').hidden=true;drawPlots();}
    }
  };
  state.worker.onerror=(e)=>{if(worker!==state.worker)return;engineFailed=true;state.ready=false;status(e.message||'The browser worker stopped.','error');setBusy(false);$('engine-title').textContent='The browser engine stopped';$('engine-detail').textContent=e.message||'Restart the engine to continue.';$('engine-retry').hidden=false;$('engine-banner').hidden=false;};
  state.worker.postMessage({type:'initialize'});
}

function requestModel(type='compute',fit=[]) {
  clearTimeout(computeTimer);
  if(type==='compute'&&pointerHeld){state.queued=true;return;}
  if(!state.dataset)return;
  if(type==='compute' && restoreExact())return;
  if(!state.ready){if(engineFailed)startEngine();return;}
  if(state.busy){state.queued=true;return;}
  state.result=null;exactPartial=null;
  if(type==='fit'){liveTiming=null;timingRevision=-1;}
  if(type==='fit' && previousExact)labelCurve('Previous PHOEBE curve · fitting');
  $('export-button').disabled=true;updateStats();drawPlots();
  const id=++state.request;
  const plotCount=type==='fit' ? 513 : plotPhases();
  state.current={id,revision:state.revision,type,plotCount,tides:state.parameters.distortion,heating:state.parameters.irradiation};state.queued=false;setBusy(true,type==='fit');
  status(type==='fit'?'Fitting selected parameters in this browser…':`Computing ${state.quality} model in this browser…`,'busy');
  clearInterval(elapsedTimer);
  if(type==='compute' && (state.current.tides || state.current.heating)){
    const started=performance.now(), revision=state.revision;
    elapsedTimer=setInterval(()=>{
      if(state.current?.id!==id || state.revision!==revision){clearInterval(elapsedTimer);return;}
      const seconds=Math.floor((performance.now()-started)/1000);
      const stage=exactPartial ? `${exactPartial.phases.length} of ${plotCount} phases` : 'calculating first 5 phases';
      status('Exact surface physics · '+stage+' · '+seconds+' s','busy');
    },1000);
  }
  state.worker.postMessage({type,id,progressive:true,payload:{parameters:{...state.parameters},dataset:state.dataset,quality:state.quality,plot_phases:plotCount,workers:Number($('surface-workers').value),fit_phases:Number($('fit-phases').value),fit}});
}

function normalizedData() {
  if(!state.dataset)return {phase:[],flux:[],sigma:null};
  const d=state.dataset;let y=[...d.y],sigma=d.sigma?[...d.sigma]:null;
  if(d.y_kind==='magnitude') {const center=median(y);y=y.map(v=>10**(-.4*(v-center)));if(sigma)sigma=sigma.map((s,i)=>.4*Math.log(10)*y[i]*s);}
  const norm=median(y);y=y.map(v=>v/norm);if(sigma)sigma=sigma.map(v=>v/norm);
  const rows=d.x.map((x,i)=>({x:wrapPhase(d.x_kind==='time'?(x-state.parameters.epoch)/state.parameters.period:x),y:y[i],s:sigma?.[i]})).sort((a,b)=>a.x-b.x);
  return {phase:rows.map(r=>r.x),flux:rows.map(r=>r.y),sigma:sigma?rows.map(r=>r.s):null};
}

function drawTimeSeries() {
  const data=state.dataset;
  if(data?.x_kind!=='time')return;
  const canvas=$('time-curve'), rect=canvas.getBoundingClientRect();
  if(!rect.width || !rect.height)return;
  const ctx=canvas.getContext('2d'), dpr=window.devicePixelRatio||1;
  canvas.width=rect.width*dpr;canvas.height=rect.height*dpr;ctx.scale(dpr,dpr);
  const left=49,right=rect.width-18,top=12,bottom=rect.height-25;
  const start=Math.min(...data.x), end=Math.max(...data.x);
  const lo=Math.min(...data.y), hi=Math.max(...data.y);
  const span=end-start || 1, height=hi-lo || 1;
  const px=t=>left+(t-start)/span*(right-left);
  const py=y=>data.y_kind==='magnitude' ? top+(y-lo)/height*(bottom-top) : bottom-(y-lo)/height*(bottom-top);
  ctx.font='10px system-ui, sans-serif';ctx.fillStyle='#696578';
  ctx.textAlign='right';
  for(const y of [lo,hi])ctx.fillText(y.toFixed(3),left-6,py(y)+3);
  ctx.textAlign='center';
  for(let i=0;i<=4;i++)ctx.fillText((span*i/4).toFixed(1),px(start+span*i/4),bottom+16);
  const {period,epoch}=state.parameters;
  const first=Math.ceil((start-epoch)/period), last=Math.floor((end-epoch)/period);
  if(last-first<80) {
    ctx.strokeStyle='#bdb3d8';ctx.setLineDash([3,4]);ctx.beginPath();
    for(let cycle=first;cycle<=last;cycle++){
      const x=px(epoch+cycle*period);ctx.moveTo(x,top);ctx.lineTo(x,bottom);
    }
    ctx.stroke();
  }
  ctx.fillStyle='#656782';
  data.x.forEach((t,i)=>ctx.fillRect(px(t)-.9,py(data.y[i])-.9,1.8,1.8));
}

const drawVelocityPlot=bindVelocityPlot($('rv-panel'));
function drawPlots() {drawVelocityPlot(state.parameters,state.dataset);drawTimeSeries();drawChart($('light-curve'),false);drawChart($('residual-curve'),true);}
function drawChart(canvas,residual) {
  const rect=canvas.getBoundingClientRect();if(!rect.width||!rect.height)return;
  const dpr=Math.min(window.devicePixelRatio||1,2);canvas.width=rect.width*dpr;canvas.height=rect.height*dpr;
  const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);
  const w=rect.width,h=rect.height,L=49,R=18,T=residual?8:20,B=residual?23:26,iw=w-L-R,ih=h-T-B;
  const current=state.result?.revision===state.revision ? state.result : null;
  const live=!current && timingRevision===state.revision ? liveTiming : null;
  const comparison=current?.comparison||live?.comparison||normalizedData();
  const visible=dragView||(exactPartial?.revision===state.revision ? exactPartial : null)||current||live||previousExact;
  const previous=live?.prior || (visible && visible===previousExact && !dragView && !current && !exactPartial);
  let ys=residual?(comparison.residual||[]):comparison.flux||[];
  const model=residual?[]:visible?.model||[];
  let min,max;
  if(residual){const a=Math.max(.005,...ys.map(Math.abs))*1.2;min=-a;max=a;}
  else{const all=[...ys,...model];min=all.length?Math.min(...all):.65;max=all.length?Math.max(...all):1.05;const gap=Math.max(.03,(max-min)*.15);min-=gap;max+=gap;}
  const px=(x)=>L+(x+.5)*iw,py=(y)=>T+(max-y)/(max-min)*ih;
  ctx.clearRect(0,0,w,h);ctx.font='10px system-ui, sans-serif';ctx.lineWidth=1;
  for(let i=0;i<=(residual?2:4);i++) {
    const value=min+(max-min)*i/(residual?2:4),pos=py(value);
    ctx.strokeStyle='#efedf3';ctx.setLineDash([]);ctx.beginPath();ctx.moveTo(L,pos);ctx.lineTo(w-R,pos);ctx.stroke();
    ctx.fillStyle='#9a96a3';ctx.textAlign='right';ctx.fillText(value.toFixed(residual?3:2),L-9,pos+3);
  }
  for(const x of [-.5,-.25,0,.25,.5]) {
    ctx.strokeStyle='#f1eff5';ctx.setLineDash([3,4]);ctx.beginPath();ctx.moveTo(px(x),T);ctx.lineTo(px(x),h-B);ctx.stroke();
    if(residual){ctx.fillStyle='#9a96a3';ctx.textAlign='center';ctx.fillText(x.toFixed(2),px(x),h-6);}
  }
  if(residual){ctx.strokeStyle='#bcb4d3';ctx.setLineDash([4,4]);ctx.beginPath();ctx.moveTo(L,py(0));ctx.lineTo(w-R,py(0));ctx.stroke();}
  else{ctx.save();ctx.translate(12,T+ih/2);ctx.rotate(-Math.PI/2);ctx.fillStyle='#8c8796';ctx.textAlign='center';ctx.fillText('Normalized flux',0,0);ctx.restore();}
  ctx.save();ctx.beginPath();ctx.rect(L,T,iw,ih);ctx.clip();ctx.setLineDash([]);
  const xs=comparison.phase||[];
  for(let i=0;i<ys.length;i++) {
    const x=px(xs[i]),y=py(ys[i]);
    if(!residual&&comparison.sigma?.[i]) {ctx.strokeStyle='#bbc0d25a';ctx.lineWidth=.8;ctx.beginPath();ctx.moveTo(x,py(ys[i]-comparison.sigma[i]));ctx.lineTo(x,py(ys[i]+comparison.sigma[i]));ctx.stroke();}
    ctx.fillStyle=residual?(live && live.label.startsWith('Preview')?'#b56a088c':'#8e83bd9c'):'#737b969c';ctx.beginPath();ctx.arc(x,y,residual?1.7:2,0,Math.PI*2);ctx.fill();
  }
  if(!residual&&visible) {
    ctx.strokeStyle=previous ? '#888494' : dragView?.exploratory ? '#b56a08' : '#6a59da';
    ctx.lineWidth=dragView ? 14 : 2.2;
    if(dragView) {
      ctx.globalAlpha=.30;
      ctx.lineJoin='round';
      ctx.lineCap='round';
      ctx.shadowColor=dragView.exploratory ? 'rgba(181,106,8,.5)' : 'rgba(106,89,218,.5)';
      ctx.shadowBlur=4*dpr;
      if('filter' in ctx) ctx.filter=`blur(${2.5*dpr}px)`;
    }
    ctx.setLineDash(previous?[5,4]:[]);ctx.beginPath();
    visible.phases.forEach((x,i)=>i?ctx.lineTo(px(x),py(model[i])):ctx.moveTo(px(x),py(model[i])));ctx.stroke();
  }
  ctx.restore();canvas.chart={L,R,T,B,px,py,min,max,w,h,data:comparison};
}

function updateStats() {
  const current=state.result?.revision===state.revision ? state.result : null;
  const live=timingRevision===state.revision ? liveTiming : null;
  $('residual-summary').textContent=current?`${current.comparison.residual.length} points`:live?.label||'—';
  const c=current?.comparison;$('rms-stat').textContent=c?c.rms.toFixed(4):'—';$('chi-stat').textContent=c?.reduced_chi2!=null?c.reduced_chi2.toFixed(2):'—';
  $('chi-note').textContent=!current && live?'Waiting for completed PHOEBE result':c?.reduced_chi2!=null?'Uses measurement errors':'Add errors to estimate χ²';
}

function installDataset(dataset,parameters=null) {
  validateDataset(dataset);exampleRequest++;clearDisplay();exactPartial=null;previousExact=null;exactHistory.clear();state.dataset=dataset;if(parameters)state.parameters={...DEFAULTS,...parameters};
  $('time-panel').hidden=dataset.x_kind!=='time';
  if(dataset.x_kind==='time'){
    state.parameters.period=parameters?.period??dataset.period;
    state.parameters.epoch=parameters?.epoch??dataset.epoch;
    const origin=Math.min(...dataset.x);
    $('time-origin').textContent='Days since '+origin.toFixed(5)+(dataset.time_system?' ('+dataset.time_system+')':'')+
      ' · '+(dataset.y_kind==='magnitude'?'magnitude':'flux')+' · dashed guides mark phase zero';
  }
  $('period-span').value=dataset.x_kind==='time'?'0.001':'full';
  $('epoch-span').value='0.001';$('eccentricity-span').value='full';
  Object.keys(zoomOptions).forEach(centerSlider);
  state.result=null;state.revision++;updateControlValues();updateStats();drawPlots();
  $('dataset-name').textContent=dataset.name||'Uploaded observations';$('dataset-description').textContent=`${dataset.synthetic?'Synthetic observations':'Your observations'} · ${dataset.x.length} points · ${dataset.y_kind==='magnitude'?'magnitudes converted to flux':'normalized flux'}`;
  if(dataset.provenance){
    const origin=dataset.synthetic?'Synthetic PHOEBE':dataset.provenance.catalog==='Kepler Eclipsing Binary Catalog, third revision'?'Kepler observations':'Observations';
    $('dataset-description').textContent=origin+' · '+dataset.x.length+' points · '+dataset.description;
  }
  $('export-button').disabled=true;$('fit-button').disabled=true;requestModel('compute');
}

function validateDataset(d) {
  if(!d||!Array.isArray(d.x)||!Array.isArray(d.y)||d.x.length!==d.y.length||d.x.length<8||d.x.length>5000)throw Error('Choose between 8 and 5,000 observations with matching coordinates and brightness values.');
  if(!['time','phase'].includes(d.x_kind)||!['flux','magnitude'].includes(d.y_kind))throw Error('Choose the coordinate and brightness formats.');
  if(!d.x.every(Number.isFinite)||!d.y.every(Number.isFinite))throw Error('Some selected data values are missing or non-numeric.');
  if(d.y_kind==='flux'&&d.y.some(v=>v<=0))throw Error('Flux values must be greater than zero.');
  if(d.sigma&&(!Array.isArray(d.sigma)||d.sigma.length!==d.x.length||d.sigma.some(v=>!Number.isFinite(v)||v<=0)))throw Error('Uncertainties must be finite and greater than zero.');
  if(d.x_kind==='time'&&(!Number.isFinite(d.period)||d.period<=0||!Number.isFinite(d.epoch)))throw Error('Time-series data need a positive period and a finite epoch, both in days.');
}

function parseText(text) {
  const lines=text.replace(/^\uFEFF/,'').split(/\r?\n/).map((s,i)=>({text:s.trim(),line:i+1})).filter(s=>s.text&&!s.text.startsWith('#'));
  if(lines.length<2)throw Error('The file does not contain enough rows.');
  const delimiter=lines[0].text.includes(',')?',':lines[0].text.includes('\t')?'\t':lines[0].text.includes(';')?';':null;
  function split(line) {
    if(!delimiter)return line.split(/\s+/);
    const cells=[];let cell='',quote=false;
    for(let i=0;i<line.length;i++) {const c=line[i];if(c==='"'){if(quote&&line[i+1]==='"'){cell+='"';i++;}else quote=!quote;}else if(c===delimiter&&!quote){cells.push(cell.trim());cell='';}else cell+=c;}
    if(quote)throw Error('A quoted field is not closed.');cells.push(cell.trim());return cells;
  }
  const first=split(lines[0].text),numeric=(s)=>s!==''&&Number.isFinite(Number(s));
  const header=first.slice(0,2).some(s=>!numeric(s));
  const headers=header?first:first.map((_,i)=>`Column ${i+1}`);
  const rows=lines.slice(header?1:0).map(s=>({cells:split(s.text),line:s.line}));
  if(headers.length<2)throw Error('The file needs at least two columns.');
  return {headers,rows};
}

function prepareImport(parsed,name) {
  parsedFile={...parsed,name};
  for(const [id,extra] of [['x-column',false],['y-column',false],['sigma-column',true]]) {
    const select=$(id);select.replaceChildren();if(extra)select.add(new Option('No uncertainty column','none'));
    parsed.headers.forEach((h,i)=>select.add(new Option(h,String(i))));
  }
  $('x-column').value='0';$('y-column').value='1';$('sigma-column').value=parsed.headers.length>=3?'2':'none';
  const first=Number(parsed.rows[0]?.cells[0]);$('x-kind').value=/phase/i.test(parsed.headers[0])||Math.abs(first)<=2?'phase':'time';
  $('y-kind').value=/mag/i.test(parsed.headers[1])?'magnitude':'flux';
  $('import-period').value=state.parameters.period;$('import-epoch').value=$('x-kind').value==='time'?first:state.parameters.epoch;
  $('timing-options').hidden=$('x-kind').value!=='time';$('import-options').hidden=false;$('load-file-button').disabled=false;
  const table=document.createElement('table'),head=document.createElement('tr');
  for(const h of parsed.headers){const td=document.createElement('th');td.textContent=h;head.append(td);}table.append(head);
  for(const row of parsed.rows.slice(0,4)){const tr=document.createElement('tr');for(const v of row.cells){const td=document.createElement('td');td.textContent=v;tr.append(td);}table.append(tr);}
  $('data-preview').replaceChildren(table);
}

function download(name,text,type='application/json') {const url=URL.createObjectURL(new Blob([text],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
async function loadExample(notify=true) {
  const id=++exampleRequest,choice=$('example-choice').value;
  try{
    const response=await fetch(new URL('../'+choice,import.meta.url));
    if(!response.ok)throw Error('The example could not be loaded.');
    const data=await response.json();
    if(id!==exampleRequest || choice!==$('example-choice').value || state.fitting)return;
    installDataset(data,choice==='example.json'?DEFAULTS:(data.truth||data.starting_parameters));
    if(notify)toast('Loaded '+data.name+'.');
  }catch(e){if(id===exampleRequest)toast(cleanError(e));}
}
function bindEvents() {
  $('rv-rescale').onclick=()=>drawVelocityPlot(state.parameters,state.dataset,true);
  for(const el of document.querySelectorAll('.close-dialog'))el.addEventListener('click',()=>el.closest('dialog').close());
  for(const dialog of document.querySelectorAll('dialog'))dialog.addEventListener('click',(e)=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}});
  $('guide-button').onclick=()=>$('guide-dialog').showModal();
  $('tidal-phases').onchange=()=>{if(state.parameters.distortion)parametersChanged();};
  $('surface-workers').onchange=()=>{
    if(state.current?.type==='compute' && (state.current.tides || state.current.heating))startEngine();
  };
  $('engine-retry').onclick=startEngine;
  $('reset-button').onclick=()=>{state.parameters={...DEFAULTS};Object.keys(zoomOptions).forEach(centerSlider);updateControlValues();parametersChanged();};
  $('example-button').onclick=()=>loadExample();
  for(const button of document.querySelectorAll('.quality'))button.onclick=()=>{state.quality=button.dataset.quality;document.querySelectorAll('.quality').forEach(b=>{b.classList.toggle('active',b===button);b.setAttribute('aria-pressed',String(b===button));});parametersChanged();scheduleCompute(50);};
  $('save-button').onclick=()=>{if(!state.dataset){toast('Load observations first.');return;}download('phoebe-lab-session.json',JSON.stringify({schema:'phoebe-lab-session-v1',parameters:state.parameters,dataset:state.dataset,quality:state.quality,tidal_phases:Number($('tidal-phases').value)},null,2));};
  $('export-button').onclick=()=>{if(state.result?.revision!==state.revision)return;download('phoebe-model.csv','phase,normalized_flux\n'+state.result.phases.map((x,i)=>`${x},${state.result.model[i]}`).join('\n')+'\n','text/csv');};
  $('stop-button').onclick=()=>{if(state.current?.type==='compute') {
    if(state.current.tides||state.current.heating){
      clearInterval(elapsedTimer);clearTimeout(computeTimer);
      state.worker.terminate();state.worker=null;state.current=null;state.queued=false;
      state.ready=false;engineFailed=true;setBusy(false);
      $('engine-pill').textContent='Engine stopped';
      $('engine-title').textContent='Surface calculation stopped';$('engine-detail').textContent='Change a parameter or retry to restart.';
      $('engine-banner').hidden=false;$('engine-retry').hidden=false;
      status('Stopped · surface calculation');return;
    }
    state.current.stopped=true;status('Stopping after this batch…','busy');return;
  }toast('Calculation stopped. Restarting the cached browser engine.');startEngine();};
  $('import-button').onclick=()=>{$('import-error').textContent='';$('import-dialog').showModal();};
  $('x-kind').onchange=()=>$('timing-options').hidden=$('x-kind').value!=='time';
  $('data-file').onchange=async(e)=>{
    const file=e.target.files[0];if(!file)return;$('import-error').textContent='';
    try {
      if(/\.(phoebe|bundle|out|ps|model)$/i.test(file.name)) {
        $('import-dialog').close();nativeFiles.openFile(file);return;
      }
      if(file.size>5000000 && !file.name.toLowerCase().endsWith('.json'))throw Error('Choose a file smaller than 5 MB.');
      const text=await file.text();
      if(file.name.toLowerCase().endsWith('.json')) {
        const project=JSON.parse(text);
        if(Array.isArray(project)){ $('import-dialog').close();nativeFiles.openFile(file);return; }
        if(project.schema!=='phoebe-lab-session-v1')throw Error('This is not a PHOEBE Lab session file.');
        for(const [key,spec] of parameterInputs){const value=Number(project.parameters?.[key]);if(!Number.isFinite(value)||value<spec.min||value>spec.max)throw Error(`The saved ${key} value is outside this app’s supported range.`);}
        for(const key of ['distortion','irradiation'])if(typeof project.parameters?.[key]!=='boolean')throw Error(`The saved ${key} setting is invalid.`);
        $('tidal-phases').value=project.tidal_phases===129?'129':'513'; // Older sessions used 513.
        state.quality=project.quality==='refined'?'refined':'preview';
        document.querySelectorAll('.quality').forEach(b=>{const active=b.dataset.quality===state.quality;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active));});
        installDataset(project.dataset,project.parameters);$('import-dialog').close();toast('Restored the saved session.');return;
      }
      prepareImport(parseText(text),file.name);
    }catch(error){$('import-error').textContent=cleanError(error);$('load-file-button').disabled=true;}
  };
  $('import-form').onsubmit=(e)=>{
    e.preventDefault();if(!parsedFile)return;
    try {
      const xc=Number($('x-column').value),yc=Number($('y-column').value),sc=$('sigma-column').value;
      if(xc===yc)throw Error('Choose different coordinate and brightness columns.');
      const d={name:parsedFile.name,x_kind:$('x-kind').value,y_kind:$('y-kind').value,x:[],y:[],sigma:sc==='none'?null:[],period:Number($('import-period').value),epoch:Number($('import-epoch').value),synthetic:false};
      const read=(row,col)=>{const value=row.cells[col];if(value===undefined||value.trim()===''||!Number.isFinite(Number(value)))throw Error(`Row ${row.line} has an invalid value in column ${col+1}.`);return Number(value);};
      for(const row of parsedFile.rows){d.x.push(read(row,xc));d.y.push(read(row,yc));if(d.sigma)d.sigma.push(read(row,Number(sc)));}
      installDataset(d);$('import-dialog').close();toast(`Loaded ${d.x.length} observations.`);
    }catch(error){$('import-error').textContent=cleanError(error);}
  };
  $('fit-button').onclick=()=>{$('fit-error').textContent='';$('fit-dialog').showModal();};
  $('fit-form').onsubmit=(e)=>{e.preventDefault();const keys=[...document.querySelectorAll('input[name=fit]:checked')].map(x=>x.value);if(!keys.length){$('fit-error').textContent='Select at least one parameter.';return;}if(keys.includes('omega') && state.parameters.eccentricity===0 && !keys.includes('eccentricity')){$('fit-error').textContent='Also select eccentricity to fit periastron angle from a circular orbit.';return;}if(state.busy){$('fit-error').textContent='Wait for the current model to finish.';return;}$('fit-dialog').close();requestModel('fit',keys);};
  $('light-curve').addEventListener('pointermove',(e)=>{
    const canvas=$('light-curve'),c=canvas.chart;if(!c||!c.data.phase.length)return;
    const rect=canvas.getBoundingClientRect(),x=e.clientX-rect.left,y=e.clientY-rect.top;
    let nearest=-1,distance=18;
    c.data.phase.forEach((phase,i)=>{const d=Math.hypot(c.px(phase)-x,c.py(c.data.flux[i])-y);if(d<distance){nearest=i;distance=d;}});
    let tip=$('plot-tooltip');if(!tip){tip=document.createElement('div');tip.id='plot-tooltip';tip.className='plot-tooltip';canvas.parentElement.append(tip);}
    tip.hidden=nearest<0;if(nearest<0)return;
    tip.textContent=`Phase ${c.data.phase[nearest].toFixed(4)} · Flux ${c.data.flux[nearest].toFixed(4)}`;tip.style.left=`${Math.min(x+10,c.w-220)}px`;tip.style.top=`${Math.max(7,y-35)}px`;
  });
  $('light-curve').addEventListener('pointerleave',()=>{if($('plot-tooltip'))$('plot-tooltip').hidden=true;});
  new ResizeObserver(drawPlots).observe($('light-curve'));
}

const {makePredictor}=await import('../experiment/predict.mjs?v=47e171fda8bf7415');
const artifact=await (await fetch(new URL('../experiment/display-model.json?v=51c7e6a97f6685df',import.meta.url))).json();
if(artifact.schema!==1 || artifact.accepted!==true) throw Error('A validated display model is required.');
const {makeJointPredictor}=await import('../experiment/joint_predict.mjs?v=5562a96a73d237db');
const jointSpec=await (await fetch(new URL('../experiment/joint.json?v=2f7ab5f687f515f8',import.meta.url))).json();
const joint=makeJointPredictor(jointSpec), paired=makePredictor(artifact);
const {makeDiscModel}=await import('../experiment/discs.mjs?v=55a956a80f13dcfd');
const {makeEightPredictor}=await import('../experiment/eight_predict.mjs');
const eightSpec=await (await fetch(new URL('../experiment/eight.json',import.meta.url))).json();
const discModel=makeDiscModel(artifact.table,artifact.n,artifact.fixed);
const exploratory=makeEightPredictor(eightSpec,discModel);
// The optional drag artifact can load alongside the exact lab.
Promise.all([
  import('../experiment/surface_predict.mjs'),
  fetch(new URL('../experiment/surface.json',import.meta.url)).then(response=>{
    if(!response.ok) throw Error(`Surface preview data returned ${response.status}`);
    return response.json();
  }),
]).then(([module,specs])=>{predictSurface=module.makeSurfacePredictor(specs,discModel);})
  .catch(error=>console.warn('Surface drag preview unavailable',error));
const ranges=GROUPS.flatMap(group=>group.items);
predictDisplay=p=>joint(p) ?? paired(p) ??
  (!p.distortion && !p.irradiation && ranges.every(([k,label,lo,hi])=>Number.isFinite(p[k]) && lo<=p[k] && p[k]<=hi)
    ? exploratory(p) : null);
const coverage=document.createElement('p');
coverage.className='muted small';
coverage.textContent='Start from defaults. A purple drag curve supports inclination, eccentricity (0–0.24) and periastron angle together, or inclination, both radii and temperature ratio on a circular orbit. The amber network previews other eight-slider combinations. Try the 30° non-eclipsing example at inclinations of 18–46° to preview tides and heating. The legend identifies any omitted effects.';
$('parameter-controls').before(coverage);
document.querySelector('#curve-title + span').textContent='Drag preview · purple tested / amber exploratory';
const nativeFiles=bindNativeFiles(()=>{
  if(!state.dataset || state.result?.revision!==state.revision || state.busy)
    throw Error('Wait for the current exact lab result before creating a native bundle.');
  return {parameters:{...state.parameters},dataset:state.dataset,quality:state.result.quality,phases:state.result.phases};
});
renderControls();bindEvents();drawPlots();
const exampleSlug=new URLSearchParams(location.search).get('example');
const picker=$('example-choice');
const linked=Array.from(picker.options).find(option=>option.value==='examples/'+exampleSlug+'.json');
if(linked)picker.value=linked.value;
await loadExample(false);
startEngine();
