"""Source-bound airborne/stone consumers; isolated generic prezero provenance candidate."""
import json,hashlib,sys
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_c9_rock_gargoyle_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
OUT=ROOT/'packages/campaign/chapter09_consumers/rock_gargoyle';SOURCE=ROOT/'packages/campaign/chapter09_source_prepare/enemies.native.v1.json'
KEYS=('enemy_1171_durokt','enemy_1172_dugago')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def decision(i,p,c):
 active=i['parameters']['normal'];eligible=bool(i['eligible_ids'].get('normal'));busy=bool(i['cast_groups'].get('normal'))
 return {'move':active and i['blocked_by'] is None and not eligible and not busy,'attack':active and eligible and not busy}
def skip(i,p,c):
 now=c['time'];
 if i['depletion_event'].get('operation')!='damage':return False
 return any(b['definition'] in p['source_buffs'] and b.get('applicability',{}).get('active',True) and (b['expires_at'] is None or now<b['expires_at']) for b in i['source'].get('components',{}).get('buffs',{}).get('instances',[]))
def flight_active(i,p,c):return not set(i['status']['abnormal_flags'])&{0,16,25,36,45} and 0 not in i['status']['abnormal_combos']
def blocker_eligibility(i,p,c):
 from ark_sim.domains.selection import eligibility_profile
 blocker=i["source"].get("components",{}).get("runtime",{}).get("blocked_by")
 if blocker is None or i["candidate"]["id"]!=blocker:return {"accepted":False,"reason":"not_actual_blocker"}
 return eligibility_profile(i,{},c)
def flight_disabled(i,p,c):
 owner=c["owner"];now=c["time"]
 return any(b["definition"]==p["required_buff"] and b["source"]==owner["id"] and b["target"]==owner["id"] and (b["expires_at"] is None or now<b["expires_at"]) and b.get("applicability",{}).get("active",True) is False for b in owner.get("components",{}).get("buffs",{}).get("instances",[]))
def providers():
 from tools.chapter08_bsnake_combat.policies_v1 import providers as base
 return {**base(),'reference.ch9.actual_blocker':{'callable':blocker_eligibility,'version':'1'},'reference.ch9.flight_disabled':{'callable':flight_disabled,'version':'1'},'reference.ch9.mode_decision':{'callable':decision,'version':'1'},'reference.ch9.source_buff_skip':{'callable':skip,'version':'1'},'reference.ch9.flight_active':{'callable':flight_active,'version':'1'}}
def replace(v,old,new):
 if isinstance(v,dict):return {k:replace(x,old,new) for k,x in v.items()}
 if isinstance(v,list):return [replace(x,old,new) for x in v]
 return v.replace(old,new) if isinstance(v,str) else v
