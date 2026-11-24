import {tidalOutline,tidalSurfaceModel} from './stellar-shapes.mjs?v=camera-detail1';
import {eccentricAnomalyAtPhase} from '../experiment/eccentric-orbit.mjs?v=436129dc9aef5ac1';

export const foldPhase = phase => ((phase + .5) % 1 + 1) % 1 - .5;

export function surfaceGeometryKey(p) {
  if(!p.contact && !p.semidetached)return null;
  return JSON.stringify(p.contact?
    ['contact',p.mass_ratio,p.fillout_factor,p.period]:
    ['semi',p.donor,p.mass_ratio,p.donor==='primary'?p.radius_secondary:p.radius_primary,p.period]);
}

// In the overhead frame, the in-plane component toward Earth points down.
export function overheadEarthDirection(inclination) {
  const y=Math.sin(inclination*Math.PI/180);
  return y>1e-9?{x:0,y}:null;
}

const radians=value=>value*Math.PI/180;

// A camera changes only the drawing projection. It never changes orbital physics.
// Positive depth points toward the camera so the painter can draw the foreground last.
export function orbitCamera(p,view='earth') {
  const mode=typeof view==='string'?view:view?.mode||'earth';
  const i=radians(p.inclination);
  let right,down,depth;
  if(mode==='above'){
    // Preserve the established overhead convention: projected Earth is straight down.
    right=[-1,0,0];down=[0,1,0];depth=[0,0,1];
  }else if(mode==='free'){
    const az=radians(Number.isFinite(view.azimuth)?view.azimuth:90);
    const el=radians(Number.isFinite(view.elevation)?view.elevation:30);
    depth=[Math.cos(el)*Math.cos(az),Math.cos(el)*Math.sin(az),Math.sin(el)];
    right=[Math.sin(az),-Math.cos(az),0];
    down=[-Math.sin(el)*Math.cos(az),-Math.sin(el)*Math.sin(az),Math.cos(el)];
  }else{
    right=[1,0,0];down=[0,-Math.cos(i),Math.sin(i)];depth=[0,Math.sin(i),Math.cos(i)];
  }
  const dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
  const project=point=>[dot(point,right),dot(point,down),dot(point,depth)];
  const earth=project([0,Math.sin(i),Math.cos(i)]),length=Math.hypot(earth[0],earth[1]);
  return {mode,right,down,depth,project,earthDirection:length>1e-9?{x:earth[0]/length,y:earth[1]/length}:null};
}

export function orbitProjection(p, view) {
  const e=p.eccentricity, w=p.omega*Math.PI/180, i=p.inclination*Math.PI/180;
  const c=Math.cos(w),s=Math.sin(w),minor=Math.sqrt(1-e*e),camera=orbitCamera(p,view);
  const anomaly=eccentricAnomalyAtPhase(e,p.omega);
  const factors=[-p.mass_ratio/(1+p.mass_ratio),1/(1+p.mass_ratio)];
  return phase=>{
    const E=anomaly(phase), u=Math.cos(E)-e,v=minor*Math.sin(E);
    const along=u*s+v*c, across=u*c-v*s;
    const [x,y,z]=camera.project([across,along,0]);
    const separation=1-e*Math.cos(E);
    const depths=factors.map(f=>f*z),delta=depths[1]-depths[0];
    const front=camera.mode==='above'?(Math.abs(Math.sin(i))<1e-9?null:along>=0?1:0):Math.abs(delta)<1e-9?null:delta>0?1:0;
    return {stars:factors.map(f=>({x:f*x,y:f*y})),depths,front,
      separation,cosLongitude:across/separation,sinLongitude:along/separation};
  };
}

