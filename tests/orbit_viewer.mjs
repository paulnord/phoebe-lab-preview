import assert from 'node:assert/strict';
import {orbitProjection, overheadEarthDirection, fluxAtPhase, foldPhase} from '../site/assets/orbit-viewer.mjs';

const p={eccentricity:0,omega:90,inclination:90,mass_ratio:.75};
const compare=(a,b)=>assert.ok(Math.abs(a-b)<1e-11, `${a} != ${b}`);
const difference=({stars:[a,b]})=>[b.x-a.x,b.y-a.y];
const earth=orbitProjection(p,'earth');
assert.equal(earth(0).front,1);
assert.equal(earth(.5).front,0);
compare(Math.hypot(...difference(earth(0))),0);
compare(Math.hypot(...difference(earth(.25))),1);
const above=orbitProjection(p,'above');
// At conjunction, the secondary is toward Earth (down); opposite at phase .5.
assert.equal(above(0).front,1);
assert.equal(above(.5).front,0);
compare(difference(above(0))[1],1);
compare(difference(above(.5))[1],-1);
// The entire overhead frame rotated, not only its vertical axis.
compare(difference(above(.25))[0],1);
compare(difference(above(.75))[0],-1);
compare(difference(above(.25))[1],0);
assert.deepEqual(overheadEarthDirection(90),{x:0,y:1});
compare(overheadEarthDirection(30).y,.5);
assert.equal(overheadEarthDirection(0),null);
const face=orbitProjection({...p,inclination:0},'earth');
assert.equal(face(0).front,null);
compare(Math.hypot(...difference(face(0))),1);
assert.deepEqual(above(.271),orbitProjection({...p,inclination:22},'above')(.271));
const e={...p,eccentricity:.31,omega:31,mass_ratio:1.17};
const ecc=orbitProjection(e,'above');
assert.equal(ecc(0).front,1);
compare(difference(ecc(0))[0],0);
assert.ok(difference(ecc(0))[1]>0);
for(const phase of [0,.08,.37,.64,.9]){
  const {stars}=ecc(phase);
  assert.ok(Math.hypot(...difference(ecc(phase)))>=1-e.eccentricity-1e-11);
  compare(stars[0].x+e.mass_ratio*stars[1].x,0);
  compare(stars[0].y+e.mass_ratio*stars[1].y,0);
  compare(difference(ecc(phase))[0],difference(ecc(phase+1))[0]);
  compare(difference(ecc(phase))[1],difference(ecc(phase+1))[1]);
}
const current={phases:[-.5,-.2,0,.25,.5],model:[.8,1,.5,1,.8]};
compare(foldPhase(.9),-.1);
compare(fluxAtPhase(current,.9),.75);
compare(fluxAtPhase(current,.125),.75);
compare(fluxAtPhase(current,.5),.8);
assert.equal(fluxAtPhase(null,0),null);
assert.equal(fluxAtPhase({phases:[-.1,.1],model:[1,1]},.25),null);
console.log('PASS: Kepler phase, Earth/above projection, front order, barycenter, periodic flux interpolation');
