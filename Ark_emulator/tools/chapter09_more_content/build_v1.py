"""Source-bound shield, phalanx aura and mage; frozen foundation V5 runtime."""
import hashlib,json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CAND=ROOT.parent/'unpack_work/campaign_campaign_foundation_v5_candidate'
sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
SOURCE=ROOT/'packages/campaign/chapter09_source_prepare/enemies.native.v1.json'
FREEZE=SOURCE.with_name('source.freeze.v2.json')
OUT=ROOT/'packages/campaign/chapter09_consumers/more_ordinary'
CORE='82db6a9db5ddd3a4c3c58f05b04e773419312ae77d5fc086fbb98a7a984bf8ae'
KEYS=('enemy_1170_dushld','enemy_1169_duphlx','enemy_1168_dumage')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def replace(v,old,new,oldid,newid):
 if isinstance(v,dict):return {k:replace(x,old,new,oldid,newid) for k,x in v.items()}
 if isinstance(v,list):return [replace(x,old,new,oldid,newid) for x in v]
 if isinstance(v,str):return v.replace(old,new).replace(oldid,newid)
 return v
def mask_eligibility(inputs,params,context):
 from ark_sim.domains.selection import eligibility_profile
 result=eligibility_profile(inputs,{},context)
 if inputs['source']['id']==inputs['candidate']['id']:return {'accepted':False,'reason':'source_excluded'}
 if not result['accepted']:return result
 now=context['time'];rows=inputs['candidate'].get('components',{}).get('buffs',{}).get('instances',[])
 ok=any(x['definition']==params['required_buff'] and x.get('applicability',{}).get('active',True) and (x['expires_at'] is None or now<x['expires_at']) for x in rows)
 return {'accepted':ok,'reason':'required_live_buff' if ok else 'missing_required_live_buff'}
def providers():
 from tools.chapter08_bsnake_combat.policies_v1 import providers as base
 return {**base(),'reference.required_live_buff.eligibility':{'callable':mask_eligibility,'version':'1'}}
