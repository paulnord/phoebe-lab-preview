// Frozen PHOEBE semi-detached display surrogate. Native PHOEBE is authoritative.
import {prepareCoordinates,classifyCoordinates} from './preview-confidence.mjs';
export function rocheLobeFraction(starMassRatio) {
  const root=Math.cbrt(starMassRatio), square=root*root;
  return .49*square/(.6*square+Math.log1p(root));
}
function nativeLobeFraction(modelSpec,q){
  const x=modelSpec.lobe_q,y=modelSpec.lobe_fraction;if(!x?.length)return null;
  let lo=0,hi=x.length-1;if(q<=x[lo])return y[lo];if(q>=x[hi])return y[hi];
  while(hi-lo>1){const mid=(lo+hi)>>1;if(x[mid]<=q)lo=mid;else hi=mid;}
  const t=(q-x[lo])/(x[hi]-x[lo]);return y[lo]+t*(y[hi]-y[lo]);
}

export function makeSemiPredictor(spec) {
  const keys=spec.keys,bounds=spec.bounds,n=spec.phases,harmonics=spec.harmonics;
  return p=>{
    if(p.semidetached!==true || p.contact===true || !['primary','secondary'].includes(p.donor) ||
       p.eccentricity!==0 || p.irradiation!==false || p.period!==spec.fixed.period)return null;
    const freeRadius=p.donor==='primary'?p.radius_secondary:p.radius_primary,modelSpec=spec.donors[p.donor];
    const lobe=nativeLobeFraction(modelSpec,p.mass_ratio) ?? rocheLobeFraction(p.donor==='primary'?p.mass_ratio:1/p.mass_ratio);
    const freeFill=freeRadius/lobe;
    if(!Number.isFinite(freeFill)||freeFill<=0||freeFill>=1)return null;
    const values={...p,free_fill:freeFill},prepared=prepareCoordinates(values,keys,bounds);if(!prepared)return null;
    const x=prepared.x;
    let nearest=Infinity;
    const kernel=modelSpec.centers.map(center=>{const d=center.reduce((sum,value,j)=>sum+(x[j]-value)**2,0);nearest=Math.min(nearest,Math.sqrt(d));return Math.exp(-modelSpec.gamma*d);});
    const previewConfidence=classifyCoordinates(prepared,nearest,modelSpec.nearest_scaled_distance_max);
    if(!previewConfidence)return null;
    const coefficients=Array.from({length:harmonics+1},(_,k)=>kernel.reduce((sum,value,j)=>sum+value*modelSpec.weights[j][k],0));
    const phases=Array.from({length:n+1},(_,j)=>j/n-.5);
    const curve=phases.map(phase=>coefficients.reduce((sum,value,k)=>sum+(k?value*Math.cos(2*Math.PI*k*phase):value),0));
    const core=curve.slice(0,n).sort((a,b)=>a-b),median=(core[n/2-1]+core[n/2])/2;for(let j=0;j<=n;j++)curve[j]/=median;
    return {phases,model:curve,exploratory:previewConfidence!=='good',previewConfidence,
      boundaryHeld:prepared.outside,surfaceMode:`semi-detached · ${p.donor} donor`,semiPreview:true,freeFill};
  };
}