export function fluxAtPhase(curve, phase) {
  if(!curve)return null;
  const {phases, model}=curve, n=phases.length, x=foldPhase(phase);
  if(n<2 || x<phases[0] || x>phases[n-1])return null;
  let lo=0,hi=n-1;
  while(hi-lo>1){const mid=(hi+lo)>>1;if(phases[mid]<x)lo=mid;else hi=mid;}
  const t=(x-phases[lo])/(phases[hi]-phases[lo]);
  if(!Number.isFinite(t) || !Number.isFinite(model[lo]) || !Number.isFinite(model[hi]))return null;
  return model[lo]+t*(model[hi]-model[lo]);
}

const colors=['#db984b','#8876d0'];
function canvasSpace(canvas) {
  const w=canvas.clientWidth,h=canvas.clientHeight,dpr=Math.min(window.devicePixelRatio||1,2);
  if(!w || !h)return null;
  const width=Math.round(w*dpr),height=Math.round(h*dpr);
  if(canvas.width!==width || canvas.height!==height){canvas.width=width;canvas.height=height;}
  const ctx=canvas.getContext('2d');
  ctx.setTransform(width/w,0,0,height/h,0,0);ctx.clearRect(0,0,w,h);
  return {ctx,w,h};
}

export function detachedOrbitRadius(p, extents=[p.radius_primary,p.radius_secondary]) {
  const factors=[p.mass_ratio/(1+p.mass_ratio),1/(1+p.mass_ratio)],apastron=1+p.eccentricity;
  return Math.max(.01,...factors.map((factor,k)=>factor*apastron+extents[k]));
}

export function orthographicScale(width,height,radius,zoom=1) {
  const factor=Math.max(.6,Math.min(1.8,Number.isFinite(zoom)?zoom:1));
  return Math.min((width-24)/(2*radius),(height-54)/(2*radius))*factor;
}

function orbitPainter(p, view, surface) {
  const camera=orbitCamera(p,view),position=orbitProjection(p,view), paths=[[],[]], radii=[p.radius_primary,p.radius_secondary];
  const extents=surface?.extents??radii;
  for(let j=0;j<144;j++){
    position(j/144).stars.forEach((star,k)=>paths[k].push(star));
  }
  const radius=detachedOrbitRadius(p,extents);
  return (canvas,phase,zoom=1)=>{
    const box=canvasSpace(canvas);if(!box)return;
    const {ctx,w,h}=box,arrow=camera.earthDirection;
    const top=8,bottom=46,cy=(h+top-bottom)/2;
    const scale=orthographicScale(w,h,radius,zoom);
    if(!(scale>0))return;
    const px=x=>w/2+x*scale,py=y=>cy+y*scale;
    paths.forEach((path,k)=>{
      ctx.strokeStyle=colors[k]+'88';ctx.setLineDash([4,4]);ctx.beginPath();
      path.forEach(({x,y},j)=>j?ctx.lineTo(px(x),py(y)):ctx.moveTo(px(x),py(y)));
      ctx.closePath();ctx.stroke();ctx.setLineDash([]);
    });
    ctx.fillStyle='#6d6880';ctx.fillRect(w/2-2,cy-2,4,4);
    if(arrow){
      ctx.strokeStyle='#3a3c53';ctx.fillStyle='#3a3c53';ctx.lineWidth=1.5;
      const start=[w/2,h-41],tip=[start[0]+18*arrow.x,start[1]+18*arrow.y];
      ctx.beginPath();ctx.moveTo(...start);ctx.lineTo(...tip);
      ctx.lineTo(tip[0]-5,tip[1]-5);ctx.moveTo(...tip);ctx.lineTo(tip[0]+5,tip[1]-5);ctx.stroke();
      ctx.font='11px system-ui';ctx.textAlign='center';ctx.fillText('Toward Earth (in-plane projection)',w/2,h-8);
    }
    const pos=position(phase);
    for(const k of pos.front===0?[1,0]:[0,1]){
      const {x,y}=pos.stars[k],cx=px(x),yy=py(y),r=radii[k]*scale;
      const fill=ctx.createRadialGradient(cx-r*.23,yy-r*.3,0,cx,yy,r);
      fill.addColorStop(0,k?'#eee8ff':'#fff2bf');fill.addColorStop(1,colors[k]);
      ctx.fillStyle=fill;ctx.strokeStyle=k?'#67569c':'#99612e';ctx.lineWidth=1;
      ctx.beginPath();
      if(surface){
        tidalOutline(surface.radii[k],p,pos,k,camera,surface.directions).forEach(([sx,sy],j)=>
          j?ctx.lineTo(cx+sx*scale,yy+sy*scale):ctx.moveTo(cx+sx*scale,yy+sy*scale));
        ctx.closePath();
      }else ctx.arc(cx,yy,r,0,2*Math.PI);
      ctx.fill();ctx.stroke();
    }
  };
}

