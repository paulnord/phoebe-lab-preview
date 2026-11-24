import {bindOrbitViewer,surfaceGeometryKey} from './orbit-viewer.mjs?v=native-surfaces1';
import {bindSolveOrbit,bindStarGuide} from './stellar-shapes.mjs?v=geometry1';
import {clearSeparation, supported as detachedWithin} from '../experiment/regional-surface.mjs?v=8d3e42c13d757728';
import {bindVelocityPlot,parseVelocity,validateVelocity} from './radial-velocity.mjs?v=f528f9d33a0f0306';
import {bindNativeFiles} from './native-files.js?v=3b11b7a04ffb63a2';
import {requestMatches} from './request-guard.mjs?v=geometry1';
import {createScientificEngine,nativeKernelConfig} from './engine-client.mjs?v=colab-native1';
import {applyColabRuntimeUI,canOpenAdvancedWorkspace,isNativeProjectJson,NATIVE_PROJECT_ERROR} from './runtime-mode.mjs?v=colab-native2';
const $ = (id) => document.getElementById(id);
applyColabRuntimeUI(document,nativeKernelConfig);
const DEFAULTS = {contact:false,semidetached:false,donor:'primary',inclination:84.5,radius_primary:.21,radius_secondary:.17,fillout_factor:.25,temperature_ratio:.84,mass_ratio:.75,eccentricity:0,omega:90,period:1.8,epoch:0,distortion:false,irradiation:false};
const GROUPS = [
  {name:'Orbit',items:[
    ['inclination','Inclination',0,90,.1,1,'°','0° is face-on. At 90° the orbit is edge-on.'],
    ['eccentricity','Eccentricity',0,.35,.001,4,'','Zero is a circular orbit. Increasing eccentricity brings the stars closer together at periastron.'],
    ['omega','Periastron angle',0,360,1,0,'°','The orientation of an eccentric orbit.'],
  ]},
  {name:'The stars',items:[
    ['radius_primary','Primary radius / separation',.10,.32,.002,3,'','Larger stars generally make broader eclipses.'],
    ['radius_secondary','Secondary radius / separation',.08,.29,.002,3,'','Compare the eclipse widths and depths.'],
    ['fillout_factor','Contact fill-out factor',.10,.50,.005,3,'','Sets the shared Roche-envelope potential in contact mode.'],
    ['temperature_ratio','Temperature ratio T₂ / T₁',.58,1.10,.005,3,'','Watch the relative depths of the two eclipses.'],
    ['mass_ratio','Mass ratio M₂ / M₁',.2,1.5,.01,2,'','At fixed fractional radii, changing mass ratio mainly shifts surface gravity in the spherical preview.'],
  ]},
  {name:'Timing',items:[
    ['period','Orbital period',.1,100,.01,7,'d','Use the arrow keys on a zoomed slider to step by 0.0000001 day.'],
    ['epoch','Primary-eclipse epoch',-1e9,1e9,.001,7,'d','Time of phase zero, in the same time system as your observations.'],
  ]},
];
const state = {parameters:{...DEFAULTS},quality:'preview',dataset:null,result:null,revision:0,ready:false,busy:false,fitting:false,queued:false,worker:null,request:0,current:null};
let computeTimer,engineRestartTimer,toastTimer,parsedFile,exampleRequest=0;
const parameterInputs = new Map();
let predictEccentricSweep = null, eccentricSweepSpec = null;
let predictNear = null, nearRocheReference = null, predictBroad = null, predictTemperature = null, predictSurface = null, predictRegional = null, predictDisplay = null, predictContact = null, predictSemi = null, dragView = null, pointerHeld = false;
const modeOf=p=>p.contact?'contact':p.semidetached?'semi':'detached';
const modeSnapshots={detached:{...DEFAULTS},semi:null,contact:null};
let timingRevision=-1, liveTiming=null;
let exactPartial = null, previousExact = null, engineFailed = false, elapsedTimer;
let orbitSurface={key:null,status:'idle',mesh:null,error:null,id:null},surfaceRequest=0,surfaceTimer;
let drawOrbitViewer=()=>{};
const exactHistory = new Map();
const modelHistory=[];
let historyIndex=-1;

function updateHistoryButtons() {
  const locked=state.fitting || pointerHeld;
  $('undo-model').disabled=locked || historyIndex<=0;
  $('redo-model').disabled=locked || historyIndex<0 || historyIndex===modelHistory.length-1;
}

function recordModel() {
  const previous=modelHistory[historyIndex];
  if(!previous || Object.keys(DEFAULTS).some(key=>previous[key]!==state.parameters[key])) {
    modelHistory.splice(historyIndex+1);
    modelHistory.push({...state.parameters});
    if(modelHistory.length>101) modelHistory.shift();
    historyIndex=modelHistory.length-1;
  }
  updateHistoryButtons();
}

function stepModel(direction) {
  const target=historyIndex+direction;
  if(state.fitting || pointerHeld || target<0 || target>=modelHistory.length) return;
  const before=state.parameters;
  historyIndex=target;
  state.parameters={...modelHistory[target]};
  const changed=Object.keys(DEFAULTS).filter(key=>before[key]!==state.parameters[key]);
  Object.keys(zoomOptions).forEach(centerSlider);
  updateControlValues();
  parametersChanged(false,true,changed.length===1 ? changed[0] : null);
}

let latestCompleted=null, latestFit=null, previousReference=null;
let currentCurveLabel='PHOEBE model';
const plotSettings={preview:true,previous:true,signedLog:false};
try {
  const saved=JSON.parse(localStorage.getItem('phoebe.plot.settings')||'{}');
  for(const key of Object.keys(plotSettings)) if(typeof saved?.[key]==='boolean')plotSettings[key]=saved[key];
} catch { /* Use default visibility when browser storage is unavailable. */ }

const plotPhases=()=>state.parameters.distortion || state.parameters.contact || state.parameters.semidetached ? Number($('tidal-phases').value) : 513;
const geometryKey=()=>JSON.stringify([state.quality,plotPhases(),...Object.keys(DEFAULTS).map(k=>state.parameters[k])]);

function rememberExact(result) {
  latestCompleted=result;
  if(result.fit) latestFit=result;
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
  const preview=dragView || approximateView();
  clearDisplay();exactPartial=null;
  showAgreement(preview,saved,true);
  state.result={...saved,revision:state.revision};previousExact=state.result;latestCompleted=state.result;
  setBusy(false);$('export-button').disabled=false;
  $('plot-placeholder').hidden=true;
  status(`Exact PHOEBE · ${saved.phases.length} phases · restored`);drawPlots();updateStats();
  return true;
}
const legend = document.querySelector('.chart-legend span:last-child');

function labelCurve(text) {
  currentCurveLabel=text;
  legend.lastChild.textContent = text;
  const swatch=legend.querySelector('i');
  const partial=exactPartial?.revision===state.revision;
  const faint=!!dragView && !partial;
  legend.hidden=text==='Previous-period PHOEBE curve' || (faint && !plotSettings.preview) || (!dragView && !partial && text.startsWith('Previous PHOEBE curve'));
  const key=$('preview-overlay-key');
  key.hidden=!(plotSettings.preview && dragView && partial);
  if (!key.hidden) {
    key.title=previewLabel();
    key.lastChild.textContent=dragView.savedPreview ? 'Saved PHOEBE preview' : dragView.omitted?.length ? key.title : dragView.flatSphere ? 'Spherical preview' :
      dragView.surfaceMode ? 'Preview · '+dragView.surfaceMode : 'Preview';
    const previewSwatch=key.querySelector('i');
    previewSwatch.style.backgroundColor=dragView.exploratory ? '#b56a08' : '#6a59da';
    previewSwatch.style.opacity='.36';
    previewSwatch.style.height='7px';
  }
  swatch.style.backgroundColor=faint && dragView.exploratory ? '#b56a08' : '';
  swatch.style.height=faint ? '8px' : '';
  swatch.style.opacity=faint ? '.36' : '';
  swatch.style.filter=faint ? 'blur(1.8px)' : '';
}
function clearDisplay() {
  $('preview-agreement').hidden=true;
  dragView = null;
  labelCurve('PHOEBE model');
}

