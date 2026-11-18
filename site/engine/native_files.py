"""Native PHOEBE documents held separately from the interactive light-curve model."""
import ast
import json
import math
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import numpy as np
import phoebe
from phoebe.constraints import builtin
from phoebe.parameters import ParameterSet
import model
import advanced

# Accept ordinary PHOEBE parameter records. Job and distribution objects can
# contain external executables or serialized Python callables.
DATA_CLASSES = set('BoolParameter ChoiceParameter ConstraintParameter DictParameter FloatArrayParameter FloatParameter HierarchyParameter IntParameter IntArrayParameter SelectParameter SelectTwigParameter StringParameter TwigParameter UnitParameter ArrayParameter'.split())
MATH = set('sin cos tan arcsin arccos arctan arctan2 sqrt abs log10 exp log'.split())
MATH.update(k for k,v in vars(builtin).items() if not k.startswith('_') and getattr(v,'__module__',None)==builtin.__name__)
NODES = (ast.Expression,ast.BinOp,ast.UnaryOp,ast.Call,ast.Name,ast.Load,ast.Constant,
         ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Pow,ast.USub,ast.UAdd,ast.Mod)
FIELDS = {'period':'d','incl':'deg','ecc':'','per0':'deg'}


def records(text):
    try:
        rows=json.loads(text)
    except (TypeError,ValueError) as exc:
        raise ValueError('Choose a PHOEBE 2.x JSON bundle or saved model ParameterSet.') from exc
    if not isinstance(rows,list) or not rows or any(not isinstance(r,dict) for r in rows):
        raise ValueError('Expected an array of PHOEBE 2.x parameter records.')
    for r in rows:
        cls=r.get('Class')
        if cls=='DistributionParameter':
            value=r.get('value')
            if not isinstance(value,dict) or value.get('distl') not in ('Uniform','Gaussian','Delta'):
                raise ValueError('This file contains an unsupported distribution type.')
            allowed={'distl','distl.version','uniqueid','unit','label','label_latex','wrap_at','loc','scale','low','high','value'}
            if set(value)-allowed or any(not isinstance(v,(type(None),str,float,int)) for v in value.values()):
                raise ValueError('Expected a scalar PHOEBE distribution.')
            continue
        if cls not in DATA_CLASSES:
            raise ValueError(f'This browser cannot load the native parameter class {cls}.')
        if cls=='ConstraintParameter':
            expr=re.sub(r'\{[A-Za-z0-9_:@.\-]+\}','param',r['value'])
            tree=ast.parse(expr,mode='eval')
            for node in ast.walk(tree):
                if (not isinstance(node,NODES)
                    or isinstance(node,ast.Name) and node.id not in MATH|{'param','pi'}
                    or isinstance(node,ast.Call) and (not isinstance(node.func,ast.Name) or node.func.id not in MATH)
                    or isinstance(node,ast.Constant) and type(node.value) not in (float,int)):
                    raise ValueError('This constraint uses an expression outside the browser’s supported PHOEBE math.')
    return rows


def construct(rows):
    contexts={r.get('context') for r in rows}
    if contexts=={'model'}:
        labels={r.get('model') for r in rows}
        if len(labels)!=1 or None in labels:raise ValueError('Expected a single named native model.')
        return None,ParameterSet.open(rows)
    if {'system','component'}<=contexts and any(r.get('qualifier')=='phoebe_version' for r in rows):
        return phoebe.open(rows),None
    raise ValueError('Expected a native PHOEBE bundle or a model-only ParameterSet.')


def serialize(obj):
    with TemporaryDirectory() as d:
        target=Path(d)/'file.json'
        obj.save(str(target),compact=True,incl_uniqueid=isinstance(obj,phoebe.Bundle))
        return target.read_text()


def fresh_label(existing):
    name='lab_native'
    index=1
    while name in existing:
        index+=1
        name=f'lab_native{index}'
    return name


def from_lab(payload):
    p=model.parameters(payload['parameters'])
    quality=payload['quality']
    data=payload['dataset']
    # Compute in the dedicated file worker. The geometry cache in the slider
    # worker may represent an earlier request, so it is never used for export.
    grid=payload.get('phases')
    phases,normalized=model._raw_model(p,quality,phases=None if grid is None else np.asarray(grid,float))
    b=phoebe.open(json.loads(serialize(model._bundle)))
    ds='observed_lc'
    physical=np.asarray(b.get_value('fluxes',dataset=ds,model='ui_model'))
    comp=model._comparison(phases,normalized,data,p)
    scale=np.median(physical)/comp['normalization']
    x=np.asarray(data['x'],float)
    y=np.asarray(data['y'],float)
    sig=None if data.get('sigma') is None else np.asarray(data['sigma'],float)
    if data['y_kind']=='magnitude':
        y=10**(-.4*(y-np.median(y)))
        if sig is not None:sig=.4*np.log(10)*y*sig
    unit_scale=scale/np.median(y)
    b.remove_model('ui_model')
    b.set_value('t0_supconj',component='binary',context='component',value=p['epoch'])
    times=x if data['x_kind']=='time' else p['epoch']+p['period']*x
    for qualifier,val in [('times',times),('fluxes',y*unit_scale),('sigmas',[] if sig is None else sig*unit_scale)]:
        b.set_value(qualifier,dataset=ds,context='dataset',value=val)
    # Preserve the UI phase grid after shifting from the lab's folding epoch.
    b.set_value('compute_phases',dataset=ds,context='dataset',value=phases)
    b.run_compute(model='ui_model',progressbar=False,use_server='none')
    return b