export function projectNativeSurface(mesh,p,phase,view) {
  if(!mesh || mesh.schema!==1 || !Array.isArray(mesh.components) || mesh.components.length!==2)
    throw Error('Invalid native PHOEBE orbit surface.');
  if(p.contact && (mesh.geometry!=='contact' || mesh.frame!=='primary_origin' || !Number.isFinite(mesh.neck)))
    throw Error('A connected native contact envelope is required.');
  if(p.semidetached && (mesh.geometry!=='semi' || mesh.frame!=='component_local' || mesh.donor!==p.donor))
    throw Error('The native semi-detached donor surface is stale.');
  const camera=orbitCamera(p,view),pos=orbitProjection(p,view)(phase);
  function point(value,component){
    let [u,v,z]=value,sign=1,center=null;
    if(mesh.frame==='primary_origin')u-=p.mass_ratio/(1+p.mass_ratio);
    else {sign=component===0?1:-1;center=pos.stars[component];}
    const across=sign*(u*pos.cosLongitude-v*pos.sinLongitude);
    const along=sign*(u*pos.sinLongitude+v*pos.cosLongitude);
    const relative=camera.project([across,along,z]);
    return center?[center.x+relative[0],center.y+relative[1],pos.depths[component]+relative[2]]:relative;
  }
  const triangles=[];
  mesh.components.forEach((part,component)=>{
    if(!Array.isArray(part.triangles))throw Error('Native surface triangles are missing.');
    part.triangles.forEach(triangle=>{
      if(!Array.isArray(triangle)||triangle.length!==3)return;
      const points=triangle.map(value=>point(value,component));
      if(points.flat().every(Number.isFinite))triangles.push({component,points,depth:points.reduce((s,v)=>s+v[2],0)/3});
    });
  });
  return {position:pos,triangles,neck:mesh.neck};
}

export const nativeTrianglePaintOrder=triangles=>[...triangles].sort((a,b)=>a.depth-b.depth);

export function nativeOrbitRadius(mesh,p) {
  const projected=projectNativeSurface(mesh,p,0,'above');
  return Math.max(.01,...projected.triangles.flatMap(triangle=>triangle.points.map(point=>Math.hypot(...point))));
}

