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

function rocheProfile(q,d,radius) {
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
  return Array.from({length:145},(_,i)=>{
    const theta=2*pi*i/144,x=Math.cos(theta),z=Math.sin(theta);
    const r=surfaceRadius((lo+hi)/2,x,z);
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
    const key=[p.distortion,p.eccentricity,p.mass_ratio,p.radius_primary,p.radius_secondary].join('/');
    if(key!==lastKey){
      lastKey=key;shape=detachedShape(p);
      caption.textContent=shape?(p.distortion?'Roche surfaces':'Spheres')+(p.eccentricity?' · side view at periastron':' · side view'):'Detached surface reaches its Roche limit';
      canvas.setAttribute('aria-label',caption.textContent);
    }else return;
    paintShape(canvas,shape);
  }
  new ResizeObserver(()=>paintShape(canvas,shape)).observe(canvas);
  return draw;
}
