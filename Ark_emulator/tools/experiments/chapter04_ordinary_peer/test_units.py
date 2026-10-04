import json,hashlib,math
from pathlib import Path
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[3];MP=ROOT/'packages/campaign/chapter04_units/ordinary.reference_model.json';SP=ROOT/'packages/campaign/chapter04_sources/native.reference.json'
raw=MP.read_bytes();assert hashlib.sha256(raw).hexdigest()=='d53bcd485b0b67bf971fb39176fdb2abfa962e8c9055b6eb07ce643dbeff0038';MODEL=json.loads(raw)
raw=SP.read_bytes();assert hashlib.sha256(raw).hexdigest()=='3e392d80d000e27a50f11f2f33b0fa0f6be35dc1e91d7e321e2b9cf9681c4603';SOURCE=json.loads(raw)
IDS=[v['native_reference']['id'] for v in SOURCE['variants'].values() if any(v['native_reference']['id'] in e['id'] for e in MODEL['entities'])];CAPTURES=[]
def source(key):return next(v for v in SOURCE['variants'].values() if v['native_reference']['id']==key)
def fixture(key,control=False):
 p=deepcopy(MODEL);uid=next(e['id'] for e in p['entities'] if key in e['id'])
 hero={'id':'unit/peer_guard','kind':'entity','tags':['player'],'components':{'spatial':{},'selection_state':{'side':0,'motion':1,'category':1},'attributes':{'base':{'max_hp':30000,'def':113,'block_count':1}},'resources':{'hp':{'initial':30000,'capacity':30000,'role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle'},'deployable':{'base_cost':3,'capacity':1,'cooldown_seconds':0,'terrain':'ground'},'abilities':['ability/peer_stop','ability/peer_def']}}
 p['entities'].append(hero);p.setdefault('buffs',[]).extend([{'id':'buff/peer_stop','kind':'buff','duration_seconds':.5,'control':{'attack':False,'move':False,'block':False,'interrupt':True}},{'id':'buff/peer_def','kind':'buff','duration_seconds':2,'modifiers':[{'attribute':'def','layer':'flat','value':87}]}])
 p['selectors'].append({'id':'selector/peer_enemy','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'limit':1})
 p['abilities'].extend([{'id':'ability/peer_stop','kind':'ability','selector':'selector/peer_enemy','activation':{'mode':'manual','on_start':[{'op':'apply_buff','buff':'buff/peer_stop'}]},'timeline':[]},{'id':'ability/peer_def','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':'source','buff':'buff/peer_def'}]},'timeline':[]}])
 p['scenarioDraft']={'id':'scene/independent_ch4','ruleset':'ruleset/ark_standard','roster':['unit/peer_guard'],'resources':{'dp':{'initial':30,'capacity':30},'life':{'initial':99999,'capacity':99999}},'objectives':{'life_resource':'life'},'map':{'rows':3,'cols':6},'waves':[{'at':0,'definition':uid,'instanceAlias':'enemy','position':{'row':1,'col':1},'route':{'motionMode':0,'startPosition':{'row':1,'col':1},'endPosition':{'row':1,'col':5},'checkpoints':[]}}]}
 return p,uid

def create(key):
 p,uid=fixture(key);raw=(json.dumps(p,indent=2)+'\n').encode();s=Engine.create(Compiler().compile(json.loads(raw)),seed=401017);s.submit({'action':'deploy','entity':'unit/peer_guard','alias':'guard','position':{'row':1,'col':1}},at=4);return s,uid,{'sha256':hashlib.sha256(raw).hexdigest(),'fixture':json.loads(raw),'seed':401017}

