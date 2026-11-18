// Optional offline check against exact checkpoints from the slider sweep study.
import fs from 'node:fs';
import path from 'node:path';
import {makeDiscModel} from '../site/experiment/discs.mjs';
const root=process.argv[2];
const spec=JSON.parse(fs.readFileSync(new URL('../site/experiment/display-model.json',import.meta.url)));
const predict=makeDiscModel(spec.table,spec.n,spec.fixed);
function summarize(rows) {
  let sq=0,mx=0,passed=0,clamped=0,failed=0;
  for(const r of rows){
    const v=predict(r.parameters);
    if(r.status!=='ok'){failed++;continue;}
    let s=0,m=0;
    r.flux.forEach((f,i)=>{const d=v.model[i]-f;s+=d*d;m=Math.max(m,Math.abs(d));});
    sq+=s/r.flux.length;mx=Math.max(mx,m);
    if(m<=.035 && Math.sqrt(s/r.flux.length)<=.005)passed++;
    if(v.atEdge)clamped++;
  }
  return {attempts:rows.length,valid:rows.length-failed,failed,passed,clamped,rms:Math.sqrt(sq/(rows.length-failed)),max:mx};
}
function records(dir) {
  const folder=path.join(dir,'curves');
  return fs.readdirSync(folder).filter(f=>f.endsWith('.json')).map(f=>JSON.parse(fs.readFileSync(path.join(folder,f))));
}
const base=records(root), extra=records(path.join(root,'conditional'));
const nominal=base.find(r=>r.group==='nominal');
const qRows=[nominal,...base.filter(r=>r.group==='axis'&&r.varied[0]==='mass_ratio')];
const nominalPred=predict(nominal.parameters).model;
let exactDelta=0,predDelta=0;
for(const r of qRows){const pr=predict(r.parameters);r.flux.forEach((v,i)=>{
  exactDelta=Math.max(exactDelta,Math.abs(v-nominal.flux[i]));predDelta=Math.max(predDelta,Math.abs(pr.model[i]-nominalPred[i]));});}
console.log(JSON.stringify({full: summarize(base.filter(r=>r.group==='joint_wide')),
  eccentricity_to_024:summarize(extra.filter(r=>r.group==='eight_slider')),mass_ratio:{...summarize(qRows),exactDelta,predDelta}},null,2));
