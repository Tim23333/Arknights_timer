"""Source sotihd2900/350/150/18frame real blocked attack, state and disk replay."""
import hashlib,json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_complete_base_v5_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.domains.selection import DEFAULT_STATE
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
CORE='a7059989b9db7f4bc0de954b32cb5c5ba10e6b92ce040c57ea0a193549b9709a';MODULE=ROOT/'packages/campaign/chapter07_ordinary/sotihd.module.v2.reference.json';OUT=ROOT/'validation/campaign/chapter07_ordinary_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def package():
 assert sha(MODULE)=='7b6d485affb99754205c393eb1c11b528d39875d23f8cc4e98c23beef64dddb7';p=json.loads(MODULE.read_bytes());p['entities'].append({'id':'unit/ch7_probe/blocker','kind':'entity','tags':['player','ground'],'components':{'attributes':{'base':{'max_hp':10000,'atk':500,'def':100,'mres':0,'block_count':1}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'spatial':{},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'deployable':{'base_cost':7,'capacity':1,'cooldown_seconds':0,'terrain':'ground'},'lifecycle':{'policy':'policy/ark_lifecycle'}}});p['scenarioDraft']={'id':'scene/c7/source_sotihd_probe','ruleset':'ruleset/ark_standard','seed':717,'map':{'rows':1,'cols':5},'resources':{'dp':{'initial':20,'capacity':99}},'objectives':{},'roster':['unit/ch7_probe/blocker'],'initialEntities':[{'definition':p['entities'][0]['id'],'instanceAlias':'source','position':{'row':0,'col':0},'route':{'motionMode':'WALK','startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':4},'checkpoints':[]}}]};return p
def make():return Engine.create(Compiler().compile(package()))
def deploy(s):s.submit({'action':'deploy','definition':'unit/ch7_probe/blocker','position':{'row':0,'col':0},'alias':'blocker'},at=0)
def test_exact_source_stats_no_passive_no_SP_and_defined_silence_immunity():
 assert implementation_digest()==CORE;p=package();d=p['entities'][0];a=d['components']['attributes']['base'];assert (a['max_hp'],a['atk'],a['def'],a['attack_interval'],a['attack_speed_ratio'])==(2900,350,150,1.4,1.0);assert set(d['components']['resources'])=={'hp'} and not d['components'].get('buffs');s=make();assert 12 in s.ctx.spatial.selection_state('source',DEFAULT_STATE)['abnormal_immunes']
def test_real_block_first18_frame_and_two_source_hits_with_true_DP():
 s=make();deploy(s);s.session.advance(2);assert s.ctx.spatial.blocked_by('source')==s.session.world.resolve('blocker') and s.ctx.resources.current('system/battle','dp')==13;s.session.advance(16);assert s.ctx.resources.current('blocker','hp')==10000;s.session.advance(1);hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert len(hits)==1 and hits[0]['time']==18 and hits[0]['payload']['amount']==250;s.session.advance(50);hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert len(hits)==2 and [e['payload']['amount'] for e in hits]==[250,250] and hits[1]['time']-hits[0]['time']==43
def test_current_target_DEF_at_hit_and_public_ordered_CP_head():
 p=package();OUT.mkdir(parents=True,exist_ok=True);s=Engine.create(Compiler().compile(p));deploy(s);s.session.advance(10);cp=OUT/'prehit.cp.json';assert not cp.exists();h=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,h));s.session.advance(20);r.session.advance(20);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot();(OUT/'actual_input.json').write_text(json.dumps(p,indent=2)+'\n',encoding='utf8',newline='');(OUT/'actual_trace.json').write_text(json.dumps({'checkpoint_sha':h,'snapshot':s.snapshot()},indent=2)+'\n',encoding='utf8',newline='')
def test_unblocked_no_invented_free_target_and_source_death_cancels_attack():
 s=make();s.session.advance(20);assert not [e for e in s.session.events if e['type']=='ability.started'];s=make();deploy(s);s.session.advance(10);s.ctx.lifecycle.retire('source','withdrawn');s.session.advance(20);assert not [e for e in s.session.events if e['type']=='damage.accepted']
