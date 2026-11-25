const units={inclination:'deg',radius_primary:'separation',radius_secondary:'separation',
  fillout_factor:'dimensionless',temperature_ratio:'T2/T1',mass_ratio:'M2/M1',
  eccentricity:'dimensionless',omega:'deg',period:'day',epoch:'dataset time unit'};

const xml=value=>String(value??'').replace(/[<>&"']/g,char=>({
  '<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&apos;'}[char]));
const finite=value=>Number.isFinite(value)?value:null;

export function parameterExport({parameters,dataset,result,quality,nativePhases,runtime}) {
  const authoritative=!!result;
  const fitted=new Set(result?.fit?.parameters || []);
  const geometry=parameters.contact?'contact':parameters.semidetached?'semi-detached':'detached';
  const active=['inclination',...(geometry==='detached'?['radius_primary','radius_secondary','eccentricity','omega']:
    geometry==='contact'?['fillout_factor']:[parameters.donor==='primary'?'radius_secondary':'radius_primary']),
    'temperature_ratio','mass_ratio','period','epoch'];
  const rows=active.map(name=>({name,value:finite(parameters[name]),unit:units[name],
    role:fitted.has(name)?'fitted':result?.fit?'held fixed during fit':authoritative?'forward-model value':'unfitted snapshot value'}));
  rows.push({name:'primary_mass',value:1.2,unit:'solar mass',role:'fixed by PHOEBE Lab'},
            {name:'primary_temperature',value:6300,unit:'K',role:'fixed by PHOEBE Lab'},
            {name:'passband',value:'Johnson:V',unit:null,role:'fixed by PHOEBE Lab'});
  const comparison=result?.comparison;
  return {
    schema:'phoebe-lab-parameters-v1',
    export_kind:result?.fit?'native_fit_result':authoritative?'exact_forward_model_snapshot':'unfitted_parameter_snapshot',
    authority:{authoritative,stale:false,
      statement:authoritative?'Current completed native PHOEBE result.':'Parameter snapshot only; no current exact PHOEBE result or fit statistics are claimed.'},
    model:{geometry,donor:parameters.semidetached?parameters.donor:null,
      mass_ratio_definition:'q = Msecondary / Mprimary',phase_zero_definition:'epoch / PHOEBE t0_supconj',
      parameters:rows,surface_physics:{distortion:parameters.distortion,irradiation:parameters.irradiation}},
    observations:{name:dataset?.name||null,count:dataset?.x?.length||0,
      coordinate:dataset?.x_kind||null,brightness:dataset?.y_kind||null,
      time_system:dataset?.time_system||null,provenance:dataset?.provenance||null,
      has_point_uncertainties:!!dataset?.sigma},
    computation:{quality,native_curve_phases:nativePhases,engine_runtime:authoritative?(result.runtime||runtime):null,
      engine_version:authoritative?'PHOEBE 2.5.4':null,model_phase_count:authoritative?result.phases.length:null},
    fit:result?.fit?{parameters:[...result.fit.parameters],objective_phases:result.fit.objective_phases,
      evaluations:result.fit.evaluations,converged:result.fit.converged,
      message:result.fit.message||null,uncertainties:null,
      note:'PHOEBE Lab does not estimate parameter uncertainties or uniqueness.'}:null,
    statistics:authoritative?{residual_rms:comparison?.rms??null,reduced_chi2:comparison?.reduced_chi2??null,
      normalized_flux:true}:null,
  };
}

function pathData(xs,ys,px,py){return xs.map((x,i)=>(i?'L':'M')+px(x).toFixed(2)+' '+py(ys[i]).toFixed(2)).join(' ');}
function axes({left,right,top,bottom,min,max,label}){
  const width=right-left,height=bottom-top,parts=[];
  for(let i=0;i<=4;i++){
    const x=left+width*i/4,phase=-.5+i/4;
    parts.push(`<line x1="${x}" y1="${top}" x2="${x}" y2="${bottom}" class="grid"/>`,
      `<text x="${x}" y="${bottom+20}" class="tick" text-anchor="middle">${phase.toFixed(2)}</text>`);
  }
  for(let i=0;i<=4;i++){
    const y=bottom-height*i/4,value=min+(max-min)*i/4;
    parts.push(`<line x1="${left}" y1="${y}" x2="${right}" y2="${y}" class="grid"/>`,
      `<text x="${left-10}" y="${y+4}" class="tick" text-anchor="end">${value.toFixed(label==='Residual (observed - model)'?3:2)}</text>`);
  }
  parts.push(`<line x1="${left}" y1="${bottom}" x2="${right}" y2="${bottom}" class="axis"/>`,
    `<line x1="${left}" y1="${top}" x2="${left}" y2="${bottom}" class="axis"/>`,
    `<text transform="translate(${left-58} ${(top+bottom)/2}) rotate(-90)" class="label" text-anchor="middle">${xml(label)}</text>`);
  return parts.join('');
}

