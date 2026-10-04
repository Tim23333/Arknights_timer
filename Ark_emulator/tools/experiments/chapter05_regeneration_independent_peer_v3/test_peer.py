import json,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[3];MODULE=ROOT/'packages/campaign/chapter05_units/regenerating/model.json';SOURCE=ROOT/'packages/campaign/chapter05_sources/native.reference.json';INPUTS=[];CAPTURES=[]
assert hashlib.sha256(MODULE.read_bytes()).hexdigest()=='6c4cb6a264b3f66a7d084070b67ea0bf25020d2fe2fe5a1d46c61a4a46e5e01b'
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()=='323baee04eca79f6e750cf45d460ffe678667c1614763814436402e8187badd5'
NATIVE=json.loads(SOURCE.read_bytes());VARIANTS={v['native_enemy']['native_id']:v for v in NATIVE['variants'].values() if v['native_enemy']['native_id'] in ['enemy_1044_zomstr','enemy_1043_zomsbr']};KEYS=list(VARIANTS)
def source(key):return VARIANTS[key]['native_enemy']['resolved']['attributes']
def fixture(key,hp=1000,dormant=False,block=False):
 p=json.loads(MODULE.read_bytes());enemy=next(e for e in p['entities'] if e['metadata']['native_variant_id']==VARIANTS[key]['variant_id']);aid='ability/peer/cost';enemy['components']['abilities'].append(aid)
 director={'id':'unit/peer/director','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':10000,'atk':40,'def':37,'mres':0,'block_count':1 if block else 0}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'abilities':['ability/peer/boost','ability/peer/shrink','ability/peer/expand','ability/peer/hit','ability/peer/kill','ability/peer/retire','ability/peer/activate'],'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}};p['entities'].append(director)
 p['buffs']=[{'id':'buff/peer/regen','kind':'buff','duration_seconds':.1,'active_rule':'rule/peer/active','modifiers':[{'attribute':'hp_recovery_per_sec','layer':'flat','value':100}]},{'id':'buff/peer/cap','kind':'buff','modifiers':[{'attribute':'max_hp','layer':'flat','value':1200-source(key)['maxHp']}]}]
 p['rules'].append({'id':'rule/peer/active','kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':'True'}})
 p['abilities'].extend([{'id':'ability/peer/'+name,'kind':'ability','activation':{'mode':'manual','on_start':[effect]},'timeline':[]} for name,effect in [('boost',{'op':'apply_buff','target':2,'buff':'buff/peer/regen'}),('shrink',{'op':'apply_buff','target':2,'buff':'buff/peer/cap'}),('expand',{'op':'remove_buff','target':2,'buff':'buff/peer/cap'}),('hit',{'op':'damage','target':2,'damage_type':'true','scale':1}),('kill',{'op':'damage','target':2,'damage_type':'true','scale':1000}),('retire',{'op':'retire','target':2,'parameters':{'reason':'withdrawn'}}),('activate',{'op':'activate_predefined','target':'battle','parameters':{'key':'dormant'}})]])
 p['abilities'].append({'id':aid,'kind':'ability','activation':{'mode':'manual','costs':[{'resource':'hp','amount':10}],'on_start':[{'op':'emit','event':'peer.cost_paid'}]},'timeline':[]})
 item={'definition':enemy['id'],'instanceAlias':'enemy','position':{'row':1,'col':1},'components':{'resources':{'hp':{'initial':hp}}}}
 if dormant:item.update(active=False,registration_key='dormant')
 else:
  director['components']['abilities'].remove('ability/peer/activate')
  p['abilities']=[a for a in p['abilities'] if a['id']!='ability/peer/activate']
 if block:
  item['route']={'motionMode':0,'startPosition':{'row':1,'col':1},'endPosition':{'row':1,'col':5},'checkpoints':[]}
  director['components']['deployable']={'base_cost':0,'capacity':1,'cooldown_seconds':0,'terrain':'ground'}
 p['scenarioDraft']={'id':'scene/peer/regen','ruleset':'ruleset/ark_standard','map':{'rows':4,'cols':7},'objectives':{'life_resource':'life'},'resources':{'life':{'initial':99999,'capacity':99999}},'initialEntities':[item,{'definition':director['id'],'instanceAlias':'director','position':{'row':1,'col':1} if block else {'row':3,'col':6}}]}
 return p
