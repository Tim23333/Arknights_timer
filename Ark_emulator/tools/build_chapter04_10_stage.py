"""Exact 4-10 43/7 join on an explicit Frost module and selected V2 runtime."""
import argparse,hashlib,json,sys
from collections import Counter
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PINS={
 'packages/campaign/chapter04_plans/source.plan.json':'2b9a49412d64945eacca82282866b4c8b12eb11f5676dd831878a51ec01a9086',
 'packages/campaign/chapter04_units/ordinary.reference_model.json':'d53bcd485b0b67bf971fb39176fdb2abfa962e8c9055b6eb07ce643dbeff0038',
 'packages/campaign/chapter04_units/ranged/combat_guard.source_circle.reference_model.json':'d2a20696aed4a3c5d693500d4bd2e4c7311181b54f2912adb7bca17755f98bfd',
 'packages/campaign/roster/fixed12.m26.reference_module.json':'fd48b0cc67a6b96457b6d7df69397493b3914d65676c554a92b90193374c2c04',
 'packages/campaign/chapter01_stage_models/m26/level_main_01-12.partial.json':'a68023a0ec81cc95df9ccdec452979f5131fda648dc6673b8a3e9110108e38a1'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load_bound(path,pin):
 if sha(path)!=pin:raise ValueError('Frozen 4-10 input changed '+str(path))
 return json.loads(Path(path).read_bytes())
def build(frost_module,frost_sha):
 from ark_sim import Compiler
 from ark_sim.adapters.api import implementation_digest
 from tools.build_reference_stage_scenario_v2 import compose
 from tools.campaign_content_composition import compose_modules,reachable_content
 data={name:load_bound(ROOT/name,pin) for name,pin in PINS.items()};frost=load_bound(frost_module,frost_sha);plan=data['packages/campaign/chapter04_plans/source.plan.json'];stage=plan['stages']['level_main_04-10'];native=stage['native_document'];roster=data['packages/campaign/roster/fixed12.m26.reference_module.json'];portal_source=data['packages/campaign/chapter01_stage_models/m26/level_main_01-12.partial.json']
 modules=[('ordinary',data['packages/campaign/chapter04_units/ordinary.reference_model.json']),('ranged_source_circle',data['packages/campaign/chapter04_units/ranged/combat_guard.source_circle.reference_model.json']),('complete_frost_explicit',frost),('fixed12',roster)]
 definitions,_=compose_modules(modules);units={}
 for d in definitions.values():
  vid=d.get('metadata',{}).get('native_variant_id',d.get('metadata',{}).get('native_variant'))
  if d['kind']=='entity' and vid:
   if vid in units:raise ValueError('Conflicting exact stage variant '+vid)
   units[vid]=d['id']
 bindings={};rows=[]
 for vid in stage['variant_ids']:
  if vid not in units:raise ValueError('Missing exact 4-10 variant '+vid)
  ref=plan['variants'][vid]['native_reference'];motion=plan['variants'][vid]['native_enemy']['resolved']['motion']
  if ref not in native['enemyDbRefs']:raise ValueError('Native enemy reference mismatch '+vid)
  if ref['id'] in bindings:raise ValueError('Ambiguous native enemy key')
  bindings[ref['id']]={'unit':units[vid],'motion':motion};rows.append({'variant_id':vid,'native_reference':deepcopy(ref),'unit_definition':units[vid],'native_motion':motion})
 profiles={k:deepcopy(portal_source['scenarioDraft']['map']['tile_mechanics'][k]) for k in ('tile_telin','tile_telout')};assert profiles=={'tile_telin':{'type':'route_checkpoint_portal','role':'entry'},'tile_telout':{'type':'route_checkpoint_portal','role':'exit'}}
 scene,controls=compose(native,'level_main_04-10',bindings,profiles)
 if controls:
  # Preserve the helper's real immediate, managed UI observation consumers.
  # No rendering or player acknowledgement is inferred for these source actions.
  for control in controls:
   for step in control.get('steps',[]):
    if step.get('kind')!='effects' or any(e.get('op')!='emit' or e.get('event') not in ('reference.enemy_info.observed','reference.route_preview.observed') for e in step.get('effects',[])):raise ValueError('4-10 unexpected native control requires a real explicit consumer')
  modules.append(('native_observation_controls',{'definitions':deepcopy(controls)}))
 if any(native.get(key) for key in ('predefines','hardPredefines')) and any((native.get(key) or {}).get(bucket) for key in ('predefines','hardPredefines') for bucket in ('characterInsts','tokenInsts','characterCards','tokenCards')):raise ValueError('New native predefines require explicit real consumers')
 scene['roster']=deepcopy(roster['manifest']['metadata']['roster']);scene['rules']=deepcopy(roster['manifest']['metadata']['stage_rules'])
 if definitions[scene['rules']['movement.speed']]['parameters']['multiplier']!=native['options']['moveMultiplier']:raise ValueError('Native move multiplier not consumed')
 native_life=deepcopy(scene['resources']['life']);scene['resources']['life'].update(initial=99999,capacity=99999)
 modules.append(('spawn_policy',{'rules':[deepcopy(r) for r in portal_source['rules'] if r['id']=='rule/m7_spawn_rectangle']}))
 result,_=reachable_content(scene,modules,manifest_id='package/reference/level_main_04-10/complete_frost_explicit');meta=result['manifest']['metadata'];meta.update(source_locks={**PINS,str(Path(frost_module).resolve()):frost_sha},builder_sha256=sha(Path(__file__)),required_runtime=implementation_digest(),variant_bindings=rows,source_births=43,native_options=deepcopy(native['options']),native_predefines=deepcopy(native.get('predefines')),native_hard_predefines=deepcopy(native.get('hardPredefines')),native_runes=deepcopy(native.get('runes')),native_optional_runes=deepcopy(native.get('optionalRunes')),native_global_buffs=deepcopy(native.get('globalBuffs')),portal_profile_source={'path':'packages/campaign/chapter01_stage_models/m26/level_main_01-12.partial.json','sha256':PINS['packages/campaign/chapter01_stage_models/m26/level_main_01-12.partial.json'],'profiles':profiles},goal_base_life_authoring={'native':native_life,'selected_initial':99999,'selected_capacity':99999,'operator_enemy_HP_unchanged':True},inherited_module_metadata={label:deepcopy(p.get('manifest',{}).get('metadata',{})) for label,p in modules},model_policies={'ranged_module':'source_circle','full_frost_module':str(Path(frost_module).resolve()),'full_frost_module_sha256':frost_sha,'native_motion_binding':'Native resolved stage motion; full Frost module retains its explicit source/reference skill target policies'},full_stage_executed=False,actual_client_verified=False,source_runtime_review_status='Fresh exact author join; independent consumers and frozen full runtime/module receipts remain necessary')
 s=result['scenarioDraft'];births=sum(a.get('count',1) for w in s['timeline']['waves'] for f in w['fragments'] for a in f['actions'] if a['kind']=='spawn');tiles=Counter(t['tileKey'] for t in s['map']['tiles']);checkpoint_counts=Counter(c['type'] for w in s['timeline']['waves'] for f in w['fragments'] for a in f['actions'] if a['kind']=='spawn' for c in a['spawn']['route'].get('checkpoints',[]))
 if births!=43 or len(rows)!=7 or len(s['roster'])!=12 or len(set(s['roster']))!=12 or s['parameters']['deploy_capacity']!=10 or s['resources']['dp']['initial']!=10 or native['options']['moveMultiplier']!=.5 or tiles['tile_telin']!=2 or tiles['tile_telout']!=2 or checkpoint_counts['DISAPPEAR']!=2 or checkpoint_counts['APPEAR_AT_POS']!=2 or s['seed']!=native['randomSeed']:raise ValueError('Exact native 4-10 accounting changed')
 Compiler().compile(result);return result
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--runtime-root',type=Path,required=True);ap.add_argument('--expected-core',required=True);ap.add_argument('--frost-module',type=Path,required=True);ap.add_argument('--frost-sha256',required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();runtime=a.runtime_root.resolve();sys.path.insert(0,str(runtime));sys.path.insert(1,str(ROOT));import ark_sim
 from ark_sim.adapters.api import implementation_digest
 if Path(ark_sim.__file__).resolve().parent!=runtime/'ark_sim' or implementation_digest()!=a.expected_core:raise ValueError('Wrong selected V2 runtime')
 if a.output.exists():raise ValueError('Preserve previous stage package')
 result=build(a.frost_module,a.frost_sha256);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha256':sha(a.output),'core':a.expected_core,'births':43,'variants':7,'fixed_roster':12,'native_slots':10,'native_DP':10,'portal_entry_exit_cells':[2,2],'full_stage_executed':False}))
if __name__=='__main__':main()
