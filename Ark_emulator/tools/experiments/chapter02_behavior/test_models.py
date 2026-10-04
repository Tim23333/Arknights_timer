"""Source-number expectations with public command fixtures and exact replay."""
import json,sys,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter02_behavior_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
import ark_sim
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.build_chapter02_behavior_models import build,OUT
INPUTS=[]
def make(p):
 raw=json.dumps(p,sort_keys=True,separators=(',',':')).encode();INPUTS.append({'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'seed':2702,'document':json.loads(raw)})
 return Engine.create(Compiler().compile(json.loads(raw)),seed=2702)
def check(s):
 r=Engine.restore(s.program,s.checkpoint());s.advance(2);r.advance(2);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
def fixture(initial):
 p=deepcopy(json.loads(OUT.read_bytes()))
 p['entities'].append({'id':'unit/peer','kind':'entity','tags':['player'],'metadata':{'native_category':1},'components':{'attributes':{'base':{'max_hp':10000,'atk':1000,'def':100,'mres':20}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'abilities':['ability/peer_shot','ability/peer_move','ability/peer_defdown','ability/peer_retire']}})
 p['selectors'] += [{'id':'selector/peer','kind':'selector','region':{'type':'all'},'filters':[{'tag':'probe'}],'limit':1}]
 p['abilities'] += [{'id':'ability/peer_shot','kind':'ability','selector':'selector/peer','activation':{'mode':'manual','on_start':[{'op':'damage','damage_type':'physical'}]},'timeline':[]},
 {'id':'ability/peer_defdown','kind':'ability','selector':'selector/peer','activation':{'mode':'manual','on_start':[{'op':'apply_buff','buff':'buff/chapter02/skulsr_defdown'}]},'timeline':[]},
 {'id':'ability/peer_move','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'move','target':'source','position_from_payload':False,'position':{'row':0,'col':6}}]},'timeline':[]},
 {'id':'ability/peer_retire','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'retire','target':'source','parameters':{'reason':'withdraw'}}]},'timeline':[]}]
 # Canonical source dependencies unchanged; publicly authored probe abilities only on synthetic actors.
 p['abilities'][-2]['activation']['on_start'][0].pop('position_from_payload')
 p['entities'].append({'id':'unit/ally','kind':'entity','tags':['enemy','probe'],'metadata':{'native_category':1},'components':{'attributes':{'base':{'max_hp':10000,'def':100,'mres':0}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'abilities':['ability/peer_move','ability/peer_retire']}})
 p['scenarioDraft']={'id':'scenario/chapter02_probes','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':8},'objectives':{},'initialEntities':initial,'waves':[]}
 return p
def actor(key,alias,col):return {'definition':key,'instanceAlias':alias,'position':{'row':0,'col':col}}
def skill(s,source,ability,t):s.submit({'action':'skill','source':source,'ability':ability},at=t)

def test_fly_attacker_range_frame_damage_without_blocker():
 p=fixture([actor('unit/chapter02/enemy_1005_yokai_2','drone',0),actor('unit/peer','peer',2)])
 s=make(p);s.advance(8);assert s.ctx.resources.current('peer','hp')==10000
 s.advance(1);hits=[e for e in s.session.events if e['type']=='damage.accepted']
 assert len(hits)==1 and hits[0]['time']==8 and hits[0]['payload']['amount']==120 # ATK220-DEF100
 assert s.ctx.spatial.blocked_by('drone') is None;check(s)

def test_fly_attacker_outside_actual_circle_never_casts():
 p=fixture([actor('unit/chapter02/enemy_1005_yokai_2','drone',0),actor('unit/peer','peer',2.01)])
 s=make(p);s.advance(10);assert not [e for e in s.session.events if e['type']=='ability.started'];check(s)

def test_empty_fly_combat_has_no_attack_and_uses_air_route():
 p=fixture([actor('unit/chapter02/enemy_1005_yokai','drone',0),actor('unit/peer','peer',1)])
 p['scenarioDraft']['initialEntities'][0]['route']={'motionMode':1,'startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':7},'checkpoints':[]}
 s=make(p);s.advance(10);assert not [e for e in s.session.events if e['type']=='ability.started']
 assert abs(s.ctx.get('drone',('spatial','position'))['col']-.3)<1e-8;check(s)

def test_defup_real_settlement_enter_leave_and_source_exclusion():
 p=fixture([actor('unit/chapter02/enemy_1017_defdrn','drone',0),actor('unit/ally','ally',2.5),actor('unit/peer','peer',4)])
 s=make(p);skill(s,'peer','ability/peer_shot',0);skill(s,'ally','ability/peer_move',1);skill(s,'peer','ability/peer_shot',2);s.advance(3)
 hits=[e['payload']['amount'] for e in s.session.events if e['type']=='damage.accepted'];assert hits==[600,900] # 1000-(100+300), then1000-100
 # Source SelfOption.EXCLUDE2 means no own +300. A real shot proves it.
 p=fixture([actor('unit/chapter02/enemy_1017_defdrn','drone',0),actor('unit/peer','peer',1)])
 p['entities'][2]['tags'].append('probe');s2=make(p);skill(s2,'peer','ability/peer_shot',0);s2.advance(1)
 assert [e['payload']['amount'] for e in s2.session.events if e['type']=='damage.accepted']==[850] #1000-150
 check(s);check(s2)

def test_two_emitters_withdraw_restores_only_its_layer():
 p=fixture([actor('unit/chapter02/enemy_1017_defdrn','a',0),actor('unit/chapter02/enemy_1017_defdrn','b',1),actor('unit/ally','ally',2),actor('unit/peer','peer',4)])
 # Public management probe on source entity; no change to its canonical abilities/buffs.
 p['entities'][2]['components']['abilities'].append('ability/peer_retire')
 s=make(p);skill(s,'peer','ability/peer_shot',0);skill(s,'a','ability/peer_retire',1);skill(s,'peer','ability/peer_shot',2);skill(s,'b','ability/peer_retire',3);skill(s,'peer','ability/peer_shot',4);s.advance(5)
 assert [e['payload']['amount'] for e in s.session.events if e['type']=='damage.accepted']==[300,600,900]
 check(s)

def test_skulsr_defdown_five_second_half_open_settlement():
 p=fixture([actor('unit/ally','ally',0),actor('unit/peer','peer',1)])
 s=make(p);skill(s,'peer','ability/peer_defdown',0);skill(s,'peer','ability/peer_shot',149);skill(s,'peer','ability/peer_shot',150);s.advance(151)
 assert [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']==[(149,950),(150,900)]
 check(s)

def test_complete_claim_rejected_and_build_source_exact():
 with pytest.raises(ValueError,match='unresolved'):build(require_complete=True)
 assert OUT.read_bytes()==(json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode()