def make(p):INPUTS.append(deepcopy(p));return Engine.create(Compiler().compile(p),seed=510510)
def ev(s,t):return [thaw(e) for e in s.session.events if e['type']==t]
def capture(s,label):CAPTURES.append({'case':label,'events':thaw(tuple(s.session.events)),'commands':s.export_replay(),'snapshot':s.snapshot()})
def exact(s,tmp,n):
 h=write_ordered(tmp/'checkpoint.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp/'checkpoint.json',h));s.advance(n);r.advance(n)
 assert s.checkpoint()==r.checkpoint() and s.snapshot()==replay(s.program,s.export_replay()).snapshot()
def test_source_variants_frames_and_stage_counts_are_exact_and_not_plain_substitution():
 assert len(VARIANTS)==2;p=json.loads(MODULE.read_bytes());bindings=p['manifest']['metadata']['variant_bindings'];assert {b['variant_id'] for b in bindings}=={v['variant_id'] for v in VARIANTS.values()}
 for key,v in VARIANTS.items():
  a=source(key);entity=next(e for e in p['entities'] if e['metadata']['native_variant_id']==v['variant_id']);base=entity['components']['attributes']['base']
  assert [base['max_hp'],base['atk'],base['def'],base['mres'],base['hp_recovery_per_sec']]==[a['maxHp'],a['atk'],a['def'],a['magicResistance'],a['hpRecoveryPerSec']]
  combat=v['modes'][0]['nodes']['_combat'];assert combat['native_class']=='MeleeAttack' and combat['raw']['_selectTargetSource']==2
  events=combat['animation_binding']['events'];assert len(events)==1 and events[0]['frame']==(26 if key=='enemy_1044_zomstr' else 12)
  assert not v['passive_and_skill_components'] and not v['modes'][0]['nodes']['_attack'].get('native_class')
 plan=json.loads((ROOT/'packages/campaign/chapter05_plans/source.plan.json').read_bytes());assert plan['stages']['level_main_05-09']['spawn_by_key']['enemy_1044_zomstr']==10
 assert plan['stages']['level_main_05-10']['spawn_by_key']['enemy_1044_zomstr']==22 and plan['stages']['level_main_05-10']['spawn_by_key']['enemy_1043_zomsbr']==44
@pytest.mark.parametrize('key',KEYS)
def test_independent_7_then23_quantum_hp_integral_and_disk_resume(key,tmp_path):
 rate=source(key)['hpRecoveryPerSec'];s=make(fixture(key,hp=913));s.advance(7);assert s.ctx.resources.current('enemy','hp')==pytest.approx(913+7*rate/30,abs=1e-8)
 exact(s,tmp_path,23);capture(s,'integral_'+key);assert s.ctx.resources.current('enemy','hp')==pytest.approx(913+rate,abs=1e-8)
 assert not ev(s,'healing.accepted') and not ev(s,'regeneration.accepted')
@pytest.mark.parametrize('key',KEYS)
def test_dynamic_regen_buff_half_open3ticks_is_live_and_does_not_change_other_rate(key,tmp_path):
 rate=source(key)['hpRecoveryPerSec'];s=make(fixture(key));s.submit({'action':'skill','source':'director','ability':'ability/peer/boost'},at=5);s.advance(7);exact(s,tmp_path,3);capture(s,'buff_regen_'+key)
 assert s.ctx.resources.current('enemy','hp')==pytest.approx(1000+10*rate/30+10,abs=1e-8)
 assert not s.ctx.get('enemy',('buffs','instances'))
@pytest.mark.parametrize('key',KEYS)
def test_dynamic_capacity_shrink_clamps_then_expand_resumes_preserving_absolute_hp(key,tmp_path):
 rate=source(key)['hpRecoveryPerSec'];s=make(fixture(key,hp=1199.5));s.submit({'action':'skill','source':'director','ability':'ability/peer/shrink'},at=3);s.submit({'action':'skill','source':'director','ability':'ability/peer/expand'},at=5)
 s.advance(5);assert s.ctx.resources.current('enemy','hp')==1200;exact(s,tmp_path,2);capture(s,'capacity_'+key)
 assert s.ctx.resources.current('enemy','hp')==pytest.approx(1200+2*rate/30,abs=1e-8)
 assert s.ctx.get('enemy',('resources','hp','observed_capacity'))==source(key)['maxHp']
@pytest.mark.parametrize('key,accepted_at',[('enemy_1044_zomstr',1),('enemy_1043_zomsbr',2)])
def test_public_hp_cost_checks_before_same_tick_regeneration_not_after_it(key,accepted_at,tmp_path):
 rate=source(key)['hpRecoveryPerSec'];s=make(fixture(key,hp=5))
 for tick in [0,1,2]:s.submit({'action':'skill','source':'enemy','ability':'ability/peer/cost'},at=tick)
 s.advance(1);exact(s,tmp_path,2);capture(s,'same_tick_cost_'+key)
 accepted=[e for e in ev(s,'command.accepted') if e['payload']['action']['ability']=='ability/peer/cost'];assert [e['time'] for e in accepted]==[accepted_at]
 assert s.ctx.resources.current('enemy','hp')==pytest.approx(5+3*rate/30-10,abs=1e-8)
@pytest.mark.parametrize('key',KEYS)
@pytest.mark.parametrize('lethal',[False,True])
def test_same_tick_true_damage_is_before_regen_and_zero_health_never_recovers(key,lethal,tmp_path):
 rate=source(key)['hpRecoveryPerSec'];s=make(fixture(key,hp=80));s.submit({'action':'skill','source':'director','ability':'ability/peer/'+('kill' if lethal else 'hit')},at=0);s.advance(1)
 if lethal:assert not s.ctx.alive('enemy') and s.ctx.resources.current('enemy','hp')==0
 else:assert s.ctx.resources.current('enemy','hp')==pytest.approx(40+rate/30,abs=1e-8)
 exact(s,tmp_path,3);capture(s,'damage_'+key+'_'+str(lethal))
 if lethal:assert s.ctx.resources.current('enemy','hp')==0 and s.ctx.state()['kills']==1
 else:assert s.ctx.resources.current('enemy','hp')==pytest.approx(40+4*rate/30,abs=1e-8)
@pytest.mark.parametrize('key',KEYS)
def test_dormant_public_activation_has_no_catchup_and_source_withdraw_stops_regen(key,tmp_path):
 rate=source(key)['hpRecoveryPerSec'];s=make(fixture(key,dormant=True));s.submit({'action':'skill','source':'director','ability':'ability/peer/activate'},at=5);s.submit({'action':'skill','source':'director','ability':'ability/peer/retire'},at=8)
 s.advance(5);assert not s.ctx.active('enemy') and s.ctx.resources.current('enemy','hp')==1000;exact(s,tmp_path,7);capture(s,'dormant_withdraw_'+key)
 assert not s.ctx.active('enemy') and s.ctx.resources.current('enemy','hp')==pytest.approx(1000+3*rate/30,abs=1e-8)
@pytest.mark.parametrize('key',KEYS)
def test_actual_blocked_combat_damage_uses_single_native_frame_and_regens_during_windup(key,tmp_path):
 s=make(fixture(key,block=True));s.advance(3);assert s.ctx.spatial.blocked_by('enemy')==s.session.world.resolve('director');exact(s,tmp_path,30);capture(s,'melee_'+key)
 ref=s.session.world.resolve('enemy');start=next(e for e in ev(s,'ability.started') if e['payload']['source']==ref);packets=[e for e in ev(s,'damage.accepted') if e['payload']['source']==ref];assert len(packets)==1
 frame=VARIANTS[key]['modes'][0]['nodes']['_combat']['animation_binding']['events'][0]['frame'];assert packets[0]['time']-start['time']==frame and packets[0]['payload']['amount']==source(key)['atk']-37
 assert s.ctx.resources.current('enemy','hp')==pytest.approx(1000+33*source(key)['hpRecoveryPerSec']/30,abs=1e-8)
