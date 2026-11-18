export function bindAdvanced(call,action,commit) {
  const el=id=>document.getElementById('adv-'+id);
  const panel=document.getElementById('advanced-panel');
  const options=(node,values)=>node.replaceChildren(...values.map(v=>new Option(v,v)));
  let rows=[], doc=null, field=null, selected=null;
  function resetField() {field=null;selected=null;el('detail').hidden=true;}
  function filter() {
    const list=el('parameters'),query=el('search').value.toLowerCase();
    const found=rows.filter(r=>(!el('context').value || r.context===el('context').value) && r.twig.toLowerCase().includes(query));
    list.replaceChildren(...found.map(r=>new Option(r.twig,r.id)));
    el('count').textContent=found.length+' matching parameters';
    if(selected && found.some(r=>r.id===selected))list.value=selected;
    else {list.selectedIndex=-1;resetField();}
  }
  function details(row,f) {
    const input=f.kind==='choice'||f.kind==='boolean'||f.kind==='selection' ? document.createElement('select')
      : document.createElement(f.kind==='array'||f.kind==='view'?'textarea':'input');
    if(input.tagName==='SELECT') {
      const choices=f.kind==='boolean'?['false','true']:f.choices;
      options(input,choices);
      if(f.kind==='selection'){
        input.multiple=true;
        for(const o of input.options)o.selected=f.value.includes(o.value);
      }else input.value=String(f.value);
    }else if(f.kind==='number'||f.kind==='integer'){
      input.type='number';input.step=f.kind==='integer'?'1':'any';
      if(f.limits[0]!=null)input.min=f.limits[0];
      if(f.limits[1]!=null)input.max=f.limits[1];
      input.value=f.value;
    }else{
      if(input.tagName==='TEXTAREA')input.rows=4;
      input.value=typeof f.value==='string'?f.value:JSON.stringify(f.value);
    }
    input.id='adv-value';
    el('input').replaceChildren(input);
    el('label').textContent=row.twig+(f.unit?' ('+f.unit+')':'');
    el('help').textContent=[f.description,f.constrained?'PHOEBE derives this value from a constraint.':''].filter(Boolean).join(' ');
    field=f;selected=row.id;
    el('priors').hidden=!f.editable||f.kind!=='number';
    el('detail').hidden=false;
    options(el('target'),f.flip);
    el('target').hidden=el('flip').hidden=!f.flip.length;
  }
  async function loadField(id) {
    const row=rows.find(r=>r.id===id);
    if(row)details(row,await call('field',{id}));
  }
  function kindControls() {
    const feature=el('category').value==='feature';
    const kind=el('kind').value;
    el('star-label').hidden=!feature||kind!=='spot';
    el('rv-label').hidden=!feature||kind==='spot';
    options(el('rv'),kind==='rv_offset'?doc.rv:doc.lc);
  }
  function loadKinds() {
    options(el('kind'),doc.objects[el('category').value]||[]);
    kindControls();
  }
  async function refresh(meta) {
    doc=meta;panel.hidden=meta.kind!=='bundle';
    if(panel.hidden){rows=[];resetField();return;}
    const context=el('context').value,cat=el('category').value;
    rows=await call('catalog');
    options(el('context'),['',...new Set(rows.map(r=>r.context).sort())]);
    el('context').options[0].textContent='All contexts';el('context').value=context;
    filter();
    if(selected)await loadField(selected);
    options(el('category'),Object.keys(doc.objects));if(cat)el('category').value=cat;
    options(el('star'),doc.stars);options(el('rv'),doc.rv);
    options(el('solver'),doc.solvers);options(el('solution'),doc.solutions);
    loadKinds();el('report').textContent='';
  }
  function controls(busy) {
    if(!doc||panel.hidden)return;
    if(field){el('value').disabled=busy||!field.editable;el('apply').disabled=busy||!field.editable;}
    el('solve').disabled=busy||!doc.solvers.length;
    el('adopt').disabled=busy||!doc.solutions.length;
  }
  function change(op,args){return action('Updating the native PHOEBE bundle…',async()=>{
    await commit(await call(op,args));});}
  el('context').onchange=filter;el('search').oninput=filter;
  el('parameters').onchange=()=>action('Reading PHOEBE parameter…',async()=>{
    await loadField(el('parameters').value);});
  el('apply').onclick=()=>action('Applying parameter…',async()=>{
    const input=el('value');
    if(!input.reportValidity())return;
    let value=input.value;
    if(field.kind==='integer'||field.kind==='number')value=input.valueAsNumber;
    if(field.kind==='boolean')value=value==='true';
    if(field.kind==='array')value=JSON.parse(value);
    if(field.kind==='selection')value=Array.from(input.selectedOptions,o=>o.value);
    await commit(await call('set_field',{id:selected,value}));
  });
  el('prior-add').onclick=()=>change('distribution',{id:selected,label:el('prior-label').value,
    family:el('family').value,a:el('prior-a').valueAsNumber,b:el('prior-b').valueAsNumber});
  el('flip').onclick=()=>change('flip',{id:selected,target:el('target').value});
  el('category').onchange=loadKinds;el('kind').onchange=kindControls;
  el('add').onclick=()=>change('add',{category:el('category').value,kind:el('kind').value,
    component:el('star').value,dataset:el('rv').value});
  el('solve').onclick=()=>change('solve',{solver:el('solver').value});
  el('adopt').onclick=()=>change('adopt',{solution:el('solution').value});
  el('checks').onclick=()=>action('Checking PHOEBE bundle…',async()=>{el('report').textContent=await call('checks');});
  return {refresh,controls};
}
