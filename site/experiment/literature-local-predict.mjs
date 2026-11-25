// Display-only native-PHOEBE surrogate for the SZ Her and V1128 Tau neighborhoods.
import {prepareCoordinates,classifyCoordinates} from './preview-confidence.mjs';
function interpolate(x,y,value){
  if(value<=x[0])return y[0];if(value>=x[x.length-1])return y[y.length-1];
  let lo=0,hi=x.length-1;while(hi-lo>1){const mid=(lo+hi)>>1;if(x[mid]<=value)lo=mid;else hi=mid;}
  const t=(value-x[lo])/(x[hi]-x[lo]);return y[lo]+t*(y[hi]-y[lo]);
}
export function makeLiteratureLocalPredictor(spec){
  return p=>{
    if(p.eccentricity!==0||p.irradiation!==false)return null;
    const mode=p.contact===true?'contact':p.semidetached===true&&p.donor==='secondary'?'semi_secondary':null;
    if(!mode)return null;
    const model=spec.modes[mode],domain=spec.bounds[mode];
    let shape=p.fillout_factor;
    if(mode==='semi_secondary'){
      const lobe=interpolate(model.lobe_q,model.lobe_fraction,p.mass_ratio);
      shape=p.radius_primary/lobe;
      if(!Number.isFinite(shape)||shape<=0||shape>=1)return null;
    }
    const values={...p,shape,log_period:Math.log(p.period)};
    const bounds={inclination:domain.inclination,mass_ratio:domain.mass_ratio,shape:domain.shape,
      temperature_ratio:domain.temperature_ratio,log_period:domain.period.map(Math.log)};
    const prepared=prepareCoordinates(values,spec.keys,bounds,.08);if(!prepared)return null;
    let nearest=Infinity;
    const kernel=model.centers.map(center=>{const d=center.reduce((sum,value,j)=>sum+(prepared.x[j]-value)**2,0);nearest=Math.min(nearest,Math.sqrt(d));return Math.exp(-model.gamma*d);});
    const previewConfidence=classifyCoordinates(prepared,nearest,model.nearest_scaled_distance_max);if(!previewConfidence)return null;
    const coefficients=Array.from({length:spec.harmonics+1},(_,k)=>kernel.reduce((sum,value,j)=>sum+value*model.weights[j][k],0));
    const phases=Array.from({length:spec.phases+1},(_,j)=>j/spec.phases-.5);
    const curve=phases.map(phase=>coefficients.reduce((sum,value,k)=>sum+(k?value*Math.cos(2*Math.PI*k*phase):value),0));
    const core=curve.slice(0,spec.phases).sort((a,b)=>a-b),median=(core[spec.phases/2-1]+core[spec.phases/2])/2;
    for(let j=0;j<curve.length;j++)curve[j]/=median;
    return {phases,model:curve,exploratory:previewConfidence!=='good',previewConfidence,boundaryHeld:prepared.outside,
      surfaceMode:mode==='contact'?'contact · V1128 Tau trained neighborhood':'semi-detached · secondary donor · SZ Her trained neighborhood',literatureLocal:true,freeFill:mode==='semi_secondary'?shape:undefined};
  };
}
