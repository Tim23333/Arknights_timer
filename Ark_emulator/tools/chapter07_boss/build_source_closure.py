"""Exact selected Patriot source, including all passive/dependency gaps."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'packages/campaign/chapter07_boss/patrt'
VID='enemy_1506_patrt@0/a53a85a6d0cd714f'
PINS={'packages/campaign/chapter07_consumption_plan/source.consumption.plan.json':'298deaf0dc7ed9a1068d1dfe75c8b90a9e1c3f8ae0a967f3baa28ff3f87064f1','packages/campaign/chapter07_sources/native.reference.json':'8bd457cc8f24d154b304a8cf0a946b9e2a83ae1dcfc01a08073a97364dc1119e','packages/campaign/chapter07_plans/source.plan.json':'e5a60611432f7413689af811a069fb33aac57123bd58190f51161f8a01129339','packages/campaign/chapter07_predefines/source.v4.reference.json':'9ab8b1049f5e0c9d34977563ccd8ac394044f77ff8da44b9cb717f52a1b9dfcb'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 for name,pin in PINS.items():assert sha(ROOT/name)==pin
 n=json.loads((ROOT/'packages/campaign/chapter07_sources/native.reference.json').read_bytes());plan=json.loads((ROOT/'packages/campaign/chapter07_consumption_plan/source.consumption.plan.json').read_bytes());pre=json.loads((ROOT/'packages/campaign/chapter07_predefines/source.v4.reference.json').read_bytes());v=n['variants'][VID];p=n['prefabs'][v['prefab_key']];h={x['path_id']:x for x in p['hierarchy']}
 paths={}
 for key,c in p['components'].items():
  go=c['gameobject_path_id'];chain=[]
  while go in h:x=h[go];chain.append(x['name']);go=x['parent_path_id']
  paths[key]='/'.join(reversed(chain))
 keys={c['script_key'] for c in p['components'].values() if c.get('script_key')};templates={c['raw'].get('templateKey') for c in []}
 cb={k:n['bson_templates']['templates'][k] for k in ['empty','finish_current_wave_when_buff_finish','switch_mode_restart_fsm','triggerability_tick_trigger']}
 dump=ROOT.parent/'Ark_data/Il2CppDumper_current/dump.cs';lines={}
 with dump.open(encoding='utf8') as f:
  for i,line in enumerate(f,1):
   if 533026<=i<=533033 or 162370<=i<=162383:lines[str(i)]=line.rstrip()
   if i>533033:break
 closure={'schema':'ark-sim/ch7-patrt-source-closure/v1','fixed_commit':'56aee3d6c5a29c3a0d192456d70d14252cbb0804','source_locks':PINS,'source_asset_locks':n['source_locks'],'variant':v,'selected_consumption':next(x for x in plan['exact12_variants'] if x['variant_id']==VID),'prefab':p,'component_hierarchy_paths':paths,'animation':n['animations'][v['prefab_key']],'projectile_spear':n['projectiles']['projectile_spear'],'monoscripts':{k:n['native_monoscripts'][k] for k in keys},'bson_templates':cb,'ore_mine_dependencies':{'source_sha256':sha(ROOT/'packages/campaign/chapter07_predefines/source.v4.reference.json'),'prefabs':pre['prefabs'],'skill_prefabs':pre['skill_prefabs'],'skill_tables':pre['skill_tables'],'bson_templates':pre['bson_templates']},'native_enum_declarations':{'path':str(dump),'sha256':sha(dump),'excerpt':lines,'scope':'Current local declarations; nativeasset/body version equivalence remainsreference'},'identity_note':'SelectedID is patrt, no durahan variant added by name. RawAttack/Trigger null mode0 preserved; sharedCombatAttackPPtr mode1 deduped.','mechanism_consumers':{'phase0':'Actualblocked inputtarget2 only, fourphysical OnAttack19/22/25/28 full45, ASPD TimeMode0; Shield+.5ATK/+2DEF/+1RES andtaunt+2','strength':'Globalally validator side1/motion3/category1, selfDEFAULT0; +.2ATK/+200DEF andsharedstrength marker. ReferenceincludesSelf, nonstackingmultiemitter/lifecycle needactualproof','rebirth':'NativeuseAbilityToHandle1/Reborning, max1/.8500000238418579; BB60sec +15secinvulnerability. Cannot replacewith fullHP/Frostconstants/HPgrant','phase1':'Singlephysical16/full41 TimeMode0; rage+.1move/-.4interval/+.2ATK/+200DEF andimmunities0/12/16/25/sleep0','spear':'Init15/CD20 physical1.35 sourceSkill51/full103, highgroundBuildableType2/farthestpostfilter25/ground only, projectile_spear rawlifecycle','immo':'9999 skillclock isnotperiod; BuffTrigger interval.8 requests Immo_Rage true.0521 duringreborning andRage, actualsourceowner/provenance required','wave':'ReleaseWave finish_current_wave_when_buff_finish must consume actualwave, not emit-only','ore_mine':'ore_s conditional CheckContainsBuff ore_immune/IfNot onfinish trueDamage. Mine instant_damage_pure notautomatically blockedbyore_immune.'},'reference_policies':{'source_methods':'Values/flags explicit where decoded; unavailable method bodies do not block. Every guessed timing/side/lifecycle interpretation declaredreplaceable.','restore':'Use exactnative ratio.8500000238418579; no currentwiki fullHP override','aura_self':'CurrentenumDEFAULT0 follows validator, referenceincludes owner corroboratedPRTS; not explicitnativeINCLUDE1','timing':'ExplicitTimeMode0 allnormal/spear scale bothwindup/full duration; .01 minimumASPD reference clamp'},'runtime_authored':False,'complete_source_policies':False,'independent_reviewed':False,'whole_stage_executed':False,'client_verified':False}
 OUT.mkdir(parents=True,exist_ok=True);path=OUT/'source.closure.json';path.write_bytes((json.dumps(closure,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'sha256':sha(path),'bytes':path.stat().st_size}))
if __name__=='__main__':main()
