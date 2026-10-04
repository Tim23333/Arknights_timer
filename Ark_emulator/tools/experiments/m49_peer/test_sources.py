import sys,json,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m49_visibility_candidate';sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.build_chapter01_enemy_sources import NativeAssets
PACKAGE=ROOT/'packages/campaign/chapter03_visibility/three_hidden_sensor.model.json';SOURCE=ROOT/'packages/campaign/chapter03_sources/native.reference.json'
def source_fixture(name,sensor=False):
 p=json.loads(PACKAGE.read_bytes());unit=next(u for u in p['entities'] if name in u['id']);p['entities'].append({'id':'unit/peer/observer','kind':'entity','tags':['player'],'components':{'spatial':{},'selection_state':{'side':0,'motion':1,'category':1},'attributes':{'base':{'max_hp':20000,'atk':140,'def':80,'mres':40,'block_count':0}},'resources':{'hp':{'initial':20000,'capacity':20000,'role':'health'}},'abilities':['ability/peer/probe']}})
 p['selectors'].append({'id':'selector/peer/probe','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'limit':1});p['abilities'].append({'id':'ability/peer/probe','kind':'ability','selector':'selector/peer/probe','activation':{'mode':'manual','parameters':{'requires_targets':True},'on_start':[{'op':'damage','damage_type':'true'}]},'timeline':[]})
 initial=[{'definition':unit['id'],'instanceAlias':'subject','position':{'row':2,'col':2}},{'definition':'unit/peer/observer','instanceAlias':'observer','position':{'row':2,'col':3}}]
 if sensor:
  unit['components']['abilities']=[];unit['components'].pop('behavior',None)
  initial.append({'definition':'unit/chapter03/trap_005_sensor','instanceAlias':'sensor','position':{'row':2,'col':1},'components':{'resources':{'sp':{'initial':15}}}})
 p['scenarioDraft']={'id':'scene/peer/source/'+name,'ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':6,'cols':8},'initialEntities':initial};return p,unit
def make(p):return Engine.create(Compiler().compile(p),seed=4957)
def test_actual_typetree_three_checker_flags_and_modes_are_not_copied_between_units():
 s=json.loads(SOURCE.read_bytes());assets=NativeAssets()
 for name,attackoff,frame in [('enemy_1009_lurker',1,12),('enemy_1019_jshoot',0,16),('enemy_1023_jmage',0,19)]:
  prefab=s['prefabs'][name];actual=assets.closure(ROOT.parent/prefab['source']['path'],name)
  toggle=next(c for c in actual['components'].values() if c['native_class']=='ToggleablePassiveBuffAbility');checker=actual['components'][str(toggle['raw']['_checker']['m_PathID'])]['raw']
  assert (checker['_disableWhenAttack'],checker['_disableWhenBlocked'],checker['_restoreDelay'])==(attackoff,1,3) and toggle['raw']['_buffs'][0]['attributes']['abnormalFlags']==[9]
  assert {k:c['raw'] for k,c in actual['components'].items()}=={k:c['raw'] for k,c in prefab['components'].items()}
  variant=next(v for v in s['variants'].values() if v['prefab_key']==name);assert [e['frame'] for e in variant['modes'][0]['nodes']['_combat']['animation_binding']['events'] if e['name']=='OnAttack']==[frame]
@pytest.mark.parametrize('name,launch,impact,amount',[('enemy_1019_jshoot',16,19,180),('enemy_1023_jmage',19,22,210)])
def test_actual_attack_zero_keeps_invisibility_after_real_physical_or_arts_packet(name,launch,impact,amount):
 p,u=source_fixture(name);s=make(p);s.submit({'action':'skill','source':'observer','ability':'ability/peer/probe'},at=impact+2);s.advance(impact+4)
 assert [e['time'] for e in s.session.events if e['type']=='projectile.launched']==[launch]
 assert [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']==[(impact,amount)]
 assert s.ctx.spatial.eligible('observer','selector/peer/probe')==[] and s.ctx.resources.current('subject','hp')==u['components']['resources']['hp']['initial']
 assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()
@pytest.mark.parametrize('name',['enemy_1019_jshoot','enemy_1023_jmage'])
def test_real_sensor15SP20seconds_reveals9_only_and_freezes_exact_skill(name):
 p,u=source_fixture(name,True);s=make(p);s.submit({'action':'skill','source':'sensor','ability':'ability/sensor/reveal'},at=2);s.submit({'action':'skill','source':'observer','ability':'ability/peer/probe'},at=601);s.submit({'action':'skill','source':'observer','ability':'ability/peer/probe'},at=602)
 s.advance(601);assert s.ctx.resources.current('sensor','sp')==0
 s.advance(3);assert s.ctx.resources.current('subject','hp')==u['components']['resources']['hp']['initial']-140
 assert [e['time'] for e in s.session.events if e['type']=='command.rejected']==[602]
 assert s.ctx.resources.current('sensor','sp')==pytest.approx(1/30)
def test_sensor_static_source_immunity_and_invincibility_have_separate_actual_consumers():
 p,_=source_fixture('enemy_1019_jshoot',True);sensor=next(u for u in p['entities'] if 'trap_005' in u['id'])
 assert sensor['components']['resources']['sp']['recovery_freeze_abilities']==['ability/sensor/reveal']
 reveal=next(b for b in p['buffs'] if b['id']=='buff/sensor/reveal_member');assert reveal['selection_flags']['abnormal_immunes']==[9]
 selfbuff=next(b for b in p['buffs'] if b['id'] in sensor['components']['buffs']['initial']);assert selfbuff['selection_flags']['abnormal_flags']==[5]

def test_sensor_invincible5_consumes_physical_arts_true_without_spurious_HP_packets():
 p,u=source_fixture('enemy_1019_jshoot',True);sensor=next(e for e in p['entities'] if 'trap_005' in e['id']);sensor['tags'].append('peer_sensor');observer=p['entities'][-1]
 p['selectors'].append({'id':'selector/peer/sensor','kind':'selector','region':{'type':'all'},'filters':[{'tag':'peer_sensor'}],'limit':1})
 for dtype in ('physical','arts','true'):
  aid='ability/peer/'+dtype;observer['components']['abilities'].append(aid);p['abilities'].append({'id':aid,'kind':'ability','selector':'selector/peer/sensor','activation':{'mode':'manual','on_start':[{'op':'damage','damage_type':dtype}]},'timeline':[]})
 s=make(p)
 for at,dtype in enumerate(('physical','arts','true')):s.submit({'action':'skill','source':'observer','ability':'ability/peer/'+dtype},at=at)
 s.advance(4);assert s.ctx.resources.current('sensor','hp')==100 and not [e for e in s.session.events if e['type']=='damage.accepted']
 assert len([e for e in s.session.events if e['type']=='damage.rejected'])==3

def test_lurker_actual_melee_dispatch_pulses_source_checker_and_release_restores90():
 p,u=source_fixture('enemy_1009_lurker');observer=p['entities'][-1];observer['components']['attributes']['base']['block_count']=1;p['scenarioDraft']['initialEntities'][1]['position']={'row':2,'col':2};p['scenarioDraft']['initialEntities'][0]['route']={'motionMode':0,'startPosition':{'row':2,'col':2},'endPosition':{'row':2,'col':7},'checkpoints':[]}
 observer['components']['deployable']={'base_cost':0,'capacity':1,'cooldown_seconds':0,'terrain':'ground'}
 p['buffs'].append({'id':'buff/peer/still','kind':'buff','control':{'move':False}});p['buffs'].append({'id':'buff/peer/preblock','kind':'buff','duration_seconds':1/30,'control':{'attack':False}})
 p['scenarioDraft']['initialEntities'][0]['components']={'buffs':{'initial':u['components']['buffs']['initial']+['buff/peer/still','buff/peer/preblock']}}
 observer['components']['abilities'].append('ability/peer/leave');p['abilities'].append({'id':'ability/peer/leave','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'retire','target':'source','parameters':{'reason':'withdrawn'}}]},'timeline':[]})
 s=make(p);s.submit({'action':'skill','source':'observer','ability':'ability/peer/leave'},at=14);s.advance(14)
 packets=[e for e in s.session.events if e['type']=='damage.accepted'];assert [(e['time'],e['payload']['amount']) for e in packets]==[(13,220)]
 parent=next(i for i in s.ctx.get('subject',('buffs','instances')) if i['definition']=='buff/lurker/controller');assert parent['toggle_state']['last_pulse']==13
 s.advance(90);assert not any(i['definition']=='buff/lurker/invisible' for i in s.ctx.get('subject',('buffs','instances')))
 s.advance(1);assert any(i['definition']=='buff/lurker/invisible' for i in s.ctx.get('subject',('buffs','instances')))
 assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()
