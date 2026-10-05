"""Independent bounded ruin source/combat/radius/environment probes."""
import os,sys,json,hashlib,traceback,math
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_c9_duspfr_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw,digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter09_ruin_v2.build import providers
CORE='2c385c9c4a9e383988a3ff8d8d96827f0e473dde0630a3d6d92aa35c5f0dccb0';assert implementation_digest()==CORE
MODULE=ROOT/'packages/campaign/chapter09_consumers/ruin/module.v2.json';OLD=ROOT/'packages/campaign/chapter09_stage_models/level_main_09-16.native_draft.v2.life99999.json';SOURCE=ROOT/'packages/campaign/chapter09_source_prepare/duruin.transitive.source.v1.json';CLOSURE=ROOT/'packages/campaign/chapter09_consumers/pillars/source.closure.v1.json';DUMP=ROOT.parent/'Ark_data/dump.cs';REPORT=ROOT/'validation/campaign/chapter09_ruin_peer';LOG=Path(os.environ['ARKSIM_RUN_DIR']);REG=providers();BODY='unit/ch9/pillar/ruin';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
 assert implementation_digest()==CORE;assert sha(MODULE)=='220b4171830da288a421703887055c386a12a5cb81a494d69b7159a8ecccf25b'
 mod=json.loads(MODULE.read_bytes())
 for name,value in mod['manifest']['metadata']['source_locks'].items():assert sha(Path(name))==value
 return {str(p):sha(p) for p in [MODULE,OLD,SOURCE,CLOSURE,DUMP,ROOT/'tools/chapter09_ruin_v2/build.py']+[p for p in (CAND/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json'] and 'validation' not in p.parts]}
START=guard();REPORT.mkdir(parents=True,exist_ok=True)
mod=json.loads(MODULE.read_bytes());old=json.loads(OLD.read_bytes());source=json.loads(SOURCE.read_bytes());root=next(c['raw'] for c in source['native_prefab']['components'].values() if c['native_class']=='MapDependentTrap');inline=next(c['raw']['_buffs'][0] for c in source['native_prefab']['components'].values() if c['native_class']=='PassiveBuffAbility');text=DUMP.read_text(encoding='utf8');assert 'private SideType _sideType; // 0x550' in text and 'SideType ALLY = 1' in text and 'SideTypeIndex ALLY = 0' in text;assert root['_sideType']==1 and root['_category']==4
review={'source_files':{str(p):sha(p) for p in [SOURCE,CLOSURE,DUMP]},'native_class':'MapDependentTrap : Trap : Token','serialized_field_declaration':'Token[SerializeField] private SideType _sideType; 0x550','source_side_mask':1,'source_side_name':'ALLY','model_absolute_index':0,'side_mask_and_index_distinct':True,'source_category':4,'category_name':'OBSTACLE','native_HP':100,'block_count':3,'radius_squared':root['_blockRadiusSquare'],'radius':math.sqrt(root['_blockRadiusSquare']),'native_immunes':inline['attributes']['abnormalImmunes'],'native_combo_immunes':inline['attributes']['abnormalComboImmunes'],'native_environment_template':inline['templateKey'],'damage_scale_BB':inline['blackboard'],'native_Attackable_Blockable_TargetFree_serialized_fields':'No direct named fields in recovered trap component; derived state/getter method bodies absent, not inferred from raw body','combat_target_source_enum':'MeleeAttack raw2 = INPUT_TARGET, never rename BLOCKED; Enemy.AttackWrapper.SearchTarget/AssignAbility bodies absent','reference_policy':'PRTS blocked enemies break ruins; actual-blocker dispatch bypasses ordinary ranged category1 acquisition, explicitly source-reference inference','reference_url':'https://prts.wiki/w/战场废墟','reference_version':'oldid417764 inspected online; source fixed20250327/56 kept distinct','old_side1_and_missing_passive_Buff_are_actual_source_gaps':True,'whole_stage':False}
def scene(kind='duhond',new=True,position=(3,4),ranged=False):
 p=deepcopy(old);definitions={d['id']:d for d in p['definitions']}
 if new:
  for d in mod['definitions']:definitions[d['id']]=deepcopy(d)
 p['definitions']=list(definitions.values());uid=next(k for k in definitions if k.startswith('unit/ch9/'+kind+'/'));actor=definitions[uid];actor['components']['attributes']['base'].update(max_hp=4729,atk=431,**{'def':287,'mres':41,'move_speed':1.13,'attack_interval':2.3,'attack_speed_ratio':1.1});actor['components']['resources']['hp']['initial']=4729
 p['scenarioDraft']={'id':'scene/peer/ruin/'+kind+str(new),'ruleset':'ruleset/ark_standard','map':{'rows':8,'cols':10},'resources':{'life':{'initial':99999,'capacity':99999}},'initialEntities':[{'definition':BODY,'instanceAlias':'ruin','position':{'row':3,'col':4},'deployed':True},{'definition':uid,'instanceAlias':'enemy','position':{'row':position[0],'col':position[1]},**({} if ranged else {'route':{'motionMode':'WALK','startPosition':{'row':position[0],'col':position[1]},'endPosition':{'row':6,'col':4},'checkpoints':[]}})}],'commands':[]};return p

def create(p):return Engine.create(Compiler(providers=REG).compile(p),providers=REG,seed=4729287)
def events(s,t):return [(e['time'],thaw(e['payload'])) for e in s.session.events if e['type']==t]
ARTIFACTS=[]
def proof(p,name,split,end):
 a=create(p);a.advance(split);path=LOG/(name+'.checkpoint.json');pin=write_ordered(path,a.checkpoint());b=Engine.restore(a.program,load_bound(path,pin),providers=REG);a.advance(end-split);b.advance(end-split);c=replay(a.program,a.export_replay(),providers=REG);assert a.checkpoint()==b.checkpoint()==c.checkpoint();ARTIFACTS.append({'name':name,'path':str(path),'sha256':pin,'bytes':path.stat().st_size,'CPP_head_full_equal':True});return a
