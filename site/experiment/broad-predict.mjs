import {supported, phaseFeatures, systemFeatures} from './regional-surface.mjs';
import {makeDiscModel} from './discs.mjs';

export function interior(p, table, maxFill=.85) {
 const t=table.table, f=table.fixed, q=p.mass_ratio;
 const logA=(Math.log10((1+q)/(1+f.mass_ratio))+2*Math.log10(p.period/f.period))/3;
 function indices(axis,lo,hi) {
   if(lo<axis[0]||hi>axis.at(-1))return [];
   const first=Math.max(0,axis.findIndex(v=>v>=lo)-1), last=axis.findIndex(v=>v>=hi);
   return Array.from({length:last-first+1},(_,i)=>first+i);
 }
 for(const [i,r,ratio] of [[0,p.radius_primary,1/q],[1,p.radius_secondary,q]]){
   const u=Math.cbrt(ratio), lobe=.49*u*u/(.6*u*u+Math.log1p(u));
   if(r>maxFill*(1-p.eccentricity)*lobe)return false;
   const teff=t.primary_teff*(i?p.temperature_ratio:1);
   const g=t.base_logg[i]-2*Math.log10(r)-2*logA+(i?Math.log10(q/f.mass_ratio):0);
   const ti=indices(t.teffs,teff*.98,teff*1.02),gi=indices(t.gravities,g-.20,g+.20);
   if(!ti.length||!gi.length||!ti.every(a=>gi.every(b=>t.valid[a][b])))return false;
 }
 return true;
}

export function makeBroadPredictor(spec,table) {
  const discs=makeDiscModel(table.table,256,table.fixed);
  return p=>{
    if(!supported(p,spec.bounds) || !interior(p,table))return null;
    const f=phaseFeatures(p,discs);
    if(!f || !f.rows.every(row=>row.every(Number.isFinite)))return null;
    const x=systemFeatures(p,spec.bounds);
    x[5]=2*(Math.log10(p.period)+1)/3-1;
    return evaluateHeads(spec,p,f,x,'Broad slider model');
  };
}

export function evaluateHeads(spec,p,f,x,surfaceRegion) {
  const scales=[1,...f.scales];
  const coefficients=Array(f.rows[0].length).fill(0);
  function addHead(index,sign=1) {
    const head=spec.models[index];
    const hidden=head.hidden.map(weights=>Math.tanh(x.reduce((s,v,i)=>s+v*weights[i],weights.at(-1))));
    const inputs=[1,...x,...hidden];
    head.columns.forEach((column,k)=>{
      coefficients[column]+=sign*scales[index]*inputs.reduce((s,v,i)=>s+v*head.weights[i][k],0);
    });
  }
  const mode=Number(p.distortion)+2*Number(p.irradiation);
  if(mode===3 && spec.models[mode].kind!=='direct'){
    addHead(1);addHead(2);addHead(0,-1);
    if(spec.models[mode].kind!=='additive')addHead(mode);
  }else addHead(mode);
  const values=f.rows.map((row,j)=>row.reduce((s,v,k)=>s+v*coefficients[k],f.b[j]));
  const sorted=values.slice().sort((a,b)=>a-b);
  const median=(sorted[127]+sorted[128])/2;
  const model=values.map(v=>v/median);
  model.push(model[0]);
  return {...f.base,model,surfaceRegion,
    surfaceMode:['spherical','tides','heating','tides and heating'][mode],exploratory:true};
}
