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

const optionDefaults={observations:true,model:true,residuals:true,legend:true};
function figureLayout({result,width,height,options={}}){
  if(!result?.comparison || !Array.isArray(result.phases) || !Array.isArray(result.model))
    throw Error('A current completed PHOEBE result is required for figure export.');
  const visible={...optionDefaults,...options};
  if(!visible.observations&&!visible.model)throw Error('Select observations or the exact model for figure export.');
  const comparison=result.comparison,phase=comparison.phase||[],flux=comparison.flux||[],residual=comparison.residual||[];
  if(!phase.length || phase.length!==flux.length || residual.length!==phase.length)
    throw Error('The completed result does not contain aligned observations and residuals.');
  const showResiduals=visible.residuals;
  const left=92,right=width-36,lightTop=visible.legend?108:86;
  const lightBottom=showResiduals?Math.round(height*.57):height-62;
  const resTop=lightBottom+78,resBottom=height-58;
  const all=[...(visible.observations?flux:[]),...(visible.model?result.model:[])].filter(Number.isFinite),lightMin=Math.min(...all),lightMax=Math.max(...all);
  const lightGap=Math.max(.02,(lightMax-lightMin)*.08),y0=lightMin-lightGap,y1=lightMax+lightGap;
  const residualLimit=Math.max(.005,1.15*Math.max(...residual.filter(Number.isFinite).map(Math.abs)));
  const px=x=>left+(x+.5)*(right-left), lightY=y=>lightTop+(y1-y)/(y1-y0)*(lightBottom-lightTop);
  const residualY=y=>resTop+(residualLimit-y)/(2*residualLimit)*(resBottom-resTop);
  return {visible,comparison,phase,flux,residual,left,right,lightTop,lightBottom,resTop,resBottom,
    y0,y1,residualLimit,px,lightY,residualY,width,height};
}