function clearUnheated(p) {
  return !p.contact && !p.semidetached && p.irradiation === false && inSliderRanges(p) && detachedWithin(p,{}) &&
    clearSeparation(p,p.distortion ? 1.2 : 1);
}

function nearTidalLimit(p) {
  return !p.contact && !p.semidetached && p.distortion && !detachedWithin(p,{},.85);
}
function secondaryOverflows(p) {
  const spec=eccentricSweepSpec;
  return spec && p.eccentricity>=spec.secondaryLimit &&
    ['mass_ratio','radius_primary','radius_secondary'].every(key=>p[key]===spec.fixed[key]);
}
function nearLimitLabel(p) {
  return secondaryOverflows(p)?'Secondary fills its Roche lobe at periastron':'Near Roche limit · waiting for PHOEBE';
}
function approximateView() {
  const p=state.parameters;
  if(p.contact){
    if(!state.dataset || !predictContact)return null;
    const curve=predictContact({...p,epoch:0});
    return curve ? {...curve,...compareDisplayCurve(curve,normalizedData()),exploratory:true,omitted:[]} : null;
  }
  if(p.semidetached){
    if(!state.dataset || !predictSemi)return null;
    const curve=predictSemi({...p,epoch:0});
    return curve ? {...curve,...compareDisplayCurve(curve,normalizedData()),exploratory:true,omitted:[]} : null;
  }
  const omitted=[p.distortion && 'tides',p.irradiation && 'heating'].filter(Boolean);
  if (!state.dataset || !predictDisplay || secondaryOverflows(p)) return null;
  if(nearRocheReference && Object.entries(nearRocheReference.parameters).every(([key,value])=>p[key]===value)){
    const mode=p.distortion?(p.irradiation?'tides and heating':'tides'):(p.irradiation?'heating':'spherical');
    const curve={phases:nearRocheReference.phases,model:nearRocheReference.models[mode]};
    return {...compareDisplayCurve(curve,normalizedData()),savedPreview:true,surfaceMode:mode,omitted:[]};
  }
  const eccentricSweep=predictEccentricSweep?.(p);
  if(eccentricSweep)return {...eccentricSweep,...compareDisplayCurve(eccentricSweep,normalizedData()),omitted:[]};
  const clear = clearUnheated(p);
  if (clear && !p.distortion) {
    // Two unheated spherical photospheres present constant projected light.
    const line = {phases:[-.5,.5],model:[1,1]};
    return {...compareDisplayCurve(line,normalizedData()),flatSphere:true,omitted:[]};
  }
  if (state.quality!=='preview' && !omitted.length) return null;
  // Epoch places observations in phase. The phase-domain geometry uses a relative origin.
  const geometry=clear ? {...p,epoch:0} : p;
  const sweep=predictTemperature?.(geometry);
  const surface=(sweep?.preferInOverlap ? sweep : null) ?? predictSurface?.(geometry) ?? predictRegional?.(geometry) ?? sweep;
  const sphere={...p,epoch:0,distortion:false,irradiation:false};
  const calibratedSphere=!omitted.length && (joint(sphere) ?? paired(sphere));
  const broad=!surface && !calibratedSphere && (predictBroad?.({...p,epoch:0}) ?? predictNear?.(p));
  if(!surface && !broad && nearTidalLimit(p))return null;
  const curve=surface || calibratedSphere || broad || predictDisplay(sphere) || (omitted.length && inSliderRanges(sphere) && discModel(sphere));
  if (!curve) return null;
  const scaled=compareDisplayCurve(curve, normalizedData());
  return {...curve,...scaled,exploratory:!!(omitted.length||curve.exploratory),omitted:(surface || broad) ? [] : omitted};
}

// Both lists are sorted in phase. A single pass also handles the uneven grids
// produced while the exact curve is being refined.
function compareDisplayCurve(curve, obs, matchObservations=true) {
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
  const scale=matchObservations ? numerator/denominator : 1;
  const modelAtData=predicted.map(f=>scale*f);
  return {phases:x,model:y.map(f=>scale*f),
          comparison:{...obs,model_at_data:modelAtData,residual:modelAtData.map((f,i)=>obs.flux[i]-f)}};
}

function showAgreement(preview, exact, complete) {
  const target=$('preview-agreement');
  target.hidden=!preview;
  if (!preview) return;
  const x=preview.phases, y=preview.model;
  let j=0, squared=0;
  for (let i=0;i<exact.phases.length;i++) {
    const phase=exact.phases[i];
    while (j<x.length-2 && x[j+1]<phase) j++;
    const t=Math.max(0,Math.min(1,(phase-x[j])/(x[j+1]-x[j])));
    const delta=y[j]+t*(y[j+1]-y[j])-exact.model[i];
    squared+=delta*delta;
  }
  const rms=Math.sqrt(squared/exact.phases.length);
  const progress=complete ? 'Final' : 'So far';
  target.textContent=progress+' · Preview vs PHOEBE · RMS '+(100*rms).toFixed(3)+'% of normalized flux · '+exact.phases.length+' phase points';
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
  if(prior)return {...compareDisplayCurve(prior,normalizedData()),prior:true,source:prior,label:'Preview · PHOEBE curve at previous period'};
  return null;
}

function releasePointer() {
  if (!pointerHeld) return;
  pointerHeld=false;
  recordModel();
  scheduleCompute(80);
}
window.addEventListener('pointerup',releasePointer);
window.addEventListener('pointercancel',releasePointer);
window.addEventListener('blur',releasePointer);

function toast(text) { $('toast').textContent=text; $('toast').hidden=false; clearTimeout(toastTimer); toastTimer=setTimeout(()=>$('toast').hidden=true,6500); }
const showSolveOrbit=bindSolveOrbit($('solve-sky'));
function status(text,kind='ready') {
  const iconClass=kind==='busy'?'solve-orbit':kind==='error'?'status-dot error':'status-dot';
  const icon=$('model-indicator');
  if(icon.className!==iconClass)icon.className=iconClass;
  showSolveOrbit(kind==='busy',state.parameters);
  $('model-status-text').textContent=text;
}
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
      const row=document.createElement('div');row.className='parameter';row.dataset.parameter=key;
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
      parameterInputs.set(key,{number,range,digits,min,max,title,hint});
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
      if(range) {range.addEventListener('pointerdown',()=>{pointerHeld=true;updateHistoryButtons();clearTimeout(computeTimer);});range.addEventListener('input',()=>update(range));range.addEventListener('change',()=>scheduleCompute(80));}
    }
    $('parameter-controls').append(section);
  }
  for(const key of ['distortion','irradiation']) $(key).addEventListener('change',()=>{state.parameters[key]=$(key).checked;drawStarGuide(state.parameters);parametersChanged(false,true);});
  for(const radio of document.querySelectorAll('input[name="geometry"]'))radio.addEventListener('change',()=>{if(radio.checked)setGeometryMode(radio.value);});
  $('donor').addEventListener('change',()=>{state.parameters.donor=$('donor').value;updateControlValues();parametersChanged(false,true,'donor');});
  updateControlValues();
}

