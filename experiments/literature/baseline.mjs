import {readFileSync,writeFileSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {makeDiscModel} from '../../site/experiment/discs.mjs';
import {makeEightPredictor} from '../../site/experiment/eight_predict.mjs';

const out=resolve(process.argv[2]);
const json=p=>JSON.parse(readFileSync(p));
const wide=json(join(out,'table.json'));
const old=json(new URL('../../site/experiment/display-model.json',import.meta.url));
const spec=json(new URL('../../site/experiment/eight.json',import.meta.url));
const disc=makeDiscModel(wide.table,256,wide.fixed);
const deployed=makeEightPredictor(spec,makeDiscModel(old.table,256,old.fixed));
const rows=json(join(out,'coordinates.json'));
const flux=new Float64Array(rows.length*256).fill(NaN);
const prev=new Float64Array(rows.length*256).fill(NaN);
const table=wide.table;
function supports(t,g) {
  function cell(axis,x){
    if(x<axis[0] || x>axis.at(-1))return [];
    const j=axis.findIndex(v=>v>=x);
    return axis[j]===x?[j]:[j-1,j];
  }
  const ts=cell(table.teffs,t),gs=cell(table.gravities,g);
  return ts.length && gs.length && ts.every(i=>gs.every(j=>table.valid[i][j]));
}
rows.forEach(({id,parameters:p},i)=>{
  const a=(Math.log10((1+p.mass_ratio)/(1+wide.fixed.mass_ratio))+2*Math.log10(p.period/wide.fixed.period))/3;
  const g1=table.base_logg[0]-2*Math.log10(p.radius_primary)-2*a;
  const g2=table.base_logg[1]-2*Math.log10(p.radius_secondary)-2*a+Math.log10(p.mass_ratio/wide.fixed.mass_ratio);
  if(supports(6300,g1)&&supports(6300*p.temperature_ratio,g2)){
    flux.set(disc(p).model.slice(0,256),i*256);
  }
  if(!id.startsWith('hist-')){
    const curve=deployed({...p,epoch:0,distortion:false,irradiation:false});
    if(curve)prev.set(curve.model.slice(0,256),i*256);
  }
});
writeFileSync(join(out,'disc.f64'),Buffer.from(flux.buffer));
writeFileSync(join(out,'deployed.f64'),Buffer.from(prev.buffer));