def build(key, *, pillar_trait_buff=None, dependency_definitions=(), restore_profile="native_reference"):
 if key==KEYS[1] and (not isinstance(pillar_trait_buff,str) or not pillar_trait_buff):raise ValueError("gargoyle requires supplied pillar trait Buff IR ID")
 if key==KEYS[1] and not any(d.get("id")==pillar_trait_buff and d.get("kind")=="buff" for d in dependency_definitions):raise ValueError("supplied pillar trait ID requires exact compiled Buff definition")
 if restore_profile not in ("native_reference","prts_reference"):raise ValueError("unknown source restore profile")
 from ark_sim import Compiler
 from ark_sim.adapters.api import implementation_digest
 from ark_sim.domains.selection import DEFAULT_STATE
 assert key in KEYS and sha(SOURCE)=='592afac29cc32d1aeaba3ea739eb6da5a218055e255a42f53315f4a2ca0962ff'
 d=json.loads(SOURCE.read_bytes());vid,v=next((a,b) for a,b in d['variants'].items() if b['prefab_key']==key);name=key.split('_',2)[2];pref=d['prefabs'][key];cs=pref['components'];attrs=v['native_enemy']['resolved']['attributes'];bb={b['key']:b['value'] for b in v['native_enemy']['resolved']['talentBlackboard']}
 p=replace(json.loads((ROOT/'packages/campaign/chapter09_consumers/ordinary/enemy_1167_dubow.module.v1.json').read_bytes()),'ch9/dubow','ch9/'+name)
 p=replace(p,'e00578058467316a',vid.split('/')[-1]);body=p['entities'][0]['components'];prefix='rule/ch9/'+name+'/';bp='buff/ch9/'+name+'/';ap='ability/ch9/'+name+'/'
 root=next(c for c in cs.values() if c['native_class']=='Enemy');mover=next(c for c in cs.values() if c['native_class']=='MoveController')
 body['attributes']['base'].update(max_hp=attrs['maxHp'],atk=attrs['atk'],**{'def':attrs['def'],'mres':attrs['magicResistance']},move_speed=attrs['moveSpeed'],attack_interval=attrs['baseAttackTime'],mass_level=attrs['massLevel'])
 body['resources']['hp']['initial']=attrs['maxHp'];body['resources']['mode']={'initial':0,'capacity':3};body['spatial']['steering']['parameters'].update(response_factor=mover['raw']['_steeringFactor'],max_acceleration=mover['raw']['_maxSteeringForce']);body['abilities']=[]
 p['entities'][0]['metadata']={'native_variant':vid,'native_reference':v['native_reference']};p['manifest']['id']='package/ch9/'+name+'/source_v1'
 p['manifest']['metadata']={'source_locks':{str(x):sha(x) for x in [SOURCE,SOURCE.with_name('source.detail.v1.json'),SOURCE.with_name('buffs.typed.v3.json'),Path(__file__)]},'required_runtime':implementation_digest(),'native_variant':vid,'source_native':v,'source_prefab':pref,'runtime_created':True,'external_required_buffs':([pillar_trait_buff] if name=='dugago' else []),'whole_stage':False,'client_verified':False,'reference_policy':{'movement':'native .5 move_multiplier via Ark rules, source steering','stone_finish_policy':'Native ON_BUFF_FINISH has no expiry guard, so legitimate early finish executes same flight chain; death/retire removal is excluded by live-owner guard; visual-only effect Buffs do not create extra gameplay states.','source_version':'frozen official20250327 enemy assets + fixed56 enemy table','animation':'combat Spine binding; mode hooker attack replacement requires source supplement'}}
 selector=next(c for c in cs.values() if c['native_class']=='AdvancedSelector');cfg=deepcopy(selector['raw']);geo=next(g for g in pref['geometry_sources'] if g['unity_type']=='CircleCollider2D' and g['gameobject_path_id']==cfg['m_GameObject']['m_PathID'])
 p['selectors'][0]['region']['radius']=geo['raw']['m_Radius'];p['selectors'][0]['eligibility']['parameters']['source_configuration']=cfg
 # Exact melee semantics use blocker identity. Ranged mode owns source native collider.
 melee_sid='selector/ch9/'+name+'/blocker';p['selectors'].append({'id':melee_sid,'kind':'selector','region':{'type':'all'},'filters':[{'state':'alive'}],'limit':1,'eligibility':{'rule':prefix+'blocker','parameters':{'source_configuration':cfg,'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':deepcopy(DEFAULT_STATE)}}})
 p['rules'].append({'id':prefix+'blocker','kind':'rule','contract':'targeting.eligibility','parameters':{'base_rule':prefix+'eligible'},'implementation':{'type':'provider','provider':'reference.ch9.actual_blocker'}})
 # Base eligibility provider only restricts when blocked; add explicit declaration to melee activation.
 template=deepcopy(p['abilities'][0]);p['abilities']=[];profiles=[]
 for mode in v['modes']:
  idx=mode['index'];combat=mode['nodes']['_combat'];normal='native_class' in combat;aid=ap+'mode'+str(idx)
  prof={'mode':idx,'selectors':[],'cast_groups':[],'parameters':{'normal':normal}}
  if normal:
   ranged=combat['native_class']=='RangedAttack';a=deepcopy(template);a['id']=aid;a['selector']=p['selectors'][0]['id'] if ranged else melee_sid;a['activation']['condition']='inputs.resources.mode.current == '+str(idx)+( '' if ranged else " and inputs.source.components.runtime.blocked_by != None")
   detail=json.loads(SOURCE.with_name('source.detail.v1.json').read_bytes());anim=next(x['binding'] for x in detail['animation_remapped_bindings'] if x['variant_id']==vid and x['mode']==idx and x['role']=='_combat');a['duration_seconds']=anim['duration']['seconds'];a['timeline'][0]['at_seconds']=next(e['seconds'] for e in anim['events'] if e['name']=='OnAttack');e=a['timeline'][0]['effect'];e['damage_type']='arts' if combat['raw']['_damageType']==2 else 'physical'
   if not ranged:e.pop('projectile_definition',None)
   a['metadata']={'source_mode':idx,'native_combat':combat};body['abilities'].append(aid);p['abilities'].append(a);prof['selectors']=[{'key':'normal','selector':a['selector']}];prof['cast_groups']=[{'key':'normal','abilities':[aid]}]
  profiles.append(prof)
 behavior=p['behaviors'][0];behavior['decision']={'rule':prefix+'decision','mode_resource':'mode','profiles':profiles}
 next(r for r in p['rules'] if r['id']==prefix+'decision')['implementation']['provider']='reference.ch9.mode_decision'
 projectile_key='projectile_enemy_'+name;native=d['projectiles'][projectile_key];motion=next(c['raw'] for c in native['components'].values() if c['native_class']=='AdvancedMovement');simple=next(c['raw'] for c in native['components'].values() if c['native_class']=='SimpleProjectile');proj=p['projectiles'][0];proj['lifetime_seconds']=simple['_lifeTime'];proj['motion']['parameters']['speed']=motion['_speed'];proj['metadata']={'native_projectile':native}
 if name=='durokt':
  body['spatial']['motion_mode']=1;body['selection_state']['motion']=2;body['buffs']['initial']=[bp+'fly'];p['buffs']=[{'id':bp+'fly','kind':'buff','selection_flags':{'abnormal_flags':[8]},'active_rule':prefix+'flight_active'},{'id':bp+'landing_stun','kind':'buff','metadata':{'native_DB':json.loads(SOURCE.with_name('buffs.typed.v3.json').read_bytes())['found_rows']['stun'],'native_BB_stun':.5},'duration_seconds':.5,'selection_flags':{'abnormal_flags':[0]},'control':{'move':False,'attack':False,'abilities':False,'interrupt':True}}]
  p['rules'].append({'id':prefix+'flight_disabled','kind':'rule','contract':'behavior.threshold','parameters':{'required_buff':bp+'fly'},'implementation':{'type':'provider','provider':'reference.ch9.flight_disabled'}})
  p['rules'].append({'id':prefix+'flight_active','kind':'rule','contract':'buff.applicability','implementation':{'type':'provider','provider':'reference.ch9.flight_active'}})
  behavior['states']={'active':{},'ground':{}};behavior['transitions']=[{'from':'active','to':'ground','condition_rule':prefix+'flight_disabled','effects':[{'op':'modify_resource','resource':'mode','value':1},{'op':'remove_buff','buff':bp+'fly'},{'op':'set_motion_mode','value':0},{'op':'apply_buff','buff':bp+'landing_stun'},{'op':'emit','event':'native.durokt.break','payload':{}}]}]
 else:
  refraction=next(x['raw']['_buffs'][0] for x in v['passive_and_skill_components'] if x['class']=='PassiveBuffAbility' and x['raw']['_buffs'][0]['buffKey']=='enemy_refracting');p['buffs'][0]['metadata']={'native_inline':refraction};p['buffs'][0]['selection_flags']={'abnormal_immunes':refraction['attributes']['abnormalImmunes']};body['buffs']['initial']=[bp+'refracting',bp+'pillar_check'];body['rebirth']={'resource':'hp','max_count':1,'delay_seconds':0,'restore_ratio':(.20000000298023224 if restore_profile=='native_reference' else 1),'restore_rule':prefix+'restore','skip_rule':prefix+'pillar_skip','on_skip':[{'op':'modify_resource','resource':'mode','value':3}],'retain_buffs':[bp+'refracting',bp+'pillar_check'],'reset_attack_clock':True,'on_finish':[{'op':'modify_resource','resource':'mode','value':1},{'op':'apply_buff','buff':bp+'stone'}]}
  p['buffs'] += [{'id':bp+'pillar_check','kind':'buff','metadata':{'native_template':'enemy_dugago_t[attack_by_dupilr]'}},{'id':bp+'stone','kind':'buff','duration_seconds':bb['stone.duration'],'selection_flags':{'abnormal_flags':[3,22,8],'abnormal_immunes':[25]},'control':{'move':False},'modifiers':[{'attribute':'def','layer':'flat','value':bb['stone.def']},{'attribute':'mres','layer':'flat','value':bb['stone.magic_resistance']}],'on_remove':[{'op':'modify_resource','resource':'mode','value':2,'condition':'inputs.source.components.runtime.alive'},{'op':'set_motion_mode','value':1,'condition':'inputs.source.components.runtime.alive'},{'op':'apply_buff','buff':bp+'unbalance_immune','condition':'inputs.source.components.runtime.alive'}]},{'id':bp+'unbalance_immune','kind':'buff','selection_flags':{'abnormal_flags':[8],'abnormal_immunes':[25]}}]
  p['rules'] += [{'id':prefix+'restore','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'inputs.parameters.capacity * inputs.parameters.ratio'}},{'id':prefix+'pillar_skip','kind':'rule','contract':'lifecycle.rebirth_skip','dependencies':[pillar_trait_buff],'parameters':{'source_buffs':[pillar_trait_buff]},'implementation':{'type':'provider','provider':'reference.ch9.source_buff_skip'}}]
  p['manifest']['metadata']['reference_policy']['rebirth_conflict']={'native_hpRechargeRatio':next(c['raw']['_hpRechargeRatio'] for c in cs.values() if c['native_class']=='RebornTalent'),'model_restore_ratio':body['rebirth']['restore_ratio'],'profile':restore_profile,'reference_url':'https://prts.wiki/w/守墓石像','choice':'Default fixed native20%; explicit prts_reference100% alternative. Version conflict retained; neither is client verified.'}
 p['manifest']['metadata']['source_bson_templates']={k:v for k,v in d['bson_templates']['templates'].items() if name in k}
 fixture=deepcopy(p);fixture['buffs']+=deepcopy(list(dependency_definitions));fixture['scenarioDraft']={'id':'scene/rock/compile','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':4},'initialEntities':[{'definition':p['entities'][0]['id'],'position':{'row':0,'col':0}}]};Compiler(providers=providers()).compile(fixture)
 return p
if __name__=='__main__':
 OUT.mkdir(parents=True,exist_ok=True)
 for k in KEYS:
  
  if k==KEYS[1]:continue
  p=build(k);f=OUT/(k+'.module.v1.json');f.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(k,sha(f))
