import json,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[3];MODULE=ROOT/'packages/campaign/chapter05_boss/mephi/model.json';REGEN=ROOT/'packages/campaign/chapter05_units/regenerating/model.json';SOURCE=ROOT/'packages/campaign/chapter05_sources/native.reference.json';INPUTS=[];CAPTURES=[]
assert hashlib.sha256(MODULE.read_bytes()).hexdigest()=='c96480241c8bff878e0017525606dbdede7a42d2d06a16b49893d8c0a4ce3fe1'
UID='unit/ch5/mephi/6468197a2a582f8b';HEAL='ability/ch5/mephi/normal_heal';MEMBER='buff/ch5/mephi/mephi_t_healaura'
def ally():return {'id':'unit/peer/nonmutant','kind':'entity','tags':['enemy','plain_probe'],'components':{'attributes':{'base':{'max_hp':2000,'atk':0,'hp_recovery_per_sec':10}},'resources':{'hp':{'initial':100,'capacity_attribute':'max_hp','role':'health','recovery':{'mode':'continuous'},'recovery_rule':'rule/ch5/regen/hp_recovery','parameters':{'pause_at_full':True}}},'selection_state':{'side':1,'motion':1,'category':1,'unit_type':2},'spatial':{},'abilities':[],'lifecycle':{'policy':'policy/ark_lifecycle'}}}
def fixture(dormant=False):
 p=json.loads(MODULE.read_bytes());r=json.loads(REGEN.read_bytes())
 for key in ['entities','abilities','selectors','rules','behaviors']:p.setdefault(key,[]).extend(r.get(key,[]))
 small=next(e['id'] for e in r['entities'] if 'enemy_1043_zomsbr' in e['id']);large=next(e['id'] for e in r['entities'] if 'enemy_1044_zomstr' in e['id']);p['entities'].append(ally())
 director={'id':'unit/peer/director','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':10000,'atk':100}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'spatial':{},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'abilities':['ability/peer/boost','ability/peer/retire_small','ability/peer/kill','ability/peer/external','ability/peer/activate'],'lifecycle':{'policy':'policy/ark_lifecycle'}}};p['entities'].append(director)
 p.setdefault('buffs',[]).append({'id':'buff/peer/boost','kind':'buff','modifiers':[{'attribute':'atk','layer':'flat','value':100}]})
 p['abilities'].extend([{'id':'ability/peer/'+name,'kind':'ability','activation':{'mode':'manual','on_start':[effect]},'timeline':[]} for name,effect in [('boost',{'op':'apply_buff','target':2,'buff':'buff/peer/boost'}),('retire_small',{'op':'retire','target':3,'parameters':{'reason':'withdrawn'}}),('kill',{'op':'damage','target':2,'damage_type':'true','scale':1000}),('external',{'op':'apply_buff','target':4,'buff':MEMBER}),('activate',{'op':'activate_predefined','target':'battle','parameters':{'key':'mephi'}})]])
 initial=[{'definition':UID,'instanceAlias':'mephi','position':{'row':1,'col':1},'components':{'resources':{'hp':{'initial':5000}}}},{'definition':small,'instanceAlias':'small','position':{'row':1,'col':2},'components':{'resources':{'hp':{'initial':100}}}},{'definition':large,'instanceAlias':'large','position':{'row':2,'col':1},'components':{'resources':{'hp':{'initial':2000}}}},{'definition':'unit/peer/nonmutant','instanceAlias':'plain','position':{'row':1,'col':3}},{'definition':director['id'],'instanceAlias':'director','position':{'row':8,'col':35}}]
 if dormant:initial[0].update(active=False,registration_key='mephi')
 else:
  director['components']['abilities'].remove('ability/peer/activate');p['abilities']=[a for a in p['abilities'] if a['id']!='ability/peer/activate']
 p['scenarioDraft']={'id':'scene/peer/mephi','ruleset':'ruleset/ark_standard','map':{'rows':10,'cols':40},'objectives':{'life_resource':'life'},'resources':{'life':{'initial':99999,'capacity':99999}},'initialEntities':initial}
 return p
