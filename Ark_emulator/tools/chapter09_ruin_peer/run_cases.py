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
review={'source_files':{str(p):sha(p) for p in [SOURCE,CLOSURE,DUMP]},'native_class':'MapDependentTrap : Trap : Token','serialized_field_declaration':'Token[SerializeField] private SideType _sideType; 0x550','source_side_mask':1,'source_side_name':'ALLY','model_absolute_index':0,'side_mask_and_index_distinct':True,'source_category':4,'category_name':'OBSTACLE','native_HP':100,'block_count':3,'radius_squared':root['_blockRadiusSquare'],'radius':math.sqrt(root['_blockRadiusSquare']),'native_immunes':inline['attributes']['abnormalImmunes'],'native_combo_immunes':inline['attributes']['abnormalComboImmunes'],'native_environment_template':inline['templateKey'],'damage_scale_BB':inline['blackboard'],'native_Attackable_Blockable_TargetFree_serialized_fields':'No direct named fields in recovered trap component; derived state/getter method bodies absent, not inferred from raw body','combat_target_source_enum':'MeleeAttack raw2 = INPUT_TARGET, never rename BLOCKED; Enemy.AttackWrapper.SearchTarget/AssignAbility bodies absent','reference_policy':'PRTS blocked enemies break ruins; actual-blocker dispatch bypasses ordinary ranged category1 acquisition, explicitly source-reference inference','reference_url':'https://prts.wiki/w/战场废墟','reference_version':'oldid417764 inspected online; source fixed20250327/56 kept distinct','old_side1_and_missing_passive_Buff_are_actual_source_gaps':True,'whole_stage':False};(REPORT/'source.review.json').write_text(json.dumps(review,indent=2),encoding='utf8')
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
RESULTS=[];FACTS={}
def old_counter():
 s=create(scene(new=False));s.advance(105);assert s.ctx.spatial.blocked_by('enemy')==s.session.world.resolve('ruin');assert s.ctx.resources.current('ruin','hp')==100;assert not events(s,'ability.started');FACTS['old_counter']={'reproduced':True,'core':CORE,'actual_blocked':True,'ruin_HP':100,'ticks':105,'ordinary_attack_count':0,'consumer_failure_not_counted_as_green':True};(REPORT/'old.actual.counter.json').write_text(json.dumps(FACTS['old_counter'],indent=2),encoding='utf8')
def combat():
 s=proof(scene(),'nativecombat_different',12,90);assert not s.ctx.alive('ruin');assert s.ctx.state().get('kills',0)==0;assert s.ctx.spatial.blocked_by('enemy') is None;assert s.ctx.get('enemy',('spatial','position'))['row']>3;hits=events(s,'damage.accepted');assert len(hits)==1 and hits[0][1]['amount']==100;FACTS['combat']={'first_hit_tick':hits[0][0],'raw_ATK':431,'HP_clamped_amount':100,'route_released':True,'native_wave_kill_count':0}
def radius():
 r=math.sqrt(root['_blockRadiusSquare']);facts=[]
 for delta,want in [(-.0001,True),(0,False),(.0001,False)]:
  p=scene(position=(3+r+delta,4));uid=p['scenarioDraft']['initialEntities'][1]['definition'];actor=next(d for d in p['definitions'] if d['id']==uid);actor['components'].pop('behavior',None);actor['components']['abilities']=[];actor['components']['attributes']['base']['move_speed']=0;s=create(p);s.advance(1);actual=s.ctx.spatial.blocked_by('enemy') is not None;assert actual==want;facts.append({'delta':delta,'actual_blocked':actual,'position':s.ctx.get('enemy',('spatial','position'))})
 FACTS['radius']=facts

