import json
from pathlib import Path
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[3];INPUTS=[];CAPTURES=[]
def fixture(state=None,tag='ground',facing='right'):
 p=json.loads((ROOT/'packages/campaign/chapter06_npcs/swllow.v2.model.json').read_bytes());npc=p['entities'][0]['id']
 enemy={'id':'unit/peer/target','kind':'entity','tags':['enemy',tag],'components':{'attributes':{'base':{'max_hp':10000,'atk':0,'def':31,'mres':0,'move_speed':0}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'selection_state':{'side':1,'motion':2 if tag=='flying' else 1,'category':1,'unit_type':1,**(state or {})},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}}
 p['entities'].append(enemy);p['controls']=[{'id':'control/peer/activate','kind':'control','clock_policy':'logical','ack_policy':'external','steps':[{'kind':'ack','key':'native_activation'},{'kind':'effects','effects':[{'op':'activate_predefined','target':'battle','parameters':{'key':'char_367_swllow'}}]}]}]
 p['scenarioDraft']={'id':'scene/independent/native_npc','ruleset':'ruleset/ark_standard','map':{'rows':4,'cols':5},'parameters':{'deploy_capacity':0},'resources':{'life':{'initial':1,'capacity':1},'dp':{'initial':0,'capacity':99,'recovery_rate':1/9999,'recovery':{'mode':'periodic','interval_seconds':9999}}},'objectives':{},'initialEntities':[{'definition':npc,'instanceAlias':'native_actor','active':False,'registration_key':'char_367_swllow','position':{'row':2,'col':2},'facing':facing},{'definition':enemy['id'],'instanceAlias':'target','position':{'row':2,'col':3 if facing=='right' else 1}}],'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'fragments':[{'actions':[{'kind':'control','definition':'control/peer/activate','instanceAlias':'native_activation','managed':True,'blocks_wave':True,'blocks_fragment':True}]}]}]}}
 return p
def make(p):INPUTS.append(deepcopy(p));return Engine.create(Compiler().compile(p),seed=6461)
def ev(s,t):return [thaw(e) for e in s.session.events if e['type']==t]
def capture(s,k):CAPTURES.append({'case':k,'events':thaw(tuple(s.session.events)),'commands':s.export_replay(),'snapshot':s.snapshot(),'checkpoint':s.checkpoint()})
def activate(s,t=20):s.submit({'action':'control_ack','control':'native_activation','step':0},at=t)
def test_true_hidden_npc_has_no_behavior_before_activation_and_no_fabricated_skill_sp(tmp_path):
 s=make(fixture());activate(s);s.advance(19);assert not ev(s,'ability.started') and not ev(s,'projectile.launched') and not ev(s,'random.sampled') and not s.session.random.snapshot()['samples']
 ref=s.session.world.resolve('native_actor');cp=tmp_path/'dormant.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,h));s.advance(101);r.advance(101);head=replay(s.program,s.export_replay());capture(s,'dormant_public_activation')
 assert s.checkpoint()==r.checkpoint()==head.checkpoint() and thaw(tuple(s.session.events))==thaw(tuple(head.session.events))
 assert s.session.world.resolve('native_actor')==ref and s.ctx.active(ref) and 'sp' not in s.ctx.get(ref,('resources',))
 assert s.ctx.get(ref,('abilities',))==['ability/ch6/npc/swllow_normal'] and s.ctx.get(ref,('attributes','base'))['max_hp']==1306
def test_actual_source_motion_three_admits_flying_target():
 s=make(fixture(tag='flying'));activate(s,1);s.advance(50);capture(s,'flying_target')
 assert ev(s,'damage.accepted')
@pytest.mark.parametrize('state',[{'target_free':True},{'camouflage':True}])
def test_native_zero_ignore_flags_reject_unselectable_target(state):
 s=make(fixture(state));activate(s,1);s.advance(50);capture(s,'free_target_'+repr(state));assert not ev(s,'ability.started') and not ev(s,'damage.accepted')
@pytest.mark.parametrize('face',['right','left'])
def test_real_facing_range_and_one_crit_draw_per_accepted_single_projectile_packet(face):
 s=make(fixture(facing=face));activate(s,1);s.advance(80);capture(s,'facing_'+face);hits=ev(s,'damage.accepted');launches=ev(s,'projectile.launched')
 assert hits and len(hits)==len(launches) and all(e['payload']['amount'] in [417,641] for e in hits)
 # Derive actual decisions from the recorded imp samples; no forced seed/procs.
 samples=[e for e in s.session.random.snapshot()['samples'] if e['stream']=='imp']
 assert len(samples)==len(hits)
 assert [e['payload']['amount'] for e in hits]==[641 if e['value']<.15 else 417 for e in samples]
