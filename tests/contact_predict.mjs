import assert from 'node:assert/strict';
import fs from 'node:fs';
import {makeContactPredictor} from '../site/experiment/contact-predict.mjs';
const spec=JSON.parse(fs.readFileSync(new URL('../site/experiment/contact-model.json',import.meta.url)));
const predict=makeContactPredictor(spec);
const p={contact:true,inclination:80,mass_ratio:.7,fillout_factor:.25,temperature_ratio:.9,
  period:1.8,eccentricity:0,irradiation:false};
const started=performance.now();let curve;
for(let i=0;i<1000;i++)curve=predict({...p,inclination:75+10*(i%101)/100});
const elapsed=performance.now()-started;
assert.ok(curve&&curve.phases.length===257&&curve.model.every(Number.isFinite));
assert.equal(predict({...p,contact:false}),null);
assert.equal(predict({...p,period:2}),null);
assert.equal(predict({...p,mass_ratio:.3}),null);
assert.equal(predict({...p,irradiation:true}),null);
console.log(JSON.stringify({status:'PASS',predictions:1000,total_ms:elapsed,mean_ms:elapsed/1000}));
