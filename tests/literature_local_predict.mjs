import assert from 'node:assert/strict';import fs from 'node:fs';
import {makeLiteratureLocalPredictor} from '../site/experiment/literature-local-predict.mjs';
import {makeContactPredictor} from '../site/experiment/contact-predict.mjs';
import {makeSemiPredictor} from '../site/experiment/semi-predict.mjs';
const local=JSON.parse(fs.readFileSync(new URL('../site/experiment/literature-local-model.json',import.meta.url)));
const predict=makeLiteratureLocalPredictor(local);
const contact={contact:true,semidetached:false,donor:'primary',inclination:86,mass_ratio:.534,fillout_factor:.134,temperature_ratio:6400/6200,period:.305371,eccentricity:0,irradiation:false};
const semi={contact:false,semidetached:true,donor:'secondary',inclination:87.566,mass_ratio:.4715,radius_primary:.318,radius_secondary:.17,temperature_ratio:4881/7262,period:.8180837,eccentricity:0,irradiation:false};
for(const p of [contact,semi]){const curve=predict(p);assert(curve);assert.equal(curve.model.length,257);assert(curve.model.every(Number.isFinite));assert(['good','caution'].includes(curve.previewConfidence));assert.equal(curve.literatureLocal,true);}
assert.equal(predict({...contact,period:.8}),null);assert.equal(predict({...semi,temperature_ratio:.9}),null);assert.equal(predict({...semi,donor:'primary'}),null);assert.equal(predict({...contact,irradiation:true}),null);
const oldContact=makeContactPredictor(JSON.parse(fs.readFileSync(new URL('../site/experiment/contact-model.json',import.meta.url))));
const oldSemi=makeSemiPredictor(JSON.parse(fs.readFileSync(new URL('../site/experiment/semi-model.json',import.meta.url))));
assert(oldContact({...contact,period:1.8,mass_ratio:.7,fillout_factor:.25,temperature_ratio:.9,inclination:80}));
assert(oldSemi({...semi,period:1.8,mass_ratio:.75,radius_primary:.25,temperature_ratio:.9,inclination:84.5}));
const began=performance.now();for(let i=0;i<1000;i++)predict({...contact,inclination:82+7*(i%101)/100});
console.log(JSON.stringify({status:'PASS',predictions:1000,mean_ms:(performance.now()-began)/1000}));
