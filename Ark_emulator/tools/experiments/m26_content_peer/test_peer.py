"""Exact frozen stage content + independent C4/normal qualification witnesses."""
from pathlib import Path
from copy import deepcopy
import json,hashlib,sys
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m26_decision_eligibility_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
import ark_sim
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw,digest
from ark_sim.tools.replay import replay
from tools.campaign_streaming_evidence import observations,canonical_hash,export_events,write_canonical
PINS={'01-11':'a1a8a9091da743d0cbf966e2d44f521488f64d5dbd6d6bfe153f452d7431e215','01-12':'a68023a0ec81cc95df9ccdec452979f5131fda648dc6673b8a3e9110108e38a1'}
INPUTS=[]
def package(stage='01-11'):
 path=ROOT/f'packages/campaign/chapter01_stage_models/m26/level_main_{stage}.partial.json';raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==PINS[stage];return json.loads(raw)
def make(p):
 raw=json.dumps(p,sort_keys=True,separators=(',',':')).encode();INPUTS.append({'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'seed':2604,'document':json.loads(raw)});return Engine.create(Compiler().compile(json.loads(raw)),seed=2604)
def exact(s):
 r=Engine.restore(s.program,s.checkpoint());s.advance(2);r.advance(2);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
def fixture(targets,ready=False):
 p=package();w=next(e for e in p['entities'] if e['id']=='unit/chapter01_w')
 if ready:w['components']['resources']['c4_clock_0']['initial']=20
 initial=[{'definition':w['id'],'instanceAlias':'w','position':{'row':2,'col':0}}]
 for alias,col,motion,side,category in targets:
  uid='unit/peer/'+alias;p['entities'].append({'id':uid,'kind':'entity','tags':['player','ground' if motion==1 else 'fly'],'components':{'attributes':{'base':{'max_hp':5000,'def':0,'mres':0}},'resources':{'hp':{'initial':5000,'capacity':5000,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'selection_state':{'motion':motion,'side':side,'category':category}}})
  initial.append({'definition':uid,'instanceAlias':alias,'position':{'row':2,'col':col}})
 p['scenarioDraft']={'id':'scenario/m26_content_peer','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':5,'cols':6},'initialEntities':initial,'waves':[]};return p

def test_flying_target_c4_allowed_normal_motion_rejected_real_explosion():
 s=make(fixture([('fly',2,2,0,1)],ready=True));s.advance(115)
 starts=[e['payload']['ability'] for e in s.session.events if e['type']=='ability.started']
 assert 'ability/chapter01_w_c4_0' in starts and not any('normal' in a for a in starts)
 assert [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']==[(114,846)]
 exact(s)

@pytest.mark.parametrize('side,category',[(1,1),(0,2)])
def test_relative_side_and_category_reject_looks_player_tag(side,category):
 s=make(fixture([('invalid',2,2,side,category)],ready=True));s.advance(25)
 assert not [e for e in s.session.events if e['type'] in ('ability.started','projectile.launched','damage.accepted')];exact(s)

def test_normal_walk_qualification_excludes_closer_fly():
 s=make(fixture([('fly',1,2,0,1),('ground',2,1,0,1)]));s.advance(36)
 assert s.ctx.resources.current('fly','hp')==5000 and s.ctx.resources.current('ground','hp')==4060
 # Authored9/23 plus distance2 / speed5 =>12 motion ticks =>21/35.
 assert [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']==[(21,470),(35,470)]
 exact(s)

@pytest.mark.parametrize('stage',['01-11','01-12'])
def test_source_sparse_patches_unknowns_and_geometry_preserved(stage):
 p=package(stage);parent=json.loads((ROOT/f'packages/campaign/chapter01_stage_models/m22/level_main_{stage}.partial.json').read_bytes());compiled=Compiler().compile(p)
 units={e['id']:e for e in p['entities']};old={s['id']:s for s in parent['selectors']}
 records=p['manifest']['metadata']['m26_content']['actor_states']
 for r in records:
  state=units[r['unit']]['components']['selection_state']
  assert state=={**r['math_policy_fields'],**r['source_literal_patch']}
  assert not r['actual_client_verified']
  assert set(r['math_policy_fields']).isdisjoint(r['source_literal_patch'])
 for s in p['selectors']:
  if s['id'].startswith(('selector/chapter01_w_normal','selector/enemy_1028_mocock')):
   before=deepcopy(old[s['id']]);after=deepcopy(s);after.pop('eligibility');after.get('metadata',{}).pop('m26_source_qualification')
   if not after.get('metadata'):after.pop('metadata',None)
   if not before.get('metadata'):before.pop('metadata',None)
   assert before==after
 assert not p['manifest']['metadata']['m26_content']['native_actual_correct']
 assert 'native_enemy_target_free_abnormal_filters_and_move_attack_FSM' in p['manifest']['metadata']['pending_model_gaps']
 if stage=='01-11':
  assert units['unit/ch1_predefined_adnach_e0_l20']['components']['selection_state']['profession']==2
  assert p['manifest']['metadata']['roster_selection_profile']['selection']=='fixed12_test_override'
  assert len(p['scenarioDraft']['roster'])==12
  assert 'unit/ch1_predefined_adnach_e0_l20' not in p['scenarioDraft']['roster']
 assert len(compiled.definitions)>250

def test_stream_observations_full_snapshot_and_journal_exact(tmp_path):
 s=make(fixture([('ground',2,1,0,1)]));s.advance(30)
 result=observations(s);assert result['snapshot']==digest(s.snapshot());assert result['events']==digest(thaw(s.session.events))
 path=tmp_path/'full.events.jsonl';journal=export_events(path,s);rows=[json.loads(line) for line in path.read_bytes().splitlines()]
 assert rows==thaw(s.session.events) and journal['events']==len(rows)
 assert journal['sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
 assert [e['id'] for e in rows]==list(range(1,len(rows)+1))
 exact(s)

def test_stream_continuation_hash_includes_real_future_tasks():
 s=make(fixture([('ground',2,1,0,1)]));before=observations(s)
 s.submit({'action':'withdraw','source':'ground'},at=100)
 after=observations(s);assert before['snapshot']==after['snapshot'] and before['continuation_state']!=after['continuation_state']
 r=Engine.restore(s.program,s.checkpoint());s.advance(3);r.advance(3);assert observations(s)==observations(r)

def test_canonical_nested_values_and_write_have_no_dropped_fields(tmp_path):
 value={'z':[0,-0.0,1.25,'中文',False,None,{'operand':{'x':7,'y':[2,3]}}],'a':'\n\"'}
 expected=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
 assert canonical_hash(value)==hashlib.sha256(expected).hexdigest()
 path=tmp_path/'canonical.json';write_canonical(path,value);assert path.read_bytes()==expected+b'\n'
