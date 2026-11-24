import {eccentricAnomalyAtPhase} from '../experiment/eccentric-orbit.mjs?v=436129dc9aef5ac1';

// Geometric side view in the orbital plane, perpendicular to the line of centers.
// Lengths are in units of the semimajor axis. Both lab stars have syncpar=1.
const pi=Math.PI;
const volumeDirections=[];
const nodes=[.0950125098,.2816035508,.4580167777,.6178762444,.7554044084,.8656312024,.9445750231,.9894009350];
const weights=[.1894506105,.1826034150,.1691565194,.1495959888,.1246289713,.0951585117,.0622535239,.0271524594];
// Gauss-Legendre integration in cos(theta) about the line of centers,
// with azimuthal symmetry in each quadrant.
for(let i=0;i<nodes.length;i++)for(const x of [-nodes[i],nodes[i]])for(let j=0;j<4;j++){
  const z=Math.sqrt(1-x*x)*Math.sin((j+.5)*pi/8);
  volumeDirections.push([x,z,weights[i]/8]);
}

function rocheSurface(q,d,radius) {
  const rotation=(1+q)/2;
  function potential(r,x,z){
    return 1/r+q*(1/Math.sqrt(d*d+r*r-2*d*r*x)-r*x/(d*d))+rotation*r*r*(1-z*z);
  }
  // Along the line of centers the potential first reaches a minimum at L1.
  let lo=0,hi=d;
  for(let i=0;i<42;i++){
    const r=(lo+hi)/2;
    if(-1/(r*r)+q/((d-r)**2)-q/(d*d)+2*rotation*r>0)hi=r;else lo=r;
  }
  const l1=(lo+hi)/2,critical=potential(l1,1,0);
  function surfaceRadius(level,x,z){
    let a=0,b=l1;
    for(let i=0;i<23;i++){
      const r=(a+b)/2;
      if(potential(r,x,z)>level)a=r;else b=r;
    }
    return (a+b)/2;
  }
  function meanCube(level){
    let sum=0;
    for(const [x,z,w] of volumeDirections)sum+=w*surfaceRadius(level,x,z)**3;
    return sum;
  }
  const target=radius**3;
  if(meanCube(critical)<target)return null;
  lo=critical;hi=potential(Math.min(radius*.5,l1*.5),1,0);
  for(let i=0;i<22;i++){
    const level=(lo+hi)/2;
    if(meanCube(level)>target)lo=level;else hi=level;
  }
  const level=(lo+hi)/2;
  return (x,z)=>surfaceRadius(level,x,z);
}

function rocheProfile(q,d,radius) {
  const surface=rocheSurface(q,d,radius);
  if(!surface)return null;
  return Array.from({length:145},(_,i)=>{
    const theta=2*pi*i/144,x=Math.cos(theta),z=Math.sin(theta);
    const r=surface(x,z);
    return [r*x,r*z];
  });
}

export function detachedShape(p){
  const d=1-p.eccentricity;
  function outline(q,r,x0,sign){
    const points=p.distortion?rocheProfile(q,d,r):Array.from({length:97},(_,i)=>[r*Math.cos(i*pi/48),r*Math.sin(i*pi/48)]);
    return points?.map(([x,z])=>[x0+sign*x,z]);
  }
  const primary=outline(p.mass_ratio,p.radius_primary,0,1);
  const secondary=outline(1/p.mass_ratio,p.radius_secondary,d,-1);
  if(!primary || !secondary)return null;
  return {outlines:[primary,secondary]};
}

export function paintShape(canvas,shape){
  const w=canvas.clientWidth,h=canvas.clientHeight;
  if(!w || !h)return;
  const dpr=Math.min(devicePixelRatio||1,2);
  canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);
  if(!shape)return;
  const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);
  const outlines=shape.outlines, points=outlines.flat(),xs=points.map(p=>p[0]),zs=points.map(p=>p[1]);
  const xmin=Math.min(...xs),xmax=Math.max(...xs),zmax=Math.max(...zs.map(Math.abs));
  const scale=Math.min((w-12)/(xmax-xmin),(h-6)/(2*zmax));
  const px=x=>w/2+(x-(xmin+xmax)/2)*scale,py=z=>h/2-z*scale;
  const colors=[['#ffe7b5','#dda462','#9b632e'],['#e6e2ff','#aa9ce1','#71619c']];
  const path=new Path2D();
  outlines.forEach((outline,i)=>{
    const component=new Path2D();
    outline.forEach(([x,z],j)=>j?component.lineTo(px(x),py(z)):component.moveTo(px(x),py(z)));
    component.closePath();path.addPath(component);
    const cx=shape.neck==null?null:px(shape.neck);
    const fills=cx==null?[i]:[0,1];
    for(const k of fills){
      ctx.save();ctx.clip(component);
      if(cx!=null){ctx.beginPath();ctx.rect(k?cx:0,0,k?w-cx:cx,h);ctx.clip();}
      const xx=outline.map(v=>px(v[0]));
      const left=k && cx!=null?cx:Math.min(...xx),right=!k && cx!=null?cx:Math.max(...xx);
      const cy=py(.4*Math.max(...outline.map(v=>v[1]))),gx=left+.37*(right-left);
      const g=ctx.createRadialGradient(gx,cy,0,gx,cy,Math.max(1,.75*(right-left)));
      colors[k].forEach((c,j)=>g.addColorStop(j/2,c));
      ctx.fillStyle=g;ctx.fillRect(0,0,w,h);ctx.restore();
    }
  });
  ctx.lineWidth=1;ctx.strokeStyle='#55465899';ctx.stroke(path);
}