export function scientificFigureSvg({datasetName,result,width=960,height=720,options={}}){
  const p=figureLayout({result,width,height,options});
  const {visible,phase,flux,residual,left,right,lightTop,lightBottom,resTop,resBottom,
    y0,y1,residualLimit,px,lightY,residualY}=p;
  const observations=visible.observations?phase.map((x,i)=>Number.isFinite(flux[i])?`<circle cx="${px(x).toFixed(2)}" cy="${lightY(flux[i]).toFixed(2)}" r="2" class="observation"/>`:'').join(''):'';
  const residuals=visible.residuals?phase.map((x,i)=>Number.isFinite(residual[i])?`<circle cx="${px(x).toFixed(2)}" cy="${residualY(residual[i]).toFixed(2)}" r="2" class="residual"/>`:'').join(''):'';
  const runtime=result.runtime||'PHOEBE 2.5.4';
  const metadata=xml(JSON.stringify({schema:'phoebe-lab-figure-v1',authoritative:true,runtime,phases:result.phases.length,visible}));
  const legend=[];let legendX=left;
  if(visible.legend){
    if(visible.observations){legend.push(`<circle cx="${legendX+4}" cy="82" r="3" class="observation"/><text x="${legendX+14}" y="86" class="tick">Observations</text>`);legendX+=112;}
    if(visible.model){legend.push(`<line x1="${legendX}" y1="82" x2="${legendX+16}" y2="82" class="model"/><text x="${legendX+24}" y="86" class="tick">Exact PHOEBE model</text>`);legendX+=160;}
    if(visible.residuals)legend.push(`<circle cx="${legendX+4}" cy="82" r="3" class="residual"/><text x="${legendX+14}" y="86" class="tick">Residuals</text>`);
  }
  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="title description">
<title id="title">${xml(datasetName||'PHOEBE Lab light curve')}</title><desc id="description">Selected observations, current authoritative PHOEBE model, and residual display.</desc><metadata>${metadata}</metadata>
<style>.background{fill:white}.grid{stroke:#e8e6ec;stroke-width:1}.axis{stroke:#777282;stroke-width:1.2}.tick{font:12px sans-serif;fill:#625d70}.label{font:14px sans-serif;fill:#332f3b}.heading{font:600 20px sans-serif;fill:#25212c}.subtitle{font:12px sans-serif;fill:#625d70}.model{fill:none;stroke:#6a59da;stroke-width:2.5}.observation{fill:#68718d;fill-opacity:.72}.residual{fill:#6e5ba9;fill-opacity:.78}.zero{stroke:#a8a2b1;stroke-dasharray:5 4}</style>
<rect class="background" width="100%" height="100%"/><text x="${left}" y="35" class="heading">${xml(datasetName||'PHOEBE Lab light curve')}</text><text x="${left}" y="58" class="subtitle">Authoritative PHOEBE model - ${xml(runtime)} - ${result.phases.length} model phases</text>
${legend.join('')}
${axes({left,right,top:lightTop,bottom:lightBottom,min:y0,max:y1,label:'Normalized flux'})}
${visible.model?`<path d="${pathData(result.phases,result.model,px,lightY)}" class="model"/>`:''}${observations}
${visible.residuals?axes({left,right,top:resTop,bottom:resBottom,min:-residualLimit,max:residualLimit,label:'Residual (observed - model)'}):''}
${visible.residuals?`<line x1="${left}" y1="${residualY(0)}" x2="${right}" y2="${residualY(0)}" class="zero"/>${residuals}`:''}
<text x="${(left+right)/2}" y="${height-16}" class="label" text-anchor="middle">Orbital phase</text>
</svg>`;
}

const pdfSafe=value=>String(value??'').replace(/[^\x20-\x7e]/g,'?').replace(/([\\()])/g,'\\$1');
const pdfNumber=value=>Number(value.toFixed(3));
function pdfCircle(x,y,r,height){
  const k=.55228475*r,cy=height-y;
  return `${pdfNumber(x+r)} ${pdfNumber(cy)} m ${pdfNumber(x+r)} ${pdfNumber(cy+k)} ${pdfNumber(x+k)} ${pdfNumber(cy+r)} ${pdfNumber(x)} ${pdfNumber(cy+r)} c ${pdfNumber(x-k)} ${pdfNumber(cy+r)} ${pdfNumber(x-r)} ${pdfNumber(cy+k)} ${pdfNumber(x-r)} ${pdfNumber(cy)} c ${pdfNumber(x-r)} ${pdfNumber(cy-k)} ${pdfNumber(x-k)} ${pdfNumber(cy-r)} ${pdfNumber(x)} ${pdfNumber(cy-r)} c ${pdfNumber(x+k)} ${pdfNumber(cy-r)} ${pdfNumber(x+r)} ${pdfNumber(cy-k)} ${pdfNumber(x+r)} ${pdfNumber(cy)} c f`;
}
function pdfText(x,y,size,value,height){return `BT /F1 ${size} Tf ${pdfNumber(x)} ${pdfNumber(height-y)} Td (${pdfSafe(value)}) Tj ET`;}
function pdfAxes(parts,{left,right,top,bottom,min,max,label,height}){
  parts.push('.91 .9 .93 RG .6 w');
  for(let i=0;i<=4;i++){
    const x=left+(right-left)*i/4,phase=-.5+i/4;
    parts.push(`${pdfNumber(x)} ${pdfNumber(height-top)} m ${pdfNumber(x)} ${pdfNumber(height-bottom)} l S`,pdfText(x-14,bottom+18,10,phase.toFixed(2),height));
    const y=bottom-(bottom-top)*i/4,value=min+(max-min)*i/4;
    parts.push(`${pdfNumber(left)} ${pdfNumber(height-y)} m ${pdfNumber(right)} ${pdfNumber(height-y)} l S`,pdfText(left-46,y+3,10,value.toFixed(label.startsWith('Residual')?3:2),height));
  }
  parts.push('.46 .44 .51 RG 1 w',`${left} ${height-bottom} m ${right} ${height-bottom} l S`,`${left} ${height-bottom} m ${left} ${height-top} l S`,
    pdfText(left-4,top-10,11,label,height));
}
function pdfDocument(contents,width,height){
  const stream=contents.join('\n')+'\n';
  const objects=[
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${width} ${height}] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>`,
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>',
    `<< /Length ${stream.length} >>\nstream\n${stream}endstream`,
  ];
  let pdf='%PDF-1.4\n% PHOEBE Lab vector figure\n',offsets=[0];
  objects.forEach((object,index)=>{offsets.push(pdf.length);pdf+=`${index+1} 0 obj\n${object}\nendobj\n`;});
  const xref=pdf.length;pdf+=`xref\n0 ${objects.length+1}\n0000000000 65535 f \n`;
  for(let i=1;i<offsets.length;i++)pdf+=String(offsets[i]).padStart(10,'0')+' 00000 n \n';
  pdf+=`trailer\n<< /Size ${objects.length+1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return new TextEncoder().encode(pdf);
}

export function scientificFigurePdf({datasetName,result,width=960,height=720,options={}}){
  const p=figureLayout({result,width,height,options});
  const {visible,phase,flux,residual,left,right,lightTop,lightBottom,resTop,resBottom,
    y0,y1,residualLimit,px,lightY,residualY}=p,parts=['1 1 1 rg',`0 0 ${width} ${height} re f`];
  parts.push('0.15 0.13 0.17 rg',pdfText(left,35,20,datasetName||'PHOEBE Lab light curve',height),
    '.38 .36 .44 rg',pdfText(left,58,11,`Authoritative PHOEBE model - ${result.runtime||'PHOEBE 2.5.4'} - ${result.phases.length} model phases`,height));
  let legendX=left;
  if(visible.legend){
    if(visible.observations){parts.push('.41 .44 .55 rg',pdfCircle(legendX+4,82,3,height),pdfText(legendX+14,86,10,'Observations',height));legendX+=112;}
    if(visible.model){parts.push('.42 .35 .85 RG 2 w',`${legendX} ${height-82} m ${legendX+16} ${height-82} l S`,'.38 .36 .44 rg',pdfText(legendX+24,86,10,'Exact PHOEBE model',height));legendX+=160;}
    if(visible.residuals)parts.push('.43 .36 .66 rg',pdfCircle(legendX+4,82,3,height),pdfText(legendX+14,86,10,'Residuals',height));
  }
  pdfAxes(parts,{left,right,top:lightTop,bottom:lightBottom,min:y0,max:y1,label:'Normalized flux',height});
  if(visible.model){parts.push('.42 .35 .85 RG 2 w');result.phases.forEach((x,i)=>parts.push(`${pdfNumber(px(x))} ${pdfNumber(height-lightY(result.model[i]))} ${i?'l':'m'}`));parts.push('S');}
  if(visible.observations){parts.push('.41 .44 .55 rg');phase.forEach((x,i)=>{if(Number.isFinite(flux[i]))parts.push(pdfCircle(px(x),lightY(flux[i]),2,height));});}
  if(visible.residuals){
    pdfAxes(parts,{left,right,top:resTop,bottom:resBottom,min:-residualLimit,max:residualLimit,label:'Residual (observed - model)',height});
    parts.push('.66 .64 .7 RG [.4 .4] 0 d',`${left} ${pdfNumber(height-residualY(0))} m ${right} ${pdfNumber(height-residualY(0))} l S`,'[] 0 d','.43 .36 .66 rg');
    phase.forEach((x,i)=>{if(Number.isFinite(residual[i]))parts.push(pdfCircle(px(x),residualY(residual[i]),2,height));});
  }
  parts.push('.2 .18 .23 rg',pdfText((left+right)/2-32,height-16,12,'Orbital phase',height));
  return pdfDocument(parts,width,height);
}

export function parameterTable(report){
  return report.model.parameters.map(row=>({parameter:row.name,value:row.value,unit:row.unit||'',role:row.role}));
}

const tabCell=value=>String(value??'').replace(/[\t\r\n]+/g,' ');
export function parameterTsv(report){
  const rows=[['Parameter','Value','Unit','Role'],...parameterTable(report).map(row=>[row.parameter,row.value,row.unit,row.role])];
  return rows.map(row=>row.map(tabCell).join('\t')).join('\r\n')+'\r\n';
}