function setGeometryMode(mode) {
  const prior=modeOf(state.parameters);if(mode===prior)return;
  modeSnapshots[prior]={...state.parameters};
  if(modeSnapshots[mode])state.parameters={...modeSnapshots[mode]};
  else if(mode==='contact')state.parameters={...state.parameters,contact:true,semidetached:false,fillout_factor:.25,eccentricity:0,omega:90,period:1.8,distortion:false,irradiation:false};
  else if(mode==='semi')state.parameters={...state.parameters,contact:false,semidetached:true,donor:'primary',radius_secondary:.195,eccentricity:0,omega:90,period:1.8,distortion:false,irradiation:false};
  else state.parameters={...DEFAULTS};
  Object.keys(zoomOptions).forEach(centerSlider);
  updateControlValues();
  parametersChanged(false,true,'geometry');
}

const drawStarGuide=bindStarGuide($('star-shape'),$('star-view'));
drawOrbitViewer=bindOrbitViewer(()=>{
  const parameters=state.parameters;
  const pack=(curve,label)=>({parameters,curve,label,surface:orbitSurface});
  const partial=exactPartial?.revision===state.revision?exactPartial:null;
  const completed=state.result?.revision===state.revision &&
    Object.keys(DEFAULTS).every(k=>state.result.parameters?.[k]===parameters[k])?state.result:null;
  const timing=timingRevision===state.revision && !liveTiming?.prior?liveTiming:null;
  if(partial)return pack(partial,'PHOEBE in progress · '+partial.phases.length+' computed phases');
  if(completed)return pack(completed,'PHOEBE · '+completed.quality+' resolution · '+completed.phases.length+' computed phases');
  if(dragView)return pack(dragView,previewLabel());
  if(timing)return pack(timing,timing.label);
  return pack(null,'No curve for the current settings yet.');
},()=>scheduleOrbitSurface(0,true));
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
  const mode=modeOf(state.parameters),contact=mode==='contact',semi=mode==='semi';
  $('geometry-'+mode).checked=true;$('donor').value=state.parameters.donor;$('donor-row').hidden=!semi;
  $('geometry-explanation').textContent=contact
    ? 'Contact: one fill-out factor controls the connected common envelope.'
    : semi
    ? `Semi-detached: the ${state.parameters.donor} fills its Roche lobe; adjust the other star with its one visible radius control.`
    : 'Detached: adjust both stellar radii independently.';
  for(const [key,ordinary] of [['radius_primary','Primary radius / separation'],['radius_secondary','Secondary radius / separation']]){
    const item=parameterInputs.get(key),free=semi && key===(state.parameters.donor==='primary'?'radius_secondary':'radius_primary');
    const name=free ? `Free ${key==='radius_primary'?'primary':'secondary'} radius / separation` : ordinary;
    item.title.textContent=name;item.number.setAttribute('aria-label',name);item.range.setAttribute('aria-label',name+' slider');
    item.hint.textContent=free ? 'The donor is fixed at its Roche lobe; this is the other star’s independent radius.' : key==='radius_primary' ? 'Larger stars generally make broader eclipses.' : 'Compare the eclipse widths and depths.';
  }
  $('distortion').checked=state.parameters.distortion;$('irradiation').checked=state.parameters.irradiation;
  $('distortion').disabled=mode!=='detached' || state.fitting;
  document.querySelector('[data-parameter="radius_primary"]').hidden=contact || (semi&&state.parameters.donor==='primary');
  document.querySelector('[data-parameter="radius_secondary"]').hidden=contact || (semi&&state.parameters.donor==='secondary');
  for(const key of ['eccentricity','omega'])document.querySelector(`[data-parameter="${key}"]`).hidden=mode!=='detached';
  document.querySelector('[data-parameter="fillout_factor"]').hidden=!contact;
  const freeRadius=state.parameters.donor==='primary'?'radius_secondary':'radius_primary';
  const allowed=contact?new Set(['inclination','fillout_factor','temperature_ratio','mass_ratio']):semi?new Set(['inclination',freeRadius,'temperature_ratio','mass_ratio','period']):null;
  for(const input of document.querySelectorAll('input[name=fit]'))input.closest('label').hidden=allowed?!allowed.has(input.value):input.value==='fillout_factor';
  document.querySelector('input[name=fit][value="radius_primary"]').closest('label').querySelector('strong').textContent='Primary radius / separation';
  document.querySelector('input[name=fit][value="radius_secondary"]').closest('label').querySelector('strong').textContent='Secondary radius / separation';
  if(semi){
    const freeFit=document.querySelector(`input[name=fit][value="${freeRadius}"]`);
    freeFit.closest('label').querySelector('strong').textContent=`Free ${freeRadius==='radius_primary'?'primary':'secondary'} radius`;
  }
  $('fit-scope').textContent=contact
    ? 'Contact fits use inclination, shared fill-out factor, temperature ratio and mass ratio. The final curve, residuals and CSV are recomputed natively at 513 phases.'
    : semi
    ? `Semi-detached fits keep the ${state.parameters.donor} donor on its native Roche constraint and can move inclination, the free-star radius, temperature ratio, mass ratio or period. The final curve is recomputed natively at 513 phases.`
    : 'Choose detached model parameters and a phase budget for each trial. Every observation contributes; the final curve, residuals and CSV are recomputed natively at 513 phases.';
  $('example-button').disabled=mode!=='detached' || state.fitting;
  drawStarGuide(state.parameters);
}

function previewLabel() {
  if(state.parameters.contact)return 'Experimental contact surrogate · native validation required';
  if(state.parameters.semidetached)return `Experimental semi-detached surrogate · ${state.parameters.donor} donor · native validation required`;
  if (dragView.savedPreview) return 'Saved PHOEBE preview · '+dragView.surfaceMode+' · 256 phases';
  if (dragView.flatSphere) return 'Spherical preview · no heating or eclipses';
  return dragView?.surfaceMode ? 'Approximate surface preview · '+dragView.surfaceMode+(dragView.surfaceRegion?' · '+dragView.surfaceRegion:'')+(state.quality==='refined'?' · preview model':'') : dragView?.omitted?.length
    ? 'Approximate spherical curve · '+dragView.omitted.join(' and ')+' omitted'+(dragView.atEdge?' · atmosphere clamped':'')
    : dragView?.exploratory
    ? ['Approximate · eight-slider neural preview', dragView.periodOutside ? 'outside joint training periods' : '', dragView.atEdge ? 'atmosphere clamped' : ''].filter(Boolean).join(' · ')
    : 'Approximate · drag preview';
}

function refreshPreview() {
  if (!state.dataset || state.fitting ||
      state.result?.revision===state.revision || exactPartial?.revision===state.revision ||
      timingRevision===state.revision) return;
  const curve=approximateView();
  if (!curve) {
    if(nearTidalLimit(state.parameters) || secondaryOverflows(state.parameters))labelCurve(nearLimitLabel(state.parameters));
    return;
  }
  dragView=curve;
  labelCurve(previewLabel());
  $('plot-placeholder').hidden=true;
  drawPlots();
}

