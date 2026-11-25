import assert from 'node:assert/strict';
import {parameterExport,parameterTable,scientificFigureSvg} from '../site/assets/scientific-export.mjs';

const parameters={contact:true,semidetached:false,donor:'primary',inclination:86,radius_primary:.21,
  radius_secondary:.17,fillout_factor:.134,temperature_ratio:1.032,mass_ratio:.534,eccentricity:0,
  omega:90,period:.305371,epoch:2454842.4996855,distortion:false,irradiation:false};
const dataset={name:'Held-out observations',x:[0,1],x_kind:'time',y:[1,.8],y_kind:'flux',
  time_system:'HJD',provenance:{doi:'10.test/example'}};
const comparison={phase:[-.25,.25],flux:[1,.8],model_at_data:[.99,.81],residual:[.01,-.01],rms:.01,reduced_chi2:null};
const result={phases:[-.5,0,.5],model:[1,.7,1],comparison,runtime:'Colab native Python',
  fit:{parameters:['inclination','mass_ratio'],objective_phases:129,evaluations:8,converged:true,message:'done'}};

const snapshot=parameterExport({parameters,dataset,result:null,quality:'preview',nativePhases:129,runtime:'Browser WebAssembly'});
assert.equal(snapshot.export_kind,'unfitted_parameter_snapshot');assert.equal(snapshot.authority.authoritative,false);
assert.equal(snapshot.statistics,null);assert.equal(snapshot.computation.engine_runtime,null);
assert(parameterTable(snapshot).every(row=>row.role!=='fitted'));

const fitted=parameterExport({parameters,dataset,result,quality:'preview',nativePhases:129,runtime:'Colab native Python'});
assert.equal(fitted.export_kind,'native_fit_result');assert.equal(fitted.authority.authoritative,true);
assert.equal(fitted.model.mass_ratio_definition,'q = Msecondary / Mprimary');
assert.equal(fitted.model.phase_zero_definition,'epoch / PHOEBE t0_supconj');
assert.equal(fitted.fit.uncertainties,null);assert.equal(fitted.statistics.residual_rms,.01);
assert.equal(parameterTable(fitted).find(row=>row.parameter==='mass_ratio').role,'fitted');
assert.equal(parameterTable(fitted).find(row=>row.parameter==='period').role,'held fixed during fit');

assert.throws(()=>scientificFigureSvg({datasetName:'none',result:null}),/current completed/);
const svg=scientificFigureSvg({datasetName:'Held-out & checked',result});
for(const text of ['<svg','Normalized flux','Residual (observed - model)','Orbital phase','Authoritative native PHOEBE model','Colab native Python'])assert(svg.includes(text),text);
assert(svg.includes('Held-out &amp; checked'));assert(svg.includes('class="model"'));
assert.equal((svg.match(/class="observation"/g)||[]).length,2);
assert.equal((svg.match(/class="residual"/g)||[]).length,2);
console.log(JSON.stringify({status:'PASS',svg_bytes:svg.length,parameter_rows:parameterTable(fitted).length}));
