import assert from 'node:assert/strict';import fs from 'node:fs';
import {makeSemiPredictor,rocheLobeFraction} from '../site/experiment/semi-predict.mjs';
const spec=JSON.parse(fs.readFileSync(new URL('../site/experiment/semi-model.json',import.meta.url)));
const predict=makeSemiPredictor(spec),q=.75;
for(const donor of ['primary','secondary']){
  const m=spec.donors[donor],x=m.lobe_q,y=m.lobe_fraction;let i=1;while(x[i]<q)i++;const lobe=y[i-1]+(q-x[i-1])/(x[i]-x[i-1])*(y[i]-y[i-1]),freeRadius=.55*lobe;
  const p={semidetached:true,contact:false,donor,inclination:84.5,mass_ratio:q,radius_primary:donor==='secondary'?freeRadius:.21,radius_secondary:donor==='primary'?freeRadius:.17,temperature_ratio:.9,eccentricity:0,period:1.8,irradiation:false};
  const curve=predict(p);assert(curve);assert.equal(curve.model.length,257);assert(Math.max(...curve.model)-Math.min(...curve.model)>.05);assert(Math.abs(curve.freeFill-.55)<1e-12);assert(['good','caution','outside'].includes(curve.previewConfidence));
  assert.equal(predict({...p,[donor==='primary'?'radius_secondary':'radius_primary']:.999*lobe}),null);
  assert.equal(predict({...p,period:2}),null);assert.equal(predict({...p,irradiation:true}),null);assert.equal(predict({...p,semidetached:false}),null);
}
const m=spec.donors.primary,x=m.lobe_q,y=m.lobe_fraction;let j=1;while(x[j]<q)j++;const lobe=y[j-1]+(q-x[j-1])/(x[j]-x[j-1])*(y[j]-y[j-1]);const start=performance.now();for(let i=0;i<1000;i++)predict({semidetached:true,contact:false,donor:'primary',inclination:84.5,mass_ratio:q,radius_primary:.21,radius_secondary:.55*lobe,temperature_ratio:.9,eccentricity:0,period:1.8,irradiation:false});
console.log(JSON.stringify({status:'PASS',predictions:1000,mean_ms:(performance.now()-start)/1000}));
