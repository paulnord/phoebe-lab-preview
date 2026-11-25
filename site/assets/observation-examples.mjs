export const OBSERVATION_EXAMPLES=Object.freeze({
  'observed-sz-her':Object.freeze({
    path:'examples/observed-sz-her-johnson-v.csv',
    name:'SZ Herculis · Johnson V',
    description:'Published differential Johnson V photometry · secondary donor · q=0.4715 guidance · no point uncertainties',
    time_system:'HJD',
    period:.8180837,
    epoch:2454588.167997,
    parameters:Object.freeze({contact:false,semidetached:true,donor:'secondary',inclination:87.566,
      radius_primary:.318,temperature_ratio:4881/7262,mass_ratio:.4715,eccentricity:0,omega:90,
      period:.8180837,epoch:2454588.167997,distortion:false,irradiation:false}),
    provenance:Object.freeze({catalog:'CDS J/AJ/143/34 table2',doi:'10.1088/0004-6256/143/2/34',
      url:'https://cdsarc.cds.unistra.fr/viz-bin/cat/J/AJ/143/34',
      selection:'All 437 published Johnson V rows; original HJD and differential magnitude; no published point uncertainty.'}),
  }),
  'observed-v1128-tau':Object.freeze({
    path:'examples/observed-v1128-tau-johnson-v.csv',
    name:'V1128 Tauri · Johnson V',
    description:'Published differential Johnson V photometry · model phase zero aligned to the alternate conjunction · q=0.534 guidance · no point uncertainties',
    time_system:'HJD',
    period:.305371,
    published_primary_epoch:2454842.3470,
    epoch:2454842.4996855,
    parameters:Object.freeze({contact:true,semidetached:false,donor:'primary',inclination:86,
      fillout_factor:.134,temperature_ratio:6400/6200,mass_ratio:.534,eccentricity:0,omega:90,
      period:.305371,epoch:2454842.4996855,distortion:false,irradiation:false}),
    provenance:Object.freeze({catalog:'CDS J/AJ/148/126 table3',doi:'10.1088/0004-6256/148/6/126',
      url:'https://cdsarc.cds.unistra.fr/viz-bin/cat/J/AJ/148/126',
      selection:'All 690 published V1128 Tau Johnson V rows; original HJD and differential magnitude; no published point uncertainty.',
      published_primary_epoch_hjd:2454842.3470,
      spectroscopic_epoch_hjd:2453864.7026,
      spectroscopic_period_days:.3053707,
      spectroscopic_source:'https://doi.org/10.1088/0004-6256/136/2/586',
      component_label_crosscheck:'https://www.raa-journal.org/issues/all/2011/v11n5/202203/P020220325510030141420.pdf',
      phoebe_epoch_convention:'https://ui.phoebe-project.org/docs/latest/tutorials/t0s',
      model_alignment:'PHOEBE t0_supconj initialized one half-period later at HJD 2454842.4996855; this does not revise the published eclipse timing.'}),
  }),
});

export function observationDataset(preset,parsed){
  if(!preset || !parsed?.rows?.length)throw Error('The published observation table is empty.');
  const values=parsed.rows.map(row=>row.cells.slice(0,2).map(Number));
  if(values.some(row=>row.length!==2 || row.some(value=>!Number.isFinite(value))))
    throw Error('The published observation table contains a non-numeric time or magnitude.');
  return {name:preset.name,synthetic:false,x_kind:'time',y_kind:'magnitude',
    x:values.map(row=>row[0]),y:values.map(row=>row[1]),period:preset.period,epoch:preset.epoch,
    time_system:preset.time_system,description:preset.description,provenance:{...preset.provenance}};
}