def environment_and_ranged():
 p=scene('dumage',position=(3,5),ranged=True);s=proof(p,'ranged_category4',10,70);assert s.ctx.alive('ruin') and s.ctx.resources.current('ruin','hp')==100;assert not events(s,'ability.started');FACTS['ranged_category4']={'source_relative_enemy_side_passes_after_sidefix':True,'defaultcategory1_excludes_obstacle4':True,'not_blocked':s.ctx.spatial.blocked_by('enemy') is None}
 p=deepcopy(mod);p['manifest']['requires']=['preset/ark_standard'];p['rules']=[{'id':'rule/peer/fixed_no_source','kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'packet','expression':"{'accepted': True, 'amount': inputs.effect.fixed_amount, 'allocations': [], 'events': []}"}],'output':'nodes.packet'}}]
 p['scenarioDraft']={'id':'scene/peer/ruin/env','ruleset':'ruleset/ark_standard','map':{'rows':8,'cols':10},'resources':{'life':{'initial':99999,'capacity':99999}},'initialEntities':[{'definition':BODY,'instanceAlias':'ruin','position':{'row':3,'col':4}}],'scheduledEffects':[]}
 for at,amount,env in [(7,47,True),(11,11,False)]:p['scenarioDraft']['scheduledEffects'].append({'at':at,'effect':{'op':'no_source_damage','target':2,'fixed_amount':amount,'damage_type':'true','attack_type':'NONE','damage_without_modify':False,'ignore_for_sp':True,'node_is_env_damage':env,'env_blackboard_injected':False,'environmental':env,'origin':{'native':'peer_ruin_environment' if env else 'peer_ordinary'},'rules':{'damage.pipeline':'rule/peer/fixed_no_source'}}})
 s=proof(p,'NoSource_environment_ordinary',9,15);assert s.ctx.resources.current('ruin','hp')==89;assert [(t,x['amount']) for t,x in events(s,'damage.accepted')]==[(7,0),(11,11)];projection=s.ctx.spatial.selection_state('ruin',__import__('ark_sim.domains.selection',fromlist=['DEFAULT_STATE']).DEFAULT_STATE);assert projection['abnormal_immunes']==[0,12,16] and projection['abnormal_combo_immunes']==[0];FACTS['environment']={'environment47_zero':True,'ordinary_NoSource11_actual':True,'HP':89,'immunes':projection['abnormal_immunes'],'combo_immunes':projection['abnormal_combo_immunes']}

def coupled_counter():
 s=create(scene('coupled/dushdo'));s.advance(110);assert s.ctx.spatial.blocked_by('enemy')==s.session.world.resolve('ruin');assert s.ctx.resources.current('ruin','hp')==100;starts=events(s,'ability.started');assert not starts;FACTS['coupled_counter']={'reproduced':True,'ticks':110,'ruin_HP':100,'actual_blocked':True,'automatic_attack_count':0,'cause':'blocked selector still applies ordinary category1 eligibility against obstacle4'};(REPORT/'coupled.actual.counter.json').write_text(json.dumps(FACTS['coupled_counter'],indent=2),encoding='utf8')
for name,fn in [('old_source_counter',old_counter),('different_native_combat_CPP',combat),('native_squared_radius_boundaries',radius),('environment_NoSource_and_ranged_obstacle',environment_and_ranged),('real_dushdo_blocked_counter',coupled_counter)]:
 try:fn();RESULTS.append({'case':name,'passed':True})
 except Exception as e:RESULTS.append({'case':name,'passed':False,'error':str(e),'traceback':traceback.format_exc()})
current=guard();report={'core':CORE,'actual_exit':0 if all(x['passed'] for x in RESULTS) and current==START else 1,'results':RESULTS,'facts':FACTS,'source_before':START,'source_after':current,'source_guard_equal':current==START,'artifacts':ARTIFACTS,'comparison_exclusions':[],'countercases_are_evidence_of_old_or_remaining_model_failure_not_consumer_admission':True,'whole_stage':False};(REPORT/'actual.v2.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps({'actual_exit':report['actual_exit'],'results':RESULTS,'facts':FACTS}));raise SystemExit(report['actual_exit'])
