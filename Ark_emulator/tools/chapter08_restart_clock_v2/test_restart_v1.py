"""Generic opt-in restart ownership, callbacks, atomicity and durable replay."""
import sys,json
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_behavior_restart_clock_v2_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound

def effect():
    return {'op':'restart_behavior','target':'self','state':'half','parameters':{'abilities':['ability/old','ability/new'],
        'reset_attack_clock':True,'initial_cooldowns':{'ability/new':1},'reason':'source_restart'}}

def package():
    p={'schemaVersion':2,'manifest':{'id':'package/restart/author','requires':['preset/ark_standard']},
        'entities':[{'id':'unit/boss','kind':'entity','tags':['enemy'],'components':{'attributes':{'base':{'max_hp':1000,'atk':100,'def':10,'mres':0}},
            'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'},'mode':{'initial':0,'capacity':1}},'spatial':{},
            'abilities':['ability/old','ability/new'],'behavior':{'machine':'behavior/boss'},'lifecycle':{'policy':'policy/ark_lifecycle'}}},
            {'id':'unit/target','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':1000,'def':37,'mres':27}},
                'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'}},'spatial':{}}}],
        'abilities':[{'id':'ability/old','kind':'ability','selector':'selector/player','activation':{'mode':'manual'},'duration_seconds':1,
            'timeline':[{'at':20,'effect':{'op':'damage','damage_type':'physical','scale':1}}]},
            {'id':'ability/new','kind':'ability','selector':'selector/player','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]}],
        'selectors':[{'id':'selector/player','kind':'selector','region':{'type':'all'},'filters':[{'tag':'player'}]},
            {'id':'selector/boss','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}]}],
        'behaviors':[{'id':'behavior/boss','kind':'behavior','initial':'normal','states':{'normal':{},'half':{'on_enter':[{'op':'modify_resource','target':'self','resource':'mode','value':1}]}},'transitions':[]}],
        'scenarioDraft':{'id':'scene/restart','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':3},'initialEntities':[
            {'definition':'unit/boss','instanceAlias':'boss','position':{'row':0,'col':0}},
            {'definition':'unit/target','instanceAlias':'target','position':{'row':0,'col':1}}],
            'scheduledEffects':[{'at':10,'effect':{**effect(),'target':'selected','selector':'selector/boss'}}]}}
    return p

def hits(s):return [e for e in s.session.events if e['type']=='damage.accepted']

def test_real_cancel_and_new_clock_at40_CP_head(tmp_path):
    program=Compiler().compile(package());s=Engine.create(program)
    s.submit({'action':'skill','source':'boss','ability':'ability/old'},at=0)
    s.submit({'action':'skill','source':'boss','ability':'ability/new'},at=39)
    s.submit({'action':'skill','source':'boss','ability':'ability/new'},at=40)
    s.advance(5);cp=tmp_path/'actual.cp.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h))
    s.advance(40);r.advance(40);head=replay(program,s.export_replay())
    assert s.snapshot()==r.snapshot()==head.snapshot() and list(s.session.events)==list(r.session.events)==list(head.session.events)
    assert [(e['time'],e['payload']['amount']) for e in hits(s)]==[(40,100)]
    assert [e['time'] for e in s.session.events if e['type']=='ability.interrupted']==[10]
    assert s.ctx.resources.current('boss','mode')==1 and s.ctx.get('boss',('behavior','state'))=='half'
    assert [e['time'] for e in s.session.events if e['type']=='command.rejected']==[39]

def test_callback_late_failure_rolls_back_cancel_RNG_world_events_jobs():
    p=package();p['scenarioDraft']['scheduledEffects']=[]
    p['behaviors'][0]['states']['half']['on_enter']+=[{'op':'random','stream':'restart','probability':1,'effects':[{'op':'emit','event':'restart.drawn'}]},
        {'op':'modify_resource','resource':'missing','delta':1}]
    s=Engine.create(Compiler().compile(p));s.submit({'action':'skill','source':'boss','ability':'ability/old'},at=0);s.advance(5)
    before=s.checkpoint()
    with pytest.raises(ValueError):s.ctx.effects.execute('boss',['boss'],effect())
    assert s.checkpoint()==before and s.ctx.behavior._restart_busy==set()
    with pytest.raises(ValueError):s.ctx.effects.execute('boss',['boss'],effect())
    assert s.checkpoint()==before and s.ctx.behavior._restart_busy==set()

def test_source_owned_buff_release_late_failure_rollback():
    p=package();p['scenarioDraft']['scheduledEffects']=[];p['buffs']=[{'id':'buff/owned','kind':'buff','on_remove':[{'op':'modify_resource','resource':'missing','delta':1}]}]
    p['abilities'][0]['activation']['on_start']=[{'op':'apply_buff','target':'self','buff':'buff/owned','bind_to_cast':True}]
    s=Engine.create(Compiler().compile(p));s.submit({'action':'skill','source':'boss','ability':'ability/old'},at=0);s.advance(5);before=s.checkpoint()
    with pytest.raises(ValueError):s.ctx.effects.execute('boss',['boss'],effect())
    assert s.checkpoint()==before and s.ctx.behavior._restart_busy==set()

def test_on_exit_retire_stops_enter_and_clock_assignment():
    p=package();p['scenarioDraft']['scheduledEffects']=[];p['behaviors'][0]['states']['normal']['on_exit']=[{'op':'retire','target':'self','parameters':{'reason':'withdrawn'}}]
    s=Engine.create(Compiler().compile(p));s.advance(5);s.ctx.effects.execute('boss',['boss'],effect())
    assert not s.ctx.active('boss') and s.ctx.resources.current('boss','mode')==0
    assert s.ctx.get('boss',('behavior','state'))=='normal' and s.ctx.get('boss',('runtime','cooldowns'),{}).get('ability/new') is None
    assert not any(e['type']=='behavior.restarted' for e in s.session.events)

def test_nested_same_actor_restart_rejected_and_private_guard_cleared():
    p=package();p['scenarioDraft']['scheduledEffects']=[];p['behaviors'][0]['states']['half']['on_enter'].append(effect())
    s=Engine.create(Compiler().compile(p));before=s.checkpoint()
    with pytest.raises(ValueError,match='Recursive restart'):s.ctx.effects.execute('boss',['boss'],effect())
    assert s.checkpoint()==before and s.ctx.behavior._restart_busy==set()

@pytest.mark.parametrize('change',[lambda e:e['parameters'].update(reset_attack_clock=1),lambda e:e['parameters'].update(abilities=[]),
    lambda e:e['parameters'].update(abilities=['ability/old','ability/old']),lambda e:e['parameters'].update(initial_cooldowns={'ability/new':True}),
    lambda e:e['parameters'].update(initial_cooldowns={'ability/foreign':0}),lambda e:e['parameters'].update(reason=''),
    lambda e:e['parameters'].update(foo=1)])
def test_strict_malformed_compile_and_runtime_atomic(change):
    p=package();e=p['scenarioDraft']['scheduledEffects'][0]['effect'];change(e)
    with pytest.raises(ValueError):Compiler().compile(p)
    q=package();q['scenarioDraft']['scheduledEffects']=[];s=Engine.create(Compiler().compile(q));before=s.checkpoint()
    with pytest.raises(ValueError):s.ctx.effects.execute('boss',['boss'],e)
    assert s.checkpoint()==before

def test_foreign_declared_ability_closure_resolves_but_actual_target_rejects():
    p=package();p['scenarioDraft']['scheduledEffects']=[];p['abilities'].append({'id':'ability/foreign','kind':'ability','activation':{'mode':'manual'},'timeline':[]})
    p['entities'][0]['dependencies']=['ability/foreign'];s=Engine.create(Compiler().compile(p));e=effect();e['parameters']['abilities'].append('ability/foreign');before=s.checkpoint()
    with pytest.raises(ValueError,match='actually possessed'):s.ctx.effects.execute('boss',['boss'],e)
    assert s.checkpoint()==before

def test_nooption_transition_preserves_ongoing_cast():
    p=package();p['scenarioDraft']['scheduledEffects'][0]['effect']={'op':'transition','selector':'selector/boss','state':'half'}
    s=Engine.create(Compiler().compile(p));s.submit({'action':'skill','source':'boss','ability':'ability/old'},at=0);s.advance(25)
    assert [(e['time'],e['payload']['amount']) for e in hits(s)]==[(20,63)]
    assert not any(e['type']=='behavior.restarted' for e in s.session.events)
