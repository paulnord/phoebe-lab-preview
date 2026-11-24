import {tidalOutline,tidalSurfaceModel} from './stellar-shapes.mjs?v=90806d58aeae79bc';
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

export function orbitProjection(p, view) {
  const e=p.eccentricity, w=p.omega*Math.PI/180, i=p.inclination*Math.PI/180;
  const c=Math.cos(w),s=Math.sin(w),minor=Math.sqrt(1-e*e),ci=Math.cos(i),si=Math.sin(i);
  const anomaly=eccentricAnomalyAtPhase(e,p.omega);
  const factors=[-p.mass_ratio/(1+p.mass_ratio),1/(1+p.mass_ratio)];
  return phase=>{
    const E=anomaly(phase), u=Math.cos(E)-e,v=minor*Math.sin(E);
    const along=u*s+v*c, across=u*c-v*s;
    // Rotate the entire overhead frame 180°, preserving orbital direction.
    const [x,y]=view==='above'?[-across,along]:[across,-along*ci];
    const separation=1-e*Math.cos(E);
    return {stars:factors.map(f=>({x:f*x,y:f*y})),depths:factors.map(f=>view==='above'?0:f*along*si),front:Math.abs(si)<1e-9?null:along>=0?1:0,
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

function orbitPainter(p, view, surface) {
  const position=orbitProjection(p,view), paths=[[],[]], radii=[p.radius_primary,p.radius_secondary];
  const extents=surface?.extents??radii;
  let extentX=0,extentY=0;
  for(let j=0;j<144;j++){
    position(j/144).stars.forEach((star,k)=>{
      paths[k].push(star);
      extentX=Math.max(extentX,Math.abs(star.x)+extents[k]);
      extentY=Math.max(extentY,Math.abs(star.y)+extents[k]);
    });
  }
  return (canvas,phase)=>{
    const box=canvasSpace(canvas);if(!box)return;
    const {ctx,w,h}=box,arrow=view==='above'?overheadEarthDirection(p.inclination):null;
    const top=8, bottom=arrow?46:8, cy=(h+top-bottom)/2;
    const scale=Math.min((w-24)/(2*extentX),(h-top-bottom)/(2*extentY));
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
      const start=[w/2,h-41],tip=[start[0]+18*arrow.x,start[1]+18*Math.sign(arrow.y)];
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
        tidalOutline(surface.radii[k],p,pos,k,view).forEach(([sx,sy],j)=>
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
  const pos=orbitProjection(p,view)(phase),ci=Math.cos(p.inclination*Math.PI/180),si=Math.sin(p.inclination*Math.PI/180);
  function point(value,component){
    let [u,v,z]=value,sign=1,center=null;
    if(mesh.frame==='primary_origin')u-=p.mass_ratio/(1+p.mass_ratio);
    else {sign=component===0?1:-1;center=pos.stars[component];}
    const across=sign*(u*pos.cosLongitude-v*pos.sinLongitude);
    const along=sign*(u*pos.sinLongitude+v*pos.cosLongitude);
    const relative=view==='above'?[-across,along,z]:[across,-along*ci+z*si,along*si+z*ci];
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

function nativeOrbitPainter(p,view,mesh) {
  const position=orbitProjection(p,view),paths=[[],[]];
  let extentX=.7,extentY=.7;
  for(let j=0;j<72;j++){
    const phase=j/72,pos=position(phase),projected=projectNativeSurface(mesh,p,phase,view);
    pos.stars.forEach((star,k)=>paths[k].push(star));
    for(const {points} of projected.triangles)for(const point of points){extentX=Math.max(extentX,Math.abs(point[0]));extentY=Math.max(extentY,Math.abs(point[1]));}
  }
  return (canvas,phase)=>{
    const box=canvasSpace(canvas);if(!box)return;
    const {ctx,w,h}=box,arrow=view==='above'?overheadEarthDirection(p.inclination):null;
    const top=8,bottom=arrow?46:8,cy=(h+top-bottom)/2;
    const scale=Math.min((w-24)/(2*extentX),(h-top-bottom)/(2*extentY));
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
      const start=[w/2,h-41],tip=[start[0]+18*arrow.x,start[1]+18*Math.sign(arrow.y)];
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

export function bindOrbitViewer(readModel,ensureSurface=()=>{}) {
  const id=name=>document.getElementById('orbit-'+name);
  const dialog=id('dialog'), speed=id('speed'),scrub=id('phase'),play=id('play'),view=id('view');
  const motion=matchMedia('(prefers-reduced-motion: reduce)');
  let playing=false,phase=0,last=0,frame=0,key='',paint,launcher,lastAvailable=null;
  const setPlaying=value=>{playing=value;last=0;play.textContent=value?'Pause':'Play';};
  function draw(){
    if(!dialog.open)return;
    const {parameters:p,curve,label,surface}=readModel();
    const k=[view.value,p.contact,p.semidetached,p.donor,p.inclination,p.eccentricity,p.omega,p.mass_ratio,p.radius_primary,p.radius_secondary,p.distortion,surface?.key,surface?.status].join('/');
    if(k!==key){
      key=k;
      const constrained=p.contact||p.semidetached,detachedSurface=constrained?null:tidalSurfaceModel(p);
      const nativeMesh=constrained && surface?.status==='ready'?surface.mesh:null;
      paint=nativeMesh?nativeOrbitPainter(p,view.value,nativeMesh):constrained?(canvas=>{canvas.width=Math.max(1,canvas.clientWidth);canvas.height=Math.max(1,canvas.clientHeight);canvas.getContext('2d').clearRect(0,0,canvas.width,canvas.height);}):orbitPainter(p,view.value,detachedSurface);
      const nativeState=surface;
      id('shape-note').textContent=nativeMesh&&p.contact?
        'Native PHOEBE connected common-envelope surface; the pinched color boundary marks the neck.' : nativeMesh&&p.semidetached?
        `Native PHOEBE co-rotating surfaces; the ${p.donor} donor fills its Roche lobe.` : constrained&&nativeState?.status==='error'?
        `Native PHOEBE surface failed: ${nativeState.error}` : constrained?
        'Building the native PHOEBE phase-zero surface; no detached substitute is shown.' : detachedSurface?
        'Animated detached Roche surfaces. Heating is not shown.' : p.distortion?
        'Detached Roche surfaces are unavailable for these settings. Showing round disk radii instead.' :
        'Round disks (tidal distortion off). Heating is not shown.';
    }
    paint(id('sky'),phase);
    const i=p.inclination.toFixed(1);
    id('inclination').textContent=view.value==='above'?
      (overheadEarthDirection(p.inclination)?'Inclination '+i+'°. Arrow shows only the part of the Earth direction in the orbital plane.':'Inclination '+i+'°. Earth lies along the orbital pole, so there is no in-plane arrow.'):
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
    launcher=button;phase=0;ensureSurface();dialog.showModal();run(!motion.matches);
  });
  play.addEventListener('click',()=>run(!playing));
  scrub.addEventListener('input',()=>{phase=Number(scrub.value);run(false);});
  view.addEventListener('change',draw);
  speed.addEventListener('change',()=>{last=0;draw();});
  id('close').addEventListener('click',()=>dialog.close());
  dialog.addEventListener('close',()=>{
    run(false);
    if(launcher?.getClientRects().length)launcher.focus();
    else document.querySelector('.orbit-launch')?.focus();
  });
  motion.addEventListener('change',()=>{if(motion.matches && dialog.open)run(false);});
  new ResizeObserver(draw).observe(id('sky'));
  return draw;
}
