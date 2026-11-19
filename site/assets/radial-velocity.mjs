import {eccentricAnomalyAtPhase} from '../experiment/eccentric-orbit.mjs?v=436129dc9aef5ac1';

// IAU nominal solar mass parameter (m³/s²); model.py fixes the primary at 1.2 solar masses.
const solarGM = 1.3271244e20;
const phases = Array.from({length:513}, (_,i)=>i/512-.5);

export function radialVelocities({period, mass_ratio:q, inclination, eccentricity:e, omega}) {
  const rad = Math.PI/180;
  const speed = Math.cbrt(2*Math.PI*solarGM*1.2*(1+q)/(period*86400))/1000;
  const k2 = speed*Math.sin(inclination*rad)/((1+q)*Math.sqrt(1-e*e));
  const k1 = q*k2;
  const anomaly = eccentricAnomalyAtPhase(e,omega);
  const cw = Math.cos(omega*rad), sw = Math.sin(omega*rad);
  const ratio = Math.sqrt(1-e*e);
  const shape = phases.map(phase=>{
    const E = anomaly(phase);
    // cos(true anomaly + omega) + e*cos(omega), positive for recession.
    return ratio*(ratio*cw*Math.cos(E)-sw*Math.sin(E))/(1-e*Math.cos(E));
  });
  return {phases,k1,k2,primary:shape.map(f=>k1*f),secondary:shape.map(f=>-k2*f)};
}

// Velocities and their uncertainties are in km/s. Times share the photometry clock.
export function validateVelocity(data) {
  if(!data || !['phase','time'].includes(data.axis) || !Array.isArray(data.rows) ||
     !data.rows.length || data.rows.length>10000 || !Number.isFinite(data.gamma))throw Error('Choose 1 to 10,000 radial-velocity rows and a finite systemic velocity.');
  for(const [index,row] of data.rows.entries()){
    if(!Array.isArray(row) || row.length!==5 || !Number.isFinite(row[0]) ||
       (row[1]==null && row[2]==null) || row.some(v=>v!==null && !Number.isFinite(v)) ||
       [1,2].some(k=>row[k+2]!==null && (row[k]===null || row[k+2]<0)))
      throw Error('Check velocity row '+(index+1)+'. Each uncertainty needs a velocity and must be nonnegative.');
  }
}

export function parseVelocity(text,dataset) {
  const lines=text.trim().split(/\r?\n/).map(s=>s.trim()).filter(s=>s && !s.startsWith('#'));
  const split=(s)=>lines[0]?.includes(',')?s.split(',').map(v=>v.trim()):s.split(/\s+/);
  const header=split(lines[0]||'').map(s=>s.toLowerCase());
  const coords=['time','phase'].filter(k=>header.includes(k));
  if(coords.length!==1 || !['rv1','rv2'].some(k=>header.includes(k)) || new Set(header).size!==header.length)
    throw Error('Use phase or time and at least one of rv1 and rv2 as column headers.');
  const data={axis:coords[0],gamma:0,rows:[]};
  if(data.axis==='time' && dataset.x_kind!=='time'){
    const info=dataset.provenance;
    if(!Number.isFinite(info?.epoch_bjd_minus_2400000) || !(info?.catalog_period_days>0))
      throw Error('For phase-only photometry, import the velocities with a phase column or open a time-series light curve.');
    data.reference_epoch=info.epoch_bjd_minus_2400000;
    data.reference_period=info.catalog_period_days;
  }
  for(const [i,line] of lines.slice(1).entries()){
    const fields=split(line);
    if(fields.length!==header.length)throw Error('Field count differs from the header on data row '+(i+1)+'.');
    data.rows.push([data.axis,'rv1','rv2','err1','err2'].map(k=>{
      const value=fields[header.indexOf(k)];
      return value==null || value===''?null:Number(value);
    }));
  }
  validateVelocity(data);
  return data;
}

export function velocityPhase(x,observations,dataset,params) {
  let phase=x;
  if(observations.axis==='time'){
    const dynamic=dataset.x_kind==='time';
    phase=(x-(dynamic?params.epoch:observations.reference_epoch))/(dynamic?params.period:observations.reference_period);
  }
  return phase-Math.floor(phase+.5);
}

