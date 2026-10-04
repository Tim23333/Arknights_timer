"""Actual original50000 source-mode transition and retained projectile scope."""
import json,sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_behavior_restart_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter08_behavior_restart.build_talula_burn_v4 import OUT,build,sha
from tools.chapter08_boss.talula_skill_policies_v3 import providers

def package(cross=10):
    p=json.loads(OUT.read_bytes());p['entities'].append({'id':'unit/restart/source/player','kind':'entity','tags':['player'],'components':{
        'attributes':{'base':{'max_hp':10000,'atk':0,'def':137,'mres':27}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},
        'spatial':{},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1}}})
    p['selectors'].append({'id':'selector/restart/source/boss','kind':'selector','region':{'type':'all'},'filters':[{'tag':'boss'}]})
    p['scenarioDraft']={'id':'scene/restart/source','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':5},'initialEntities':[
        {'definition':p['entities'][0]['id'],'instanceAlias':'boss','position':{'row':1,'col':1}},
        {'definition':'unit/restart/source/player','instanceAlias':'target','position':{'row':1,'col':2}}],
        'scheduledEffects':[{'at':cross,'effect':{'op':'modify_resource','resource':'hp','value':25000,'selector':'selector/restart/source/boss'}}]};return p

def proof(p,tmp_path,split,end):
    reg=providers();program=Compiler(providers=reg).compile(p);s=Engine.create(program,providers=reg);s.advance(split)
    cp=tmp_path/'actual.cp.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h),providers=reg);s.advance(end-split);r.advance(end-split);head=replay(program,s.export_replay(),providers=reg)
    assert s.snapshot()==r.snapshot()==head.snapshot() and list(s.session.events)==list(r.session.events)==list(head.session.events);return s

def test_source_rebuild_actual50000HP_4skills_and_restartflags():
    assert json.loads(OUT.read_bytes())==build()

def test_prelaunch_mode_cross10_cancelsold30_and_resets7_15skills(tmp_path):
    s=proof(package(),tmp_path,5,80);old='ability/ch8/talula/0/attack'
    assert not [e for e in s.session.events if e['type']=='projectile.launched' and e['payload']['ability']==old]
    assert [(e['time'],e['payload']['ability']) for e in s.session.events if e['type']=='ability.interrupted']==[(10,old)]
    assert s.ctx.get('boss',('behavior','state'))=='half' and s.ctx.resources.current('boss','mode')==1
    assert s.ctx.get('boss',('runtime','cooldowns','ability/ch8/talula/1/dragon_fire'))==220
    assert s.ctx.get('boss',('runtime','cooldowns','ability/ch8/talula/1/dance_fire'))==460
    assert [e['time'] for e in s.session.events if e['type']=='projectile.launched']==[40]

def test_alreadylaunch30_cross31_retainsold_hit33_then_new_mode(tmp_path):
    s=proof(package(31),tmp_path,30,90);h=[e for e in s.session.events if e['type']=='damage.accepted']
    assert h[0]['time']==33 and h[0]['payload']['ability']=='ability/ch8/talula/0/attack'
    assert h[0]['payload']['amount']==pytest.approx(1500*.4000000059604645*.73)
    assert [e['time'] for e in s.session.events if e['type']=='behavior.restarted']==[31]
    assert not s.ctx.behavior._restart_busy

def test_threshold_callback_fault_rolls_back_whole_restart():
    p=package();p['scenarioDraft']['scheduledEffects']=[];p['behaviors'][0]['states']['half']['on_enter'].append({'op':'modify_resource','resource':'missing','delta':1})
    reg=providers();s=Engine.create(Compiler(providers=reg).compile(p),providers=reg);s.advance(5);before=s.checkpoint()
    effect=p['behaviors'][0]['states']['half_restart']['on_enter'][0]
    with pytest.raises(ValueError):s.ctx.effects.execute('boss',['boss'],effect)
    assert s.checkpoint()==before and not s.ctx.behavior._restart_busy
