// Browser benchmark for the frozen wider fit on an enumerated set of exact systems.
import {makeDiscModel} from '../experiment/discs.mjs';
import {eccentricOrbit} from '../experiment/eccentric-orbit.mjs';
function unpack(s) {
  const raw=Uint8Array.from(atob(s), c=>c.charCodeAt(0));
  const view=new DataView(raw.buffer);
  return Float64Array.from({length:raw.length/8}, (_,k)=>view.getFloat64(k*8,true));
}
export function makeWide(spec, table, cases) {
  const eligible=new Map(cases.map(c=>[c.id,c.p]));
  const disc=makeDiscModel(table.table,256,table.fixed);
  const projection=unpack(spec.projection), weights=unpack(spec.w);
  const mean=[.35,.18,.16,.95,-.1,1.5,0,0,1,.85,.85,.12];
  const scale=[.4,.12,.10,.32,.8,2,.35,.35,1,1,1,.18];
  return id=>{
    const p=eligible.get(id);
    if(!p)return null;
    const b=disc(p).model.slice(0,256);
    if(spec.kind==='disc')return b;
    const orbit=eccentricOrbit(p.inclination,p.eccentricity,p.omega);
    const sides=[],closest=[2,2],depth=[.02,.02];
    for(let j=0;j<256;j++){
      const point=orbit(j/256-.5),side=point.primary?0:1;
      sides.push(side);
      closest[side]=Math.min(closest[side],point.sep);
      depth[side]=Math.max(depth[side],1-b[j]);
    }
    const angle=Math.PI*p.omega/180;
    const sum=p.radius_primary+p.radius_secondary;
    const x=[Math.cos(Math.PI*p.inclination/180),p.radius_primary,p.radius_secondary,p.temperature_ratio,
      Math.log(p.mass_ratio),Math.log(p.period),p.eccentricity*Math.cos(angle),p.eccentricity*Math.sin(angle),
      p.radius_secondary/p.radius_primary,closest[0]/sum,closest[1]/sum,1-Math.min(...b)]
      .map((v,k)=>Math.max(-5,Math.min(5,(v-mean[k])/scale[k])));
    const features=[1,...x];
    for(let k=0;k<144;k++)features.push(Math.tanh(x.reduce((a,f,i)=>a+f*projection[i*144+k],spec.bias[k])));
    const z=new Float64Array(spec.columns);
    for(let k=0;k<z.length;k++)z[k]=features.reduce((a,v,i)=>a+v*weights[i*z.length+k],0);
    for(let j=0;j<256;j++){
      let delta=z[j];
      if(spec.kind==='profile'){
        const side=sides[j],d=(1-b[j])/depth[side];
        delta=d*(z[2*side]+(1-d)*z[2*side+1]);
      }else if(spec.kind==='fourier'){
        delta=z[0];
        for(let k=1;k<=16;k++){
          const angle=2*Math.PI*j*k/256;
          delta+=2*(z[k]*Math.cos(angle)-z[16+k]*Math.sin(angle));
        }
      }
      b[j]+=delta;
    }
    return b;
  };
}