export function bindVelocityPlot(panel) {
  const canvas=panel.querySelector('canvas'), primary=panel.querySelector('#rv-primary');
  const secondary=panel.querySelector('#rv-secondary');
  let previousKey='', previousDataset, previousMeasurements, limit=0;
  return function draw(params,dataset,rescale=false) {
    const {width,height}=canvas.getBoundingClientRect(), dpr=window.devicePixelRatio||1;
    if(!width || !height || !dataset)return;
    const observations=dataset.radial_velocity;
    const gamma=observations?.gamma ?? 0;
    const key=[params.epoch,gamma,params.period,params.mass_ratio,params.inclination,params.eccentricity,params.omega,width,height,dpr].join('/');
    if(previousDataset!==dataset || previousMeasurements!==observations || rescale)limit=0;
    else if(key===previousKey)return;
    previousKey=key;previousDataset=dataset;previousMeasurements=observations;
    const count=observations?.rows.reduce((n,row)=>n+Number(row[1]!=null)+Number(row[2]!=null),0) ?? 0;
    panel.querySelector('#rv-summary').textContent=count
      ? count+' measured velocities · '+(observations.source || 'Imported observations')
      : 'Model curves only';
    panel.querySelector('#rv-source').hidden=observations?.doi!=='10.1093/mnras/stt886';
    panel.querySelector('#rv-gamma-control').hidden=!observations;
    panel.querySelector('#rv-gamma').value=gamma;
    panel.querySelector('#rv-clock').textContent=dataset.time_system || (Number.isFinite(dataset.provenance?.epoch_bjd_minus_2400000)?'BJD − 2400000':'the photometry time system');
    const rv=radialVelocities(params);
    primary.textContent=`Primary ${count ? "● " : ""}K₁ = ${rv.k1.toFixed(1)} km/s`;
    secondary.textContent=`Secondary ${count ? "▲ " : ""}K₂ = ${rv.k2.toFixed(1)} km/s`;
    const peak=Math.max(rv.k1,rv.k2)*(1+Math.abs(params.eccentricity*Math.cos(params.omega*Math.PI/180)));
    // Retain the vertical scale as velocities shrink so a period swipe is visible.
    let extent=Math.abs(gamma)+peak;
    for(const row of observations?.rows || []){
      for(const k of [1,2])if(row[k]!=null)extent=Math.max(extent,Math.abs(row[k])+(row[k+2]??0));
    }
    limit=Math.max(10,limit,Math.ceil(extent/10)*10);
    const left=49, right=width-18, top=12, bottom=height-24;
    const px=x=>left+(x+.5)*(right-left), py=y=>top+(limit-y)/(2*limit)*(bottom-top);
    canvas.width=width*dpr;canvas.height=height*dpr;
    const ctx=canvas.getContext('2d');
    ctx.scale(dpr,dpr);ctx.font='10px system-ui, sans-serif';ctx.fillStyle='#625d70';
    ctx.textAlign='right';
    for(const y of [-limit,-limit/2,0,limit/2,limit]){
      ctx.strokeStyle=y===0?'#a9a3b7':'#eeedf2';ctx.beginPath();ctx.moveTo(left,py(y));ctx.lineTo(right,py(y));ctx.stroke();
      ctx.fillText(String(y),left-8,py(y)+3);
    }
    ctx.textAlign='center';
    for(const phase of [-.5,-.25,0,.25,.5]){
      ctx.strokeStyle='#efedf3';ctx.beginPath();ctx.moveTo(px(phase),top);ctx.lineTo(px(phase),bottom);ctx.stroke();
      ctx.fillText(String(phase),px(phase),bottom+15);
    }
    for(const [values,color,dashes] of [[rv.primary,'#5948bd',[]],[rv.secondary,'#087c83',[6,3]]]){
      ctx.strokeStyle=color;ctx.lineWidth=2;ctx.setLineDash(dashes);ctx.beginPath();
      values.forEach((y,i)=>i?ctx.lineTo(px(phases[i]),py(y+gamma)):ctx.moveTo(px(phases[i]),py(y+gamma)));ctx.stroke();
    }
    ctx.setLineDash([]);ctx.lineWidth=1;
    for(const row of observations?.rows || []){
      const x=px(velocityPhase(row[0],observations,dataset,params));
      for(const k of [1,2]){
        if(row[k]==null)continue;
        const y=py(row[k]),error=row[k+2];
        ctx.strokeStyle=ctx.fillStyle=k===1?'#4936a0':'#00656b';
        if(error!=null){
          const lo=py(row[k]-error),hi=py(row[k]+error);
          ctx.beginPath();ctx.moveTo(x,lo);ctx.lineTo(x,hi);
          ctx.moveTo(x-2,lo);ctx.lineTo(x+2,lo);ctx.moveTo(x-2,hi);ctx.lineTo(x+2,hi);ctx.stroke();
        }
        ctx.beginPath();
        if(k===1)ctx.arc(x,y,3,0,2*Math.PI);
        else {ctx.moveTo(x,y-4);ctx.lineTo(x+3.5,y+2.5);ctx.lineTo(x-3.5,y+2.5);ctx.closePath();}
        ctx.fill();
      }
    }
  };
}
