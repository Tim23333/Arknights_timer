from pathlib import Path
from copy import deepcopy
import importlib.util
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.build_chapter04_bslime_model import build


def fixture():
    p=build();uid=p['entities'][0]['id']
    p['rules'].append({'id':'rule/restore','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'inputs.parameters.capacity * inputs.parameters.ratio'}})
    p['entities'][0]['components']['rebirth']={'resource':'hp','max_count':1,'delay_seconds':.1,'restore_ratio':1,'restore_rule':'rule/restore'}
    p['selectors'].append({'id':'selector/kill','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'limit':1})
    p['abilities'].extend([{'id':'ability/kill','kind':'ability','selector':'selector/kill','activation':{'mode':'manual'},'timeline':[{'at_seconds':0,'effect':{'op':'damage','damage_type':'true'}}]},
        {'id':'ability/instant','kind':'ability','selector':'selector/kill','activation':{'mode':'manual'},'timeline':[{'at_seconds':0,'effect':{'op':'instant_kill','parameters':{'cause':'test_source','skip_rebirth':True}}}]}])
    p['entities'].append({'id':'unit/hero','kind':'entity','tags':['player'],'components':{'spatial':{},'selection_state':{'side':0,'motion':1,'category':1},
        'attributes':{'base':{'max_hp':5000,'atk':3000,'def':100}},'resources':{'hp':{'initial':5000,'capacity':5000,'role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/kill','ability/instant']}})
    p['scenarioDraft']={'id':'scene/rebirth_death','ruleset':'ruleset/ark_standard','objectives':{'type':'waves','life_resource':'life'},'resources':{'life':{'initial':99999,'capacity':99999}},'map':{'rows':3,'cols':5},'initialEntities':[
        {'definition':uid,'instanceAlias':'slime','position':{'row':1,'col':1}}, {'definition':'unit/hero','instanceAlias':'hero','position':{'row':1,'col':2}}]}
    return p


def events(s,kind):return [e for e in s.session.events if e['type']==kind]


def test_first_rebirth_no_projectile_final_death_one_projectile_and_one_claim(tmp_path):
    s=Engine.create(Compiler().compile(fixture()),seed=80021);s.submit({'action':'skill','source':'hero','ability':'ability/kill'},at=1);s.submit({'action':'skill','source':'hero','ability':'ability/kill'},at=7)
    s.advance(5);assert s.ctx.alive('slime') and not events(s,'projectile.launched') and not events(s,'combat.kill')
    cp=tmp_path/'cp.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin));s.advance(35);r.advance(35)
    assert len(events(s,'projectile.launched'))==len(events(s,'combat.kill'))==1
    assert s.ctx.get('slime',('runtime','death_generation'))==1 and s.ctx.resources.current('hero','hp')==4060
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()


def test_nested_instantkill_during_death_emit_avoids_duplicate_generation(monkeypatch):
    p=fixture();p['entities'][0]['components']['rebirth']['max_count']=0;s=Engine.create(Compiler().compile(p),seed=80021)
    original=s.ctx.buffs.toggles.pulse;entered=[]
    def callback(event,payload):
        original(event,payload)
        if event=='projectile.launched' and not entered:
            entered.append(True);s.ctx.effects.execute('hero',['slime'],{'op':'instant_kill','parameters':{'cause':'nested','skip_rebirth':True}})
    monkeypatch.setattr(s.ctx.buffs.toggles,'pulse',callback)
    s.submit({'action':'skill','source':'hero','ability':'ability/kill'},at=1);s.advance(3)
    assert len(events(s,'projectile.launched'))==len(events(s,'combat.kill'))==1
    assert s.ctx.get('slime',('runtime','death_generation'))==1


def test_environment_kills_real_slime_but_delayed_boom_keeps_slime_source():
    p=fixture();p['entities'][0]['components']['rebirth']['max_count']=0
    p['rules'].append({'id':'rule/env','kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph',
        'nodes':[{'id':'settle','expression':"{'accepted':True,'amount':inputs.effect.fixed_amount,'allocations':[],'events':[]}"}],'output':'nodes.settle'}})
    p['entities'][1]['dependencies']=['rule/env']
    s=Engine.create(Compiler().compile(p),seed=80021)
    request={'op':'no_source_damage','fixed_amount':3000,'damage_type':'true','attack_type':'NONE','damage_without_modify':False,
        'ignore_for_sp':False,'node_is_env_damage':False,'env_blackboard_injected':True,'environmental':True,'origin':{'kind':'fixture_environment'},
        'rules':{'damage.pipeline':'rule/env'}}
    # Keep the rule in the compiled closure through an actual bounded reference.
    # This is direct API source-free settlement instrumentation, not replay.
    result=s.ctx.effects.execute(None,[s.session.world.resolve('slime')],request)
    s.advance(32)
    kills=events(s,'combat.kill');assert len(kills)==1 and kills[0]['payload']['source'] is None
    assert kills[0]['payload']['origin']['kind']=='fixture_environment'
    hits=[e for e in events(s,'damage.accepted') if e['payload']['source']==s.session.world.resolve('slime')]
    assert len(hits)==1 and hits[0]['payload']['amount']==940 and s.ctx.resources.current('hero','hp')==4060
