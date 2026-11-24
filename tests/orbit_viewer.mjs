import assert from 'node:assert/strict';
import {orbitCamera, orbitProjection, overheadEarthDirection, fluxAtPhase, foldPhase, surfaceGeometryKey, projectNativeSurface, nativeTrianglePaintOrder} from '../site/assets/orbit-viewer.mjs';
import {tidalOutline, tidalSurfaceModel} from "../site/assets/stellar-shapes.mjs";

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
const freeView={mode:'free',azimuth:90,elevation:25},free=orbitProjection(p,freeView);
assert.equal(free(0).front,1);assert.equal(free(.5).front,0);
assert.ok(orbitCamera(p,freeView).earthDirection.y<0,'free camera shows a projected direction toward Earth');
assert.equal(orbitCamera(p,'earth').earthDirection,null,'Earth preset looks directly toward Earth');
assert.deepEqual(orbitCamera(p,'above').earthDirection,{x:0,y:1},'overhead preset keeps Earth down');
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

const tideParams={...p,inclination:85,mass_ratio:.85,radius_primary:.3,radius_secondary:.24,distortion:true};
const tide=tidalSurfaceModel(tideParams);
assert.ok(tide);
assert.strictEqual(tide,tidalSurfaceModel({...tideParams,omega:20,inclination:76}), 'camera changes reuse expensive Roche samples');
const highTide=tidalSurfaceModel(tideParams,'high');
assert.ok(highTide.directions.length>tide.directions.length,'high detail samples a denser physical Roche surface');
assert.strictEqual(highTide,tidalSurfaceModel({...tideParams,omega:20,inclination:76},'high'),'high-detail Roche samples are cached independently of the camera');
const span=(outline,axis)=>Math.max(...outline.map(v=>v[axis]))-Math.min(...outline.map(v=>v[axis]));
for(const k of [0,1]){
  const above=orbitProjection(tideParams,'above');
  const first=tidalOutline(tide.radii[k],tideParams,above(0),k,'above');
  const quarter=tidalOutline(tide.radii[k],tideParams,above(.25),k,'above');
  assert.ok(span(first,1)>span(first,0)+.005, 'elongated along the vertical line of centers at conjunction');
  assert.ok(span(quarter,0)>span(quarter,1)+.005, 'elongated along the horizontal line of centers at quadrature');
  compare(span(first,1),span(quarter,0));
  compare(span(first,0),span(quarter,1));
  const earth=orbitProjection(tideParams,'earth');
  const headOn=tidalOutline(tide.radii[k],tideParams,earth(0),k,'earth');
  const sideOn=tidalOutline(tide.radii[k],tideParams,earth(.25),k,'earth');
  assert.ok(span(sideOn,0)>span(headOn,0)+.005, 'visible elongation changes in the Earth projection too');
}
const oval={...tideParams,eccentricity:.18}, ovalTide=tidalSurfaceModel(oval);
assert.equal(ovalTide.radii[0].length,5);
const shapeAt=separation=>tidalOutline(ovalTide.radii[0],oval,
  {separation,cosLongitude:0,sinLongitude:1},0,'above');
const a=span(shapeAt(.82),1),b=span(shapeAt(.91),1);
assert.ok(a>b,'periastron is more distorted');
compare(span(shapeAt(.865),1),(a+b)/2);
assert.equal(tidalSurfaceModel({...oval,eccentricity:.35}),null,'overflow does not invent a closed surface');
assert.equal(tidalSurfaceModel({...oval,distortion:false}),null);
console.log('PASS: Roche silhouettes turn in both views, selectable detail changes physical samples, eccentric distortion interpolates, invalid surfaces fall back');

const semiParams={...p,contact:false,semidetached:true,donor:'primary',period:1.8,
  radius_primary:.22,radius_secondary:.19,fillout_factor:.25};
