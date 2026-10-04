"""Actual source Cold/Frozen and generic application adversarial author probes."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from ark_sim import Compiler, Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.domains.selection import DEFAULT_STATE
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered, load_bound
from tools.chapter06.cold.build_module import build, COLD, FROZEN, APPLICATION
from tools.chapter06.cold.policies import providers

ROOT = Path(__file__).resolve().parents[3]
CORE = '4ef955c5d5a7628382fc3d15003bb0a30c749832d210ca50897355568ec8d329'


def fixture_package(*, immune=(), factor=1, ratio=1.5, effects=(), rule_expression=None):
    p = build()
    source = {'max_hp':10000,'atk':100,'def':0,'mres':0,'attack_interval':1,'attack_speed_ratio':1,'move_speed':1,'block_count':0}
    target = {**source,'def':20,'one_minus_status_resistance':factor}
    for alias, attrs, tags in [('caster',source,['enemy']),('caster2',source,['enemy']),('target',target,['player','cold_receiver'])]:
        p.setdefault('entities',[]).append({'id':'unit/test/cold/'+alias,'kind':'entity','tags':tags,
            'components':{'attributes':{'base':attrs},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'},'sp':{'initial':0,'capacity':100,'recovery_rate':1,'recovery_freeze_rule':'rule/ch6/cold/frozen_recovery'}},
                'spatial':{},'selection_state':{'side':0 if alias=='target' else 1,'motion':1,'category':1,'unit_type':1,
                    'abnormal_immunes':list(immune)}, 'lifecycle':{'policy':'policy/ark_lifecycle'},
                'abilities':['ability/ch6/cold/apply5','ability/ch6/cold/apply10','ability/test/cold/hit'] if alias!='target' else [],
                'buffs':{'initial':['buff/ch6/cold/frozen_atkscale'+str(ratio)]} if alias=='caster' else {}}})
    p['abilities'].append({'id':'ability/test/cold/hit','kind':'ability','activation':{'mode':'manual'},
        'selector':'selector/ch6/cold/receiver','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'physical','scale':1}}]})
    if rule_expression is not None:
        r=next(r for r in p['rules'] if r['id']==APPLICATION);r['implementation']={'type':'expression','expression':rule_expression}
    p['scenarioDraft']={'id':'scene/ch6/cold/author','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':10},
        'initialEntities':[{'definition':'unit/test/cold/'+a,'instanceAlias':a,'position':{'row':0,'col':i}} for i,a in enumerate(('caster','caster2','target'))],
        'scheduledEffects':list(effects)}
    return p


def fixture(**kwargs):
    p=fixture_package(**kwargs);reg=providers()
    return Engine.create(Compiler(providers=reg).compile(p),seed=616,providers=reg)


def apply(s, seconds=10, at=0, source='caster'): s.submit({'action':'skill','source':source,'ability':'ability/ch6/cold/apply'+str(seconds)},at=at)
def hit(s, at=0): s.submit({'action':'skill','source':'caster','ability':'ability/test/cold/hit'},at=at)
def state(s): return s.ctx.spatial.selection_state('target',DEFAULT_STATE)
def flags(s): return state(s)['abnormal_flags']
def instances(s): return [i for i in s.ctx.get('target',('buffs','instances'),[]) if i['definition'] in (COLD,FROZEN)]


def test_exact_candidate_source_row_fields_and_modifiers():
    assert implementation_digest()==CORE
    d=json.loads((ROOT/'packages/campaign/chapter06_cold/source.decoded.json').read_bytes())
    assert d['rows']['e2c_cold']['decoded']['attributes']['value']['abnormalFlags']==[23]
    assert d['rows']['e2c_cold']['decoded']['attributes']['value']['attributeModifiers'][0]['value']==-30
    assert d['rows']['e2c_freeze']['decoded']['attributes']['value']['abnormalFlags']==[16]
    assert d['rows']['e2c_cold']['decoded']['statusResistable']['value']==1


@pytest.mark.parametrize('seconds,ticks',[(5,150),(10,300)])
def test_actual_cold_duration_halfopen_aspeed_and_expiry(seconds,ticks):
    s=fixture();apply(s,seconds);s.session.advance(ticks-1)
    assert 23 in flags(s) and 16 not in flags(s)
    assert s.ctx.attributes.value('target','attack_speed_ratio')==pytest.approx(.7)
    assert instances(s)[0]['expires_at']==ticks
    s.session.advance(2);assert 23 not in flags(s) and instances(s)==[]
    assert s.ctx.attributes.value('target','attack_speed_ratio')==1


def test_second_cold_cross_source_transforms_to_real_frozen_and_removes_cold():
    s=fixture();apply(s,10);apply(s,5,at=30,source='caster2');s.session.advance(31)
    assert 16 in flags(s) and 23 not in flags(s)
    assert len(instances(s))==1 and instances(s)[0]['definition']==FROZEN and instances(s)[0]['expires_at']==180
    assert s.ctx.attributes.value('target','attack_speed_ratio')==1
    c=s.ctx.buffs.controls('target');assert not c['move'] and not c['attack'] and not c['abilities']


def test_frozen_refresh_uses_current_source_duration_not_old_remaining_lifetime():
    s=fixture();apply(s,5);apply(s,5,at=10);apply(s,10,at=100,source='caster2');s.session.advance(101)
    assert len(instances(s))==1 and instances(s)[0]['definition']==FROZEN and instances(s)[0]['expires_at']==400
    s.session.advance(298);assert 16 in flags(s)
    s.session.advance(2);assert 16 not in flags(s) and s.ctx.buffs.controls('target')['move']


@pytest.mark.parametrize('factor,expected',[(1,300),(.5,150),(.25,75)])
def test_real_status_resistance_duration(factor,expected):
    s=fixture(factor=factor);apply(s,10);s.session.advance(1)
    assert instances(s)[0]['expires_at']==expected


def test_cold_immune_no_contribution_but_public_command_only_records_acceptance():
    s=fixture(immune=[23]);apply(s);s.session.advance(1)
    assert instances(s)==[] and 23 not in flags(s) and 16 not in flags(s)
    assert s.ctx.attributes.value('target','attack_speed_ratio')==1


def test_frozen_immune_repeated_cold_retains_slow_refresh_not_control():
    s=fixture(immune=[16]);apply(s,5);apply(s,10,at=20,source='caster2');s.session.advance(21)
    assert 23 in flags(s) and 16 not in flags(s) and instances(s)[0]['expires_at']==320
    assert s.ctx.buffs.controls('target')['move'] and s.ctx.attributes.value('target','attack_speed_ratio')==pytest.approx(.7)


@pytest.mark.parametrize('ratio,normal,frozen',[(1.5,80,130),(2.5,80,230)])
def test_target_frozen_atkscale_is_before_defense_not_always_self_attack(ratio,normal,frozen):
    s=fixture(ratio=ratio);hit(s);apply(s,10,at=1);apply(s,10,at=2);hit(s,at=3);s.session.advance(4)
    ev=[e['payload']['amount'] for e in s.session.events if e['type']=='damage.accepted']
    assert ev==[normal,frozen] and s.ctx.attributes.value('caster','atk')==100


def test_noop_plan_has_exact_checkpoint_and_rng_unchanged_on_direct_public_effect():
    s=fixture(rule_expression="{'accepted':False,'operations':[]}")
    before=s.checkpoint()
    s.ctx.effects.execute('caster',['target'],{'op':'buff_application','application_rule':APPLICATION,'allowed':[COLD,FROZEN],'parameters':{'duration_seconds':10}})
    assert s.checkpoint()==before


@pytest.mark.parametrize('expression',[
    "{'accepted':1,'operations':[]}",
    "{'accepted':False,'operations':[{'kind':'apply','buff':'buff/ch6/cold/e2c_cold','duration_seconds':5}]}",
    "{'accepted':True,'operations':[{'kind':'apply','buff':'foreign','duration_seconds':5}]}",
    "{'accepted':True,'operations':[{'kind':'apply','buff':'buff/ch6/cold/e2c_cold','duration_seconds':True}]}",
    "{'accepted':True,'operations':[{'kind':'apply','buff':'buff/ch6/cold/e2c_cold','duration_seconds':-1}]}",
    "{'accepted':True,'operations':[{'kind':'apply','buff':'buff/ch6/cold/e2c_cold','duration_seconds':5,'target':999}]}",
    "{'accepted':True,'operations':[{'kind':'remove','buff':'buff/ch6/cold/e2c_cold','instance':'buff/99/1','generation':1}]}"
])
def test_malformed_foreign_typed_plan_rolls_back_all_state(expression):
    s=fixture(rule_expression=expression);before=s.checkpoint()
    with pytest.raises(ValueError):s.ctx.effects.execute('caster',['target'],{'op':'buff_application','application_rule':APPLICATION,'allowed':[COLD,FROZEN],'parameters':{'duration_seconds':10}})
    assert s.checkpoint()==before


def test_allowed_buff_dependency_is_validated_before_engine():
    p=fixture_package();a=p['abilities'][0]['timeline'][0]['effect'];a['allowed']=['unit/test/cold/target']
    with pytest.raises(ValueError,match='Buff'):Compiler(providers=providers()).compile(p)


def test_on_remove_callback_retires_target_without_old_plan_touching_it_again():
    p=fixture_package();cold=next(b for b in p['buffs'] if b['id']==COLD)
    cold['on_remove']=[{'op':'retire','parameters':{'reason':'dead'}}]
    s=Engine.create(Compiler(providers=providers()).compile(p),seed=616,providers=providers())
    apply(s,10);apply(s,5,at=1);s.session.advance(2)
    assert not s.ctx.alive('target')
    assert len([e for e in s.session.events if e['type']=='entity.died'])==1


def test_actual_frozen_stops_route_and_sp_then_resumes_on_exact_expiry():
    p=fixture_package();p['scenarioDraft']['initialEntities'][2]['route']={'motionMode':'WALK','startPosition':{'row':0,'col':2},'endPosition':{'row':0,'col':9},'checkpoints':[]}
    s=Engine.create(Compiler(providers=providers()).compile(p),seed=616,providers=providers())
    apply(s,5);apply(s,5,at=10);s.session.advance(11)
    pos=s.ctx.get('target',('spatial','position'));sp=s.ctx.resources.current('target','sp')
    s.session.advance(148)
    assert s.ctx.get('target',('spatial','position'))==pos and s.ctx.resources.current('target','sp')==sp
    s.session.advance(2)
    assert s.ctx.get('target',('spatial','position'))['col']>pos['col']
    assert s.ctx.resources.current('target','sp')==pytest.approx(sp+1/30)


def test_frozen_really_interrupts_pending_manual_damage_and_rejects_new_cast():
    p=fixture_package();p['selectors'].append({'id':'selector/test/cold/caster','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'},{'state':'alive'}],'limit':1})
    p['abilities'].append({'id':'ability/test/cold/delayed','kind':'ability','activation':{'mode':'manual'},'selector':'selector/test/cold/caster',
        'timeline':[{'at':60,'effect':{'op':'damage','damage_type':'physical','scale':1}}]})
    p['entities'][2]['components']['abilities']=['ability/test/cold/delayed']
    s=Engine.create(Compiler(providers=providers()).compile(p),seed=616,providers=providers())
    s.submit({'action':'skill','source':'target','ability':'ability/test/cold/delayed'},at=0)
    apply(s,5,at=1);apply(s,5,at=10)
    s.submit({'action':'skill','source':'target','ability':'ability/test/cold/delayed'},at=11)
    s.session.advance(61)
    assert s.ctx.resources.current('caster','hp')==10000
    assert not [e for e in s.session.events if e['type']=='damage.accepted']
    assert [e for e in s.session.events if e['type']=='ability.interrupted' and e['payload']['source']==s.session.world.resolve('target')]
    assert [e for e in s.session.events if e['type']=='command.rejected' and e['time']==11]


def test_immunity_added_mid_frozen_suppresses_flags_control_and_target_multiplier():
    s=fixture();apply(s,10);apply(s,10,at=1);s.session.advance(2)
    s.ctx.set('target',('selection_state','abnormal_immunes'),[16]);s.ctx.buffs.reconcile()
    assert 16 not in flags(s) and s.ctx.buffs.controls('target')['move']
    hit(s,at=2);s.session.advance(1)
    assert [e['payload']['amount'] for e in s.session.events if e['type']=='damage.accepted']==[80]


def test_stale_remove_handle_does_not_remove_callback_refreshed_generation():
    p=fixture_package();p['buffs'] += [{'id':'buff/test/a','kind':'buff','duration_seconds':10,
        'on_remove':[{'op':'apply_buff','buff':'buff/test/b'}]}, {'id':'buff/test/b','kind':'buff','duration_seconds':10}]
    effect=p['abilities'][0]['timeline'][0]['effect'];effect['allowed']=['buff/test/a','buff/test/b']
    # Handles are target4's first and second instances, both generation1.
    r=next(r for r in p['rules'] if r['id']==APPLICATION)
    r['implementation']={'type':'expression','expression':"{'accepted':True,'operations':[{'kind':'remove','buff':'buff/test/a','instance':'buff/4/1','generation':1},{'kind':'remove','buff':'buff/test/b','instance':'buff/4/2','generation':1}]}"}
    s=Engine.create(Compiler(providers=providers()).compile(p),seed=616,providers=providers())
    s.ctx.buffs.apply('caster','target','buff/test/a');s.ctx.buffs.apply('caster','target','buff/test/b')
    s.ctx.effects.execute('caster',['target'],effect)
    remaining=s.ctx.get('target',('buffs','instances'))
    assert len(remaining)==1 and remaining[0]['definition']=='buff/test/b' and remaining[0]['generation']==2


def test_actual_cp_and_from_start_replay_keep_transform_refresh_and_damage(tmp_path):
    s=fixture();apply(s,10);apply(s,5,at=20,source='caster2');hit(s,at=21);apply(s,10,at=100)
    s.session.advance(10);p=tmp_path/'actual.cold.json';pin=write_ordered(p,s.checkpoint())
    restored=Engine.restore(s.program,load_bound(p,pin),providers=providers())
    s.session.advance(392);restored.session.advance(392)
    repeated=replay(s.program,s.export_replay(),providers=providers())
    assert s.snapshot()==restored.snapshot()==repeated.snapshot()
    assert instances(s)==[] and s.ctx.resources.current('target','hp')==9870