def capture(s,raw,expected,tmp):
 s.advance(35);h=write_ordered(tmp/'checkpoint.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp/'checkpoint.json',h));s.advance(45);r.advance(45);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
 CAPTURES.append({'input':raw,'expected':expected,'snapshot':s.snapshot(),'commands':s.export_replay(),'checkpoint_bytes_sha256':h,'events':thaw(tuple(s.session.events)),'checkpoint_equal':True,'commands_replay_equal':True})

@pytest.mark.parametrize('key',IDS)
def test_independent_native_values_frames_and_each_packet(key,tmp_path):
 v=source(key);attrs=v['native_enemy']['resolved']['attributes'];s,uid,raw=create(key);e=next(e for e in MODEL['entities'] if e['id']==uid);base=e['components']['attributes']['base']
 for src,dst in [('maxHp','max_hp'),('atk','atk'),('def','def'),('magicResistance','mres'),('moveSpeed','move_speed'),('baseAttackTime','attack_interval'),('massLevel','mass_level')]:assert base[dst]==attrs[src]
 assert e['components']['resources']['hp']['initial']==attrs['maxHp'];assert attrs['stunImmune'] is False and attrs['hpRecoveryPerSec']==0
 if key=='enemy_1002_nsabr':assert v['native_reference']['level']==1 and attrs['maxHp']==2750 and v['native_enemy']['raw_rows'][0]['enemyData']['attributes']['maxHp']['m_value']==1650
 if key=='enemy_1034_laxe':assert attrs['atk']==850
 node=v['modes'][0]['nodes']['_combat'];assert node['native_class']==('MultiMeleeAttack' if key=='enemy_1014_rogue_2' else 'MeleeAttack') and node['raw']['_selectTargetSource']==2
 frames=[e['frame'] for e in node['animation_binding']['events'] if e['name']=='OnAttack'];scale=.5 if len(frames)==2 else node['raw']['_atkScale'];amount=max(attrs['atk']*scale-113,attrs['atk']*scale*.05)
 s.advance(5);assert s.ctx.spatial.blocked_by('enemy')==s.session.world.resolve('guard') and s.ctx.resources.current('enemy','hp')==attrs['maxHp']
 capture(s,raw,{'DEF':113,'ATK':attrs['atk'],'frames':frames,'packet_scale':scale,'packet_amount':amount},tmp_path)
 en=s.session.world.resolve('enemy');starts=[e for e in s.session.events if e['type']=='ability.started' and e['payload']['source']==en];hits=[e for e in s.session.events if e['type']=='damage.accepted' and e['payload']['source']==en]
 first=starts[0];assert [e['time']-first['time'] for e in hits[:len(frames)]]==frames;assert all(e['payload']['amount']==pytest.approx(amount) for e in hits);assert hits[0]['payload']['target']==s.session.world.resolve('guard')
 if len(frames)==2:assert sum(e['payload']['amount'] for e in hits[:2])==pytest.approx(224) and len([e for e in s.session.events if e['type']=='attack.accepted' and e['payload']['source']==en and e['time']<=first['time']+23])==1


def test_control_cancels_pending_multihit_and_halfopen_restores(tmp_path):
 s,uid,raw=create('enemy_1014_rogue_2');s.submit({'action':'skill','source':'guard','ability':'ability/peer_stop'},at=8);capture(s,raw,{'stop_start':8,'stop_expiry':23,'no_packet_in':[8,23]},tmp_path)
 en=s.session.world.resolve('enemy');hits=[e for e in s.session.events if e['type']=='damage.accepted' and e['payload']['source']==en];assert not any(8<=e['time']<23 for e in hits);assert any(e['type']=='ability.interrupted' and e['payload']['source']==en for e in s.session.events)
 starts=[e['time'] for e in s.session.events if e['type']=='ability.started' and e['payload']['source']==en];assert any(x>=23 for x in starts)


def test_second_packet_reads_live_def_buff_at_hit(tmp_path):
 s,uid,raw=create('enemy_1014_rogue_2');s.submit({'action':'skill','source':'guard','ability':'ability/peer_def'},at=20);capture(s,raw,{'first_amount':112,'second_amount':25,'live_DEF_second':200},tmp_path)
 en=s.session.world.resolve('enemy');hits=[e for e in s.session.events if e['type']=='damage.accepted' and e['payload']['source']==en];assert hits[0]['payload']['amount']==112 and hits[1]['payload']['amount']==25

