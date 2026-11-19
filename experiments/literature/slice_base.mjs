import {readFileSync,writeFileSync} from 'node:fs';
import {join} from 'node:path';
import {makeDiscModel} from '../../site/experiment/discs.mjs';
const out=process.argv[2];
const spec=JSON.parse(readFileSync(new URL('../../site/experiment/display-model.json',import.meta.url)));
const disc=makeDiscModel(spec.table,256,spec.fixed);
const rows=JSON.parse(readFileSync(join(out,'coordinates.json')));
const bases={};
for(const r of rows){
  if(r.id.startsWith('eccentric-') || r.id.startsWith('surface-'))bases[r.id]=disc(r.parameters).model.slice(0,256);
}
writeFileSync(join(out,'slice-disc.json'),JSON.stringify(bases));