export function scientificFigureSvg({datasetName,result,width=960,height=720}){
  if(!result?.comparison || !Array.isArray(result.phases) || !Array.isArray(result.model))
    throw Error('A current completed PHOEBE result is required for figure export.');
  const comparison=result.comparison,phase=comparison.phase||[],flux=comparison.flux||[],residual=comparison.residual||[];
  if(!phase.length || phase.length!==flux.length || residual.length!==phase.length)
    throw Error('The completed result does not contain aligned observations and residuals.');
  const left=92,right=width-36,lightTop=100,lightBottom=Math.round(height*.57),resTop=lightBottom+78,resBottom=height-58;
  const all=[...flux,...result.model].filter(Number.isFinite),lightMin=Math.min(...all),lightMax=Math.max(...all);
  const lightGap=Math.max(.02,(lightMax-lightMin)*.08),y0=lightMin-lightGap,y1=lightMax+lightGap;
  const residualLimit=Math.max(.005,1.15*Math.max(...residual.filter(Number.isFinite).map(Math.abs)));
  const px=x=>left+(x+.5)*(right-left), lightY=y=>lightTop+(y1-y)/(y1-y0)*(lightBottom-lightTop);
  const residualY=y=>resTop+(residualLimit-y)/(2*residualLimit)*(resBottom-resTop);
  const observations=phase.map((x,i)=>Number.isFinite(flux[i])?`<circle cx="${px(x).toFixed(2)}" cy="${lightY(flux[i]).toFixed(2)}" r="2" class="observation"/>`:'').join('');
  const residuals=phase.map((x,i)=>Number.isFinite(residual[i])?`<circle cx="${px(x).toFixed(2)}" cy="${residualY(residual[i]).toFixed(2)}" r="2" class="residual"/>`:'').join('');
  const runtime=result.runtime||'PHOEBE 2.5.4';
  const metadata=xml(JSON.stringify({schema:'phoebe-lab-figure-v1',authoritative:true,runtime,phases:result.phases.length}));
  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="title description">
<title id="title">${xml(datasetName||'PHOEBE Lab light curve')}</title><desc id="description">Observed normalized flux, current authoritative PHOEBE model, and observed minus model residuals.</desc><metadata>${metadata}</metadata>
<style>.background{fill:white}.grid{stroke:#e8e6ec;stroke-width:1}.axis{stroke:#777282;stroke-width:1.2}.tick{font:12px sans-serif;fill:#625d70}.label{font:14px sans-serif;fill:#332f3b}.heading{font:600 20px sans-serif;fill:#25212c}.subtitle{font:12px sans-serif;fill:#625d70}.model{fill:none;stroke:#6a59da;stroke-width:2.5}.observation{fill:#68718d;fill-opacity:.72}.residual{fill:#6e5ba9;fill-opacity:.78}.zero{stroke:#a8a2b1;stroke-dasharray:5 4}</style>
<rect class="background" width="100%" height="100%"/><text x="${left}" y="35" class="heading">${xml(datasetName||'PHOEBE Lab light curve')}</text><text x="${left}" y="58" class="subtitle">Authoritative native PHOEBE model - ${xml(runtime)} - ${result.phases.length} model phases</text>
${axes({left,right,top:lightTop,bottom:lightBottom,min:y0,max:y1,label:'Normalized flux'})}
<path d="${pathData(result.phases,result.model,px,lightY)}" class="model"/>${observations}
${axes({left,right,top:resTop,bottom:resBottom,min:-residualLimit,max:residualLimit,label:'Residual (observed - model)'})}
<line x1="${left}" y1="${residualY(0)}" x2="${right}" y2="${residualY(0)}" class="zero"/>${residuals}
<text x="${(left+right)/2}" y="${height-16}" class="label" text-anchor="middle">Orbital phase</text>
</svg>`;
}

export function parameterTable(report){
  return report.model.parameters.map(row=>({parameter:row.name,value:String(row.value),unit:row.unit||'',role:row.role}));
}
