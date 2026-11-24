// Frozen PHOEBE-contact display surrogate.  Exact PHOEBE remains authoritative.
import {prepareCoordinates,classifyCoordinates} from './preview-confidence.mjs';
export function makeContactPredictor(spec) {
  const keys=spec.keys, bounds=spec.bounds, centers=spec.centers, weights=spec.weights;
  const n=spec.phases, harmonics=spec.harmonics;
  return p=>{
    if(p.contact!==true || p.eccentricity!==0 || p.irradiation!==false || p.period!==spec.fixed.period)return null;
    const prepared=prepareCoordinates(p,keys,bounds);if(!prepared)return null;
    const x=prepared.x;
    let nearest=Infinity;
    const kernel=centers.map(center=>{
      const d=center.reduce((sum,value,j)=>sum+(x[j]-value)**2,0);
      nearest=Math.min(nearest,Math.sqrt(d));
      return Math.exp(-spec.gamma*d);
    });
    const previewConfidence=classifyCoordinates(prepared,nearest,spec.nearest_scaled_distance_max);
    if(!previewConfidence)return null;
    const coefficients=Array.from({length:harmonics+1},(_,k)=>
      kernel.reduce((sum,value,j)=>sum+value*weights[j][k],0));
    const phases=Array.from({length:n+1},(_,j)=>j/n-.5);
    const model=phases.map(phase=>coefficients.reduce((sum,value,k)=>
      sum+(k?value*Math.cos(2*Math.PI*k*phase):value),0));
    const core=model.slice(0,n).sort((a,b)=>a-b), median=(core[n/2-1]+core[n/2])/2;
    for(let j=0;j<=n;j++)model[j]/=median;
    return {phases,model,exploratory:previewConfidence!=='good',previewConfidence,
      boundaryHeld:prepared.outside,surfaceMode:'contact-envelope preview',contactPreview:true};
  };
}
