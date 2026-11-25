import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {OBSERVATION_EXAMPLES,observationDataset} from '../site/assets/observation-examples.mjs';

const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
function parsed(preset){
  const lines=fs.readFileSync(path.join(root,'site',preset.path),'utf8').trim().split(/\r?\n/);
  return {rows:lines.slice(1).map((line,index)=>({line:index+2,cells:line.split(',')}))};
}

const semi=OBSERVATION_EXAMPLES['observed-sz-her'];
const contact=OBSERVATION_EXAMPLES['observed-v1128-tau'];
const semiData=observationDataset(semi,parsed(semi));
const contactData=observationDataset(contact,parsed(contact));

assert.equal(semiData.x.length,437);assert.equal(contactData.x.length,690);
assert.equal(semiData.period,.8180837);assert.equal(semiData.epoch,2454588.167997);
assert.equal(contactData.period,.305371);assert.equal(contactData.epoch,2454842.3470);
assert.equal(semi.parameters.semidetached,true);assert.equal(semi.parameters.donor,'secondary');
assert.equal(semi.parameters.radius_primary,.318);assert.equal(semi.parameters.mass_ratio,.4715);
assert.equal(contact.parameters.contact,true);assert.equal(contact.parameters.mass_ratio,.534);
assert.equal(contact.parameters.fillout_factor,.134);assert.equal(contact.parameters.temperature_ratio,6400/6200);
for(const data of [semiData,contactData]){
  assert.equal(data.synthetic,false);assert.equal(data.x_kind,'time');assert.equal(data.y_kind,'magnitude');
  assert.equal('sigma' in data,false,'published rows must not acquire synthetic error bars');
  assert(data.x.every(Number.isFinite));assert(data.y.every(Number.isFinite));
}
console.log('Published observation presets: geometry, ephemeris, rows and no invented errors passed');
