from pathlib import Path
from copy import deepcopy
import sys
import pytest
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_m76_death_projectiles_v7_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.build_chapter04_bslime_model import build
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[]


def fixture(silenced=False,objectives=True):
    p=build();uid=p['entities'][0]['id']
    if silenced:p['entities'][0]['components']['selection_state']['abnormal_flags']=[12]
    def guard(name,motion=1,category=1):return {'id':'unit/'+name,'kind':'entity','tags':['player'],
        'components':{'spatial':{},'selection_state':{'side':0,'motion':motion,'category':category},
            'attributes':{'base':{'max_hp':5000,'atk':3000,'def':100,'mres':90}},
            'resources':{'hp':{'initial':5000,'capacity':5000,'role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/kill']}}
    p['entities'].extend([guard('hero'),guard('fly',2),guard('device',1,4)])
    p['selectors'].append({'id':'selector/kill','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'limit':1})
    p['abilities'].append({'id':'ability/kill','kind':'ability','selector':'selector/kill','activation':{'mode':'manual'},'timeline':[{'at_seconds':0,'effect':{'op':'damage','damage_type':'true'}}]})
    p['scenarioDraft']={'id':'scene/death/projectile','ruleset':'ruleset/ark_standard','objectives':{'type':'waves','life_resource':'life'} if objectives else {},
        'resources':{'life':{'initial':99999,'capacity':99999}},'map':{'rows':3,'cols':5},'initialEntities':[
            {'definition':uid,'instanceAlias':'slime','position':{'row':1,'col':1}},
            *[{'definition':'unit/'+n,'instanceAlias':n,'position':{'row':1,'col':2}} for n in ('hero','fly','device')]]}
    INPUTS.append(p);s=Engine.create(Compiler().compile(p),seed=76021);s.submit({'action':'skill','source':'hero','ability':'ability/kill'},at=1);return s


def ev(s,kind):return [e for e in s.session.events if e['type']==kind]


def test_exact_death_one_second_1040_before_defense_blocks_victory_and_disk_replay(tmp_path):
    s=fixture();s.advance(15);assert not s.ctx.alive('slime') and not s.ctx.state()['finished']
    assert s.ctx.resources.current('hero','hp')==5000 and len(ev(s,'projectile.launched'))==1
    cp=tmp_path/'cp.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin));s.advance(20);r.advance(20)
    hits=[e for e in ev(s,'damage.accepted') if e['payload']['source']==s.session.world.resolve('slime')]
    assert [(e['time'],e['payload']['amount']) for e in hits]==[(31,940)]
    assert s.ctx.resources.current('fly','hp')==5000 and s.ctx.resources.current('device','hp')==5000
    assert s.ctx.state()['finished'] and s.ctx.state()['kills']==1 and len(ev(s,'projectile.invalid'))==1
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()


def test_source_silenced_death_rejects_before_emission_no_delayed_damage():
    s=fixture(silenced=True);s.advance(35)
    assert len(ev(s,'death_projectile.rejected'))==1 and not ev(s,'projectile.launched')
    assert s.ctx.resources.current('hero','hp')==5000 and s.ctx.state()['finished']


def test_withdrawn_retire_never_triggers_true_death_emission():
    s=fixture(objectives=False);s.ctx.lifecycle.retire('slime','withdrawn');s.advance(35)
    assert not ev(s,'projectile.launched') and not ev(s,'death_projectile.rejected')


def test_bad_decision_rolls_hp_events_rng_tasks_and_death_all_back():
    p=build();p['rules'][0]['implementation']['expression']='1/0';p['rules'][-2].setdefault('dependencies',[]).append('rule/ch4/bslime_qualification');p['scenarioDraft']={'id':'scene/bad','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':2},'initialEntities':[{'definition':p['entities'][0]['id'],'instanceAlias':'slime','position':{'row':0,'col':0}}]}
    s=Engine.create(Compiler().compile(p));before=s.checkpoint()
    with pytest.raises(Exception):s.ctx.resources.adjust('slime','hp',-3000,source='slime')
    assert s.checkpoint()==before


def test_legal_sync_projectile_launch_callback_cannot_emit_twice(monkeypatch):
    s=fixture(objectives=False);original=s.ctx.buffs.toggles.pulse;visited=[]
    def callback(event,payload):
        original(event,payload)
        if event=='projectile.launched' and not visited:
            visited.append(True);s.ctx.lifecycle.retire('slime','dead')
    monkeypatch.setattr(s.ctx.buffs.toggles,'pulse',callback)
    s.advance(3)
    assert len(ev(s,'projectile.launched'))==1 and s.ctx.state()['kills']==1 and len(ev(s,'entity.died'))==1


def test_launch_callback_withdraw_keeps_actual_retirement_reason(monkeypatch):
    s=fixture(objectives=False);original=s.ctx.buffs.toggles.pulse
    def callback(event,payload):
        original(event,payload)
        if event=='projectile.launched':s.ctx.lifecycle.retire('slime','withdrawn')
    monkeypatch.setattr(s.ctx.buffs.toggles,'pulse',callback);s.advance(3)
    assert s.ctx.get('slime',('runtime','state'))=='withdrawn' and s.ctx.state()['kills']==0 and not ev(s,'entity.died')


def test_target_moves_out_before_expiry_is_not_hit(monkeypatch):
    s=fixture(objectives=False);s.advance(3)
    s.ctx.effects.execute('hero',['hero'],{'op':'move','position':{'row':1,'col':4}})
    s.advance(32);assert s.ctx.resources.current('hero','hp')==5000


@pytest.mark.parametrize('patch',[lambda p:p['projectiles'][0].update(completion_blocking=1),
    lambda p:p['entities'][0]['components']['lifecycle']['death_projectiles'][0].update(effect={'op':'damage'}),
    lambda p:p['projectiles'][0]['lifecycle'].update(target_invalid='cancel'),
    lambda p:p['entities'][0]['components']['lifecycle']['death_projectiles'][0].update(rule='rule/ch4/bslime_fixed')])
def test_invalid_effects_references_and_flag_types_compile_rejected(patch):
    p=build();patch(p);p['scenarioDraft']={'id':'scene/invalid','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':2},'initialEntities':[{'definition':p['entities'][0]['id'],'position':{'row':0,'col':0}}]}
    with pytest.raises(ValueError):Compiler().compile(p)


def test_runtime_effective_override_rejected_before_entity_or_alias_publish():
    s=fixture(objectives=False);before=s.checkpoint();uid=s.ctx.entity('slime')['definition_id']
    with pytest.raises(ValueError):s.ctx.lifecycle.create(uid,{'row':0,'col':3},alias='bad',component_overrides={
        'lifecycle':{'death_projectiles':[{'rule':'unknown','parameters':{},'projectile_definition':'unknown','effect':{'op':'area','center':'source','radius':1,'effects':[]}}]}})
    assert s.checkpoint()==before


def test_defeat_can_cancel_completion_blocking_projectile_without_post_terminal_damage():
    s=fixture();s.advance(3);s.ctx.resources.adjust('system/battle','life',value=0);s.advance(35)
    assert s.ctx.state()['finished'] and s.ctx.state()['result']=='defeat'
    assert s.ctx.resources.current('hero','hp')==5000
    assert any(e['payload']['reason']=='battle_terminal' for e in ev(s,'projectile.invalid'))
