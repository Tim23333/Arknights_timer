"""Actual native normal/death/silence/qualified-area and retained Cold author checks."""
import json
from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.domains.selection import DEFAULT_STATE
from ark_sim.tools.replay import replay
from tools.chapter06_units.snslime.test_required_payload import package,public_inputs,COLD
from tools.chapter06_units.snslime.build_module import OUT
from tools.chapter06.cold.policies import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
CORE='8b9f226882502ce9b9d8029102fff5832f2ba01e5449096502908b670d889e9b'
def fixture(p=None):return Engine.create(Compiler(providers=providers()).compile(p or package(),packages=[COLD]),seed=6267,providers=providers())
def flags(s,who):return s.ctx.spatial.selection_state(who,DEFAULT_STATE)['abnormal_flags']
def hp(s,who):return s.ctx.resources.current(who,'hp')
def outgoing(s):return [(e['time'],e['payload']['target'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted' and e['payload']['source']==s.session.world.resolve('slime')]

def test_exact_source_action_payload_and_source_node_not_mage_or_story():
    assert implementation_digest()==CORE
    p=json.loads(OUT.read_bytes());m=p['manifest']['metadata'];a=p['entities'][0]['components']['attributes']['base']
    assert (a['max_hp'],a['atk'],a['def'],a['mres'],a['attack_interval'])==(3250,300,0,0,1.7)
    assert m['source_action']['_attackType']=='SPLASH' and m['source_action']['_noSource'] is False
    assert m['source_action']['_ignoreForSp'] is False and m['source_simple']['_lifeTime']==1
    assert m['source_circle']['raw']['m_Radius']==pytest.approx(1.65)
    assert m['source_template'][0]['_abnormalFlag']=='SILENCED'
    assert m['source_talent']['raw']['_projectileBuffs'][0]['buffKey']=='e2c_cold'

def test_actual_normal_block_fourteen_and_interval51_before_death():
    s=fixture()
    s.submit({'action':'deploy','definition':'unit/test/snslime/killer','alias':'killer','position':{'row':0,'col':0}},at=0)
    s.session.advance(67)
    assert s.ctx.spatial.blocked_by('slime')==s.session.world.resolve('killer')
    assert outgoing(s)==[(15,s.session.world.resolve('killer'),200),(66,s.session.world.resolve('killer'),200)]
    assert hp(s,'slime')==3250 and hp(s,'killer')==9600
    assert not [e for e in s.session.events if e['type']=='projectile.launched']

def test_true_death_exact_two_targets_after_one_second_and_halfopen_cold_expiry():
    s=fixture();public_inputs(s);s.session.advance(3)
    assert not s.ctx.alive('slime') and hp(s,'slime')==0 and outgoing(s)==[]
    assert len([e for e in s.session.events if e['type']=='entity.died'])==1
    assert len([e for e in s.session.events if e['type']=='projectile.launched'])==1
    s.session.advance(29);assert outgoing(s)==[]
    s.session.advance(1)
    assert outgoing(s)==[(32,s.session.world.resolve('killer'),500),(32,s.session.world.resolve('friend'),500)]
    for who in ('killer','friend'):
        assert hp(s,who)==9500 and 23 in flags(s,who)
        instances=s.ctx.get(who,('buffs','instances'),[])
        assert len(instances)==1 and instances[0]['expires_at']==332
        assert s.ctx.attributes.value(who,'attack_speed_ratio')==pytest.approx(.7)
    s.session.advance(298);assert 23 in flags(s,'killer')
    s.session.advance(2);assert 23 not in flags(s,'killer') and 23 not in flags(s,'friend')
    assert not s.ctx.alive('slime') and hp(s,'slime')==0

def silenced_package():
    p=package();p['buffs']=[{'id':'buff/test/snslime/silence','kind':'buff','duration_seconds':10,'selection_flags':{'abnormal_flags':[12]}}]
    p['abilities'].append({'id':'ability/test/snslime/silence','kind':'ability','activation':{'mode':'manual'},'selector':'selector/test/snslime/enemy','timeline':[{'at':0,'effect':{'op':'apply_buff','buff':'buff/test/snslime/silence'}}]})
    p['entities'][1]['components']['abilities'].append('ability/test/snslime/silence')
    return p

def test_public_silence_at_true_death_blocks_emission_not_death_itself():
    s=fixture(silenced_package());public_inputs(s);s.submit({'action':'skill','source':'killer','ability':'ability/test/snslime/silence'},at=1)
    s.session.advance(35)
    assert not s.ctx.alive('slime') and hp(s,'slime')==0
    assert not outgoing(s) and not [e for e in s.session.events if e['type']=='projectile.launched']
    assert hp(s,'killer')==hp(s,'friend')==10000 and flags(s,'killer')==flags(s,'friend')==[]

@pytest.mark.parametrize('field,value,hit',[('motion',2,False),('category',2,False),('side',1,False),('camouflage',True,True),('target_free',True,False)])
def test_actual_native_area_qualification_controls_damage_and_cold_together(field,value,hit):
    p=package();p['entities'][2]['components']['selection_state'][field]=value
    s=fixture(p);public_inputs(s);s.session.advance(34)
    assert hp(s,'killer')==9500 and 23 in flags(s,'killer')
    assert hp(s,'friend')==(9500 if hit else 10000) and (23 in flags(s,'friend'))==hit

def test_actual_boundary_outside_native_radius_and_public_withdraw_discard_target():
    s=fixture()
    s.submit({'action':'deploy','definition':'unit/test/snslime/killer','alias':'killer','position':{'row':0,'col':0}},at=0)
    s.submit({'action':'deploy','definition':'unit/test/snslime/friend','alias':'friend','position':{'row':0,'col':2}},at=0)
    s.submit({'action':'skill','source':'killer','ability':'ability/test/snslime/kill'},at=2);s.session.advance(34)
    assert hp(s,'killer')==9500 and hp(s,'friend')==10000 and not flags(s,'friend')
    s=fixture();public_inputs(s);s.submit({'action':'withdraw','source':'friend'},at=10);s.session.advance(34)
    assert hp(s,'killer')==9500 and 23 in flags(s,'killer')
    assert not s.ctx.alive('friend') and hp(s,'friend')==10000 and not flags(s,'friend')

@pytest.mark.parametrize('immune,expected', [([23],False),([16],True)])
def test_source_cold_immunity_keeps_actual_splash_accepted(immune,expected):
    p=package();p['entities'][2]['components']['selection_state']['abnormal_immunes']=immune
    s=fixture(p);public_inputs(s);s.session.advance(34)
    assert hp(s,'friend')==9500 and (23 in flags(s,'friend'))==expected

@pytest.mark.parametrize('tick',[1,3,31])
def test_actual_before_death_and_pending_expiry_disk_cp_full_public_head(tick,tmp_path):
    s=fixture();public_inputs(s);s.session.advance(tick)
    path=tmp_path/'snslime.actual.json';pin=write_ordered(path,s.checkpoint());restored=Engine.restore(s.program,load_bound(path,pin),providers=providers())
    s.session.advance(334-tick);restored.session.advance(334-tick)
    assert s.snapshot()==restored.snapshot()==replay(s.program,s.export_replay(),providers=providers()).snapshot()
    assert hp(s,'slime')==0 and not s.ctx.alive('slime') and hp(s,'killer')==hp(s,'friend')==9500
    assert flags(s,'killer')==flags(s,'friend')==[]
