"""Owned lifetime/cast cleanup and control retirement context boundaries."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools.experiments.m15_peer import verify as h


def owned_cleanup():
    p=h.generic_data();p['scenarioDraft']['initialEntities']=[]
    p['entities'] += [{'id':'unit/owner','kind':'entity','tags':['ally'],'components':{'attributes':{'base':{'max_hp':20}},'resources':{'hp':{'initial':20,'capacity':20,'role':'health'}},'spatial':{},'abilities':['ability/summon','ability/remove_owner']}},
        {'id':'unit/child','kind':'entity','tags':['ally'],'components':{'attributes':{'base':{'max_hp':30}},'resources':{'hp':{'initial':30,'capacity':30,'role':'health'}},'spatial':{},'abilities':['ability/long_child']}}]
    p['abilities'] += [{'id':'ability/summon','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'spawn','definition':'unit/child','owner':'source','position':{'row':0,'col':1},'lifetime_seconds':5,'parameters':{'on_owner_retire':'remove'}}]},'timeline':[]},
        {'id':'ability/remove_owner','kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':h.retire('removed')}]},
        {'id':'ability/long_child','kind':'ability','activation':{'mode':'manual'},'duration_seconds':2,'timeline':[{'at_seconds':1,'effect':{'op':'emit','event':'peer.child_should_not_fire'}}]}]
    p['scenarioDraft']['initialEntities']=[{'definition':'unit/owner','instanceAlias':'owner','position':{'row':0,'col':0}}]
    s=h.make(p);h.command(s,'owner','ability/summon',0);s.advance(1)
    owner=s.session.world.resolve('owner');children=[e['id'] for e in s.session.world.entities() if e['components'].get('ownership',{}).get('owner')==owner];assert len(children)==1
    child=children[0];h.command(s,child,'ability/long_child',1);h.command(s,'owner','ability/remove_owner',3);s.advance(160)
    assert not s.ctx.alive(owner) and not s.ctx.alive(child) and s.ctx.resources.current(owner,'hp')==20 and s.ctx.resources.current(child,'hp')==30
    assert not [e for e in s.session.events if e['type']=='peer.child_should_not_fire']
    assert not [t for t in s.session.scheduler.pending if t['kind'] in ('domain.lifecycle.expire','domain.ability.effect','domain.ability.finish')]
    return h.finish(s,{'owner_retire3_recursively_removes_child_preservesHP20_30':True,'child_windup_and_finish_and_lifetime_tasks_cancelled':True})


def rollback_restores_owned_cleanup():
    p=h.generic_data();s=h.make(p)
    owner=s.session.world.resolve('device')
    child=s.ctx.lifecycle.create('unit/no_policy',position={'row':0,'col':1},owner=owner,lifetime_seconds=2,on_owner_retire='remove')
    before=s.checkpoint()
    try:s.ctx.effects.execute(owner,[owner],{'op':'retire','target':'source','parameters':{'reason':'removed'},'effects':[{'op':'modify_resource','resource':'nonexistent','delta':1}]})
    except ValueError:pass
    else:raise AssertionError('expected failure after recursive cleanup')
    assert before==s.checkpoint() and s.ctx.alive(owner) and s.ctx.alive(child)
    return h.finish(s,{'failure_after_parent_and_child_retire_restores_lifetime_jobs_world_event_counters':True},False)


def control_explicit_selector_and_rejections():
    from ark_sim import Compiler
    errors=[]
    for target in ('source','selected','self'):
        p=h.generic_data();p['controls']=[{'id':'control/peer','kind':'control','clock_policy':'logical','ack_policy':'immediate','steps':[{'kind':'effects','effects':[h.retire('removed',target)]}]}]
        p['scenarioDraft']['timeline']={'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'fragments':[{'actions':[{'kind':'control','definition':'control/peer'}]}]}]}
        p['scenarioDraft'].pop('waves',None)
        try:Compiler().compile(p)
        except ValueError as error:errors.append({'target':target,'error':str(error)})
        else:raise AssertionError('ambiguous battle-source control retire compiled')
    p=h.generic_data();p['controls']=[{'id':'control/peer','kind':'control','clock_policy':'logical','ack_policy':'immediate',
        'steps':[{'kind':'effects','effects':[dict(h.retire('removed','selected'),selector='selector/plain')]}]}]
    p['scenarioDraft'].pop('waves',None);p['scenarioDraft']['timeline']={'policy':'managed_clear','negative_timeout_policy':'wait_for_clear',
        'waves':[{'fragments':[{'actions':[{'kind':'control','definition':'control/peer','instanceAlias':'retirer'}]}]}]}
    s=h.make(p);s.advance(3)
    assert not s.ctx.alive('plain') and s.ctx.resources.current('plain','hp')==80 and s.ctx.state()['kills']==0
    assert s.ctx.controls.instance('retirer')['status']=='completed' and s.ctx.alive('system/battle')
    return {'context_compile_rejections':errors,'selector_control_retire':h.finish(s,{'explicit_all_actor_selector_removes_only_actor_not_battle':True})}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runtime-root',type=Path,default=h.CANDIDATE);parser.add_argument('--digest',default=h.CORE);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    sys.path.insert(0,str(args.runtime_root.resolve()));import ark_sim
    from ark_sim.adapters.api import implementation_digest
    assert Path(ark_sim.__file__).resolve().parent==args.runtime_root.resolve()/'ark_sim' and implementation_digest()==args.digest
    files=[Path(__file__),Path(h.__file__),h.PACKAGE,h.SOURCE];before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files};cases=[]
    for name,fn in [('owned_cleanup',owned_cleanup),('rollback_owned_cleanup',rollback_restores_owned_cleanup),('control_context',control_explicit_selector_and_rejections)]:
        try:cases.append({'case':name,'result':'passed','actual':fn()})
        except Exception as error:cases.append({'case':name,'result':'failed','error':repr(error)})
    after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files};stable=before==after and implementation_digest()==args.digest;passed=stable and all(c['result']=='passed' for c in cases)
    value={'schema':'ark-sim/bounded-retire-peer-review/v1','passed':passed,'implementation_sha256':args.digest,'runtime_module':ark_sim.__file__,
        'identity_stable':stable,'source_at_start':before,'source_at_completion':after,'cases':cases,
        'tests':[{'path':str(Path(__file__).relative_to(ROOT)).replace('\\','/'),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'result':'passed' if passed else 'failed'}],
        'scope':'generic retirement ownership/tasks/atomicity/control source context; no wholeEMP/terrain approval','formal_approval':False,'review_receipt':False}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':passed,'cases':[(c['case'],c['result'],c.get('error')) for c in cases]}));return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
