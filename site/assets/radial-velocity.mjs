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

export function bindVelocityPlot(panel) {
  const canvas=panel.querySelector('canvas'), primary=panel.querySelector('#rv-primary');
  const secondary=panel.querySelector('#rv-secondary');
  let previousKey='', previousDataset, limit=0;
  return function draw(params,dataset,rescale=false) {
    const {width,height}=canvas.getBoundingClientRect(), dpr=window.devicePixelRatio||1;
    if(!width || !height || !dataset)return;
    const key=[params.period,params.mass_ratio,params.inclination,params.eccentricity,params.omega,width,height,dpr].join('/');
    if(previousDataset!==dataset || rescale)limit=0;
    else if(key===previousKey)return;
    previousKey=key;previousDataset=dataset;
    const rv=radialVelocities(params);
    primary.textContent=`Primary K₁ = ${rv.k1.toFixed(1)} km/s`;
    secondary.textContent=`Secondary K₂ = ${rv.k2.toFixed(1)} km/s`;
    const peak=Math.max(rv.k1,rv.k2)*(1+Math.abs(params.eccentricity*Math.cos(params.omega*Math.PI/180)));
    // Retain the vertical scale as velocities shrink so a period swipe is visible.
    limit=Math.max(10,limit,Math.ceil(peak/10)*10);
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
      values.forEach((y,i)=>i?ctx.lineTo(px(phases[i]),py(y)):ctx.moveTo(px(phases[i]),py(y)));ctx.stroke();
    }
  };
}