class Workspace:
    def __init__(self):
        self.bundle=None
        self.standalone=None

    def metadata(self):
        b=self.bundle
        if b is None:
            return dict(kind='model',models=list(self.standalone.models),datasets=list(self.standalone.datasets),
                        computes=[],orbits={},version=None)
        orbits={}
        for label in b.hierarchy.get_orbits():
            ops={}
            for k,unit in FIELDS.items():
                v=b.get_parameter(qualifier=k,component=label,context='component')
                ops[k]=dict(value=float(v.get_value(unit=unit)),editable=v.is_constraint is None)
            orbits[label]=ops
        computes=[c for c in b.computes if b.get_compute(compute=c).kind=='phoebe']
        return dict(kind='bundle',models=list(b.models),datasets=list(b.datasets),computes=computes,
                    orbits=orbits,stars=list(b.hierarchy.get_stars()),objects=advanced.kinds(),
                    rv=b.filter(context='dataset',kind='rv').datasets,lc=b.filter(context='dataset',kind='lc').datasets,solvers=list(b.solvers),solutions=list(b.solutions),version=str(b.get_value(qualifier='phoebe_version',check_default=False,check_visible=False)))

    def model(self,label):
        if self.bundle is not None:
            if label not in self.bundle.models:raise ValueError('Select a saved model.')
            return self.bundle.get_model(model=label)
        if self.standalone is None:raise ValueError('Open a model first.')
        return self.standalone

    def series(self,label):
        ps=self.model(label)
        items=[]
        for par in ps.to_list():
            if par.qualifier not in ('fluxes','rvs'):continue
            times=ps.filter(qualifier='times',dataset=par.dataset,component=par.component)
            if len(times)!=1:continue
            x=np.asarray(times.to_list()[0].get_value(unit='d'),float)
            y=np.asarray(par.get_value(),float)
            if x.ndim!=1 or y.shape!=x.shape or not len(x):continue
            valid=np.isfinite(x)&np.isfinite(y)
            if not np.any(valid):continue
            order=np.argsort(x[valid],kind='stable')
            items.append(dict(label=' · '.join(v for v in [par.dataset,par.component,par.qualifier] if v),
                         times=x[valid][order].tolist(),values=y[valid][order].tolist(),unit=str(par.default_unit)))
        return items

    def act(self,op,p):
        if op=='open':
            b,ps=construct(records(p['text']))
            current=Workspace()
            current.bundle,current.standalone=b,ps
            meta=current.metadata()
            self.bundle,self.standalone=b,ps
            return meta
        if op=='lab':
            b=from_lab(p)
            self.bundle,self.standalone=b,None
            return self.metadata()
        if op=='new':
            templates={'Detached':{},'Contact':{'contact_binary':True},'Semi-detached primary':{'semidetached':'primary'},
                       'Semi-detached secondary':{'semidetached':'secondary'}}
            b=phoebe.default_binary(**templates[p['template']])
            b.add_dataset('lc',compute_phases=np.linspace(-.5,.5,65),passband='Johnson:V')
            self.bundle,self.standalone=b,None
            return self.metadata()
        if op=='series':return self.series(p['label'])
        if op=='save_model':return serialize(self.model(p['label']))
        if self.bundle is None:raise ValueError('Open a PHOEBE bundle first.')
        if op=='catalog':return advanced.catalog(self.bundle)
        if op=='field':return advanced.field(advanced.parameter(self.bundle,p['id']))
        if op=='checks':return str(self.bundle.run_checks())
        if op in ('set_field','flip','distribution','add','solve','adopt'):
            candidate=phoebe.open(json.loads(serialize(self.bundle)))
            advanced.change(candidate,op,p)
            self.bundle=candidate
            return self.metadata()
        if op=='save_bundle':return serialize(self.bundle)
        if op in ('compute','attach'):
            # Work on a private copy. Failure leaves the open file intact.
            candidate=phoebe.open(json.loads(serialize(self.bundle)))
            if op=='compute':
                if p['compute'] not in self.metadata()['computes']:raise ValueError('Choose a native PHOEBE compute set.')
                edits=p.get('edits',{})
                if not set(edits)<=FIELDS.keys():raise ValueError('Unknown orbital parameter.')
                for key,value in edits.items():
                    if not math.isfinite(value):raise ValueError('Orbital values must be finite.')
                    candidate.set_value(qualifier=key,context='component',component=p['orbit'],unit=FIELDS[key],value=value)
                label=fresh_label(candidate.models)
                candidate.run_compute(compute=p['compute'],model=label,use_server='none',progressbar=False)
            else:
                rows=records(p['text'])
                b,ps=construct(rows)
                if b is not None:raise ValueError('Attach a model-only ParameterSet.')
                if not set(ps.datasets)<=set(candidate.datasets):raise ValueError('The model references a dataset missing from this bundle.')
                if not set(ps.components)<=set(candidate.components):raise ValueError('The model references a component missing from this bundle.')
                label=ps.model if ps.model not in candidate.models else fresh_label(candidate.models)
                # Standalone model parameters receive fresh IDs when attached.
                candidate.import_model([{k:v for k,v in r.items() if k!='uniqueid'} for r in rows],model=label)
            self.bundle=candidate
            return dict(self.metadata(),selected=label)
        raise ValueError('Unknown native file operation.')


workspace=Workspace()
