"""Independent category mask and runtime/definition data-only filter matrix."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools.experiments.m15_peer import verify as h
from tools.experiments.m15_peer import retire_boundaries as r


def retain_selector(data,selector_id):
    aid='ability/anchor/'+selector_id.rsplit('/',1)[-1]
    data['entities'][0]['components']['abilities'].append(aid)
    data['abilities'].append({'id':aid,'kind':'ability','activation':{'mode':'manual'},'selector':selector_id,'timeline':[]})


def mask_matrix():
    data=h.scene(sp=5);base=next(e for e in data['entities'] if e['id']=='unit/peer_enemy')
    data['scenarioDraft']['initialEntities']=data['scenarioDraft']['initialEntities'][:1]
    values=[('missing','missing'),('default',1),('mixed',3),('trap',2),('other',4),('zero',0),('bool',True),('string','1'),('null',None)]
    for name,category in values:
        definition=deepcopy(base);definition['id']='unit/matrix_'+name
        if category!='missing':definition['metadata']={'native_category':category}
        data['entities'].append(definition);data['scenarioDraft']['initialEntities'].append({'definition':definition['id'],'instanceAlias':name,'position':{'row':4,'col':5}})
    s=h.make(data);h.command(s,'device','ability/chapter01_emp/burst',0);s.advance(24)
    hits=[e for e in s.session.events if e['type']=='damage.accepted'];wanted={s.session.world.resolve(x) for x in ('missing','default','mixed')}
    assert {e['payload']['target'] for e in hits}==wanted and len(hits)==3
    for name,category in values:assert s.ctx.resources.current(name,'hp')==(2200 if name in ('missing','default','mixed') else 3000)
    return h.finish(s,{'bits1_accepts1_3_and_explicitmissingDefault1':True,'2_4_0_bool_string_null_excluded':True})


def separate_scopes():
    data=h.generic_data();data['scenarioDraft']['initialEntities'][1]['components']={'resources':{'hp':{'initial':70}}}
    specs=[('runtime_current',{'scope':'runtime','path':['components','resources','hp','current'],'equals':70},True),
        ('definition_current_default',{'scope':'definition','path':['components','resources','hp','current'],'equals':91,'default':91},True),
        ('runtime_current_not_default',{'scope':'runtime','path':['components','resources','hp','current'],'equals':91,'default':91},False),
        ('definition_initial',{'scope':'definition','path':['components','resources','hp','initial'],'equals':80},True),
        ('runtime_initial_missing',{'scope':'runtime','path':['components','resources','hp','initial'],'equals':80},False)]
    for name,spec,_ in specs:
        data['selectors'].append({'id':'selector/'+name,'kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'},{'field':spec}],'limit':None});retain_selector(data,'selector/'+name)
    s=h.make(data);target=s.session.world.resolve('plain');before=s.checkpoint();out=[]
    for name,spec,wanted in specs:
        actual=s.ctx.spatial.select('device','selector/'+name);assert actual==([target] if wanted else []);out.append({'name':name,'selected':actual})
    # These are real read-only selector calculations; traces are observable,
    # so this API-level evidence is deliberately not command-replayed.
    assert s.ctx.resources.current('plain','hp')==70
    return {'expected':'runtime current70 vs definition initial80/missing-default91 are distinct; no world mutation','actual':out,'API_only':True}


def empty_cast_once():
    data=h.scene(sp=5);data['scenarioDraft']['initialEntities']=data['scenarioDraft']['initialEntities'][:1]
    s=h.make(data);h.command(s,'device','ability/chapter01_emp/burst',0);h.command(s,'device','ability/chapter01_emp/burst',46);s.advance(47)
    assert s.ctx.resources.current('system/battle','dp')==40 and s.ctx.resources.current('device','hp')==100 and not s.ctx.alive('device')
    assert not [e for e in s.session.events if e['type']=='damage.accepted']
    assert len([e for e in s.session.events if e['type']=='entity.died'])==1 and len([e for e in s.session.events if e['type']=='command.rejected'])==1
    return h.finish(s,{'root_allowNoTarget1_empty_cast_pays10dp_5sp_and_retires45_once':True,'recast_after_retire_rejected':True})


def data_only_and_bad_schema():
    from ark_sim import Compiler
    data=h.generic_data();entity=next(e for e in data['entities'] if e['id']=='unit/no_policy');entity['metadata']={'number':10}
    data['selectors'].append({'id':'selector/no_getattr','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'},
        {'field':{'scope':'definition','path':['metadata','number','real'],'equals':10}}],'limit':None})
    retain_selector(data,'selector/no_getattr')
    s=h.make(data);assert not s.ctx.spatial.select('device','selector/no_getattr') # int.real is not a data key
    class Poison:
        accessed=False
        @property
        def value(self):Poison.accessed=True;raise AssertionError('property getter was invoked')
    bad=deepcopy(data);next(e for e in bad['entities'] if e['id']=='unit/no_policy')['metadata']['poison']=Poison()
    try:Compiler().compile(bad)
    except (ValueError,TypeError):pass
    else:raise AssertionError('nonJSON metadata object admitted')
    assert not Poison.accessed
    variants=[{'path':[],'equals':1},{'path':['x',True],'equals':1},{'path':'metadata.x','equals':1},
        {'path':['x'],'equals':1,'bits_any':1},{'path':['x'],'bits_any':True},{'path':['x'],'bits_any':-1},
        {'scope':'python','path':['x'],'equals':1},{'path':['x'],'equals':1,'default':float('nan')}]
    errors=[]
    for spec in variants:
        p=deepcopy(data);p['selectors'][-1]['filters'][-1]={'field':spec}
        try:Compiler().compile(p)
        except (ValueError,TypeError) as error:errors.append(str(error))
        else:raise AssertionError('bad field specification compiled: '+repr(spec))
    return {'no_python_attribute_or_side_effect_getter':True,'bad_specs_rejected':errors,'API_compile_only':True}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runtime-root',type=Path,required=True);parser.add_argument('--digest',required=True);parser.add_argument('--package',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    sys.path.insert(0,str(args.runtime_root.resolve()));import ark_sim
    from ark_sim.adapters.api import implementation_digest
    assert Path(ark_sim.__file__).resolve().parent==args.runtime_root.resolve()/'ark_sim' and implementation_digest()==args.digest
    h.PACKAGE=args.package.resolve();files=[Path(__file__),Path(h.__file__),Path(r.__file__),h.PACKAGE,h.SOURCE];start={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    cases=[]
    functions={'mask_matrix':mask_matrix,'runtime_definition_scope':separate_scopes,'data_only_schema':data_only_and_bad_schema,'empty_cast':empty_cast_once,
        **{name:fn for name,fn in h.CASES.items()},'retire_owned_cleanup':r.owned_cleanup,'retire_owned_rollback':r.rollback_restores_owned_cleanup,'retire_control_context':r.control_explicit_selector_and_rejections}
    for name,fn in functions.items():
        try:cases.append({'case':name,'result':'passed','actual':fn()})
        except Exception as error:cases.append({'case':name,'result':'failed','error':repr(error)})
    end={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files};stable=start==end and implementation_digest()==args.digest;passed=stable and all(c['result']=='passed' for c in cases)
    value={'schema':'ark-sim/bounded-category-device-peer-review/v1','passed':passed,'implementation_sha256':args.digest,'input_package_sha256':hashlib.sha256(h.PACKAGE.read_bytes()).hexdigest(),'runtime_module':ark_sim.__file__,
        'source_at_start':start,'source_at_completion':end,'identity_stable':stable,'cases':cases,
        'tests':[{'path':str(Path(__file__).relative_to(ROOT)).replace('\\','/'),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'result':'passed' if passed else 'failed'}],
        'scope':'category data filter and prior EMP/retire slice only; no terrain/fulldevice approval','formal_approval':False,'review_receipt':False}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':passed,'cases':[(c['case'],c['result'],c.get('error')) for c in cases]}));return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