def make(p):INPUTS.append(deepcopy(p));return Engine.create(Compiler().compile(p),seed=51507)
def ev(s,t):return [thaw(e) for e in s.session.events if e['type']==t]
def capture(s,label):CAPTURES.append({'case':label,'events':thaw(tuple(s.session.events)),'commands':s.export_replay(),'snapshot':s.snapshot()})
def exact(s,tmp,n):
 h=write_ordered(tmp/'cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp/'cp.json',h));s.advance(n);r.advance(n);assert s.checkpoint()==r.checkpoint() and s.snapshot()==replay(s.program,s.export_replay()).snapshot()
def test_source_heal33_max3_same_pointer_and_actual_bb_multiplier():
 p=json.loads(MODULE.read_bytes());s=json.loads(SOURCE.read_bytes());v=next(v for v in s['variants'].values() if v['native_enemy']['native_id']=='enemy_1507_mephi');m=v['modes'][0]
 assert m['nodes']['_combat']['path_id']==m['nodes']['_attack']['path_id'];assert [e['frame'] for e in m['nodes']['_attack']['animation_binding']['events']]==[33]
 a=v['native_enemy']['resolved']['attributes'];base=p['entities'][0]['components']['attributes']['base'];assert [base['max_hp'],base['atk'],base['def'],base['mres'],base['attack_interval']]==[a['maxHp'],a['atk'],a['def'],a['magicResistance'],a['baseAttackTime']]==[28000,500,200,60,6]
 assert v['native_enemy']['resolved']['talentBlackboard']==[{'key':'healaura.hp_recovery_per_sec','value':1.0,'valueStr':None}]
@pytest.mark.parametrize('boost,amount',[(False,500),(True,600)])
def test_lowest3_capture_self_allowed_live_source_attack_and_global_nonmutant_rate(boost,amount,tmp_path):
 s=make(fixture())
 if boost:s.submit({'action':'skill','source':'director','ability':'ability/peer/boost'},at=20)
 s.advance(30);exact(s,tmp_path,4);capture(s,'lowest3_'+str(boost))
 heals=ev(s,'healing.accepted');assert len(heals)==3 and {e['payload']['target'] for e in heals}=={2,3,5} and all(e['time']==33 and e['payload']['amount']==pytest.approx(amount,abs=1e-10) for e in heals)
 assert s.ctx.resources.current('small','hp')==pytest.approx(100+34*160/30+amount,abs=1e-7)
 assert s.ctx.resources.current('large','hp')==pytest.approx(2000+34*400/30,abs=1e-7)
 assert s.ctx.resources.current('plain','hp')==pytest.approx(100+34*20/30+amount,abs=1e-7)
 assert s.ctx.resources.current('mephi','hp')==5000+amount
def test_captured_target_withdrawal_has_no_fourth_target_replacement(tmp_path):
 s=make(fixture());s.submit({'action':'skill','source':'director','ability':'ability/peer/retire_small'},at=20);s.advance(15);exact(s,tmp_path,20);capture(s,'captured_dies')
 assert {e['payload']['target'] for e in ev(s,'healing.accepted')}=={2,5};assert s.ctx.resources.current('large','hp')==pytest.approx(2000+35*400/30,abs=1e-7)
 assert not s.ctx.active('small')
def test_mephi_death_removes_owned_members_but_preserves_external_same_definition(tmp_path):
 s=make(fixture());s.submit({'action':'skill','source':'director','ability':'ability/peer/external'},at=1);s.submit({'action':'skill','source':'director','ability':'ability/peer/kill'},at=10);s.advance(5);exact(s,tmp_path,11);capture(s,'owned_aura_external')
 assert not s.ctx.active('mephi') and not ev(s,'healing.accepted')
 rows=[b for b in s.ctx.get('large',('buffs','instances')) if b['definition']==MEMBER];assert len(rows)==1 and rows[0]['source']==s.session.world.resolve('director') and not rows[0].get('aura_parent')
 # One Mephi contributes +1 until death; the independent external contribution
 # remains +1. Tick0 has400, ticks1..9 have600, ticks10..15 have400.
 assert s.ctx.resources.current('large','hp')==pytest.approx(2000+(400+9*600+6*400)/30,abs=1e-7)
 assert not any(b.get('aura_parent') for alias in ['small','large','plain'] for b in s.ctx.get(alias,('buffs','instances')))
def test_dormant_source_has_no_aura_then_activation_and_true_death_switch_live_rates(tmp_path):
 p=fixture(True);p['scenarioDraft']['initialEntities'][0]['components']['resources']['hp']['initial']=28000
 s=make(p);s.submit({'action':'skill','source':'director','ability':'ability/peer/activate'},at=5);s.submit({'action':'skill','source':'director','ability':'ability/peer/kill'},at=12);s.advance(4);assert not any(b['definition']==MEMBER for b in s.ctx.get('large',('buffs','instances')))
 exact(s,tmp_path,12);capture(s,'dormant_aura_interval');assert not s.ctx.active('mephi')
 assert s.ctx.resources.current('large','hp')==pytest.approx(2000+(5*200+7*400+4*200)/30,abs=1e-7)
 assert not any(b['definition']==MEMBER for b in s.ctx.get('large',('buffs','instances')))
