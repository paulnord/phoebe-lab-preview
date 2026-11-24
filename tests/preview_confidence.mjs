import assert from 'node:assert/strict';
import {prepareCoordinates,classifyCoordinates,geometryPhysicalReason} from '../site/experiment/preview-confidence.mjs';

const bounds={a:[0,10],b:[-1,1]},keys=['a','b'];
let prepared=prepareCoordinates({a:5,b:0},keys,bounds);
assert.equal(classifyCoordinates(prepared,.2,1),'good');
prepared=prepareCoordinates({a:.2,b:0},keys,bounds);
assert.equal(classifyCoordinates(prepared,.2,1),'caution');
prepared=prepareCoordinates({a:10.5,b:0},keys,bounds);
assert.equal(prepared.outside,true);assert.equal(classifyCoordinates(prepared,.4,1),'outside');
assert.equal(prepareCoordinates({a:12,b:0},keys,bounds),null);
assert.equal(classifyCoordinates(prepareCoordinates({a:5,b:0},keys,bounds),1.3,1),null);

const base={mass_ratio:.75,radius_primary:.21,radius_secondary:.17,eccentricity:0,
  contact:false,semidetached:false,donor:'primary',fillout_factor:.25};
assert.equal(geometryPhysicalReason(base),null);
assert.match(geometryPhysicalReason({...base,radius_primary:.7}),/Roche lobe|overlap/);
assert.equal(geometryPhysicalReason({...base,semidetached:true,radius_secondary:.12}),null);
assert.match(geometryPhysicalReason({...base,semidetached:true,radius_secondary:.5}),/free secondary/);
assert.equal(geometryPhysicalReason({...base,contact:true}),null);
assert.match(geometryPhysicalReason({...base,contact:true,fillout_factor:1}),/contact fill-out/);
console.log('Preview confidence: green, amber, red, unavailable, and all geometry physical gates passed');