export function bindStarGuide(canvas,caption){
  let lastKey='',shape;
  function draw(p){
    const key=[p.contact,p.semidetached,p.donor,p.distortion,p.eccentricity,p.mass_ratio,p.radius_primary,p.radius_secondary].join('/');
    if(key!==lastKey){
      lastKey=key;shape=p.contact||p.semidetached?null:detachedShape(p);
      caption.textContent=p.contact?'Shared contact envelope · open the orbit viewer for the native connected surface':p.semidetached?`${p.donor[0].toUpperCase()+p.donor.slice(1)} donor fills its Roche lobe · open the orbit viewer for native tidal surfaces`:shape?(p.distortion?'Roche surfaces':'Spheres')+(p.eccentricity?' · side view at periastron':' · side view'):'Detached surface reaches its Roche limit';
      canvas.setAttribute('aria-label',caption.textContent);
    }else return;
    paintShape(canvas,shape);
  }
  new ResizeObserver(()=>paintShape(canvas,shape)).observe(canvas);
  return draw;
}

// Project the relative separation onto the sky in semimajor-axis units.
function skyOrbit(p) {
  const e=p.eccentricity, omega=p.omega*pi/180, inclination=p.inclination*pi/180;
  const cosW=Math.cos(omega), sinW=Math.sin(omega), cosI=Math.cos(inclination);
  const minor=Math.sqrt(1-e*e), anomaly=eccentricAnomalyAtPhase(e,p.omega);
  return phase=>{
    const E=anomaly(phase);
    const x=Math.cos(E)-e, y=minor*Math.sin(E);
    const along=x*sinW+y*cosW;
    const across=x*cosW-y*sinW, separation=1-e*Math.cos(E);
    return {x:across,y:-along*cosI,separation,cosLongitude:across/separation,
      sinLongitude:along/separation,secondaryInFront:along>=0};
  };
}


// Local +x points toward the companion and +z is the orbital pole.
// Sample the same detached Roche equipotential used by the side-view guide.
function makeSurfaceDirections(rings,azimuths){
  const directions=[[1,0,0],[-1,0,0]];
  for(let ring=1;ring<rings;ring++){
    const angle=pi*ring/rings;
    for(let j=0;j<azimuths;j++){
      const azimuth=2*pi*j/azimuths;
      directions.push([Math.cos(angle),Math.sin(angle)*Math.cos(azimuth),Math.sin(angle)*Math.sin(azimuth)]);
    }
  }
  return directions;
}
const surfaceDirections=makeSurfaceDirections(12,20);
const highSurfaceDirections=makeSurfaceDirections(18,32);

function tidalRadii(q,r,e,directions){
  const samples=[];
  for(let i=0;i<(e?5:1);i++){
    const d=1-e+2*e*i/4;
    const surface=rocheSurface(q,d,r);
    if(!surface)return null;
    samples.push(directions.map(([x,,z])=>surface(x,z)));
  }
  return samples;
}

// The outer boundary of the sky-projected surface samples, in drawing order.
function silhouette(points){
  points.sort((a,b)=>a[0]-b[0] || a[1]-b[1]);
  function half(ordered){
    const edge=[];
    for(const point of ordered){
      while(edge.length>=2){
        const a=edge[edge.length-2], b=edge[edge.length-1];
        if((b[0]-a[0])*(point[1]-a[1])>(b[1]-a[1])*(point[0]-a[0]))break;
        edge.pop();
      }
      edge.push(point);
    }
    edge.pop();
    return edge;
  }
  const lower=half(points);
  return lower.concat(half(points.reverse()));
}

// Cache the expensive Roche solve independently of the camera and orbital phase.
const tidalCache=new Map();
export function tidalSurfaceModel(p,detail='preview') {
  if(!p.distortion)return null;
  const q=p.mass_ratio,e=p.eccentricity;
  const resolved=detail==='high'?'high':'preview',directions=resolved==='high'?highSurfaceDirections:surfaceDirections;
  const key=[resolved,q,e,p.radius_primary,p.radius_secondary].join('/');
  if(!tidalCache.has(key)){
    const radii=[tidalRadii(q,p.radius_primary,e,directions),tidalRadii(1/q,p.radius_secondary,e,directions)];
    tidalCache.set(key,radii.every(Boolean)?{
      detail:resolved,directions,radii,extents:radii.map(samples=>Math.max(...samples.flat()))
    }:null);
  }
  return tidalCache.get(key);
}