function nativeOrbitPainter(p,view,mesh) {
  const camera=orbitCamera(p,view),position=orbitProjection(p,view),paths=[[],[]];
  for(let j=0;j<72;j++){
    const phase=j/72,pos=position(phase);
    pos.stars.forEach((star,k)=>paths[k].push(star));
  }
  const radius=nativeOrbitRadius(mesh,p);
  return (canvas,phase,zoom=1)=>{
    const box=canvasSpace(canvas);if(!box)return;
    const {ctx,w,h}=box,arrow=camera.earthDirection;
    const top=8,bottom=46,cy=(h+top-bottom)/2;
    const scale=orthographicScale(w,h,radius,zoom);
    const px=x=>w/2+x*scale,py=y=>cy+y*scale;
    paths.forEach((path,k)=>{
      ctx.strokeStyle=colors[k]+'55';ctx.setLineDash([4,4]);ctx.beginPath();
      path.forEach(({x,y},j)=>j?ctx.lineTo(px(x),py(y)):ctx.moveTo(px(x),py(y)));
      ctx.closePath();ctx.stroke();ctx.setLineDash([]);
    });
    const projected=projectNativeSurface(mesh,p,phase,view);
    for(const triangle of nativeTrianglePaintOrder(projected.triangles)){
      const [[x0,y0],[x1,y1],[x2,y2]]=triangle.points;
      const area=Math.abs((x1-x0)*(y2-y0)-(y1-y0)*(x2-x0));
      if(area<1e-10)continue;
      ctx.globalAlpha=1;
      ctx.fillStyle=colors[triangle.component];ctx.strokeStyle=colors[triangle.component]+'88';ctx.lineWidth=.35;
      ctx.beginPath();ctx.moveTo(px(x0),py(y0));ctx.lineTo(px(x1),py(y1));ctx.lineTo(px(x2),py(y2));ctx.closePath();ctx.fill();ctx.stroke();
    }
    ctx.globalAlpha=1;ctx.fillStyle='#6d6880';ctx.fillRect(w/2-2,cy-2,4,4);
    if(arrow){
      ctx.strokeStyle='#3a3c53';ctx.fillStyle='#3a3c53';ctx.lineWidth=1.5;
      const start=[w/2,h-41],tip=[start[0]+18*arrow.x,start[1]+18*arrow.y];
      ctx.beginPath();ctx.moveTo(...start);ctx.lineTo(...tip);ctx.lineTo(tip[0]-5,tip[1]-5);ctx.moveTo(...tip);ctx.lineTo(tip[0]+5,tip[1]-5);ctx.stroke();
      ctx.font='11px system-ui';ctx.textAlign='center';ctx.fillText('Toward Earth (in-plane projection)',w/2,h-8);
    }
  };
}

function drawCurve(canvas, curve, phase) {
  const box=canvasSpace(canvas);if(!box)return;
  const {ctx,w,h}=box, left=42,right=w-13,top=7,bottom=h-24;
  const px=x=>left+(x+.5)*(right-left);
  ctx.font='10px system-ui';ctx.textAlign='center';ctx.fillStyle='#625d73';
  ctx.strokeStyle='#e0dbea';ctx.beginPath();ctx.moveTo(left,top);ctx.lineTo(left,bottom);ctx.lineTo(right,bottom);ctx.stroke();
  for(const x of [-.5,-.25,0,.25,.5])ctx.fillText(String(x),px(x),h-9);
  if(!curve)return;
  const finite=curve.model.filter(Number.isFinite);
  if(finite.length<2)return;
  const lo=Math.min(...finite),hi=Math.max(...finite),pad=Math.max(.015,(hi-lo)*.1);
  const py=y=>top+(hi+pad-y)/(hi-lo+2*pad)*(bottom-top);
  ctx.textAlign='right';
  for(const y of [lo,hi])ctx.fillText(y.toFixed(2),left-5,py(y)+3);
  ctx.strokeStyle='#6857c9';ctx.lineWidth=1.8;ctx.beginPath();
  let started=false;
  curve.phases.forEach((x,j)=>{
    const y=curve.model[j];
    if(!Number.isFinite(y)){started=false;return;}
    if(started)ctx.lineTo(px(x),py(y));else {ctx.moveTo(px(x),py(y));started=true;}
  });
  ctx.stroke();
  const y=fluxAtPhase(curve,phase);
  if(y!==null){
    const x=px(foldPhase(phase));ctx.strokeStyle='#97571a';ctx.fillStyle='#97571a';ctx.lineWidth=1;
    ctx.beginPath();ctx.moveTo(x,py(y));ctx.lineTo(x,bottom);ctx.stroke();
    ctx.beginPath();ctx.arc(x,py(y),4,0,2*Math.PI);ctx.fill();
  }
}