function unavailableReason() {
  if(state.parameters.contact)return 'Contact preview unavailable outside its validated domain · release for native PHOEBE';
  if(state.parameters.semidetached)return 'Semi-detached preview unavailable outside its validated domain · release for native PHOEBE';
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
  if(!pointerHeld)recordModel();
  previousReference=latestFit||latestCompleted;
  $('preview-agreement').hidden=true;
  const interrupt=physics && state.current?.type==='compute' &&
    (state.current.mode!==modeOf(state.parameters) || (state.current.tides && !state.parameters.distortion) || (state.current.heating && !state.parameters.irradiation));
  if(physics && key==='geometry' && !interrupt){clearTimeout(engineRestartTimer);engineRestartTimer=null;}
  exactPartial=null;
  state.revision++;
  $('export-button').disabled=true;
  $('fit-button').disabled=true;
  timingRevision=key==='epoch'||key==='period' ? state.revision : -1;
  liveTiming=timingRevision===state.revision ? timingDisplay() : null;
  if(timingRevision===state.revision)dragView=liveTiming?.omitted ? liveTiming : null;
  else dragView=slider || physics || state.parameters.distortion || state.parameters.irradiation || clearUnheated(state.parameters) ? approximateView() : null;
  labelCurve(dragView ? previewLabel() : liveTiming ? (liveTiming.prior?'Previous-period PHOEBE curve':'Exact PHOEBE curve · updated phases') : (nearTidalLimit(state.parameters) || secondaryOverflows(state.parameters)) ? nearLimitLabel(state.parameters) : previousExact ? 'Previous PHOEBE curve · awaiting recalculation' :
    slider ? unavailableReason() : 'Waiting for PHOEBE');
  if(dragView) $('plot-placeholder').hidden=true;
  status('Parameters changed · waiting for PHOEBE','busy');
  scheduleOrbitSurface();
  drawPlots();updateStats();
  if(!pointerHeld){
    if(interrupt){
      clearTimeout(computeTimer);clearTimeout(engineRestartTimer);
      // A running PHOEBE surface generator cannot be cancelled cooperatively:
      // its worker must be replaced. Let rapid geometry clicks settle first so
      // we create only one new Pyodide/WASM interpreter for the final mode.
      engineRestartTimer=setTimeout(()=>{
        engineRestartTimer=null;
        const current=state.current;
        if(current?.type==='compute' && current.mode!==modeOf(state.parameters))startEngine();
        else if(state.busy)state.queued=true;
        else requestModel('compute');
      },500);
      status('Geometry changed · safely stopping the previous PHOEBE model','busy');
      return;
    }
    if(!slider && restoreExact()){
      if(engineFailed){startEngine();restoreExact();}
      return;
    }
    if(engineFailed){startEngine();return;}
    scheduleCompute();
  }
}
function scheduleCompute(delay=450) {clearTimeout(computeTimer);computeTimer=setTimeout(()=>requestModel('compute'),delay);}

function scheduleOrbitSurface(delay=350,retry=false) {
  clearTimeout(surfaceTimer);
  const key=surfaceGeometryKey(state.parameters);
  if(!key){orbitSurface={key:null,status:'idle',mesh:null,error:null,id:null};drawOrbitViewer();return;}
  if(orbitSurface.key!==key){orbitSurface={key,status:'pending',mesh:null,error:null,id:null};drawOrbitViewer();}
  else if(orbitSurface.status==='ready' || (orbitSurface.status==='pending'&&orbitSurface.id) || (!retry&&orbitSurface.status==='error'))return;
  else if(retry&&orbitSurface.status==='error')orbitSurface={key,status:'pending',mesh:null,error:null,id:null};
  surfaceTimer=setTimeout(requestOrbitSurface,delay);
}

function requestOrbitSurface() {
  const key=surfaceGeometryKey(state.parameters);
  if(!key || key!==orbitSurface.key)return;
  if(!state.ready || state.busy){surfaceTimer=setTimeout(requestOrbitSurface,400);return;}
  const id=`surface-${++surfaceRequest}`;
  orbitSurface={key,status:'pending',mesh:null,error:null,id};drawOrbitViewer();
  state.worker.postMessage({type:'surface',id,payload:{parameters:{...state.parameters},triangles:500}});
}
function setBusy(busy,fitting=false) {
  state.busy=busy;state.fitting=fitting;updateHistoryButtons();
  $('fit-button').disabled=!state.ready||busy||state.result?.revision!==state.revision;
  $('stop-button').hidden=!busy;
  document.querySelectorAll('.quality').forEach(button=>{button.disabled=fitting;});
  $('tidal-phases').disabled=fitting;
  $('surface-workers').disabled=fitting;Object.keys(zoomOptions).forEach(key=>{$(key+'-span').disabled=fitting;});
  $('example-choice').disabled=fitting;
  $('import-button').disabled=fitting;$('example-button').disabled=fitting || modeOf(state.parameters)!=='detached';$('reset-button').disabled=fitting;
  for(const {number,range} of parameterInputs.values()) {number.disabled=fitting;if(range)range.disabled=fitting;}
  for(const radio of document.querySelectorAll('input[name="geometry"]'))radio.disabled=fitting;
  $('donor').disabled=fitting;$('distortion').disabled=fitting || modeOf(state.parameters)!=='detached';$('irradiation').disabled=fitting;
}

