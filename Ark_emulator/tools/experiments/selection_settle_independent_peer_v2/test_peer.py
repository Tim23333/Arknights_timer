import json,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[3];MODULE=ROOT/'packages/campaign/chapter05_units/special/model.selection_settle.reference.json';SOURCE=ROOT/'packages/campaign/chapter05_sources/native.reference.json';INPUTS=[];CAPTURES=[]
assert hashlib.sha256(MODULE.read_bytes()).hexdigest()=='fa314fcf5e46ddcef792ced3f1f7f86cc1586d7f74e5915af305f270dff55b8d'
NATIVE=json.loads(SOURCE.read_bytes());H='enemy_1045_hammer';L='enemy_1038_lunmag'
def fixture(key,immune=False,blocked=True,sp=0):
 p=json.loads(MODULE.read_bytes());unit=next(e for e in p['entities'] if key in e['id']);guard={'id':'unit/peer/guard','kind':'entity','tags':['player','ground'],'components':{'attributes':{'base':{'max_hp':10000,'atk':0,'def':37,'mres':25,'block_count':1 if blocked else 0}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1,'abnormal_immunes':[0] if immune else []},'spatial':{},'deployable':{'base_cost':0,'capacity':1,'cooldown_seconds':0,'terrain':'ground'},'abilities':['ability/peer/immune_damage'],'lifecycle':{'policy':'policy/ark_lifecycle'}}};p['entities'].append(guard)
 p['buffs'].append({'id':'buff/peer/immune_damage','kind':'buff','duration_seconds':1,'active_rule':'rule/peer/active','damage_hooks':[{'phase':'after','rule':'rule/peer/reject'}]});p['rules'].extend([{'id':'rule/peer/active','kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':'True'}},{'id':'rule/peer/reject','kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'answer','expression':"{'accepted':False,'amount':0,'allocations':[],'events':[]}"}],'output':'nodes.answer'}}]);p['abilities'].append({'id':'ability/peer/immune_damage','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':'source','buff':'buff/peer/immune_damage'}]},'timeline':[]})
 actor={'definition':unit['id'],'instanceAlias':'enemy','position':{'row':1,'col':1}}
 if blocked:actor['route']={'motionMode':0,'startPosition':{'row':1,'col':1},'endPosition':{'row':1,'col':6},'checkpoints':[]}
 if key==H:actor['components']={'resources':{'sp':{'initial':sp}}}
 p['scenarioDraft']={'id':'scene/peer/ch5_special','ruleset':'ruleset/ark_standard','map':{'rows':4,'cols':8},'objectives':{'life_resource':'life'},'resources':{'life':{'initial':99999,'capacity':99999},'dp':{'initial':25,'capacity':99}},'initialEntities':[actor,{'definition':guard['id'],'instanceAlias':'guard','position':{'row':1,'col':1 if blocked else 2}}]}
 return p
def make(p):INPUTS.append(deepcopy(p));return Engine.create(Compiler().compile(p),seed=551038)
def ev(s,t):return [thaw(e) for e in s.session.events if e['type']==t]
def capture(s,label):CAPTURES.append({'case':label,'events':thaw(tuple(s.session.events)),'snapshot':s.snapshot(),'commands':s.export_replay()})
def exact(s,tmp,n):
 h=write_ordered(tmp/'cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp/'cp.json',h));s.advance(n);r.advance(n);assert s.checkpoint()==r.checkpoint() and s.snapshot()==replay(s.program,s.export_replay()).snapshot()
def test_actual_variants_frames_and_shared_lunmag_pptr_are_unique():
 p=json.loads(MODULE.read_bytes());assert len(p['entities'])==2
 for key,frame in [(H,28),(L,21)]:
  v=next(v for v in NATIVE['variants'].values() if v['native_enemy']['native_id']==key);u=next(e for e in p['entities'] if e['metadata']['native_variant_id']==v['variant_id']);a=v['native_enemy']['resolved']['attributes'];base=u['components']['attributes']['base'];assert [base['max_hp'],base['atk'],base['def'],base['mres']]==[a['maxHp'],a['atk'],a['def'],a['magicResistance']]
  assert v['modes'][0]['nodes']['_combat']['animation_binding']['events'][0]['frame']==frame
  if key==L:assert v['modes'][0]['raw']['_combat']['m_PathID']==v['modes'][0]['raw']['_attack']['m_PathID']==4029926580866268503
@pytest.mark.parametrize('immune',[False,True])
def test_hammer_actual_sp_cost_before_skill_hit_then_one_recovery_and_stun_applicability(immune,tmp_path):
 s=make(fixture(H,immune));s.advance(212);assert s.ctx.resources.current('enemy','sp')==0
 exact(s,tmp_path,28);capture(s,'hammer_sp_stun_'+str(immune))
 starts=[e for e in ev(s,'ability.started') if e['payload']['source']==2];assert [e['time'] for e in starts]==[1,106,211] and starts[-1]['payload']['ability'].endswith('/stun')
 assert [e['time'] for e in ev(s,'damage.accepted')]==[29,134,239] and all(e['payload']['amount']==963 for e in ev(s,'damage.accepted'))
 assert s.ctx.resources.current('enemy','sp')==1 and len(ev(s,'attack.accepted'))==3
 stun=next(b for b in s.ctx.get('guard',('buffs','instances')) if b['definition']=='buff/ch5/special/hammer_stun');assert stun['expires_at']==449
 assert s.ctx.buffs.controls('guard')['block'] is immune
def test_hammer_skill_rejected_damage_does_not_apply_stun_or_award_attack_sp(tmp_path):
 s=make(fixture(H,sp=2));s.submit({'action':'skill','source':'guard','ability':'ability/peer/immune_damage'},at=120);s.advance(107);assert s.ctx.resources.current('enemy','sp')==0
 exact(s,tmp_path,29);capture(s,'hammer_damage_immune')
 assert [e['time'] for e in ev(s,'damage.accepted')]==[29] and s.ctx.resources.current('enemy','sp')==0
 assert not any(b['definition']=='buff/ch5/special/hammer_stun' for b in s.ctx.get('guard',('buffs','instances')))
def test_lunmag_unblocked_range2_attack_trigger_must_produce_one_ranged_packet(tmp_path):
 s=make(fixture(L,blocked=False));s.advance(22);exact(s,tmp_path,5);capture(s,'lunmag_unblocked')
 assert len(ev(s,'damage.accepted'))==1 and ev(s,'damage.accepted')[0]['time']==24 and ev(s,'damage.accepted')[0]['payload']['amount']==300
def test_lunmag_actual_input_blocker_ignores_extreme_unrelated_taunt_and_one_payload(tmp_path):
 p=fixture(L,blocked=True);other=deepcopy(p['scenarioDraft']['initialEntities'][1]);other['instanceAlias']='other';other['position']={'row':2,'col':1};other['components']={'attributes':{'base':{'taunt_level':1000000000,'block_count':0}}};p['scenarioDraft']['initialEntities'].append(other)
 s=make(p);s.advance(3);assert s.ctx.spatial.blocked_by('enemy')==s.session.world.resolve('guard');exact(s,tmp_path,24);capture(s,'lunmag_blocked_taunt')
 packets=ev(s,'damage.accepted');assert len(packets)==1 and packets[0]['payload']['target']==s.session.world.resolve('guard') and packets[0]['payload']['amount']==300
 assert len(ev(s,'projectile.launched'))==1
def test_lunmag_unselectable_input_blocker_has_no_fallback_to_legal_neighbor():
 p=fixture(L,blocked=True);p['scenarioDraft']['initialEntities'][1]['components']={'selection_state':{'target_free':True}};other=deepcopy(p['scenarioDraft']['initialEntities'][1]);other['instanceAlias']='other';other['position']={'row':2,'col':1};other['components']={'attributes':{'base':{'block_count':0,'taunt_level':1000000000}}};p['scenarioDraft']['initialEntities'].append(other)
 s=make(p);s.advance(30);capture(s,'lunmag_free_blocker');assert s.ctx.spatial.blocked_by('enemy')==s.session.world.resolve('guard') and not ev(s,'damage.accepted')
