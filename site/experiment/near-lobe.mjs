import {interior,evaluateHeads} from './broad-predict.mjs?v=5ec4cc7cc1c776c2';
import {phaseFeatures,systemFeatures,supported} from './regional-surface.mjs';
import {eccentricAnomalyAtPhase} from './eccentric-orbit.mjs';
import {makeDiscModel} from './discs.mjs';

export function lobeFractions(p){
  const fraction=(r,q)=>{
    const u=Math.cbrt(q);
    return r*(.6*u*u+Math.log1p(u))/(.49*u*u*(1-p.eccentricity));
  };
  return [fraction(p.radius_primary,1/p.mass_ratio),fraction(p.radius_secondary,p.mass_ratio)];
}

export function nearFeatures(p,discs,bounds){
  const f=phaseFeatures(p,discs);
  if(!f || !f.rows.every(row=>row.every(Number.isFinite)))return null;
  const x=systemFeatures(p,bounds),[l1,l2]=lobeFractions(p);
  x[5]=2*(Math.log10(p.period)+1)/3-1;
  const r=p.radius_primary,s=p.radius_secondary,t=p.temperature_ratio;
  const light=r*r/(r*r+s*s*t**4);
  x.push(2*l1-1,2*l2-1,2*light-1,(s-r)/(s+r));
  const w=p.omega*Math.PI/180,e=p.eccentricity,anomaly=eccentricAnomalyAtPhase(e,p.omega);
  const ext=f.rows.map((row,j)=>{
    const E=anomaly(j/256-.5),d=1-e*Math.cos(E);
    const a=(Math.cos(E)-e)/d,b=Math.sqrt(1-e*e)*Math.sin(E)/d;
    const u=a*Math.cos(w)-b*Math.sin(w),v=a*Math.sin(w)+b*Math.cos(w);
    const u2=u*u,v2=v*v,h=1/d**3;
    const base=f.b[j],dep=1-base;
    return [h*h,h*h*(1-2*v2),h*h*(1-8*u2*v2),
      v*h/d,v*(1-4*u2)*h/d, u*v*h*h,
      dep*(h-1),dep*u,dep*(1-2*v2),
      ...row.slice(9,17).map(k=>k*(h-1)),dep*dep*(v>=0?1:0),dep*dep*(v<0?1:0)];
  });
  const clear=ext.filter((_,j)=>f.b[j]===1);
  const means=ext[0].map((_,i)=>clear.reduce((a,row)=>a+row[i],0)/clear.length);
  f.rows=f.rows.map((row,j)=>row.concat(ext[j].map((v,k)=>v-means[k])));
  return {...f,x};
}

export function nearRegion(p,table,spec){
  if(!supported(p,spec.bounds,.995) || p.period<1.5 || p.period>12 ||
     p.temperature_ratio<.65 || p.inclination<8 || !interior(p,table,.995))return null;
  const [primary,secondary]=lobeFractions(p);
  if(Math.max(primary,secondary)<.85)return null;
  const local=secondary>primary && p.radius_primary>=.196 && p.radius_primary<=.252 &&
    p.mass_ratio>=.62 && p.mass_ratio<=.97 && p.eccentricity>=.15 && p.eccentricity<=.275 &&
    p.temperature_ratio>=.86 && p.period>=4.3 && p.period<=8.5 &&
    p.inclination>=78 && p.omega>=260 && p.omega<=340;
  return local?'preset':'wider';
}

export function makeNearPredictor(spec,table){
  const discs=makeDiscModel(table.table,256,table.fixed);
  return p=>{
    const region=nearRegion(p,table,spec);
    const mode=Number(p.distortion)+2*Number(p.irradiation);
    if(!spec.enabled[region]?.includes(spec.modes[mode]))return null;
    const f=nearFeatures(p,discs,spec.bounds);
    return f?evaluateHeads(spec,p,f,f.x,'Near Roche lobe'):null;
  };
}
