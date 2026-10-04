"""Current declared reference/table simulation; historical40% package unchanged."""
import argparse,json,hashlib
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'packages/campaign/chapter02_behavior/reference50/skulsr.model.json'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def build():
 parent=ROOT/'packages/campaign/chapter02_behavior/m28/skulsr.DB.partial.json';assert sha(parent)=='856378cc9cccfe31f54d8e9f5b78dd72c9db443567f7c8e9df8a8d09d5066295';p=json.loads(parent.read_bytes())
 source=ROOT/'packages/campaign/chapter02_sources/native.reference.json';data=json.loads(source.read_bytes());stage=data['stages']['level_main_02-10'];vid='enemy_1500_skulsr@0/082a711ecbcd1bdf';assert vid in stage['resolved_variant_ids'];v=data['variants'][vid];a=v['native_enemy']['resolved']['attributes'];bb={x['key']:x['value'] for x in v['native_enemy']['resolved']['talentBlackboard']};assert (a['maxHp'],a['atk'],bb['atkup.atk'],bb['atkup.hp_ratio'])==(10500,1000,.5,.5)
 root=next(c['raw'] for c in v['components'].values() if c['native_class']=='Enemy');mover=next(c['raw'] for c in v['components'].values() if c['native_class']=='MoveController');assert root['_delayToBorn']==0 and root['_blockVolume']==1
 assert a['hpRecoveryPerSec']==0 and a['spRecoveryPerSec']==0 and a['stunImmune'] is False and a['silenceImmune'] is True
 unit=p['entities'][0];unit['id']='unit/chapter02/enemy_1500_skulsr/level_0/082a711ecbcd1bdf';unit['metadata'].update(native_variant=vid,declared_silence_immune=True,silence_policy='No silenceable selected source talent; HP threshold ATK talent remains active regardless of SILENCED12. Other external skill suppression not inferred.')
 unit['components']['spatial']={'motion_mode':0,'steering':{'rule':'rule/skulsr/steering','parameters':{'response_factor':mover['_steeringFactor'],'max_acceleration':mover['_maxSteeringForce'],'arrival_radius':.05}}};unit['components']['selection_state'].update(side=1,motion=1,category=1);unit['components']['lifecycle']['leak_loss']=2
 p['rules'] += [{'id':'rule/skulsr/steering','kind':'rule','contract':'movement.steering','implementation':{'type':'provider','provider':'ark.movement.steering_velocity'}},
 {'id':'rule/skulsr/area_cells','kind':'rule','contract':'area.members','implementation':{'type':'provider','provider':'ark.area.cell_offsets'}},
 {'id':'rule/skulsr/decision','kind':'rule','contract':'behavior.decision','implementation':{'type':'expression','expression':"{'move': inputs.controls.move and inputs.blocked_by == None and inputs.cast_groups.normal == [] and inputs.eligible_ids.ranged == [], 'attack': inputs.controls.attack and inputs.controls.abilities and inputs.cast_groups.normal == [] and ((inputs.blocked_by in inputs.eligible_ids.combat) if inputs.blocked_by != None else inputs.eligible_ids.ranged != [])}"}}]
 profiles=[]
 for index in (0,1):
  group=[f'ability/skulsr_attack_{index}',f'ability/skulsr_combat_{index}'];profiles.append({'mode':index,'selectors':[{'key':'ranged','selector':f'selector/skulsr_attack_{index}'},{'key':'combat','selector':f'selector/skulsr_combat_{index}'}],'cast_groups':[{'key':'normal','abilities':group}]})
 p['behaviors']=[{'id':'behavior/skulsr/reference','kind':'behavior','initial':'active','states':{'active':{}},'transitions':[],'decision':{'rule':'rule/skulsr/decision','mode_resource':'mode','profiles':profiles}}];unit['components']['behavior']={'machine':'behavior/skulsr/reference'}
 for ability in p['abilities']:
  ident=ability['id']
  if ident.startswith(('ability/skulsr_attack_','ability/skulsr_combat_')):
   ranged=ident.startswith('ability/skulsr_attack_');index=int(ident.rsplit('_',1)[1]);ability['activation']['mode']='automatic_attack';ability['activation']['parameters'].update(auto_only=True,counts_as_attack=True)
   blocked="('blocked_by' in inputs.source.components.runtime and inputs.source.components.runtime.blocked_by != None)"
   ability['activation']['condition']=f'inputs.resources.mode.current == {index} and '+('not '+blocked if ranged else blocked)
   if ranged:
    for item in ability['timeline']:
     old=item['effect'];item['effect']={'op':'area','projectile_definition':old['projectile_definition'],'center':'target','membership_rule':'rule/skulsr/area_cells','parameters':{'offsets':[[r,c] for r in (-1,0,1) for c in (-1,0,1)]},'filters':[{'tag':'player'},{'state':'alive'}],'effects':[{k:deepcopy(value) for k,value in old.items() if k!='projectile_definition'}]}
   ability['metadata']['dispatch_profile']='Automatic blocked melee / unblocked ranged, declared pure decision; exact source mode/frame operands.'
  elif ident=='ability/skulsr_enter':ability['activation']['condition']=ability['activation']['condition'].replace('<= params.hp_threshold','< params.hp_threshold')
  elif ident=='ability/skulsr_leave':ability['activation']['condition']=ability['activation']['condition'].replace('> params.hp_threshold','>= params.hp_threshold')
 projectile=p['projectiles'][0];projectile['metadata']['model_gap']='';projectile['metadata']['profile']='Homogeneous2D homing speed5, actual impact center half-up target cell plus8 offsets; source 3x3 reference policy, no UnityBox physics claim.'
 # Damage-first then after-success DEF debuff is explicit; refresh ends five seconds after last successful hit.
 for buff in p['buffs']:
  if buff['id']=='buff/chapter02/skulsr_defdown':buff['metadata']['attachment_driver_pending']=False
 meta=p['manifest']['metadata'];meta.update(required_runtime_feature='area.members pure optional effect rule',required_runtime=None,status='complete_declared_reference_boss_model',builder_sha256=sha(__file__),source_variant=vid,source_stage='level_main_02-10',reference={'url':'https://m.prts.wiki/w/碎骨','observed_revision':367689,'page_last_edited':'2025-10-21','checked_date':'2026-10-03','read_evidence':'Root successful web read documented in docs/campaign/REFERENCE_FIRST_DELIVERY.md; peer fetch timed out','rules':['HP strictly below50% ATK+50%','unblocked two source grenade signals26% physical each','target cell plus surrounding8cells','DEF direct ratio-50% for5seconds']},model_gaps=[],model_delivery_ready=True,client_verified=False,actual_game_correct=False,formal_approved=False,feedback_pending=['historical prefab checker .4 vs table/reference .5','native Loader/FSM/family dispatch method bodies','source-speed scaling, steering and collider-to-grid precision','damage-first DEF attachment ordering and refresh declaration','captured primary grenade cancels if target invalid/hidden; retained source packets declared'],profiles={'HP':'0<hp<5250 enters; hp>=5250 restores; fixed actual maxHP10500; heal/damage resources events','dispatch':'mode-specific automatic blocked melee / unblocked ranged; f53 versus f14/f17;3second per-cast interval','area':'actual impact point half-up project_cell plus8 surroundingcells; all eligible living player targets including flight','attachment':'physical settlement then DEF direct-ratio-.5, refresh5s; no melee attachment','sampling':'source/target at_hit, source-retired in-flight packet retains source snapshots/current data as existing policy','silence':'fixed source silenceImmune true; selected HP phase driver unsilenceable','birth':'actual Enemy _delayToBorn0, immediate create at wave spawn'})
 meta['source_locks'].update({str(source.relative_to(ROOT)):sha(source),str(parent.relative_to(ROOT)):sha(parent)})
 p['manifest']['id']='chapter02/skulsr/reference50';return p
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args();p=build();b=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode();OUT.parent.mkdir(parents=True,exist_ok=True)
 if a.check:assert OUT.read_bytes()==b
 else:OUT.write_bytes(b)
 print(json.dumps({'passed':True,'sha256':sha(OUT)}))
