"""Actual birth pause/expiry controls with source45tick delay, HP unchanged."""
from pathlib import Path
import sys,json,hashlib
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m37_projectile_refs_candidate';sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.build_chapter02_airdrp_birth import build,OUT
from test_units import fixture as post_born_fixture
INPUTS=[]
def fixture(index,policy='targetable',cost=0):
 post=post_born_fixture(index);birth=build(policy,cost);birth['entities'].append(post['entities'][-1]);birth['scenarioDraft']=post['scenarioDraft'];birth['scenarioDraft']['id']+='/birth45';return birth
def make(p):
 raw=json.dumps(p,separators=(',',':')).encode();INPUTS.append({'sha256':hashlib.sha256(raw).hexdigest(),'seed':20902,'document':json.loads(raw)});return Engine.create(Compiler().compile(json.loads(raw)),seed=20902)
def exact(s):
 r=Engine.restore(s.program,s.checkpoint());s.advance(2);r.advance(2);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
@pytest.mark.parametrize('index,hp,damage',[(0,1450,120),(1,2300,200)])
def test_source_45_birth_frame_is_half_open_and_first_attack_after_expiry(index,hp,damage):
 s=make(fixture(index));s.advance(45)
 assert s.ctx.resources.current('enemy','hp')==hp and s.ctx.get('enemy',('spatial','position'))=={'row':0,'col':0}
 assert not [e for e in s.session.events if e['type'] in ('ability.started','damage.accepted','enemy.birth_phase_finished')]
 r=Engine.restore(s.program,s.checkpoint());s.advance(15);r.advance(15)
 assert [e['time'] for e in s.session.events if e['type']=='enemy.birth_phase_finished']==[45]
 # Grid path appears at45, actual blocking then combat starts46, sourcef13->59.
 assert [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']==[(59,damage)]
 assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
def test_temporary_zero_cost_does_not_consume_blocker_capacity_and_restores_real_volume():
 s=make(fixture(0));s.advance(45)
 before=[e['payload']['value'] for e in s.session.events if e['type']=='calculation' and e['payload'].get('calculation_id')=='blocking.occupancy'];assert before and set(before)=={0}
 s.advance(1);at45=[e['payload']['value'] for e in s.session.events if e['type']=='calculation' and e['time']==45 and e['payload'].get('calculation_id')=='blocking.occupancy'];assert at45 and set(at45)=={1};exact(s)
def test_public_manual_source_command_cannot_bypass_birth_controls():
 p=fixture(0);unit=p['entities'][0];unit['components']['abilities'].append('ability/probe');p['abilities'].append({'id':'ability/probe','kind':'ability','activation':{'mode':'manual'},'timeline':[]})
 s=make(p);s.submit({'action':'skill','source':'enemy','ability':'ability/probe'},at=44);s.submit({'action':'skill','source':'enemy','ability':'ability/probe'},at=45);s.advance(46)
 assert [(e['time'],e['type']) for e in s.session.events if e['type'] in ('command.accepted','command.rejected')]==[(44,'command.rejected'),(45,'command.accepted')];exact(s)
def test_target_free_is_explicit_eligibility_policy_not_global_visibility_claim():
 p=fixture(0,'target_free_eligibility');p['entities'][0]['components']['selection_state']={'side':1,'motion':1,'category':1}
 # Independent custom qualification contract reads projected live targetfree state.
 p['rules'].append({'id':'rule/targetable','kind':'rule','contract':'targeting.eligibility','implementation':{'type':'expression','expression':"{'accepted':not inputs.selection_states.candidate.target_free,'reason':'explicit_birth_policy'}"}})
 default={'side':0,'motion':1,'category':1,'profession':0,'unit_type':1,'abnormal_flags':[],'abnormal_combos':[],'target_free_flags':[],'target_free_combos':[],'target_free':False,'ally_target_free':False,'heal_free':False,'camouflage':False,'can_select_camouflage':False}
 qualified=json.loads((ROOT/'packages/campaign/selector_eligibility/m25.source_profiles.json').read_bytes());raw_config=qualified['selectors'][0]['eligibility']['parameters']['source_configuration']
 p['selectors'].append({'id':'selector/probe','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'eligibility':{'rule':'rule/targetable','parameters':{'source_configuration':raw_config,'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':default}}});p['entities'][-1]['dependencies']=['selector/probe'];s=make(p);before=s.checkpoint()
 assert s.ctx.spatial.eligible('blocker','selector/probe')==[] and s.checkpoint()==before
 s.advance(46);assert s.ctx.spatial.eligible('blocker','selector/probe')==[s.session.world.resolve('enemy')];exact(s)
def test_explicit_policy_and_frozen_birth_build():
 assert OUT.read_bytes()==(json.dumps(build('targetable',0),ensure_ascii=False,indent=2)+'\n').encode()
 with pytest.raises(ValueError,match='explicit'):build(None,0)
 with pytest.raises(ValueError,match='explicit'):build('targetable',False)
