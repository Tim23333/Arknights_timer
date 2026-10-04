"""Exact source sotisd intrinsic taunt Buff and28frame/114cycle real blocked packets."""
import hashlib,json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_complete_base_v5_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from ark_sim.domains.selection import DEFAULT_STATE
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
MODULE=ROOT/'packages/campaign/chapter07_ordinary_remaining/sotisd.module.v2.reference.json';OUT=ROOT/'validation/campaign/chapter07_sotisd_v1'
def package():
 p=json.loads(MODULE.read_bytes());assert hashlib.sha256(MODULE.read_bytes()).hexdigest()=='fc8f197c32719526eb7ec68fe70200e4d26a8767da3a7190a4beae124e3fed24';p['entities'].append({'id':'unit/author/sotisd/blocker','kind':'entity','tags':['player','ground'],'components':{'attributes':{'base':{'max_hp':10000,'atk':0,'def':100,'mres':0,'block_count':1}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'deployable':{'base_cost':7,'capacity':1,'cooldown_seconds':0,'terrain':'ground'},'lifecycle':{'policy':'policy/ark_lifecycle'}}});p['scenarioDraft']={'id':'scene/c7/sotisd/author','ruleset':'ruleset/ark_standard','seed':71718,'map':{'rows':1,'cols':5},'resources':{'dp':{'initial':20,'capacity':99}},'objectives':{},'roster':['unit/author/sotisd/blocker'],'initialEntities':[{'definition':p['entities'][0]['id'],'instanceAlias':'source','position':{'row':0,'col':0},'route':{'motionMode':'WALK','startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':4},'checkpoints':[]}}]};return p
def make():return Engine.create(Compiler().compile(package()))
def deploy(s):s.submit({'action':'deploy','definition':'unit/author/sotisd/blocker','alias':'blocker','position':{'row':0,'col':0}},at=0)
def hits(s):return [e for e in s.session.events if e['type']=='damage.accepted']
def test_source_stats_initial_taunt_actualBuff_no_SP_and_SILENCED12():
 s=make();u=s.ctx.entity('source');assert (u['components']['attributes']['base']['max_hp'],u['components']['attributes']['base']['atk'],u['components']['attributes']['base']['def'])==(15000,700,1300);assert s.ctx.attributes.value('source','taunt_level')==1 and u['components']['buffs']['instances'][0]['definition']=='buff/ch7/source/sotisd_t' and 'sp' not in u['components']['resources'];assert s.ctx.spatial.selection_state('source',DEFAULT_STATE)['abnormal_immunes']==[12]
def test_real_block28frame_and114cycle_700minus100two600():
 s=make();deploy(s);s.session.advance(2);assert s.ctx.spatial.blocked_by('source')==s.session.world.resolve('blocker') and s.ctx.resources.current('system/battle','dp')==13;s.session.advance(27);assert not hits(s);s.session.advance(1);assert len(hits(s))==1 and hits(s)[0]['time']==29 and hits(s)[0]['payload']['amount']==600;s.session.advance(120);assert len(hits(s))==2 and hits(s)[1]['time']==143 and hits(s)[1]['payload']['amount']==600
def test_source28public_CP_head_pre_hit_complete_actualvalues():
 p=package();s=Engine.create(Compiler().compile(p));deploy(s);s.session.advance(12);OUT.mkdir(parents=True,exist_ok=True);cp=OUT/'actual12.cp.json';assert not cp.exists();h=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,h));s.session.advance(145);r.session.advance(145);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot();(OUT/'actual_evidence.json').write_text(json.dumps({'input':p,'cp_sha':h,'snapshot':s.snapshot()},indent=2)+'\n',encoding='utf8',newline='')
def test_taunt_non_silenceable_buff_remains_after_sourceflag12_and_unblocked_target_absent():
 p=package();p['buffs'].append({'id':'buff/author/silence','kind':'buff','duration_seconds':2,'selection_flags':{'abnormal_flags':[12]}});p['entities'][0]['components']['buffs']['initial'].append('buff/author/silence');s=Engine.create(Compiler().compile(p));s.session.advance(10);assert s.ctx.attributes.value('source','taunt_level')==1 and 12 not in s.ctx.spatial.selection_state('source',DEFAULT_STATE)['abnormal_flags'] and not hits(s)