def build(key):
 from ark_sim import Compiler
 from ark_sim.adapters.api import implementation_digest
 from ark_sim.domains.selection import DEFAULT_STATE
 if key not in KEYS:raise ValueError('Unsupported source closure: '+key)
 assert implementation_digest()==CORE
 assert sha(SOURCE)=='592afac29cc32d1aeaba3ea739eb6da5a218055e255a42f53315f4a2ca0962ff'
 assert sha(FREEZE)=='2362ba090627b22809a6feffcb356cd25389f0a8e2063f7e45d4c19b94489275'
 data=json.loads(SOURCE.read_bytes());vid,row=next((k,v) for k,v in data['variants'].items() if v['prefab_key']==key)
 name=key.split('_',2)[2];ranged=name=='dumage';old='dubow' if ranged else 'duhond'
 template=ROOT/f'packages/campaign/chapter09_consumers/ordinary/enemy_{1167 if ranged else 1165}_{old}.module.v1.json'
 p=json.loads(template.read_bytes());oldid=p['manifest']['metadata']['native_variant'].split('/')[-1]
 p=replace(p,'ch9/'+old,'ch9/'+name,oldid,vid.split('/')[-1]);p['manifest']['id']='package/ch9/'+name+'/source_v1'
 cs=data['prefabs'][key]['components'];root=next(c for c in cs.values() if c['native_class']=='Enemy');mover=next(c for c in cs.values() if c['native_class']=='MoveController')
 mode=row['modes'][0];combat=mode['nodes']['_combat'];raw=combat['raw'];attrs=row['native_enemy']['resolved']['attributes'];bb={x['key']:x['value'] for x in row['native_enemy']['resolved']['talentBlackboard']}
 assert len(row['modes'])==1 and not root['raw']['_commonAbilities'] and not mode['raw']['_generalAbilities']
 assert (raw['_attackType'],raw['_elementDamageType'],raw['_epDamageRatio'],raw['_selectTargetSource'],raw['_selectTargetTiming'],raw['_timeMode'])==(1,0,0,2,0,0)
 assert not raw['_activeBuffs'] and attrs['hpRecoveryPerSec']==0
 assert combat['native_class']==('RangedAttack' if ranged else 'MeleeAttack') and raw['_damageType']==(2 if ranged else 1)
 assert not attrs['silenceImmune'] and not attrs['stunImmune']
 passive=row['passive_and_skill_components'];refract=next(x for x in passive if x['class']=='PassiveBuffAbility' and x['raw']['_buffs'][0]['buffKey']=='enemy_refracting')
 inline=refract['raw']['_buffs'][0];assert (inline['templateKey'],inline['loadFromDB'],inline['isSilenceable'],bb['refracting.magic_resistance'])==('empty',0,1,70)
 meta=p['manifest']['metadata'];meta.update(source_locks={str(x):sha(x) for x in (SOURCE,FREEZE,Path(__file__),template)},required_runtime=CORE,native_variant=vid,native_reference=row['native_reference'],source_root=root,source_combat=combat,source_passive=refract,source_passive_closure=passive,native_source_stats=attrs,source_field_mapping={'stats':'native_enemy.resolved.attributes','refraction':'talentBlackboard refracting.magic_resistance + inline attributeType3/formula0','attack':'native mode0 shared/combat node; exact Spine OnAttack and duration','movement':'MoveController steering and blockVolume; .05 model arrival radius'})
 body=p['entities'][0]['components'];p['entities'][0]['metadata']={'native_variant':vid,'native_reference':row['native_reference']}
 body['attributes']['base'].update(max_hp=attrs['maxHp'],atk=attrs['atk'],**{'def':attrs['def'],'mres':attrs['magicResistance']},move_speed=attrs['moveSpeed'],attack_interval=attrs['baseAttackTime'],attack_speed_ratio=attrs['attackSpeed']/100,mass_level=attrs['massLevel'],block_cost=root['raw']['_blockVolume'])
 body['resources']['hp']['initial']=attrs['maxHp'];body['spatial']['steering']['parameters'].update(response_factor=mover['raw']['_steeringFactor'],max_acceleration=mover['raw']['_maxSteeringForce'])
 p['buffs'][0]['metadata']['native_inline']=inline
 animation=combat['animation_binding'];hit=next(e for e in animation['events'] if e['name']=='OnAttack');assert hit['exact_authored_frame'] and animation['duration']['exact_authored_frame']
 ability=p['abilities'][0];ability['duration_seconds']=animation['duration']['seconds'];ability['timeline'][0]['at_seconds']=hit['seconds'];ability['metadata']={'source_OnAttack_frame':hit['frame'],'source_full_frame':animation['duration']['frame']}
 prefix='rule/ch9/'+name+'/'
 if ranged:
  assert mode['nodes']['_attack']['path_id']==combat['path_id'] and len(passive)==1
  selector=next(c for c in cs.values() if c['native_class']=='AdvancedSelector');cfg=selector['raw'];go=cfg['m_GameObject']['m_PathID']
  geo=next(g for g in data['prefabs'][key]['geometry_sources'] if g['unity_type']=='CircleCollider2D' and g['gameobject_path_id']==go)
  assert geo['raw']['m_Offset']=={'x':0.0,'y':0.0}
  p['selectors'][0]['region']['radius']=geo['raw']['m_Radius'];p['selectors'][0]['eligibility']['parameters']['source_configuration']=deepcopy(cfg)
  native=data['projectiles'][raw['_projectileKey']];pc=native['components'];motion=next(c['raw'] for c in pc.values() if c['native_class']=='AdvancedMovement');simple=next(c['raw'] for c in pc.values() if c['native_class']=='SimpleProjectile')
  assert (motion['_moveType'],motion['_speed'],simple['_lifeTime'],simple['_maxHitNum'],simple['_stopWhenSourceInvalid'])==(1,10,10,1,0)
  proj=p['projectiles'][0];proj['lifetime_seconds']=simple['_lifeTime'];proj['metadata']={'native_projectile':native};proj['lifecycle'].update(force_reach_on_expire=bool(motion['_forceReachedWhenTimeup']),hit_on_expire=bool(simple['_alwaysHitTraceTargetInTheEnd']))
  ability['timeline'][0]['effect']['damage_type']='arts';meta['source_geometry']=geo;meta['reference_policy']['projectile']='Source homing10 life10 retain-on-source-retire, current source/target attributes at hit';meta['reference_policy']['attack_target']='Native collider2.0999999046325684; typed enemy side/ground/category, targetfree and camouflage rejection; HATE lexical priority then recent ID reference'
 else:
  assert mode['nodes']['_attack']['status']==mode['nodes']['_attackTrigger']['status']=='native_null'
  assert len(passive)==(4 if name=='duphlx' else 1)
 if name=='duphlx':
  aura=next(x for x in passive if x['class']=='AuraAbility');ar=aura['raw'];validator=cs[str(ar['_targetValidator']['m_PathID'])];vr=validator['raw'];child=ar['_buffs'][0]
  assert (ar['_selfOption'],ar['_removeBuffWhenTargetLeave'],ar['_removeBuffWhenAbilityDetached'])==(2,1,1)
  dump=ROOT.parent/'Ark_data/Il2CppDumper_current/dump.cs';assert 'public const AuraAbility.SelfOption EXCLUDE = 2;' in dump.read_text(encoding='utf8');meta['source_locks'][str(dump)]=sha(dump)
  assert vr['_buffs']==['duphlx_mask'] and (vr['_excludeKey'],vr['_filterBuffSource'],vr['_hostAsTarget'])==(0,0,0)
  assert (child['disableOverride'],child['maxStackCnt'],child['maxValidStackCnt'],child['independentCharacterSource'])==(1,-1,-1,0)
  assert child['attributes']['attributeModifiers']==[{'attributeType':2,'formulaItem':0,'value':0.0,'loadFromBlackboard':1,'fetchBaseValueFromSourceEntity':0}]
  geo=next(g for g in data['prefabs'][key]['geometry_sources'] if g['unity_type']=='CircleCollider2D' and g['gameobject_path_id']==ar['m_GameObject']['m_PathID']);assert geo['raw']['m_Radius']==1
  cfg={'_'+k:v for k,v in vr['_targetOptions'].items()};cfg.update(_forceIgnoreCamouflage=0,_needProfessionMask=0)
  sid='selector/ch9/duphlx/aura';marker='buff/ch9/duphlx/mask';member='buff/ch9/duphlx/def200';parent='buff/ch9/duphlx/aura'
  mask=next(x['raw']['_buffs'][0] for x in passive if x['class']=='PassiveBuffAbility' and x['raw']['_buffs'][0]['buffKey']=='duphlx_mask')
  p['selectors'].append({'id':sid,'kind':'selector','region':{'type':'radius','radius':geo['raw']['m_Radius']},'filters':[{'state':'alive'}],'eligibility':{'rule':prefix+'mask_eligible','parameters':{'source_configuration':cfg,'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':deepcopy(DEFAULT_STATE)}}})
  p['rules'].append({'id':prefix+'mask_eligible','kind':'rule','contract':'targeting.eligibility','parameters':{'required_buff':marker},'implementation':{'type':'provider','provider':'reference.required_live_buff.eligibility'}})
  p['buffs'] += [{'id':marker,'kind':'buff','metadata':{'native_inline':mask}}, {'id':member,'kind':'buff','stacking':{'mode':'independent'},'modifiers':[{'attribute':'def','layer':'flat','value':bb['auraDefup.def']}],'metadata':{'native_inline':child}}, {'id':parent,'kind':'buff','aura':{'selector':sid,'buff':member},'metadata':{'native_aura':aura,'native_validator':validator}}]
  body['buffs']['initial'] += [marker,parent];meta['source_geometry']=geo;meta['source_field_mapping']['aura']='CircleCollider1 not DB range1.5; EXCLUDE2; live duphlx_mask inclusion; unbounded nonoverriding DEF200 per source'
 fixture=deepcopy(p);fixture['scenarioDraft']={'id':'scene/more/compile','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':4},'initialEntities':[{'definition':p['entities'][0]['id'],'position':{'row':0,'col':0}}]}
 Compiler(providers=providers()).compile(fixture)
 return p
if __name__=='__main__':
 OUT.mkdir(parents=True,exist_ok=True)
 for key in KEYS:
  p=build(key);path=OUT/(key+'.module.v1.json');path.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(key,sha(path))

