"""Independent source-number projectile scenarios; first7 fixtures stay frozen."""
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
from tools.build_chapter02_projectile_models import build,OUT
INPUTS=[]
def fixture(key):
 p=deepcopy(json.loads(OUT.read_bytes()))
 p['entities'].append({'id':'unit/peer','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':10000,'atk':0,'def':100,'mres':20}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/peer_move','ability/peer_defup','ability/peer_free']}})
 p['buffs'] += [{'id':'buff/peer_defup','kind':'buff','duration_seconds':10,'modifiers':[{'attribute':'def','layer':'flat','value':50}]},{'id':'buff/peer_free','kind':'buff','duration_seconds':1,'selection_flags':{'abnormal_flags':[2]}}]
 p['abilities'] += [{'id':'ability/peer_retire','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'retire','target':'source','parameters':{'reason':'withdraw'}}]},'timeline':[]},{'id':'ability/peer_move','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'move','target':'source','position':{'row':0,'col':4}}]},'timeline':[]},*({'id':'ability/peer_'+name,'kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':'source','buff':'buff/peer_'+name}]},'timeline':[]} for name in ('defup','free'))]
 unit=next(e for e in p['entities'] if e['id']=='unit/chapter02/'+key);unit['components']['abilities'].append('ability/peer_retire')
 p['scenarioDraft']={'id':'scenario/chapter02_projectile','ruleset':'ruleset/ark_standard','map':{'rows':2,'cols':8},'objectives':{},'initialEntities':[{'definition':unit['id'],'instanceAlias':'caster','position':{'row':0,'col':0}},{'definition':'unit/peer','instanceAlias':'peer','position':{'row':0,'col':2}}],'waves':[]}
 return p
def make(p):
 raw=json.dumps(p,sort_keys=True,separators=(',',':')).encode();INPUTS.append({'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'seed':2703,'document':json.loads(raw)})
 return Engine.create(Compiler().compile(json.loads(raw)),seed=2703)
def skill(s,who,what,t):s.submit({'action':'skill','source':who,'ability':'ability/peer_'+what},at=t)
def exact(s):
 r=Engine.restore(s.program,s.checkpoint());s.advance(2);r.advance(2);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()

@pytest.mark.parametrize('key,launch,hit,amount',[('enemy_1011_wizard',19,25,160),('enemy_1028_mocock',22,34,80)])
def test_actual_signal_and_motion_impact(key,launch,hit,amount):
 s=make(fixture(key));s.advance(hit);assert s.ctx.resources.current('peer','hp')==10000
 s.advance(1);events=[e for e in s.session.events if e['type']=='damage.accepted'];assert [(e['time'],e['payload']['amount']) for e in events]==[(hit,amount)]
 assert [e['time'] for e in s.session.events if e['type']=='projectile.launched']==[launch];exact(s)

def test_retired_mocock_keeps_real_launched_packet_and_samples_hit_defense():
 s=make(fixture('enemy_1028_mocock'));skill(s,'caster','retire',23);skill(s,'peer','defup',25);s.advance(35)
 assert [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']==[(34,30)] #180-(100+50)
 assert not s.ctx.alive('caster');exact(s)

def test_dynamic_wizard_target_homing_after_move_and_source_retire():
 s=make(fixture('enemy_1011_wizard'));skill(s,'peer','move',20);skill(s,'caster','retire',21);s.advance(31)
 assert not [e for e in s.session.events if e['type']=='damage.accepted']
 # At launch19, target moves before first step20:4 units/10 speed =>12steps, impact31.
 s.advance(1);assert [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']==[(31,160)];exact(s)

def test_target_free_before_selection_does_not_launch_or_consume_rng():
 s=make(fixture('enemy_1011_wizard'));skill(s,'peer','free',0);s.advance(20)
 assert not [e for e in s.session.events if e['type'] in ('projectile.launched','damage.accepted')];exact(s)

def test_retired_target_cancels_projectile_without_health_allocation():
 p=fixture('enemy_1011_wizard');p['entities'][-1]['components']['abilities'].append('ability/peer_retire');s=make(p);skill(s,'peer','retire',20);s.advance(35)
 assert not [e for e in s.session.events if e['type']=='damage.accepted'];assert s.ctx.resources.current('peer','hp')==10000;exact(s)

def test_new_output_exact_and_no_complete_claim():
 assert OUT.read_bytes()==(json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode()
 with pytest.raises(ValueError,match='unresolved'):build(require_complete=True)
