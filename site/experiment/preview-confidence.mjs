// Confidence labels describe display-surrogate evidence only. They never alter
// native PHOEBE fit bounds, statistics, or exports.
export function prepareCoordinates(values,keys,bounds,margin=.15){
  const x=[];let outside=false,edge=false;
  for(const key of keys){
    const value=values[key],[lo,hi]=bounds[key],span=hi-lo;
    if(!Number.isFinite(value)||value<lo-margin*span||value>hi+margin*span)return null;
    outside ||= value<lo||value>hi;
    const held=Math.max(lo,Math.min(hi,value));
    edge ||= held-lo<.10*span||hi-held<.10*span;
    x.push(2*(held-lo)/span-1);
  }
  return {x,outside,edge};
}

export function classifyCoordinates(prepared,nearest,validatedLimit){
  if(!prepared||!Number.isFinite(nearest)||nearest>1.25*validatedLimit)return null;
  if(prepared.outside||nearest>validatedLimit)return 'outside';
  if(prepared.edge||nearest>.72*validatedLimit)return 'caution';
  return 'good';
}

const rocheFraction=q=>{const u=Math.cbrt(q);return .49*u*u/(.6*u*u+Math.log1p(u));};
export function geometryPhysicalReason(p){
  if(!Number.isFinite(p.mass_ratio)||p.mass_ratio<=0)return 'No model · mass ratio must be positive';
  if(p.contact){
    return !Number.isFinite(p.fillout_factor)||p.fillout_factor<=0||p.fillout_factor>=1
      ? 'No model · contact fill-out must stay between the inner and outer Roche surfaces' : null;
  }
  if(p.semidetached){
    const freeRadius=p.donor==='primary'?p.radius_secondary:p.radius_primary;
    const freeLobe=rocheFraction(p.donor==='primary'?p.mass_ratio:1/p.mass_ratio);
    return freeRadius>=.995*freeLobe ? `No model · the free ${p.donor==='primary'?'secondary':'primary'} also fills its Roche lobe` : null;
  }
  if(p.radius_primary+p.radius_secondary>=1-p.eccentricity)return 'No model · the detached stellar surfaces overlap at periastron';
  const limit=.995*(1-p.eccentricity);
  if(p.radius_primary>limit*rocheFraction(1/p.mass_ratio)||p.radius_secondary>limit*rocheFraction(p.mass_ratio))
    return 'No model · a detached star fills its Roche lobe at periastron';
  return null;
}
