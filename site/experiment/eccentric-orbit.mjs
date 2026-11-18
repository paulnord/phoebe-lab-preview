// PHOEBE phase zero corresponds to superior conjunction (true longitude π/2).
export function eccentricOrbit(inclination,eccentricity,omega) {
  const rad=Math.PI/180;
  const e=eccentricity,w=omega*rad,ci=Math.cos(inclination*rad),sw=Math.sin(w),cw=Math.cos(w);
  const nu=Math.PI/2-w;
  const E0=2*Math.atan2(Math.sqrt(1-e)*Math.sin(nu/2),Math.sqrt(1+e)*Math.cos(nu/2));
  const m0=E0-e*Math.sin(E0),ratio=Math.sqrt(1-e*e);
  return phase=>{
    const m=m0+2*Math.PI*phase;
    let E=m;
    for(let it=0;it<5;it++)E-=(E-e*Math.sin(E)-m)/(1-e*Math.cos(E));
    const x=Math.cos(E)-e,y=ratio*Math.sin(E),across=x*sw+y*cw;
    return {sep:Math.hypot(x*cw-y*sw,across*ci),primary:across>=0};
  };
}
