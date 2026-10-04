"""Public real blocking hardgate defeats unbounded taunt and keeps native eligibility."""
import json
from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.domains.selection import DEFAULT_STATE
from ark_sim.tools.replay import replay
from tools.chapter06.cold.policies import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[2]
COLD=ROOT/'packages/campaign/chapter06_cold/model.json'

def package(kind,*,initial_sp=0,blocked=True,invalid_blocker=False):
    p=json.loads((ROOT/'packages/campaign/chapter06_units'/('snmage_v3/model.json' if kind=='mage' else 'snbow_v2/model.json')).read_bytes());u=p['entities'][0]
    if kind=='mage':u['components']['resources']['sp']['initial']=initial_sp
    for name,col,blockcount,taunt,category in [('blocker',0,3 if blocked else 0,0,2 if invalid_blocker else 1),('bait',1,0,1e100,1)]:
        p['entities'].append({'id':'unit/test/input_target/'+name,'kind':'entity','tags':['player','ground'],'components':{'attributes':{'base':{'max_hp':20000,'atk':0,'def':100,'mres':25,'attack_speed_ratio':1,'block_count':blockcount,'taunt_level':taunt}},'resources':{'hp':{'initial':20000,'capacity':20000,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':category,'unit_type':1},'spatial':{},'deployable':{'base_cost':1,'capacity':1,'cooldown_seconds':0,'terrain':'ground'},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    p['scenarioDraft']={'id':'scene/ch6/input_target/'+kind,'ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':2,'cols':6},'resources':{'dp':{'initial':30,'capacity':99}},'initialEntities':[{'definition':u['id'],'instanceAlias':'enemy','position':{'row':0,'col':0},'route':{'motionMode':'WALK','startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':4},'checkpoints':[]}}],'roster':['unit/test/input_target/blocker','unit/test/input_target/bait']}
    return p
def create(kind,**kwargs):return Engine.create(Compiler(providers=providers()).compile(package(kind,**kwargs),packages=[COLD]),seed=6293,providers=providers())
def deploy(s):
    for name,col in [('blocker',0),('bait',1)]:s.submit({'action':'deploy','definition':'unit/test/input_target/'+name,'alias':name,'position':{'row':0,'col':col}},at=0)
def hits(s):return [e for e in s.session.events if e['type']=='damage.accepted']

@pytest.mark.parametrize('kind,initial',[('mage',0),('mage',2),('bow',0)])
def test_public_same_tick_settle_real_blocker_hardgate_despite_unbounded_taunt(kind,initial):
    s=create(kind,initial_sp=initial);deploy(s);s.session.advance(160)
    blocker=s.session.world.resolve('blocker');bait=s.session.world.resolve('bait')
    assert s.ctx.spatial.blocked_by('enemy')==blocker
    assert hits(s) and all(e['payload']['target']==blocker for e in hits(s))
    assert s.ctx.resources.current('bait','hp')==20000
    casts=[e for e in s.session.events if e['type']=='ability.started']
    assert casts and all(list(e['payload']['targets'])==[blocker] for e in casts)
    if kind=='mage' and initial==2:assert 23 in s.ctx.spatial.selection_state('blocker',DEFAULT_STATE)['abnormal_flags']

@pytest.mark.parametrize('kind',['mage','bow'])
def test_existing_real_blocker_ineligible_native_category_has_no_other_target_fallback(kind):
    s=create(kind,initial_sp=2 if kind=='mage' else 0,invalid_blocker=True);deploy(s);s.session.advance(160)
    assert s.ctx.spatial.blocked_by('enemy')==s.session.world.resolve('blocker')
    assert not hits(s) and not [e for e in s.session.events if e['type']=='projectile.launched']

@pytest.mark.parametrize('kind',['mage','bow'])
def test_unblocked_preserves_original_range_eligibility_and_native_hatred_policy(kind):
    s=create(kind,blocked=False);deploy(s);s.session.advance(40)
    assert s.ctx.spatial.blocked_by('enemy') is None
    assert hits(s) and all(e['payload']['target']==s.session.world.resolve('bait') for e in hits(s))

@pytest.mark.parametrize('kind',['mage','bow'])
def test_public_blocker_withdraw_releases_relation_new_cast_then_bait_only(kind):
    s=create(kind);deploy(s);s.submit({'action':'withdraw','source':'blocker'},at=2);s.session.advance(160)
    assert s.ctx.spatial.blocked_by('enemy') is None and not s.ctx.alive('blocker')
    assert hits(s) and all(e['payload']['target']==s.session.world.resolve('bait') for e in hits(s))

@pytest.mark.parametrize('kind',['mage','bow'])
def test_current_input_target_gate_and_settled_relation_disk_cp_public_head(kind,tmp_path):
    s=create(kind,initial_sp=2 if kind=='mage' else 0);deploy(s);s.session.advance(1)
    assert s.ctx.spatial.blocked_by('enemy')==s.session.world.resolve('blocker')
    p=tmp_path/'input_target.json';pin=write_ordered(p,s.checkpoint());restored=Engine.restore(s.program,load_bound(p,pin),providers=providers())
    s.session.advance(160);restored.session.advance(160)
    assert s.snapshot()==restored.snapshot()==replay(s.program,s.export_replay(),providers=providers()).snapshot()
    assert all(e['payload']['target']==s.session.world.resolve('blocker') for e in hits(s))