// Return a silhouette relative to the center of a star, in semimajor-axis units.
// The local x direction points to its companion; rotate the 3-D lobe before
// projecting. Above the orbit the sky axes rotate 180° to put Earth below.
export function tidalOutline(samples,p,pos,star,view,directions=surfaceDirections) {
  const e=p.eccentricity,ci=Math.cos(p.inclination*pi/180),si=Math.sin(p.inclination*pi/180);
  const bin=e?Math.max(0,Math.min(samples.length-1,(pos.separation-1+e)*(samples.length-1)/(2*e))):0;
  const lo=Math.floor(bin),hi=Math.ceil(bin),t=bin-lo,sign=star===0?1:-1;
  return silhouette(directions.map(([u,v,z],i)=>{
    const size=(1-t)*samples[lo][i]+t*samples[hi][i];
    const across=sign*(u*pos.cosLongitude-v*pos.sinLongitude);
    const along=sign*(u*pos.sinLongitude+v*pos.cosLongitude);
    if(view && typeof view.project==='function'){
      const projected=view.project([size*across,size*along,size*z]);
      return projected.slice(0,2);
    }
    return view==='above'?[-size*across,size*along]:[size*across,size*(-along*ci+z*si)];
  }));
}

function makeOrbitPainter(canvas,p) {
  const w=canvas.clientWidth,h=canvas.clientHeight,dpr=Math.min(devicePixelRatio||1,2);
  canvas.width=Math.round(w*dpr); canvas.height=Math.round(h*dpr);
  const ctx=canvas.getContext('2d');
  ctx.scale(dpr,dpr);
  const position=skyOrbit(p), q=p.mass_ratio;
  const stars=[
    {factor:-q/(1+q),radius:p.radius_primary,colors:['#fff1bd','#e5b26d','#9b632e']},
    {factor:1/(1+q),radius:p.radius_secondary,colors:['#eeeaff','#a599e7','#71619c']}
  ];
  const surface=tidalSurfaceModel(p);
  canvas.title=p.distortion && !surface?'Detached Roche surface unavailable · showing disk radii':
    'Sky view of the selected '+(surface?'Roche surfaces':'orbit')+' · accelerated playback';
  stars.forEach((star,k)=>{star.extent=surface?.extents[k]??star.radius;});
  const sample=Array.from({length:96},(_,i)=>position(i/96));
  let maxX=0,maxY=0;
  for(const star of stars)for(const pos of sample){
    maxX=Math.max(maxX,Math.abs(pos.x*star.factor)+star.extent);
    maxY=Math.max(maxY,Math.abs(pos.y*star.factor)+star.extent);
  }
  const scale=Math.min((w-4)/(2*maxX),(h-4)/(2*maxY));
  const paths=stars.map(star=>{
    const path=new Path2D();
    sample.forEach(({x,y},i)=>{
      const px=w/2+x*star.factor*scale, py=h/2+y*star.factor*scale;
      if(i===0)path.moveTo(px,py);else path.lineTo(px,py);
    });
    path.closePath();
    return path;
  });
  function drawStar(star,pos){
    const x=w/2+pos.x*star.factor*scale, y=h/2+pos.y*star.factor*scale, r=star.radius*scale;
    const fill=ctx.createRadialGradient(x-.3*r,y-.35*r,0,x,y,r);
    star.colors.forEach((color,i)=>fill.addColorStop(i/2,color));
    ctx.fillStyle=fill;ctx.beginPath();
    if(surface){
      const k=star===stars[0]?0:1;
      tidalOutline(surface.radii[k],p,pos,k,'earth').forEach(([sx,sy],i)=>
        i?ctx.lineTo(x+sx*scale,y+sy*scale):ctx.moveTo(x+sx*scale,y+sy*scale));
      ctx.closePath();
    }else ctx.arc(x,y,r,0,2*pi);
    ctx.fill();
  }
  return phase=>{
    ctx.clearRect(0,0,w,h);
    ctx.lineWidth=.75;ctx.strokeStyle='#c6bdd8';
    for(const path of paths)ctx.stroke(path);
    const pos=position(phase),front=pos.secondaryInFront?1:0;
    drawStar(stars[1-front],pos);drawStar(stars[front],pos);
  };
}

export function bindSolveOrbit(canvas) {
  const motion=matchMedia('(prefers-reduced-motion: reduce)');
  let frame=0,paint=null,key='',start=0;
  function draw(now){
    frame=0;
    if(!paint)return;
    // A four-second orbit preserves Keplerian timing within each revolution.
    paint(motion.matches ? .25 : ((now-start)%4000)/4000);
    if(!motion.matches)frame=requestAnimationFrame(draw);
  }
  motion.addEventListener('change',()=>{cancelAnimationFrame(frame);draw(performance.now());});
  return (busy,p)=>{
    if(!busy){
      cancelAnimationFrame(frame);frame=0;paint=null;return;
    }
    const next=[p.inclination,p.eccentricity,p.omega,p.mass_ratio,p.radius_primary,p.radius_secondary,p.distortion,devicePixelRatio].join('/');
    if(!paint || next!==key){
      if(!paint)start=performance.now();
      key=next;paint=makeOrbitPainter(canvas,p);
    }
    if(!frame)draw(performance.now());
  };
}
