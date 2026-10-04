"""Machine-readable exact five-variant join, never an executable hole stub."""
from pathlib import Path
import json,hashlib,argparse
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'packages/campaign/chapter02_units/main_02-09.enemy_binding.plan.json';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def build():
 source=ROOT/'packages/campaign/chapter02_sources/native.reference.json';d=json.loads(source.read_bytes());stage=d['stages']['level_main_02-09']
 first=ROOT/'packages/campaign/chapter02_behavior/models.partial.json';ground=ROOT/'packages/campaign/chapter02_units/airdrp.birth.model.json';p=json.loads(first.read_bytes());g=json.loads(ground.read_bytes())
 paths=[source,first,ground,ROOT/'packages/campaign/chapter02_sources/attacks.model.json',ROOT/'packages/campaign/chapter02_tiles/source.reference.json'];locks={str(x.relative_to(ROOT)):sha(x) for x in paths};rows=[]
 for vid in stage['resolved_variant_ids']:
  v=d['variants'][vid];native=v['native_enemy']['native_id'];isground=v['native_enemy']['resolved']['motion']=='WALK';package=g if isground else p;path=ground if isground else first
  matches=[u for u in package['entities'] if u.get('metadata',{}).get('native_variant_id',u.get('metadata',{}).get('native_variant'))==vid]
  if len(matches)!=1:raise ValueError('exact unit variant binding missing: '+vid)
  unit=matches[0];count=sum(a['native']['count'] for a in stage['spawn_sources'] if vid in a['variant_candidates']);assert all(len(a['variant_candidates'])==1 for a in stage['spawn_sources'] if vid in a['variant_candidates'])
  root=next(c['raw'] for c in v['components'].values() if c['native_class']=='Enemy');attrs=v['native_enemy']['resolved']['attributes']
  rows.append({'variant_id':vid,'native_reference':v['native_reference'],'unit_definition':unit['id'],'package':str(path.relative_to(ROOT)),'package_sha256':sha(path),'spawn_count':count,'native_motion':v['native_enemy']['resolved']['motion'],'owned_abilities':unit['components'].get('abilities',[]),'born_delay_source':root['_delayToBorn'],'born_model_consumed':isground or root['_delayToBorn']==0,'additional_stage_stat_patch_from_source':{**({'mass_level':attrs['massLevel']} if 'massLevel' in attrs else {}),'block_cost':root['_blockVolume']},'undefined_mass_policy_needed': 'massLevel' not in attrs,'client_feedback_pending':True})
 assert len(rows)==5 and sum(r['spawn_count'] for r in rows)==52
 return {'schema':'ark-sim/chapter02-stage-enemy-join-plan/v1','status':'source-variant join plan, not runnable stage','stage':'level_main_02-09','source_locks':locks,'five_variant_bindings':rows,'join_rules':['take only these selected unit closures; no name-based/level fallback','if duplicate definition IDs, require full identical definitions before dedup','new stage wrapper consumes raw timeline/Info7/managed flags/route motion/offset; do not flatten waves','classification ledger separates wave enemies, owned tokens, NPC/device and virtual fields','birth active phase begins actual spawned actor creation; no upfront register future enemies'], 'remaining_model_delivery':['tile_hole real route/lifecycle removal/drop policy, no noop/road','gazebo FLY-only damage scale1.7 plus AS-20 and full mapBB consumer','defdrn silence status->aura suspended/restored source driver','all actor targetability policy/eligibility scope explicit, including optional birth targetfree','undefined defdrn mass if force profile requires it must choose explicit reference/default policy','complete 2-9 stage and fixed12 commands actual runthrough'], 'feedback_pending':['native callback/BB radius axes/pointbody/animation scaling/customer comparison after simulation'], 'current_goal':'complete declared reference/table simulation first, user comparison afterward, leaks/deaths permitted/base life99999','formal_approved':False}
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args();p=build();b=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode()
 if a.check:assert OUT.read_bytes()==b
 else:OUT.write_bytes(b)
 print(json.dumps({'passed':True,'check':a.check,'variants':5,'spawns':52,'sha256':sha(OUT)}))