const semiMesh={schema:1,geometry:'semi',donor:'primary',frame:'component_local',components:[
  {triangles:[[[.45,-.08,0],[.45,.08,0],[-.32,0,.16]]]},
  {triangles:[[[.18,-.05,0],[.18,.05,0],[-.16,0,.1]]]}
]};
assert.equal(surfaceGeometryKey({...semiParams,inclination:70,temperature_ratio:.8}),surfaceGeometryKey({...semiParams,inclination:88,temperature_ratio:1.1}),'camera and temperature reuse co-rotating mesh');
assert.notEqual(surfaceGeometryKey(semiParams),surfaceGeometryKey({...semiParams,radius_secondary:.2}),'free radius rebuilds semi mesh');
const semi0=projectNativeSurface(semiMesh,semiParams,0,'above');
const semiQuarter=projectNativeSurface(semiMesh,semiParams,.25,'above');
assert.equal(semi0.triangles.length,2);
const range=(triangle,axis)=>Math.max(...triangle.points.map(v=>v[axis]))-Math.min(...triangle.points.map(v=>v[axis]));
assert.ok(range(semi0.triangles[0],1)>range(semi0.triangles[0],0),'phase zero line of centers is vertical overhead');
assert.ok(range(semiQuarter.triangles[0],0)>range(semiQuarter.triangles[0],1),'quarter-phase line of centers is horizontal overhead');
assert.throws(()=>projectNativeSurface({...semiMesh,donor:'secondary'},semiParams,0,'above'),/stale/);

const conjunctionMesh=donor=>({schema:1,geometry:'semi',donor,frame:'component_local',components:[
  {triangles:[[[-.03,-.02,-.02],[.03,-.02,.02],[0,.03,0]]]},
  {triangles:[[[-.03,-.02,-.02],[.03,-.02,.02],[0,.03,0]]]}
]});
for(const donor of ['primary','secondary'])for(const phase of [0,.5]){
  const parameters={...semiParams,donor};
  const projected=projectNativeSurface(conjunctionMesh(donor),parameters,phase,'earth');
  const painted=nativeTrianglePaintOrder(projected.triangles);
  assert.equal(painted.at(-1).component,projected.position.front,
    `${donor} donor: the foreground native star is painted last at phase ${phase}`);
  assert.ok(painted.at(-1).depth>painted[0].depth,'semi-detached conjunction has a strict foreground depth');
}
for(const donor of ['primary','secondary'])for(const phase of [0,.5]){
  const parameters={...semiParams,donor},projected=projectNativeSurface(conjunctionMesh(donor),parameters,phase,freeView);
  assert.equal(nativeTrianglePaintOrder(projected.triangles).at(-1).component,projected.position.front,
    `${donor} donor: free-camera foreground is painted last at phase ${phase}`);
}

const contactParams={...semiParams,contact:true,semidetached:false,mass_ratio:1,fillout_factor:.25};
const contactMesh={schema:1,geometry:'contact',donor:'primary',frame:'primary_origin',neck:.5,components:[
  {triangles:[[[0,-.2,0],[.5,-.08,.08],[.5,.08,.08]],[[0,-.2,0],[.5,.08,.08],[0,.2,0]]]},
  {triangles:[[[.5,-.08,.08],[1,-.2,0],[1,.2,0]],[[.5,-.08,.08],[1,.2,0],[.5,.08,.08]]]}
]};
const common=projectNativeSurface(contactMesh,contactParams,0,'above');
assert.equal(common.triangles.length,4);
const primaryY=common.triangles.filter(t=>t.component===0).flatMap(t=>t.points.map(v=>v[1]));
const secondaryY=common.triangles.filter(t=>t.component===1).flatMap(t=>t.points.map(v=>v[1]));
assert.ok(Math.max(...primaryY)>=Math.min(...secondaryY)-1e-12,'contact halves meet at the native neck');
assert.notEqual(surfaceGeometryKey(contactParams),surfaceGeometryKey({...contactParams,fillout_factor:.3}),'fill-out rebuilds common envelope');
for(const phase of [0,.5]){
  const projected=projectNativeSurface(contactMesh,contactParams,phase,'earth');
  const painted=nativeTrianglePaintOrder(projected.triangles);
  assert.equal(painted.at(-1).component,projected.position.front,
    `the foreground contact half is painted last at phase ${phase}`);
}
for(const phase of [0,.5]){
  const projected=projectNativeSurface(contactMesh,contactParams,phase,freeView);
  assert.equal(nativeTrianglePaintOrder(projected.triangles).at(-1).component,projected.position.front,
    `contact free-camera foreground is painted last at phase ${phase}`);
}
const viewerSource=await import('node:fs/promises').then(fs=>fs.readFile(new URL('../site/assets/orbit-viewer.mjs',import.meta.url),'utf8'));
assert.match(viewerSource,/ctx\.globalAlpha=1;/,'native PHOEBE surfaces are fully opaque');
assert.doesNotMatch(viewerSource,/Math\.max\(\.58,Math\.min\(\.94/,'the former translucent surface range is gone');
console.log('PASS: opaque native semi/contact surfaces rotate with phase, both conjunctions occlude correctly, donor staleness fails closed, contact neck remains connected');
