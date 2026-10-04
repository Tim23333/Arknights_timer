"""Five exact native variants; module only, stage/map/timeline remain external."""
import argparse,hashlib,json
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'packages/campaign/chapter02_units/main_02-09.enemies.reference_module.json'
FILES={'source':'packages/campaign/chapter02_sources/native.reference.json','flying':'packages/campaign/chapter02_behavior/models.partial.json','born':'packages/campaign/chapter02_units/airdrp.birth_contact.model.json','status':'packages/campaign/chapter02_units/defdrn.status.m42.model.json'}
PINS={'source':'97447895b3edc69f0f60113ea96bc240c25c0fe980897614e93a94dd75e0d492','flying':'bda5488a79f44e195e23631f579d313de833f356f1decec6d6abd726800f9bc8','status':'5d2127bacff398b667120d26a1f09d7032b4ec0cf19a4bc9801d4c6446569a53'}
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def build():
 from tools.campaign_content_composition import compose_modules,reachable_content
 data={};locks={}
 for key,name in FILES.items():
  raw=(ROOT/name).read_bytes();value=hashlib.sha256(raw).hexdigest()
  if key in PINS and value!=PINS[key]:raise ValueError('Frozen enemy module drift: '+name)
  data[key]=json.loads(raw);locks[name]=value
 first=data['flying'];born=data['born'];status=data['status'];native=data['source'];stage=native['stages']['level_main_02-09']
 # Register conflicting source-backed changes explicitly before composition.
 original,_=compose_modules([('frozen_flying',first),('born_contact',born)])
 new,_=compose_modules([('status',status)]);replacements={};extra=[]
 for ident,value in new.items():
  if ident not in original:extra.append(value)
  elif original[ident]!=value:replacements[ident]={'definition':value,'reason':'Consume actual defdrn TargetValidator and SILENCED12 source qualification; old aura omitted this driver','source':FILES['status']+' sha256 '+locks[FILES['status']]}
 modules=[('frozen_flying',first),('born_contact',born),('status_new_dependencies',{'schemaVersion':2,'definitions':extra})]
 definitions,_=compose_modules(modules,replacements);rows=[]
 for vid in stage['resolved_variant_ids']:
  v=native['variants'][vid];found=[d for d in definitions.values() if d.get('kind')=='entity' and d.get('metadata',{}).get('native_variant_id',d.get('metadata',{}).get('native_variant'))==vid]
  if len(found)!=1:raise ValueError('Exact variant must bind once: '+vid)
  unit=deepcopy(found[0]);attrs=v['native_enemy']['resolved']['attributes'];root=next(c['raw'] for c in v['components'].values() if c['native_class']=='Enemy')
  base=unit['components']['attributes']['base'];base['block_cost']=root['_blockVolume']
  if attrs.get('hpRecoveryPerSec')!=0 or attrs.get('spRecoveryPerSec')!=0 or attrs.get('stunImmune') is not False:raise ValueError('Nonzero recovery or stun immunity requires an explicit executable consumer')
  mover=next(c['raw'] for c in v['components'].values() if c['native_class']=='MoveController')
  unit['components']['spatial'].update(motion_mode=0 if v['native_enemy']['resolved']['motion']=='WALK' else 1,steering={'rule':'rule/chapter02/unit_steering','parameters':{'response_factor':mover['_steeringFactor'],'max_acceleration':mover['_maxSteeringForce'],'arrival_radius':0.05}})
  unit.setdefault('metadata',{})['zero_source_consumers']={'hpRecoveryPerSec':0,'spRecoveryPerSec':0,'stunImmune':False,'policy':'No recovery resource driver required for exact zero; false immunity leaves default status acceptance. Nonzero/true source changes reject this builder.'}
  if 'massLevel' in attrs:base['mass_level']=attrs['massLevel']
  elif unit['metadata'].get('declared_mass_policy',{}).get('source_defined') is not False:raise ValueError('Undefined mass requires explicit model policy')
  replacements[unit['id']]={'definition':unit,'reason':'Exact fixed DB mass when defined, Enemy blockVolume/motion and all MoveController steering fields; zero recovery/nonimmune guard; undefined mass keeps declared replaceable fallback','source':FILES['source']+' sha256 '+locks[FILES['source']]}
  actions=[a for a in stage['spawn_sources'] if vid in a['variant_candidates']]
  if any(a['variant_candidates']!=[vid] for a in actions):raise ValueError('Ambiguous native spawn variant')
  rows.append({'variant_id':vid,'native_reference':v['native_reference'],'unit_definition':unit['id'],'spawn_count':sum(a['native']['count'] for a in actions),'native_motion':v['native_enemy']['resolved']['motion'],'owned_abilities':unit['components'].get('abilities',[]),'source_block_cost':root['_blockVolume'],'source_mass_defined':'massLevel' in attrs,'model_mass_level':base['mass_level'],'born_delay_seconds':root['_delayToBorn']})
 if len(rows)!=5 or sum(r['spawn_count'] for r in rows)!=52:raise ValueError('Five variants /52 source spawns required')
 scene={'id':'scene/dependency_audit/ch2_09','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':8,'cols':8},'initialEntities':[{'definition':r['unit_definition'],'instanceAlias':'closure'+str(i),'position':{'row':i,'col':1}} for i,r in enumerate(rows)]}
 package,report=reachable_content(scene,modules,replacements,manifest_id='package/chapter02/main_02-09/enemies/reference')
 package.pop('scenarioDraft');meta=package['manifest']['metadata'];meta.update(source_locks=locks,builder_sha256=sha(__file__),stage='level_main_02-09',variant_bindings=rows,required_core_features=['M41 tile.contact/buff.contact_flags','M42 synchronous aura qualification after Buff.remove'],model_delivery_ready=True,stage_executed=False,client_verified=False,formal_approved=False,feedback_pending=['native radius precision and callback clock','birth blocking/targetability declared source-policy','defdrn undefined mass fallback replaceable'],remaining_stage_consumers=['52 source spawns/7 Info original native timeline','32 holes actual contact profile','gazebo FLY-only1.7 damage+AS-20 occupant consumer','fixed12+base life99999 complete commands/runthrough'])
 return package
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args();out=build();raw=(json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode()
 if a.check:
  if OUT.read_bytes()!=raw:raise ValueError('Enemy closure module drift')
 else:OUT.write_bytes(raw)
 print(json.dumps({'passed':True,'check':a.check,'sha256':sha(OUT),'definitions':len(out['definitions'])}))
