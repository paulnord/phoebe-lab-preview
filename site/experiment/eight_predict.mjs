import {neuralCorrection} from './joint_predict.mjs';
import {eccentricOrbit} from './eccentric-orbit.mjs';

export function makeEightPredictor(spec, discs) {
  const rad=Math.PI/180;
  const correct=neuralCorrection(spec.network);
  return p=>{
    if (p.epoch!==0 || p.distortion!==false || p.irradiation!==false ||
        !Object.entries(spec.bounds).every(([k,[lo,hi]])=>Number.isFinite(p[k]) && p[k]>=lo && p[k]<=hi)) return null;
    const curve=discs(p);
    const e=p.eccentricity, angle=p.omega*rad;
    const z=correct([2*Math.cos(p.inclination*rad)/Math.cos(65*rad)-1,
      (p.radius_primary-.21)/.11,(p.radius_secondary-.185)/.105,(p.temperature_ratio-.84)/.26,
      (p.mass_ratio-.85)/.65,(Math.log10(p.period)-.5)/1.5,e*Math.cos(angle)/.35,e*Math.sin(angle)/.35]);
    if (spec.profile) {
      const orbit=eccentricOrbit(p.inclination,e,p.omega);
      const sides=curve.phases.slice(0,-1).map(phase=>orbit(phase).primary ? 0 : 1);
      const maxDepth=[.05,.05];
      sides.forEach((side,j)=>{maxDepth[side]=Math.max(maxDepth[side],1-curve.model[j]);});
      sides.forEach((side,j)=>{
        const depth=(1-curve.model[j])/maxDepth[side];
        curve.model[j]+=depth*(z[2*side]+(1-depth)*z[2*side+1]);
      });
    } else {
      for(let j=0;j<256;j++) curve.model[j]=z[j]+(spec.residual ? curve.model[j] : 0);
    }
    curve.periodOutside=p.period<spec.joint_training_period[0] || p.period>spec.joint_training_period[1];
    curve.model[256]=curve.model[0];
    return curve;
  };
}
