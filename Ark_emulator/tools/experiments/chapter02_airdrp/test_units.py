"""Post-born explicit model probes; native birth window stays unimplemented."""
import json,sys,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m37_projectile_refs_candidate';sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.build_chapter02_airdrp_units import build,OUT,SOURCE
INPUTS=[]
def fixture(index,blocked=True):
 p=json.loads(OUT.read_bytes());enemy=p['entities'][index];uid=enemy['id']
 p['entities'].append({'id':'unit/blocker','kind':'entity','tags':['player','ground'],'components':{'attributes':{'base':{'max_hp':10000,'def':100,'mres':0,'block_count':1 if blocked else 0}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'spatial':{},'deployable':{'base_cost':0,'capacity':1,'terrain':'ground','cooldown_seconds':0}}})
 p['scenarioDraft']={'id':'scene/air_troop_post_born','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':5},'initialEntities':[{'definition':uid,'instanceAlias':'enemy','position':{'row':0,'col':0},'route':{'motionMode':'WALK','startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':4},'checkpoints':[]}},{'definition':'unit/blocker','instanceAlias':'blocker','position':{'row':0,'col':1}}],'waves':[]};return p
def make(p):
 raw=json.dumps(p,separators=(',',':')).encode();INPUTS.append({'sha256':hashlib.sha256(raw).hexdigest(),'seed':20901,'document':json.loads(raw)});return Engine.create(Compiler().compile(json.loads(raw)),seed=20901)
def exact(s):
 r=Engine.restore(s.program,s.checkpoint());s.advance(2);r.advance(2);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
@pytest.mark.parametrize('index,health,atk,defense',[(0,1450,220,100),(1,2300,300,150)])
def test_ground_source_values_and_owned_f13_attack_when_actually_blocked(index,health,atk,defense):
 p=fixture(index);unit=p['entities'][index];attrs=unit['components']['attributes']['base']
 assert attrs['max_hp']==health and attrs['atk']==atk and attrs['def']==defense and attrs['mass_level']==0 and attrs['block_cost']==1
 assert unit['tags']==['enemy','ground'] and unit['metadata']['native_motion']=='WALK'
 s=make(p);s.advance(72);assert s.ctx.resources.current('enemy','hp')==health
 assert s.ctx.spatial.blocked_by('enemy')==s.session.world.resolve('blocker')
 assert [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']==[(14,atk-100),(71,atk-100)]
 assert len([e for e in s.session.events if e['type']=='ability.started'])==2;exact(s)
@pytest.mark.parametrize('index',[0,1])
def test_unblocked_ground_moves_without_combat_targets(index):
 s=make(fixture(index,False));s.advance(15)
 assert s.ctx.get('enemy',('spatial','position'))['col']>0 and s.ctx.spatial.blocked_by('enemy') is None
 assert not [e for e in s.session.events if e['type']=='damage.accepted'];exact(s)
def test_exact_build_and_full_accuracy_gate_remains_rejected():
 assert OUT.read_bytes()==(json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode()
 with pytest.raises(ValueError,match='born1.5'):build(require_complete=True)
@pytest.mark.parametrize('change',[lambda d:d['stages']['level_main_02-09']['resolved_variant_ids'].pop(),lambda d:next(v for v in d['variants'].values() if v['native_enemy']['native_id']=='enemy_1013_airdrp')['native_enemy'].update(native_level=1),lambda d:next(v for v in d['variants'].values() if v['native_enemy']['native_id']=='enemy_1013_airdrp')['native_enemy'].update(stage_override={'attributes':{'maxHp':0}})])
def test_wrong_stage_level_or_override_never_reuses_same_name(change):
 d=json.loads(SOURCE.read_bytes());change(d)
 with pytest.raises(ValueError):build(source=d)
def test_skill_talent_data_not_ignored():
 d=json.loads(SOURCE.read_bytes());v=next(v for v in d['variants'].values() if v['native_enemy']['native_id']=='enemy_1013_airdrp');v['native_enemy']['resolved']['skills']=[{'prefabKey':'unconsumed'}]
 with pytest.raises(ValueError):build(source=d)
