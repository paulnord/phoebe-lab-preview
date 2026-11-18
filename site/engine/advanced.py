"""Inspect the live bundle and apply typed edits with PHOEBE's native setters."""
import json
import numpy as np
import phoebe


TYPES = {'FloatParameter':'number', 'IntParameter':'integer', 'BoolParameter':'boolean',
         'ChoiceParameter':'choice', 'SelectParameter':'selection', 'FloatArrayParameter':'array',
         'IntArrayParameter':'array', 'StringParameter':'text', 'SelectTwigParameter':'selection', 'UnitParameter':'choice'}
EDIT_CONTEXTS = {'system','component','dataset','compute','feature','solver','solution','figure'}
LOCAL_SOLVERS = phoebe.list_available_solvers()
LOCAL_FEATURES = ['spot','rv_offset','gp_sklearn']


def catalog(bundle):
    params = bundle.filter(check_advanced=False, check_visible=True, check_default=True).to_list()
    return [dict(id=p.uniqueid, name=p.qualifier, twig=p.twig, context=p.context) for p in params]


def parameter(bundle, uid):
    return bundle.get_parameter(uniqueid=uid, check_advanced=False, check_visible=True, check_default=True)


def field(p):
    kind = TYPES.get(type(p).__name__, 'view')
    writable = (kind != 'view' and p.context in EDIT_CONTEXTS and not p.readonly
                and p.is_constraint is None and p.qualifier not in ('use_server','progress_every_niters'))
    unit = str(getattr(p,'default_unit',''))
    choices = [str(c) for c in getattr(p,'choices',[])]
    if p.qualifier=='passband':
        choices = sorted(set(choices).intersection(phoebe.list_installed_passbands()))
    if p.qualifier=='ebai_method':
        choices = [c for c in choices if c=='mlp']
    # Keep sets of fitted twigs as PHOEBE choices. Expressions and job objects are read-only.
    value = p.get_value()
    if kind == 'view' or type(p).__name__=='UnitParameter':
        value = str(value)
    elif isinstance(value,np.ndarray):
        value = value.tolist()
    elif isinstance(value,np.generic):
        value = value.item()
    bounds = [None if v is None else float(v.to_value(p.default_unit)) if hasattr(v,'to_value') else float(v)
              for v in getattr(p,'limits',[]) or []]
    # Some PHOEBE model and solution outputs contain NaN or infinity.
    try:
        json.dumps(value, allow_nan=False)
    except (ValueError, TypeError):
        value = str(value)
        writable = False
    constraint = p.is_constraint
    flip = []
    if constraint is not None:
        candidates = constraint.vars.to_list() + constraint.addl_vars.to_list()
        flip = sorted({v.twig for v in candidates if v.uniqueid!=p.uniqueid and v.is_constraint is None})
    return dict(kind=kind,value=value,editable=writable,description=p.description or '',unit=unit,
                limits=bounds,choices=choices,flip=flip,constrained=constraint is not None)


def set_field(b,uid,value):
    p = parameter(b,uid)
    f = field(p)
    if not f['editable']:
        raise ValueError('This parameter is derived or read-only.')
    kind = f['kind']
    if kind in ('number','integer'):
        if type(value) not in (int,float) or not np.isfinite(value) or (kind=='integer' and int(value)!=value):
            raise ValueError('Enter a finite value in the displayed unit.')
    elif kind=='boolean' and type(value) is not bool:
        raise ValueError('Choose true or false.')
    elif kind=='choice' and value not in f['choices']:
        raise ValueError('Choose one of the available values.')
    elif kind=='selection' and (not isinstance(value,list) or not all(isinstance(v,str) and v in f['choices'] for v in value)):
        raise ValueError('Choose values from the parameter choices.')
    elif kind=='text' and not isinstance(value,str):
        raise ValueError('Enter a text value.')
    elif kind=='array':
        if not isinstance(value,list):
            raise ValueError('Enter a JSON array of numbers.')
        a=np.asarray(value)
        if a.dtype.kind not in 'iuf' or not np.isfinite(a).all():
            raise ValueError('Array values must be finite numbers.')
        if type(p).__name__=='IntArrayParameter' and np.any(a!=np.floor(a)):
            raise ValueError('Enter whole numbers for this array.')
    p.set_value(value)


def kinds():
    return {'dataset':phoebe.list_available_datasets(),'feature':LOCAL_FEATURES,
            'compute':['phoebe'],'solver':LOCAL_SOLVERS}


def change(b,op,data):
    if op=='set_field':
        set_field(b,data['id'],data['value'])
    elif op=='flip':
        p=parameter(b,data['id'])
        if data['target'] not in field(p)['flip']:
            raise ValueError('Choose a free parameter in this constraint.')
        b.flip_constraint(p.is_constraint.twig,solve_for=data['target'])
    elif op=='distribution':
        p=parameter(b,data['id'])
        if not field(p)['editable'] or type(p).__name__!='FloatParameter':
            raise ValueError('Choose a free scalar parameter.')
        a,c=data['a'],data['b']
        if not all(type(v) in (int,float) and np.isfinite(v) for v in (a,c)):
            raise ValueError('Enter two finite distribution parameters.')
        if data['family']=='Gaussian' and c>0:
            dist=phoebe.gaussian(a,c)
        elif data['family']=='Uniform' and c>a:
            dist=phoebe.uniform(a,c)
        else:
            raise ValueError('Uniform requires low < high; Gaussian requires a positive standard deviation.')
        b.add_distribution(p.twig,dist,distribution=data['label'])
    elif op=='add':
        category,kind=data['category'],data['kind']
        if kind not in kinds().get(category,[]):
            raise ValueError('This type is unavailable in the local browser engine.')
        if category=='dataset':
            b.add_dataset(kind,compute_times=np.linspace(0,1,33))
        elif category=='feature':
            if kind=='spot':
                if data['component'] not in b.hierarchy.get_stars():
                    raise ValueError('Choose a star for this spot.')
                b.add_feature(kind,component=data['component'])
            elif kind=='gp_sklearn':
                b.add_feature(kind,dataset=data['dataset'])
            else:
                if data['dataset'] not in b.filter(context='dataset',kind='rv').datasets:
                    raise ValueError('Add a radial-velocity dataset first.')
                b.add_feature(kind,dataset=data['dataset'])
        elif category=='compute':
            b.add_compute(kind)
        elif category=='solver':
            b.add_solver(kind,**({'ebai_method':'mlp'} if kind=='estimator.ebai' else {}))
    elif op=='solve':
        label=data['solver']
        if label not in b.solvers or b.get_solver(solver=label).kind not in [x.split('.')[-1] for x in LOCAL_SOLVERS]+LOCAL_SOLVERS:
            raise ValueError('Choose an available local solver.')
        index=1
        while f'local_solution{index:02d}' in b.solutions:
            index+=1
        b.run_solver(solver=label,solution=f'local_solution{index:02d}',use_server='none',progressbar=False)
    elif op=='adopt':
        if data['solution'] not in b.solutions:
            raise ValueError('Choose an existing solution.')
        b.adopt_solution(solution=data['solution'])
    else:
        raise ValueError('Unknown parameter operation.')
