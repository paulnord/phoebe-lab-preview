import {makeDiscModel,makePairModel} from './discs.mjs?v=55a956a80f13dcfd';
// Coefficients are referenced to sample zero (phase -0.5).
export function makePredictor(spec) {
  const {keys, bounds, n, harmonics: h, terms, fixed} = spec;
  function inDomain(p) {
    return Object.entries(fixed).every(([k,v])=>p[k]===v)
      && keys.every((k,i)=>Number.isFinite(p[k]) && p[k]>=bounds[i][0] && p[k]<=bounds[i][1]);
  }
  if(spec.kind==='discs') {
    const evaluate=makeDiscModel(spec.table,n);
    const paired=spec.pairs ? makePairModel(spec.pairs) : ()=>null;
    return p=>inDomain(p) ? evaluate(p) : paired(p);
  }
  const binary = atob(spec.weights_f32le);
  const data = new DataView(Uint8Array.from(binary, c => c.charCodeAt(0)).buffer);
  const size = h === null ? n : 2*h+1;
  const weights = Float64Array.from({length: terms.length*size}, (_,i) => data.getFloat32(4*i,true));
  const cos = [], sin = [];
  if (h !== null) {
    for (let k=1;k<=h;k++) {
      cos[k]=Float64Array.from({length:n}, (_,j)=>2*Math.cos(2*Math.PI*j*k/n));
      sin[k]=Float64Array.from({length:n}, (_,j)=>-2*Math.sin(2*Math.PI*j*k/n));
    }
  }
  const phases = Array.from({length:n+1},(_,j)=>j/n-.5);
  return function predict(p) {
    if (!inDomain(p)) return null;
    const u=keys.map((k,i)=>2*(p[k]-bounds[i][0])/(bounds[i][1]-bounds[i][0])-1);
    const z=new Float64Array(size);
    for (const [i,t] of terms.entries()) {
      const feature=t.reduce((v,j)=>v*u[j],1);
      for(let j=0;j<size;j++) z[j]+=feature*weights[i*size+j];
    }
    let flux=z;
    if(h!==null) {
      flux=new Float64Array(n).fill(z[0]);
      for(let k=1;k<=h;k++)
        for(let j=0;j<n;j++) flux[j]+=z[k]*cos[k][j]+z[h+k]*sin[k][j];
    }
    return {phases, model:[...flux,flux[0]]};
  };
}