export function bindOrbitViewer(readModel,ensureSurface=()=>{},setDetail=()=>{}) {
  const id=name=>document.getElementById('orbit-'+name);
  const dialog=id('dialog'), speed=id('speed'),scrub=id('phase'),play=id('play'),view=id('view'),detail=id('detail');
  const cameraControls=id('camera'),azimuth=id('azimuth'),elevation=id('elevation'),cameraReadout=id('camera-readout'),sky=id('sky');
  const zoom=id('zoom'),zoomReadout=id('zoom-readout'),zoomReset=id('zoom-reset');
  const motion=matchMedia('(prefers-reduced-motion: reduce)');
  let playing=false,phase=0,last=0,frame=0,key='',paint,launcher,lastAvailable=null,drag=null;
  const cameraView=()=>view.value==='free'?{mode:'free',azimuth:Number(azimuth.value),elevation:Number(elevation.value)}:view.value;
  function syncCameraControls(){
    cameraControls.hidden=view.value!=='free';
    cameraReadout.textContent=`Azimuth ${Number(azimuth.value).toFixed(0)}° · elevation ${Number(elevation.value).toFixed(0)}°`;
  }
  function syncZoom(){
    const percent=Math.round(Number(zoom.value)*100);
    zoomReadout.textContent=percent+'%';zoom.setAttribute('aria-valuetext',percent+'%');
  }
  const setPlaying=value=>{playing=value;last=0;play.textContent=value?'Pause':'Play';};
  function draw(){
    if(!dialog.open)return;
    const {parameters:p,curve,label,surface}=readModel();
    const camera=cameraView();
    const k=[view.value,detail.value,azimuth.value,elevation.value,p.contact,p.semidetached,p.donor,p.inclination,p.eccentricity,p.omega,p.mass_ratio,p.radius_primary,p.radius_secondary,p.distortion,surface?.key,surface?.status].join('/');
    if(k!==key){
      key=k;
      const constrained=p.contact||p.semidetached,detachedSurface=constrained?null:tidalSurfaceModel(p,detail.value);
      const nativeMesh=constrained?surface?.mesh:null;
      paint=nativeMesh?nativeOrbitPainter(p,camera,nativeMesh):constrained?(canvas=>{canvas.width=Math.max(1,canvas.clientWidth);canvas.height=Math.max(1,canvas.clientHeight);canvas.getContext('2d').clearRect(0,0,canvas.width,canvas.height);}):orbitPainter(p,camera,detachedSurface);
      const nativeState=surface;
      const requested=detail.value==='high'?'High detail':'Preview detail';
      const shown=(nativeState?.displayDetail==='high'?'High':'Preview')+' detail';
      const displayed=nativeMesh?`${nativeMesh.triangles_actual} PHOEBE ntriangles · ${nativeMesh.components.reduce((sum,part)=>sum+part.triangles.length,0)} rendered facets`:'';
      const pending=nativeMesh&&nativeState?.status==='pending'?` ${requested} is regenerating.`:nativeMesh&&nativeState?.status==='error'?` ${requested} failed: ${nativeState.error}`:'';
      id('shape-note').textContent=nativeMesh&&p.contact?
        `${shown} · ${displayed}. Native PHOEBE connected common-envelope surface; the pinched color boundary marks the neck.${pending}` : nativeMesh&&p.semidetached?
        `${shown} · ${displayed}. Native PHOEBE co-rotating surfaces; the ${p.donor} donor fills its Roche lobe.${pending}` : constrained&&nativeState?.status==='error'?
        `Native PHOEBE surface failed: ${nativeState.error}` : constrained?
        `Building the native PHOEBE phase-zero surface at ${requested.toLowerCase()}; no detached substitute is shown.` : detachedSurface?
        `${requested} · ${detachedSurface.directions.length} Roche surface samples per star. Animated detached Roche surfaces; heating is not shown.` : p.distortion?
        'Detached Roche surfaces are unavailable for these settings. Showing round disk radii instead.' :
        'Round disks (tidal distortion off). Heating is not shown.';
    }
    paint(sky,phase,Number(zoom.value));
    const i=p.inclination.toFixed(1);
    id('inclination').textContent=view.value==='above'?
      (overheadEarthDirection(p.inclination)?'Inclination '+i+'°. Arrow shows only the part of the Earth direction in the orbital plane.':'Inclination '+i+'°. Earth lies along the orbital pole, so there is no in-plane arrow.'):
      view.value==='free'?'Display camera only · '+cameraReadout.textContent+'. Arrow points toward Earth; drag the orbit to rotate.':
      'Inclination '+i+'°. '+(p.inclination>1e-6?'This is the view from Earth; the nearer star is drawn in front.':'Face-on view from Earth; neither star is in front of the other.');
    id('time').textContent='Phase '+phase.toFixed(3)+' · '+(phase*p.period).toFixed(4)+' of '+Number(p.period.toFixed(7))+' model days';
    scrub.value=String(phase);
    scrub.style.setProperty('--fill',(phase*100)+'%');
    scrub.setAttribute('aria-valuetext',phase.toFixed(3)+' of one orbit');
    id('curve-status').textContent=label;
    if(lastAvailable!==Boolean(curve)){lastAvailable=Boolean(curve);id('curve').hidden=!lastAvailable;}
    if(curve)drawCurve(id('curve'),curve,phase);
  }
  function tick(now){
    frame=0;
    if(!dialog.open || !playing)return;
    if(last)phase=(phase+Math.min(now-last,100)/(Number(speed.value)*1000))%1;
    last=now;draw();frame=requestAnimationFrame(tick);
  }
  function run(value){
    if(frame)cancelAnimationFrame(frame);
    frame=0;setPlaying(value);draw();
    if(value && dialog.open)frame=requestAnimationFrame(tick);
  }
  for(const button of document.querySelectorAll('[data-open-orbit]'))button.addEventListener('click',()=>{
    launcher=button;ensureSurface();dialog.showModal();run(!motion.matches);
  });
  play.addEventListener('click',()=>run(!playing));
  scrub.addEventListener('input',()=>{phase=Number(scrub.value);run(false);});
  view.addEventListener('change',()=>{syncCameraControls();draw();});
  detail.addEventListener('change',()=>{key='';setDetail(detail.value);draw();});
  for(const control of [azimuth,elevation])control.addEventListener('input',()=>{syncCameraControls();draw();});
  zoom.addEventListener('input',()=>{syncZoom();draw();});
  zoomReset.addEventListener('click',()=>{zoom.value='1';syncZoom();draw();zoom.focus();});
  sky.addEventListener('pointerdown',event=>{
    const {parameters:p}=readModel();
    if(view.value!=='free'){
      const from=view.value;view.value='free';azimuth.value='90';
      elevation.value=from==='above'?'85':String(Math.max(-85,Math.min(85,90-p.inclination)));
      syncCameraControls();
    }
    drag={id:event.pointerId,x:event.clientX,y:event.clientY,azimuth:Number(azimuth.value),elevation:Number(elevation.value)};
    sky.setPointerCapture?.(event.pointerId);sky.classList.add('dragging');run(false);event.preventDefault();
  });
  sky.addEventListener('pointermove',event=>{
    if(!drag||event.pointerId!==drag.id)return;
    azimuth.value=String(Math.max(-180,Math.min(180,drag.azimuth+(event.clientX-drag.x)*.6)));
    elevation.value=String(Math.max(-85,Math.min(90,drag.elevation-(event.clientY-drag.y)*.6)));
    syncCameraControls();draw();
  });
  const stopDrag=event=>{if(drag&&event.pointerId===drag.id){drag=null;sky.classList.remove('dragging');}};
  sky.addEventListener('pointerup',stopDrag);sky.addEventListener('pointercancel',stopDrag);
  speed.addEventListener('change',()=>{last=0;draw();});
  id('close').addEventListener('click',()=>dialog.close());
  dialog.addEventListener('close',()=>{
    run(false);
    if(launcher?.getClientRects().length)launcher.focus();
    else document.querySelector('.orbit-launch')?.focus();
  });
  motion.addEventListener('change',()=>{if(motion.matches && dialog.open)run(false);});
  new ResizeObserver(draw).observe(id('sky'));
  syncCameraControls();syncZoom();
  return draw;
}
