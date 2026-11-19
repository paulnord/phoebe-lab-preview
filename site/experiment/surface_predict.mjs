// Interpolate a paired PHOEBE surface-minus-sphere correction on a measured slice.
function bracket(axis, value) {
  if (!Number.isFinite(value) || value < axis[0] || value > axis.at(-1)) return null;
  const right = axis.findIndex(x => x >= value);
  if (axis[right] === value) return [[right, 1]];
  const fraction = (value - axis[right - 1]) / (axis[right] - axis[right - 1]);
  return [[right - 1, 1 - fraction], [right, fraction]];
}

function makeSlice(spec, discs) {
  const {axes, dims, harmonics, fixed} = spec;
  const stride = harmonics ? 2 * harmonics + 1 : 256;
  const raw = Uint8Array.from(atob(spec.coefficients), c => c.charCodeAt(0));
  const view = new DataView(raw.buffer);
  const values = Float64Array.from({length: raw.length / 4}, (_, k) => view.getFloat32(4 * k, true));
  const basis = harmonics && Array.from({length: 256}, (_, phase) => {
    const angle = 2 * Math.PI * phase / 256;
    const terms = new Float64Array(stride);
    terms[0] = 1;
    for (let k = 1; k <= harmonics; k++) {
      terms[k] = 2 * Math.cos(k * angle);
      terms[harmonics + k] = -2 * Math.sin(k * angle);
    }
    return terms;
  });
  return p => {
    if (p.epoch !== 0 || !Object.entries(fixed).every(([k, v]) => p[k] === v)) return null;
    let corners = [[0, 1]];
    for (let j = 0; j < dims.length; j++) {
      const nodes = bracket(axes[j], p[dims[j]]);
      if (!nodes) return null;
      corners = corners.flatMap(([index, weight]) => nodes.map(([node, w]) =>
        [index * axes[j].length + node, weight * w]));
    }
    const mode = p.distortion ? (p.irradiation ? 2 : 0) : 1;
    const coefficients = new Float64Array(stride);
    for (const [index, weight] of corners) {
      for (const m of (mode === 2 && spec.additive ? [0, 1] : [mode])) {
        const offset = (index * 3 + m) * stride;
        for (let k = 0; k < stride; k++) coefficients[k] += weight * values[offset + k];
      }
    }
    const curve = discs(p);
    for (let j = 0; j < 256; j++) {
      let delta = coefficients[j];
      if (harmonics) {
        delta = 0;
        for (let k = 0; k < stride; k++) delta += basis[j][k] * coefficients[k];
      }
      curve.model[j] += delta;
    }
    curve.model[256] = curve.model[0];
    curve.surfaceMode = ['tides', 'heating', 'tides and heating'][mode];
    return curve;
  };
}

export function makeSurfacePredictor(specs, discs) {
  const predictors = specs.filter(s => s.accepted).map(s => makeSlice(s, discs));
  return p => {
    if (typeof p.distortion !== 'boolean' || typeof p.irradiation !== 'boolean' ||
        !(p.distortion || p.irradiation)) return null;
    for (const predict of predictors) {
      const result = predict(p);
      if (result) return result;
    }
    return null;
  };
}

// Native median-normalized Johnson V curves with only the secondary temperature varied.
export function makeTemperaturePredictor(sweeps) {
  const phases=Array.from({length:257},(_,i)=>i/256-.5);
  return p=>{
    for(const sweep of sweeps) {
      if(!Object.entries(sweep.fixed).every(([key,value])=>p[key]===value))continue;
      const corners=bracket(sweep.ratios,p.temperature_ratio);
      if(!corners)continue;
      const model=new Array(256).fill(0);
      for(const [i,weight] of corners) {
        for(let j=0;j<model.length;j++)model[j]+=weight*sweep.curves[i][j];
      }
      const ordered=[...model].sort((a,b)=>a-b);
      const median=(ordered[127]+ordered[128])/2;
      for(let j=0;j<model.length;j++)model[j]/=median;
      model.push(model[0]);
      return {phases,model,surfaceMode:'tides',surfaceRegion:'Temperature sweep',preferInOverlap:sweep.preferInOverlap};
    }
    return null;
  };
}

// Bilinearly interpolate native light curves sampled at this detached geometry.
export function makeEccentricLobePredictor(spec){
  const bytes=Uint8Array.from(atob(spec.flux),char=>char.charCodeAt(0));
  const view=new DataView(bytes.buffer);
  const values=Float64Array.from({length:bytes.length/4},(_,i)=>view.getFloat32(i*4,true));
  const phases=Array.from({length:257},(_,j)=>j/256-.5);
  return p=>{
    if(!Object.entries(spec.fixed).every(([key,value])=>p[key]===value))return null;
    const eccentric=bracket(spec.eccentricities,p.eccentricity);
    const temperature=bracket(spec.temperatures,p.temperature_ratio);
    if(!eccentric || !temperature)return null;
    const mode=Number(p.distortion)+2*Number(p.irradiation);
    const model=Array(256).fill(0);
    for(const [e,we] of eccentric)for(const [t,wt] of temperature){
      const offset=((e*spec.temperatures.length+t)*4+mode)*256;
      for(let j=0;j<model.length;j++)model[j]+=we*wt*values[offset+j];
    }
    const sorted=model.slice().sort((a,b)=>a-b),norm=(sorted[127]+sorted[128])/2;
    for(let j=0;j<model.length;j++)model[j]/=norm;
    model.push(model[0]);
    return {phases,model,surfaceMode:['spherical','tides','heating','tides and heating'][mode],
      surfaceRegion:'Near-lobe eccentricity sweep',exploratory:true};
  };
}