function startEngine() {
  clearTimeout(engineRestartTimer);engineRestartTimer=null;
  clearDisplay();exactPartial=null;engineFailed=false;
  clearInterval(elapsedTimer);
  if(state.worker)state.worker.terminate();
  if(orbitSurface.key)orbitSurface={...orbitSurface,status:'pending',mesh:null,error:null,id:null};
  state.ready=false;setBusy(false);state.queued=false;state.current=null;
  refreshPreview();
  $('engine-banner').hidden=false;$('engine-retry').hidden=true;
  $('engine-pill').innerHTML=nativeKernelConfig?'<span class="status-dot loading"></span>Connecting to Colab native engine':'<span class="status-dot loading"></span>Loading browser engine';
  status(nativeKernelConfig?'Connecting to native PHOEBE in this Colab runtime…':'Starting the browser engine…','busy');
  state.worker=createScientificEngine(new URL('./engine.worker.js?v=switch-safe1',import.meta.url));
  const worker=state.worker;
  state.worker.onmessage=({data})=>{
    if(worker!==state.worker)return;
    if(data.type==='status') {$('engine-title').textContent=data.title;$('engine-detail').textContent=data.detail;return;}
    if(data.type==='ready') {
      state.ready=true;$('engine-banner').hidden=true;
      $('engine-pill').innerHTML=nativeKernelConfig?'<span class="status-dot"></span>Colab native engine ready':'<span class="status-dot"></span>Browser engine ready';
      requestModel('compute');scheduleOrbitSurface();return;
    }
    if(data.type==='fatal') {
      engineFailed=true;state.ready=false;setBusy(false);$('engine-title').textContent='The scientific engine could not start';$('engine-detail').textContent=cleanError(data.error);$('engine-retry').hidden=false;
      $('engine-pill').innerHTML='<span class="status-dot error"></span>Engine unavailable';status(cleanError(data.error),'error');return;
    }
    if(data.type==='surface_result') {
      if(data.id===orbitSurface.id && surfaceGeometryKey(state.parameters)===orbitSurface.key){
        orbitSurface={...orbitSurface,status:'ready',mesh:data.value,error:null};drawOrbitViewer();
      }
      return;
    }
    if(data.type==='surface_error') {
      if(data.id===orbitSurface.id && surfaceGeometryKey(state.parameters)===orbitSurface.key){
        orbitSurface={...orbitSurface,status:'error',mesh:null,error:cleanError(data.error)};drawOrbitViewer();
      }
      return;
    }
    if(data.id!==state.current?.id)return;
    if(data.type==='fit_parameters') {
      const current=state.current;
      if(!requestMatches(current,state.revision,modeOf(state.parameters)) || current.stopped){
        state.current=null;setBusy(false);requestModel('compute');return;
      }
      state.parameters={...data.parameters};
      recordModel();
      current.revision=++state.revision;
      Object.keys(zoomOptions).forEach(centerSlider);
      updateControlValues();clearDisplay();
      dragView=approximateView();
      if(dragView)labelCurve(previewLabel());
      else if(previousExact)labelCurve('Previous PHOEBE curve · drawing fitted parameters');
      drawPlots();updateStats();
      status('Fit search complete · drawing the fitted PHOEBE curve','busy');
      state.worker.postMessage({type:'continue',id:current.id});
      return;
    }
    if(data.type==='partial') {
      const current=state.current;
      const advance=()=>{
        if(current!==state.current)return;
        if(!requestMatches(current,state.revision,modeOf(state.parameters)) || pointerHeld || state.queued || current.stopped) {
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
      if(requestMatches(current,state.revision,modeOf(state.parameters)) && !pointerHeld && !current.stopped) {
        // The worker already scaled this partial curve to the observations.
        exactPartial={revision:current.revision,...compareDisplayCurve(data,normalizedData(),false)};
        previousExact=exactPartial;
        if(timingRevision===state.revision){
          liveTiming={...exactPartial,label:`Preview · ${data.phases.length}-point PHOEBE curve`};
        }
        $('plot-placeholder').hidden=true;
        showAgreement(dragView,exactPartial,false);
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
      const matches=!current.stopped && requestMatches(current,state.revision,modeOf(state.parameters));
      state.current=null;
      setBusy(false);
      if(matches) {
        const preview=dragView;
        clearDisplay();exactPartial=null;state.result=data.result;
        showAgreement(preview,state.result,true);state.result.revision=state.revision;
        rememberExact(state.result);
        $('plot-placeholder').hidden=true;$('export-button').disabled=false;$('fit-button').disabled=false;
        let text=`${data.result.quality==='refined'?'Refined':'Preview'} model · ${data.result.phases.length} phases · ${data.result.seconds.toFixed(1)} s`;
        if(data.result.surface_workers>1)text+= ' · '+data.result.surface_workers+' workers';
        if(data.result.source==='reused_geometry')text=`Exact PHOEBE · ${data.result.phases.length} phases · updated observation comparison`;
        if(data.result.source==='stored_exact')text=`Exact PHOEBE · ${data.result.phases.length} phases · saved reference for these settings`;
        if(data.result.fit) {text=`Local fit complete · ${data.result.fit.objective_phases}-phase search · ${data.result.phases.length}-point curve · ${data.result.fit.evaluations} model evaluations · ${data.result.seconds.toFixed(1)} s`;toast(data.result.fit.converged?'Local fit completed. Inspect the residuals before accepting the model.':'The short fit reached its stopping limit. Inspect the residuals and starting values.');}
        status(text);drawPlots();updateStats();
        scheduleOrbitSurface();
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
      if(secondaryOverflows(state.parameters))labelCurve(nearLimitLabel(state.parameters));
      else if(!dragView && previousExact)labelCurve('Previous PHOEBE curve · current calculation failed');
      if(/out of memory|memory access out of bounds|wasm trap|aborted\(/i.test(data.error)) {
        engineFailed=true;state.ready=false;$('engine-banner').hidden=false;$('engine-retry').hidden=false;
        $('engine-title').textContent='The numerical engine needs to restart';$('engine-detail').textContent=cleanError(data.error);
      }
      status(cleanError(data.error),'error');toast(cleanError(data.error));
      if(!state.result){$('plot-placeholder').hidden=true;drawPlots();}
      scheduleOrbitSurface();
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
  if(type==='fit'){previousReference=latestFit||latestCompleted;clearDisplay();liveTiming=null;timingRevision=-1;}
  else if(!dragView) refreshPreview();
  if(type==='fit' && previousExact)labelCurve('Previous PHOEBE curve · fitting');
  $('export-button').disabled=true;updateStats();drawPlots();
  const id=++state.request;
  const plotCount=type==='fit' ? 513 : plotPhases();
  state.current={id,revision:state.revision,type,plotCount,mode:modeOf(state.parameters),tides:state.parameters.distortion,heating:state.parameters.irradiation};state.queued=false;setBusy(true,type==='fit');
  const location=nativeKernelConfig?'in Colab’s native Python runtime':'in this browser';
  status(type==='fit'?`Fitting selected parameters ${location}…`:`Computing ${state.quality} model ${location}…`,'busy');
  clearInterval(elapsedTimer);
  if(type==='compute' && (state.current.mode!=='detached' || state.current.tides || state.current.heating)){
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
function drawPlots() {drawVelocityPlot(state.parameters,state.dataset);drawTimeSeries();drawChart($('light-curve'),false);drawChart($('residual-curve'),true);drawOrbitViewer();}
// Same fractional scale used in the LFHCal signed-log calibration residual plots.
const residualScale=1e-4;
function signedLogFraction(fraction){
  return Math.sign(fraction)*Math.log1p(Math.abs(fraction)/residualScale)/Math.LN10;
}

function plottedResiduals(comparison,signedLog){
  const residuals=comparison?.residual || [];
  if(!signedLog)return residuals;
  return residuals.map((delta,i)=>{
    const model=comparison.model_at_data?.[i] ?? (comparison.flux[i]-delta);
    return model>0 && Number.isFinite(model) ? signedLogFraction(delta/model) : NaN;
  });
}

function signedResidualTicks(limit,height){
  const ticks=[{value:0,label:'0%'}];
  // Label the axis in fractional percentages. Keep a readable space between
  // decade labels on narrow or short displays, including the central zero.
  let last=Infinity;
  for(let power=Math.ceil(limit);power>=0;power--){
    const fraction=residualScale*10**power,value=signedLogFraction(fraction);
    if(value>limit || Math.min(last-value,value)*height/(2*limit)<12)continue;
    const label=(fraction*100).toLocaleString('en-US',{maximumFractionDigits:2})+'%';
    ticks.push({value,label:'+'+label},{value:-value,label:'−'+label});
    last=value;
  }
  return ticks;
}
function drawChart(canvas,residual) {
  const signedLog=residual && plotSettings.signedLog;
  if(residual){
    canvas.classList.toggle('signed-log',signedLog);
    $('residual-scale').textContent=signedLog?'· (observed − model) / model · signed log':'· observed − model';
    canvas.setAttribute('aria-label',signedLog
      ? 'Fractional observed minus model residuals versus orbital phase on a signed-log scale, labeled as percentages'
      : 'Observed minus modeled flux versus orbital phase, with halos on preview residuals');
  }
  const rect=canvas.getBoundingClientRect();if(!rect.width||!rect.height)return;
  const dpr=Math.min(window.devicePixelRatio||1,2);canvas.width=rect.width*dpr;canvas.height=rect.height*dpr;
  const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);
  const w=rect.width,h=rect.height,L=49,R=18,T=residual?8:20,B=residual?23:26,iw=w-L-R,ih=h-T-B;
  const current=state.result?.revision===state.revision ? state.result : null;
  const showPrior=plotSettings.previous && (!previousReference || previousReference===liveTiming?.source);
  const showTiming=timingRevision===state.revision && (!liveTiming?.prior || showPrior);
  const live=!current && showTiming ? liveTiming : null;
  const partial=exactPartial?.revision===state.revision ? exactPartial : null;
  const visible=partial || (dragView ? null : current||live);
  const faintPreview=plotSettings.preview ? dragView : null;
  const comparison=visible?.comparison||faintPreview?.comparison||normalizedData();
  const previewPoints=faintPreview?.comparison;
  if(residual) {
    const sources=[];
    if(previewPoints) sources.push('Preview halo');
    if(partial) sources.push('PHOEBE · '+partial.phases.length+' phases');
    else if(current) sources.push('PHOEBE');
    else if(visible?.label) sources.push(visible.label);
    $('residual-summary').textContent=sources.length ? sources.join(' + ')+' · '+comparison.phase.length+' observations' : '—';
  }
  const reference=!current && plotSettings.previous && previousReference && previousReference!==visible?.source && previousReference.model!==visible?.model ? previousReference : null;
  if (!residual) {
    const key=$('previous-curve-key');
    const prior=reference || visible?.source;
    key.hidden=!prior;
    if(prior)key.lastChild.textContent=prior.fit ? 'Previous fit' : 'Previous model';
  }
  const ys=residual ? plottedResiduals(visible?.comparison,signedLog) : comparison.flux;
  const previewY=residual ? plottedResiduals(previewPoints,signedLog) : [];
  const model=residual?[]:[...(visible?.model||[]),...(faintPreview?.model||[]),...(reference?.model||[])];
  let min,max;
  if(residual){
    const extent=Math.max(signedLog?signedLogFraction(residualScale):.005,
      ...ys.filter(Number.isFinite).map(Math.abs),...previewY.filter(Number.isFinite).map(Math.abs));
    min=-1.2*extent;max=1.2*extent;
  }
  else{const all=[...ys,...model];min=all.length?Math.min(...all):.65;max=all.length?Math.max(...all):1.05;const gap=Math.max(.03,(max-min)*.15);min-=gap;max+=gap;}
  const px=(x)=>L+(x+.5)*iw,py=(y)=>T+(max-y)/(max-min)*ih;
  ctx.clearRect(0,0,w,h);ctx.font='10px system-ui, sans-serif';ctx.lineWidth=1;
  const divisions=residual?2:4;
  const ticks=signedLog?signedResidualTicks(max,ih):Array.from({length:divisions+1},(_,i)=>{
    const value=min+(max-min)*i/divisions;
    return {value,label:value.toFixed(residual?3:2)};
  });
  for(const {value,label} of ticks) {
    const pos=py(value);
    ctx.strokeStyle='#efedf3';ctx.setLineDash([]);ctx.beginPath();ctx.moveTo(L,pos);ctx.lineTo(w-R,pos);ctx.stroke();
    ctx.fillStyle='#9a96a3';ctx.textAlign='right';ctx.fillText(label,L-9,pos+3);
  }
  for(const x of [-.5,-.25,0,.25,.5]) {
    ctx.strokeStyle='#f1eff5';ctx.setLineDash([3,4]);ctx.beginPath();ctx.moveTo(px(x),T);ctx.lineTo(px(x),h-B);ctx.stroke();
    if(residual){ctx.fillStyle='#9a96a3';ctx.textAlign='center';ctx.fillText(x.toFixed(2),px(x),h-6);}
  }
  if(residual){ctx.strokeStyle='#bcb4d3';ctx.setLineDash([4,4]);ctx.beginPath();ctx.moveTo(L,py(0));ctx.lineTo(w-R,py(0));ctx.stroke();}
  else{ctx.save();ctx.translate(12,T+ih/2);ctx.rotate(-Math.PI/2);ctx.fillStyle='#8c8796';ctx.textAlign='center';ctx.fillText('Normalized flux',0,0);ctx.restore();}
  ctx.save();ctx.beginPath();ctx.rect(L,T,iw,ih);ctx.clip();ctx.setLineDash([]);
  if(residual && previewPoints) {
    const color=faintPreview.exploratory ? '181,106,8' : '106,89,218';
    // A translucent outer disc distinguishes the preview under incoming PHOEBE points.
    for(const [radius,alpha] of [[4.2,.12],[1.8,.43]]) {
      ctx.fillStyle='rgba('+color+','+alpha+')';
      ctx.beginPath();
      for(let i=0;i<previewPoints.phase.length;i++){
        if(!Number.isFinite(previewY[i]))continue;
        const x=px(previewPoints.phase[i]), y=py(previewY[i]);
        ctx.moveTo(x+radius,y);ctx.arc(x,y,radius,0,2*Math.PI);
      }
      ctx.fill();
    }
  }
  const xs=comparison.phase||[];
  for(let i=0;i<ys.length;i++) {
    if(!Number.isFinite(ys[i]))continue;
    const x=px(xs[i]),y=py(ys[i]);
    if(!residual&&comparison.sigma?.[i]) {ctx.strokeStyle='#bbc0d25a';ctx.lineWidth=.8;ctx.beginPath();ctx.moveTo(x,py(ys[i]-comparison.sigma[i]));ctx.lineTo(x,py(ys[i]+comparison.sigma[i]));ctx.stroke();}
    ctx.fillStyle=residual?(visible?.prior?'#888494':'#6e5ba9c9'):'#737b969c';ctx.beginPath();ctx.arc(x,y,residual?1.7:2,0,Math.PI*2);ctx.fill();
  }
  if(!residual) {
    for (const curve of [faintPreview,reference,visible]) {
      if (!curve) continue;
      const faint=curve===faintPreview;
      const dashed=curve===reference || curve.prior;
      ctx.save();
      ctx.strokeStyle=dashed ? '#27716e' : faint && curve.exploratory ? '#b56a08' : '#6a59da';
      ctx.lineWidth=faint ? 12 : dashed ? 1.8 : 2.2;
      if(faint) {
        ctx.globalAlpha=.30;
        ctx.lineJoin='round';
        ctx.lineCap='round';
        if('filter' in ctx) ctx.filter=`blur(${2*dpr}px)`;
      }
      ctx.setLineDash(dashed ? [6,4] : []);ctx.beginPath();
      curve.phases.forEach((phase,i)=>i ? ctx.lineTo(px(phase),py(curve.model[i])) : ctx.moveTo(px(phase),py(curve.model[i])));
      ctx.stroke();ctx.restore();
    }
  }
  ctx.restore();canvas.chart={L,R,T,B,px,py,min,max,w,h,data:comparison};
}

function updateStats() {
  const current=state.result?.revision===state.revision ? state.result : null;
  const live=timingRevision===state.revision ? liveTiming : null;
  const c=current?.comparison;$('rms-stat').textContent=c?c.rms.toFixed(4):'—';$('chi-stat').textContent=c?.reduced_chi2!=null?c.reduced_chi2.toFixed(2):'—';
  $('chi-note').textContent=!current && live?'Waiting for completed PHOEBE result':c?.reduced_chi2!=null?'Uses measurement errors':'Add errors to estimate χ²';
}

function installDataset(dataset,parameters=null) {
  validateDataset(dataset);
  $('rv-error').textContent='';exampleRequest++;clearDisplay();exactPartial=null;previousExact=null;latestCompleted=null;latestFit=null;previousReference=null;exactHistory.clear();state.dataset=dataset;if(parameters)state.parameters={...DEFAULTS,...parameters};
  $('time-panel').hidden=dataset.x_kind!=='time';
  modeSnapshots[modeOf(state.parameters)]={...state.parameters};
  if(dataset.x_kind==='time'){
    state.parameters.period=parameters?.period??dataset.period;
    state.parameters.epoch=parameters?.epoch??dataset.epoch;
    const origin=Math.min(...dataset.x);
    $('time-origin').textContent='Days since '+origin.toFixed(5)+(dataset.time_system?' ('+dataset.time_system+')':'')+
      ' · '+(dataset.y_kind==='magnitude'?'magnitude':'flux')+' · dashed guides mark phase zero';
  }
  modelHistory.length=0;historyIndex=-1;recordModel();
  $('period-span').value=dataset.x_kind==='time'?'0.001':'full';
  $('epoch-span').value='0.001';$('eccentricity-span').value='full';
  Object.keys(zoomOptions).forEach(centerSlider);
  state.result=null;state.revision++;updateControlValues();updateStats();drawPlots();
  $('dataset-name').textContent=dataset.name||'Uploaded observations';$('dataset-description').textContent=`${dataset.synthetic?'Synthetic observations':'Your observations'} · ${dataset.x.length} points · ${dataset.y_kind==='magnitude'?'magnitudes converted to flux':'normalized flux'}`;
  if(dataset.provenance){
    const origin=dataset.synthetic?'Synthetic PHOEBE':dataset.provenance.catalog==='Kepler Eclipsing Binary Catalog, third revision'?'Kepler observations':'Observations';
    $('dataset-description').textContent=origin+' · '+dataset.x.length+' points · '+dataset.description;
  }
  $('export-button').disabled=true;$('fit-button').disabled=true;refreshPreview();requestModel('compute');
}

function validateDataset(d) {
  if(!d||!Array.isArray(d.x)||!Array.isArray(d.y)||d.x.length!==d.y.length||d.x.length<8||d.x.length>5000)throw Error('Choose between 8 and 5,000 observations with matching coordinates and brightness values.');
  if(d.radial_velocity){
    validateVelocity(d.radial_velocity);
    if(d.x_kind==='phase' && d.radial_velocity.axis==='time' &&
       !(Number.isFinite(d.radial_velocity.reference_epoch) && Number.isFinite(d.radial_velocity.reference_period) && d.radial_velocity.reference_period>0))
      throw Error('Time-based radial velocities need the folding ephemeris for this phase-only light curve.');
  }
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
  if(modeOf(state.parameters)!=='detached')return;
  const id=++exampleRequest,choice=$('example-choice').value;
  try{
    const response=await fetch(new URL('../'+choice,import.meta.url));
    if(!response.ok)throw Error('The example could not be loaded.');
    const data=await response.json();
    if(id!==exampleRequest || choice!==$('example-choice').value || state.fitting || modeOf(state.parameters)!=='detached')return;
    installDataset(data,choice==='example.json'?DEFAULTS:(data.truth||data.starting_parameters));
    if(notify)toast('Loaded '+data.name+'.');
  }catch(e){if(id===exampleRequest)toast(cleanError(e));}
}
function bindEvents() {
  $('undo-model').onclick=()=>stepModel(-1);
  $('redo-model').onclick=()=>stepModel(1);
  window.addEventListener('keydown',event=>{
    if(!(event.ctrlKey || event.metaKey) || event.altKey || document.querySelector('dialog[open]'))return;
    if(event.target.isContentEditable || event.target.closest('textarea,select,input:not([type="range"]):not([type="checkbox"])'))return;
    const key=event.key.toLowerCase();
    if(key!=='z' && key!=='y')return;
    const redo=key==='y' || event.shiftKey;
    if($(redo?'redo-model':'undo-model').disabled)return;
    event.preventDefault();stepModel(redo?1:-1);
  });

  for(const key of Object.keys(plotSettings)) {
    const checkbox=$('show-'+key);
    checkbox.checked=plotSettings[key];
    checkbox.addEventListener('change',()=>{
      plotSettings[key]=checkbox.checked;
      try { localStorage.setItem('phoebe.plot.settings',JSON.stringify(plotSettings)); } catch { /* Session only. */ }
      labelCurve(currentCurveLabel);
      drawPlots();
    });
  }
  $('rv-file').onchange=async event=>{
    const dataset=state.dataset,file=event.target.files[0];event.target.value='';
    if(!dataset || !file)return;
    try{
      const velocities=parseVelocity(await file.text(),dataset);
      if(dataset!==state.dataset)return;
      velocities.source=file.name;
      dataset.radial_velocity=velocities;
      $('rv-error').textContent='';
      drawVelocityPlot(state.parameters,dataset,true);
    }catch(error){if(dataset===state.dataset)$('rv-error').textContent=error.message;}
  };
  $('rv-gamma').onchange=event=>{
    const data=state.dataset?.radial_velocity;
    if(!data)return;
    if(Number.isFinite(event.target.valueAsNumber))data.gamma=event.target.valueAsNumber;
    drawVelocityPlot(state.parameters,state.dataset,true);
  };
  $('rv-rescale').onclick=()=>drawVelocityPlot(state.parameters,state.dataset,true);
  for(const el of document.querySelectorAll('.close-dialog'))el.addEventListener('click',()=>el.closest('dialog').close());
  for(const dialog of document.querySelectorAll('dialog'))dialog.addEventListener('click',(e)=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}});
  $('guide-button').onclick=()=>$('guide-dialog').showModal();
  $('tidal-phases').onchange=()=>{if(state.parameters.distortion || modeOf(state.parameters)!=='detached')parametersChanged();};
  $('surface-workers').onchange=()=>{
    if(state.current?.type==='compute' && (state.current.mode!=='detached' || state.current.tides || state.current.heating))startEngine();
  };
  $('engine-retry').onclick=startEngine;
  $('reset-button').onclick=()=>{const mode=modeOf(state.parameters);state.parameters=mode==='contact'?{...DEFAULTS,contact:true,fillout_factor:.25}:mode==='semi'?{...DEFAULTS,semidetached:true,donor:state.parameters.donor,radius_secondary:state.parameters.donor==='primary' ? .195 : .17,radius_primary:state.parameters.donor==='secondary' ? .222 : .21}:{...DEFAULTS};modeSnapshots[mode]={...state.parameters};Object.keys(zoomOptions).forEach(centerSlider);updateControlValues();parametersChanged();};
  $('example-button').onclick=()=>{if(modeOf(state.parameters)==='detached')loadExample();};
  for(const button of document.querySelectorAll('.quality'))button.onclick=()=>{state.quality=button.dataset.quality;document.querySelectorAll('.quality').forEach(b=>{b.classList.toggle('active',b===button);b.setAttribute('aria-pressed',String(b===button));});parametersChanged();scheduleCompute(50);};
  $('save-button').onclick=()=>{if(!state.dataset){toast('Load observations first.');return;}download('phoebe-lab-session.json',JSON.stringify({schema:'phoebe-lab-session-v1',parameters:state.parameters,dataset:state.dataset,quality:state.quality,tidal_phases:Number($('tidal-phases').value)},null,2));};
  $('export-button').onclick=()=>{
    if(state.result?.revision!==state.revision)return;
    const runtime=state.result.runtime || (nativeKernelConfig?'Colab native Python':'Browser WebAssembly');
    const quoted='"'+String(runtime).replaceAll('"','""')+'"';
    download('phoebe-model.csv','phase,normalized_flux,engine_runtime\n'+state.result.phases.map((x,i)=>`${x},${state.result.model[i]},${quoted}`).join('\n')+'\n','text/csv');
  };
  $('stop-button').onclick=()=>{if(state.current?.type==='compute') {
    if(state.current.mode!=='detached'||state.current.tides||state.current.heating){
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
        if(!canOpenAdvancedWorkspace(nativeKernelConfig))throw Error(NATIVE_PROJECT_ERROR);
        $('import-dialog').close();nativeFiles.openFile(file);return;
      }
      if(file.size>5000000 && !file.name.toLowerCase().endsWith('.json'))throw Error('Choose a file smaller than 5 MB.');
      const text=await file.text();
      if(file.name.toLowerCase().endsWith('.json')) {
        const project=JSON.parse(text);
        if(isNativeProjectJson(project)){
          if(!canOpenAdvancedWorkspace(nativeKernelConfig))throw Error(NATIVE_PROJECT_ERROR);
          $('import-dialog').close();nativeFiles.openFile(file);return;
        }
        if(project.schema!=='phoebe-lab-session-v1')throw Error('This is not a PHOEBE Lab session file.');
        for(const [key,spec] of parameterInputs){const value=Number(project.parameters?.[key] ?? DEFAULTS[key]);if(!Number.isFinite(value)||value<spec.min||value>spec.max)throw Error(`The saved ${key} value is outside this app’s supported range.`);}
        for(const key of ['contact','semidetached','distortion','irradiation'])if(typeof (project.parameters?.[key] ?? (key==='contact'||key==='semidetached'?false:undefined))!=='boolean')throw Error(`The saved ${key} setting is invalid.`);
        if(project.parameters?.donor!=null && !['primary','secondary'].includes(project.parameters.donor))throw Error('The saved donor setting is invalid.');
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
  import('../experiment/surface_predict.mjs?v=e7747d141ba9063d'),
  fetch(new URL('../experiment/surface.json',import.meta.url)).then(response=>{
    if(!response.ok) throw Error(`Surface preview data returned ${response.status}`);
    return response.json();
  }),
]).then(([module,specs])=>{predictSurface=module.makeSurfacePredictor(specs,discModel);refreshPreview();})
  .catch(error=>console.warn('Surface drag preview unavailable',error));
Promise.all([
  import('../experiment/surface_predict.mjs?v=e7747d141ba9063d'),
  fetch(new URL('../experiment/temperature-tides.json?v=c6980a8ff31771f6',import.meta.url)).then(response=>{
    if(!response.ok)throw Error(response.status);
    return response.json();
  }),
]).then(([module,sweeps])=>{
  predictTemperature=module.makeTemperaturePredictor(sweeps);
  refreshPreview();
}).catch(error=>console.warn('Temperature sweep unavailable',error));
Promise.all([
  import('../experiment/broad-predict.mjs?v=5ec4cc7cc1c776c2'),
  fetch(new URL('../experiment/broad-model.json',import.meta.url)).then(r=>r.json()),
  fetch(new URL('../study/table.json?v=dae38a397d622654',import.meta.url)).then(r=>r.json()),
]).then(([module,spec,table])=>{
  predictBroad=module.makeBroadPredictor(spec,table);
  refreshPreview();
}).catch(error=>console.warn('Broad slider preview unavailable',error));
Promise.all([
  import('../experiment/near-lobe.mjs?v=5402c5211bfbd7c5'),
  fetch(new URL('../experiment/near-lobe-model.json?v=65656d7dc425af16',import.meta.url)).then(r=>r.json()),
  fetch(new URL('../study/table.json?v=dae38a397d622654',import.meta.url)).then(r=>r.json()),
]).then(([module,spec,table])=>{
  predictNear=module.makeNearPredictor(spec,table);
  refreshPreview();
}).catch(error=>console.warn('Near-lobe preview unavailable',error));
Promise.all([
  import('../experiment/surface_predict.mjs?v=e7747d141ba9063d'),
  fetch(new URL('../experiment/eccentric-lobe.json?v=e111e69153377790',import.meta.url))
    .then(response=>{if(!response.ok)throw Error(response.status);return response.json();}),
]).then(([module,spec])=>{
  predictEccentricSweep=module.makeEccentricLobePredictor(spec);
  eccentricSweepSpec=spec;
  refreshPreview();
}).catch(error=>console.warn('Near-lobe eccentricity sweep unavailable',error));
fetch(new URL('../experiment/near-roche-reference.json?v=658bddb7c8e01386',import.meta.url))
  .then(response=>{if(!response.ok)throw Error(response.status);return response.json();})
  .then(reference=>{nearRocheReference=reference;refreshPreview();})
  .catch(error=>console.warn('Near-lobe reference unavailable',error));
Promise.all([
  import('../experiment/contact-predict.mjs'),
  fetch(new URL('../experiment/contact-model.json',import.meta.url)).then(response=>{
    if(!response.ok)throw Error(response.status);
    return response.json();
  }),
]).then(([module,spec])=>{
  predictContact=module.makeContactPredictor(spec);
  refreshPreview();
}).catch(error=>console.warn('Contact preview unavailable',error));
Promise.all([
  import('../experiment/semi-predict.mjs'),
  fetch(new URL('../experiment/semi-model.json',import.meta.url)).then(response=>{if(!response.ok)throw Error(response.status);return response.json();}),
]).then(([module,spec])=>{predictSemi=module.makeSemiPredictor(spec);refreshPreview();})
  .catch(error=>console.warn('Semi-detached preview unavailable',error));
const regionDetails=document.createElement('details');
regionDetails.className='small';
const regionTitle=document.createElement('summary');
regionTitle.textContent='Surface preview ranges';
regionDetails.append(regionTitle);
const regionLabels={inclination:'Inclination (°)',radius_primary:'Primary radius / separation',
  radius_secondary:'Secondary radius / separation',temperature_ratio:'Temperature ratio',
  mass_ratio:'Mass ratio',period:'Period (days)',eccentricity:'Eccentricity',omega:'Periastron (°)'};
Promise.all([
  import('../experiment/regional-surface.mjs?v=8d3e42c13d757728'),
  fetch(new URL('../experiment/regional-model.json?v=856518b1d926d27c',import.meta.url)).then(r=>r.json()),
  fetch(new URL('../study/table.json?v=dae38a397d622654',import.meta.url)).then(r=>r.json()),
  fetch(new URL('../experiment/non-eclipsing-tides.json?v=13d5f07ced6b33cf',import.meta.url))
    .then(response=>{if(!response.ok)throw Error(response.status);return response.json();})
    .catch(error=>{console.warn('Non-eclipsing tidal preview unavailable',error);return {regions:[]};}),
]).then(([module,spec,table,clear])=>{
  const regions=[...clear.regions.filter(r=>r.preferInOverlap),...spec.regions,
    ...clear.regions.filter(r=>!r.preferInOverlap)];
  predictRegional=module.makeRegionalPredictor({regions},table);
  refreshPreview();
  for(const region of regions){
    const title=document.createElement('strong'), limits=document.createElement('p');
    title.textContent=region.title+' · '+Object.keys(region.models).map(k=>({tides:'tides',heat:'heating',both:'both together'})[k]).join(', ');
    limits.textContent=Object.entries(region.domain || region.bounds).map(([k,[lo,hi]])=>
      regionLabels[k]+' '+lo+'–'+hi).join(' · ');
    if(region.minSeparationRatio) limits.textContent+=' · Heating off. The projected separation bound at periastron must exceed '+region.minSeparationRatio+' times the summed radii.';
    regionDetails.append(title,limits);
  }
  const note=document.createElement('p');
  note.textContent='With tides on and irradiation off, both built-in reference binaries also support a temperature-ratio sweep from 0.58 to 1.10 at their preset geometry. The broad slider model covers additional detached systems when both stellar atmospheres lie inside the tested table and both radii are within 85% of their periastron Roche lobes. The near-lobe preview covers additional detached systems at 85–99.5% estimated lobe filling, periods of 1.5–12 days, inclinations of at least 8°, and temperature ratios of at least 0.65 when the atmosphere table supports both stars. At the near-Roche example geometry, all four settings also cover eccentricities 0.240–0.276 and temperature ratios 0.99–1.07 together. Release a slider to start PHOEBE at the selected resolution.';
  regionDetails.append(note);
  $('parameter-controls').before(regionDetails);
}).catch(error=>console.warn('Regional surface preview unavailable',error));
const ranges=GROUPS.flatMap(group=>group.items);
const inSliderRanges=p=>ranges.every(([k,label,lo,hi])=>Number.isFinite(p[k]) && lo<=p[k] && p[k]<=hi);
predictDisplay=p=>joint(p) ?? paired(p) ??
  (!p.distortion && !p.irradiation && inSliderRanges(p)
    ? exploratory(p) : null);
const coverage=document.createElement('p');
coverage.className='muted small';
coverage.textContent='Each geometry has a separate preview. Detached uses the purple tested slices or amber eight-slider/surface models below. Semi-detached uses donor-specific native-PHOEBE training over inclination 65–90°, q 0.40–1.30, free-star lobe filling 0.25–0.82, and T₂/T₁ 0.76–1.14. Contact uses its expanded native-PHOEBE set. Semi/contact previews require P=1.8 d, circular orbit, and irradiation off and fail closed outside their tested domains.';
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
