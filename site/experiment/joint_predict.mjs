import {eccentricOrbit} from './eccentric-orbit.mjs?v=9fd4b9384af148c1';
import {overlap} from './discs.mjs?v=55a956a80f13dcfd';

function vector(encoded) {
  const raw=Uint8Array.from(atob(encoded),c=>c.charCodeAt(0));
  const view=new DataView(raw.buffer);
  return Float64Array.from({length:raw.length/4},(_,j)=>view.getFloat32(4*j,true));
}

export function neuralCorrection(spec) {
  const [a,b,c,d,e,f]=spec.weights.map(vector);
  const center=vector(spec.center), size=f.length, width=b.length;
  const trig=[];
  if(spec.head==='fourier') {
    for(let j=0;j<256;j++) {
      const row=[];
      for(let k=1;k<=(size-1)/2;k++) row.push(Math.SQRT2*Math.cos(2*Math.PI*k*j/256));
      for(let k=1;k<=(size-1)/2;k++) row.push(-Math.SQRT2*Math.sin(2*Math.PI*k*j/256));
      trig.push(row);
    }
  }
  function dense(x,weights,bias,activate) {
    const out=Float64Array.from(bias);
    for(let i=0;i<x.length;i++)
      for(let k=0;k<out.length;k++) out[k]+=x[i]*weights[i*out.length+k];
    return activate ? out.map(Math.tanh) : out;
  }
  return x=>{
    const first=dense(x,a,b,true);
    const second=dense(first,c,d,true);
    const z=dense(second,e,f,false).map((v,j)=>center[j]+spec.scale*v);
    if(spec.head==='direct') return z;
    return trig.map(row=>row.reduce((v,t,k)=>v+t*z[k+1],z[0]));
  };
}

export function makeJointPredictor(spec) {
  const phases=Array.from({length:257},(_,j)=>j/256-.5);
  const rad=Math.PI/180;
  const {sizes,radii,weights}=spec.annuli;
  const correct=spec.network ? neuralCorrection(spec.network) : null;
  return p=>{
    if(!Object.entries(spec.fixed).every(([k,v])=>p[k]===v)
       || ![p.inclination,p.eccentricity,p.omega].every(Number.isFinite)
       || p.inclination<65 || p.inclination>90 || p.eccentricity<0 || p.eccentricity>.24
       || p.omega<0 || p.omega>360) return null;
    const ecc=p.eccentricity,w=p.omega*rad,ci=Math.cos(p.inclination*rad);
    const sw=Math.sin(w),cw=Math.cos(w);
    const orbit=eccentricOrbit(p.inclination,ecc,p.omega);
    const delta=correct ? correct([(ci-.21)/.22,ecc*cw/.24,ecc*sw/.24]) : null;
    const model=new Array(257);
    for(let j=0;j<256;j++) {
      let flux=0;
      if(spec.base==='orbit') {
        const {sep,primary}=orbit(phases[j]);
        flux=1;
        if(sep<sizes[0]+sizes[1]) {
          const back=primary ? 0 : 1;
          const d=sep/sizes[back], front=sizes[1-back]/sizes[back];
          for(let k=0;k<weights[back].length;k++) flux-=overlap(d,radii[k+1],front)*weights[back][k];
        }
      }
      model[j]=flux+(delta ? delta[j] : 0);
    }
    model[256]=model[0];
    return {phases,model};
  };
}
