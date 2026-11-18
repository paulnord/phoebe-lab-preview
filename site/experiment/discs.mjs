// Integrate limb-darkened annuli behind the foreground disc. Radii and center
// separation are in units of the semimajor axis. The area helper returns area/pi.
export function overlap(d,r,s) {
  if(d>=r+s) return 0;
  if(d<=Math.abs(r-s)) return Math.min(r,s)**2;
  const clamp=x=>Math.max(-1,Math.min(1,x));
  const ca=clamp((d*d+r*r-s*s)/(2*d*r));
  const cb=clamp((d*d+s*s-r*r)/(2*d*s));
  const radical=(r+s-d)*(d+r-s)*(d-r+s)*(d+r+s);
  return (r*r*Math.acos(ca)+s*s*Math.acos(cb)-.5*Math.sqrt(Math.max(0,radical)))/Math.PI;
}

export function makeDiscModel(table,n) {
  const {teffs,gravities,radii,base_logg,primary_teff}=table;
  const raw=atob(table.log_intensity_f32le);
  const data=new DataView(Uint8Array.from(raw,c=>c.charCodeAt(0)).buffer);
  const values=Float64Array.from({length:raw.length/4},(_,i)=>data.getFloat32(4*i,true));
  const rings=radii.length-1;
  const area=Array.from({length:rings},(_,k)=>radii[k+1]**2-radii[k]**2);
  const sine=Array.from({length:n/4+1},(_,i)=>Math.sin(i*2*Math.PI/n));
  const cosine=sine.map((_,i)=>Math.cos(i*2*Math.PI/n));
  const phases=Array.from({length:n+1},(_,j)=>j/n-.5);
  function interval(axis,x) {
    if(x<axis[0]||x>axis.at(-1)) throw Error('Outside the atmosphere table');
    let i=0;
    while(i<axis.length-2 && axis[i+1]<x) i++;
    return [i,(x-axis[i])/(axis[i+1]-axis[i])];
  }
  function profile(teff,g,r) {
    const [i,u]=interval(teffs,teff), [j,v]=interval(gravities,g);
    const block=(i*gravities.length+j)*rings;
    const stride=gravities.length*rings;
    const intensities=new Float64Array(rings);
    let light=0;
    for(let k=0;k<rings;k++) {
      const idx=block+k;
      const a=(1-v)*values[idx]+v*values[idx+rings];
      const b=(1-v)*values[idx+stride]+v*values[idx+stride+rings];
      intensities[k]=Math.exp((1-u)*a+u*b);
      light+=intensities[k]*area[k];
    }
    const weights=intensities.map((val,k)=>val-(intensities[k+1]??0));
    return {r,weights,light:light*r*r};
  }
  function blocked(d,back,front) {
    if(d>=back.r+front.r) return 0;
    if(d+back.r<=front.r) return back.light;
    let light=0;
    const separation=d/back.r, size=front.r/back.r;
    for(let k=0;k<rings;k++)
      light+=overlap(separation,radii[k+1],size)*back.weights[k];
    return light*back.r*back.r;
  }
  return function(p) {
    const r1=p.radius_primary,r2=p.radius_secondary;
    const star1=profile(primary_teff,base_logg[0]-2*Math.log10(r1),r1);
    const star2=profile(primary_teff*p.temperature_ratio,base_logg[1]-2*Math.log10(r2),r2);
    const total=star1.light+star2.light;
    const b=Math.cos(p.inclination*Math.PI/180);
    const model=new Array(n+1);
    for(let j=0;j<=n/4;j++) {
      const d=Math.hypot(sine[j],b*cosine[j]);
      const primary=1-blocked(d,star1,star2)/total;
      const secondary=1-blocked(d,star2,star1)/total;
      model[n/2-j]=model[n/2+j]=primary;
      model[j]=model[n-j]=secondary;
    }
    return {phases,model};
  };
}

// Interpolate exact curves along one of the two measured eccentric-orbit slices.
export function makePairModel(spec) {
  const {fixed, eccentricity, inclination, omega, contacts, n} = spec;
  const phases = Array.from({length:n+1}, (_,j)=>j/n-.5);
  function unpack(encoded) {
    const bytes = Uint8Array.from(atob(encoded), c=>c.charCodeAt(0));
    const data = new DataView(bytes.buffer);
    return Float32Array.from({length:bytes.length/4}, (_,i)=>data.getFloat32(i*4,true));
  }
  const angleFlux = unpack(spec.omega_flux);
  const inclinationFlux = unpack(spec.inclination_flux);
  function neighbors(nodes, value) {
    const right = nodes.findIndex(x=>x>=value);
    if (nodes[right]===value) return [[right,1]];
    const w = (value-nodes[right-1])/(nodes[right]-nodes[right-1]);
    return [[right-1,1-w],[right,w]];
  }
  function sample(flux, offset, phase) {
    const pos = ((phase+.5)%1+1)%1*n;
    const j = Math.floor(pos);
    const a = flux[offset+j];
    return a+(pos-j)*(flux[offset+(j+1)%n]-a);
  }
  return p=>{
    if (!Object.entries(fixed).every(([key,value])=>p[key]===value)
        || !(p.eccentricity>=eccentricity[0] && p.eccentricity<=eccentricity.at(-1))
        || !(p.omega>=omega[0] && p.omega<=omega.at(-1))
        || !(p.inclination>=inclination[0] && p.inclination<=inclination.at(-1))
        || (p.omega!==spec.nominal_omega && p.inclination!==spec.nominal_inclination)) return null;
    const aligned = p.omega!==spec.nominal_omega;
    const axis = aligned ? omega : inclination;
    const value = aligned ? p.omega%360 : p.inclination;
    const corners = [];
    for (const [i,a] of neighbors(eccentricity,p.eccentricity))
      for (const [j,b] of neighbors(axis,value))
        corners.push({index:i*axis.length+j, weight:a*b});
    const model = new Array(n+1).fill(0);
    if (aligned) {
      // Move the four half-depth crossings together before interpolating flux.
      const target = [0,1,2,3].map(k=>corners.reduce((s,c)=>s+c.weight*contacts[c.index][k],0));
      target.push(target[0]+1);
      for (const {index,weight} of corners) {
        const src = contacts[index];
        for (let j=0; j<n; j++) {
          const t = ((phases[j]-target[0])%1+1)%1+target[0];
          let k=0;
          while (k<3 && t>target[k+1]) k++;
          const frac = (t-target[k])/(target[k+1]-target[k]);
          const at = src[k]+frac*((k===3 ? src[0]+1 : src[k+1])-src[k]);
          model[j] += weight*sample(angleFlux,index*n,at);
        }
      }
    } else {
      for (const {index,weight} of corners)
        for (let j=0; j<n; j++) model[j] += weight*inclinationFlux[index*n+j];
    }
    model[n]=model[0];
    return {phases,model};
  };
}
