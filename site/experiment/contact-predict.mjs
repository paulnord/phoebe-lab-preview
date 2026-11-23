// Frozen PHOEBE-contact display surrogate.  Exact PHOEBE remains authoritative.
export function makeContactPredictor(spec) {
  const keys=spec.keys, bounds=spec.bounds, centers=spec.centers, weights=spec.weights;
  const n=spec.phases, harmonics=spec.harmonics;
  return p=>{
    if(p.contact!==true || p.eccentricity!==0 || p.irradiation!==false || p.period!==spec.fixed.period)return null;
    const x=[];
    for(const key of keys){
      const value=p[key], [lo,hi]=bounds[key];
      if(!Number.isFinite(value)||value<lo||value>hi)return null;
      x.push(2*(value-lo)/(hi-lo)-1);
    }
    let nearest=Infinity;
    const kernel=centers.map(center=>{
      const d=center.reduce((sum,value,j)=>sum+(x[j]-value)**2,0);
      nearest=Math.min(nearest,Math.sqrt(d));
      return Math.exp(-spec.gamma*d);
    });
    if(nearest>spec.nearest_scaled_distance_max)return null;
    const coefficients=Array.from({length:harmonics+1},(_,k)=>
      kernel.reduce((sum,value,j)=>sum+value*weights[j][k],0));
    const phases=Array.from({length:n+1},(_,j)=>j/n-.5);
    const model=phases.map(phase=>coefficients.reduce((sum,value,k)=>
      sum+(k?value*Math.cos(2*Math.PI*k*phase):value),0));
    const core=model.slice(0,n).sort((a,b)=>a-b), median=(core[n/2-1]+core[n/2])/2;
    for(let j=0;j<=n;j++)model[j]/=median;
    return {phases,model,exploratory:true,surfaceMode:'contact-envelope preview',contactPreview:true};
  };
}
