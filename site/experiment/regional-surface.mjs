// Fit the phase-dependent difference between a spherical disc and exact PHOEBE.
// The browser and the training script share this feature calculation.
import {eccentricAnomalyAtPhase} from './eccentric-orbit.mjs';
import {makeDiscModel} from './discs.mjs';

const rad = Math.PI / 180;
const modes = ['tides', 'heat', 'both'];
const labels = ['tides', 'heating', 'tides and heating'];
const phaseCount = 256;

// The orbital separation is at least a(1-e), and sky projection reduces
// it by at most a factor cos(i). This bound holds between sampled phases.
export function clearSeparation(p, radiusFactor = 1) {
  const lowerBound = (1 - p.eccentricity) * Math.cos(p.inclination * rad);
  return lowerBound > radiusFactor * (p.radius_primary + p.radius_secondary);
}

export function supported(p, bounds, maxLobeFraction=.96) {
  if (!Object.entries(bounds).every(([key,[lo,hi]]) =>
        Number.isFinite(p[key]) && p[key] >= lo && p[key] <= hi)) return false;
  const lobe = q => {
    const u = Math.cbrt(q);
    return .49*u*u/(.6*u*u + Math.log1p(u));
  };
  const limit = maxLobeFraction*(1-p.eccentricity);
  return p.radius_primary <= limit*lobe(1/p.mass_ratio) &&
         p.radius_secondary <= limit*lobe(p.mass_ratio);
}

function median(values) {
  const sorted = values.slice().sort((a,b)=>a-b);
  return (sorted[127]+sorted[128])/2;
}

export function systemFeatures(p, bounds) {
  const linear = key => {
    const [lo,hi] = bounds[key];
    return 2*(p[key]-lo)/(hi-lo)-1;
  };
  const w = p.omega * rad;
  const e = p.eccentricity / bounds.eccentricity[1];
  return ['inclination','radius_primary','radius_secondary','temperature_ratio','mass_ratio','period']
    .map(linear).concat(e*Math.cos(w),e*Math.sin(w),linear('eccentricity'));
}

export function phaseFeatures(p, discs) {
  const base = discs(p);
  if (base.atEdge || !base.model.every(Number.isFinite)) return null;
  const b = base.model.slice(0,phaseCount);
  const r=p.radius_primary, s=p.radius_secondary, q=p.mass_ratio, t=p.temperature_ratio;
  const L = r*r/(r*r+s*s*t**4);
  const tidal = q*r**3*L + s**3/q*(1-L);
  const heat = L*s*s + (1-L)*r*r;
  // Radius finite differences follow eclipse contacts when inclination, radii
  // or eccentricity change; fixed-phase residuals smear these sharp features.
  const dr = discs({...p,radius_primary:r*1.01}).model;
  const ds = discs({...p,radius_secondary:s*1.01}).model;
  const e=p.eccentricity, w=p.omega*rad, sini=Math.sin(p.inclination*rad);
  const anomaly=eccentricAnomalyAtPhase(e,p.omega);
  const rows=[];
  for(let j=0;j<phaseCount;j++) {
    const E=anomaly(j/phaseCount-.5), d=1-e*Math.cos(E);
    const x=Math.cos(E)-e, y=Math.sqrt(1-e*e)*Math.sin(E);
    const along=(x*Math.cos(w)-y*Math.sin(w))/d;
    const across=(x*Math.sin(w)+y*Math.cos(w))/d;
    const c=Math.max(-1,Math.min(1,across*sini));
    const lambert=z=>(Math.sqrt(Math.max(0,1-z*z))+(Math.PI-Math.acos(z))*z)/Math.PI;
    const eclipse=[1-b[j],(dr[j]-b[j])*40,(ds[j]-b[j])*40,
                  (b[(j+1)%phaseCount]-b[(j+phaseCount-1)%phaseCount])*2];
    rows.push([1,1/d**3,(1-2*c*c)/d**3,along*across/d**3,
               lambert(c)/d**2,lambert(-c)/d**2,
               Math.cos(3*Math.atan2(across,along))/d**4,Math.sin(3*Math.atan2(across,along))/d**4,
               (1-8*across*across*along*along)/d**4,
               ...eclipse.map(v=>across>=0?v:0),...eclipse.map(v=>across<0?v:0)]);
  }
  // Fix the free continuum level before restoring the sample median.
  const continuum = rows.filter((row,j)=>b[j]===1);
  if (!continuum.length) return null;
  const means = rows[0].map((_,k)=>continuum.reduce((sum,row)=>sum+row[k],0)/continuum.length);
  for (const row of rows) for (let k=0;k<row.length;k++) row[k]-=means[k];
  return {base,b,rows,scales:[tidal,heat,tidal+heat]};
}

export function makeRegionalPredictor(spec, table) {
  const discs = makeDiscModel(table.table, phaseCount, table.fixed);
  return p=>{
    if (typeof p.distortion !== 'boolean' || typeof p.irradiation !== 'boolean' ||
        !(p.distortion || p.irradiation) || p.epoch !== 0) return null;
    const mode = p.distortion ? (p.irradiation ? 2 : 0) : 1;
    for (const region of spec.regions) {
      const net=region.models[modes[mode]];
      if (!net || !supported(p,region.domain || region.bounds)) continue;
      if (region.minSeparationRatio && !clearSeparation(p,region.minSeparationRatio)) continue;
      const data=phaseFeatures(p,discs);
      if(!data) return null;
      const x=systemFeatures(p,region.bounds);
      function coefficients(model,scale) {
        const h=[1,...x,...model.hidden.map(row=>Math.tanh(row.slice(0,-1).reduce((a,v,i)=>a+v*x[i],row.at(-1))))];
        return data.rows[0].map((_,k)=>scale*h.reduce((a,v,i)=>a+v*model.weights[i][k],0));
      }
      const values=coefficients(net,data.scales[mode]);
      for (const [i,prior] of (net.priors || []).entries()) {
        const add=coefficients(prior,data.scales[i]);
        for (let k=0;k<values.length;k++) values[k]+=add[k];
      }
      const flux=data.rows.map((row,j)=>data.b[j]+row.reduce((a,v,k)=>a+v*values[k],0));
      const norm=median(flux);
      data.base.model=flux.map(v=>v/norm);
      data.base.model.push(data.base.model[0]);
      data.base.surfaceMode=labels[mode];
      data.base.surfaceRegion=region.title;
      return data.base;
    }
    return null;
  };
}
