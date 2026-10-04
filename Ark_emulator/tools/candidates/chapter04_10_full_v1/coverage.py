"""Sealed original-event coverage; triggers and absent phases explicitly separated."""
import hashlib,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/chapter04_10_full_v1';BASE=Path('E:/ArkSimEvidence/campaign/04_10_7a04c12a1a4224ee/public_v1')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 original=BASE.with_suffix('.original.json');r=json.loads(original.read_bytes());journal=Path(r['journal']['path']);assert sha(journal)==r['journal']['sha256'];prep=json.loads((OUT/'prepared.json').read_bytes());package=json.loads(Path(prep['overlay_package']).read_bytes());boss_def=next(x['unit_definition'] for x in package['manifest']['metadata']['variant_bindings'] if x['variant_id'].startswith('enemy_1505_frstar@'));boss=None;births=Counter();deploy=[];accepted=[];refused=[];boss_events=[];boss_HP=[];portal=[];cast=[];phase=[];ice=[];tokens=[];mon=None;mon_damage=[];info=[]
 with journal.open(encoding='utf8') as f:
  for line in f:
   e=json.loads(line);v=e['payload'];kind=e['type']
   if kind=='entity.created':
    if v['definition'].startswith('unit/ch4/') and 'sealed_floor' not in v['definition']:births[v['definition']]+=1
    if v['definition']==boss_def:boss=v['source'];boss_events.append(e)
    elif v['definition']=='unit/ch4/frost/sealed_floor':ice.append(e)
    elif v['definition']=='unit/kalts_mon3tr_model':mon=v['source'];tokens.append(e)
   if kind=='command.accepted':
    accepted.append(e)
    if v['action']['action']=='deploy':deploy.append(e)
   elif kind=='command.rejected':refused.append(e)
   elif kind=='ability.started':cast.append(e)
   if kind=='movement.visibility_changed':portal.append(e)
   if kind=='reference.enemy_info.observed':info.append(e)
   if boss is not None and (v.get('source')==boss or v.get('target')==boss):
    if kind.startswith('rebirth.') or kind.startswith('lifecycle.') or kind in ('entity.died','entity.retired','entity.exited','entity.revived','ability.started','damage.accepted'):boss_events.append(e)
    if kind.startswith('rebirth.') or kind=='entity.revived':phase.append(e)
    if kind=='resource.changed' and v.get('resource')=='hp' and v.get('target')==boss:boss_HP.append(e)
   if mon is not None and kind=='damage.accepted' and v.get('source')==mon:mon_damage.append(e)
 assert len(deploy)==12 and {e['payload']['action']['entity'] for e in deploy}==set(package['scenarioDraft']['roster']);assert sum(births.values())==43 and len(births)==7 and all(e['time']<r['terminal_tick'] for e in deploy);boss_casts=[e for e in cast if e['payload']['source']==boss];counts=Counter(e['payload']['ability'] for e in boss_casts)
 result={'role':'Sealed original full-stage coverage, full CP/replay acceptance separately pending','source_original_sha':sha(original),'journal':r['journal'],'core':r['implementation'],'overlay_sha':prep['overlay_sha'],'source_native_parent_sha':prep['source_sha'],'commands_sha':prep['commands_sha'],'actual_native43births':dict(births),'all12_first_deploys_before_terminal':True,'deploy_events':deploy,'accepted_commands':accepted,'refused_commands':refused,'actual_all_ability_started':cast,'boss':{'actor':boss,'definition':boss_def,'actual_cast_counts':dict(counts),'actual_cast_events':boss_casts,'actual_lifecycle_damage_events':boss_events,'actual_HP_change_events':boss_HP,'actual_firstdown_rebirth_events':phase,'firstdown_rebirth_triggered_in_this_stage':bool(phase),'absent_phase_policy':'No branch claimed merely because source contains it; Root independent Frost source cases cover true firstdown/reset/rebirth separately'},'portal':{'actual_visibility_transition_count':len(portal),'actual_source_events':portal,'note':'Events include exact source entry/exit and hidden/motion transitions; original coordinates/profile remain consumed'},'ice_sealed_floor':{'actual_created':len(ice),'creation_events':ice},'native_enemy_info_events':info,'Mon3tr':{'actual_created':tokens,'actual_outgoing_damage_events':mon_damage},'terminal':{'actual_event_tick':r['terminal_tick'],'observed_end':r['end_tick'],'kills':r['state']['kills'],'leaks':r['state']['leaks'],'base_life':r['base_life_final']},'no_all_skills_or_all_phases_claim':True,'client_verified':False}
 dest=OUT/'original_coverage.json'
 if dest.exists():raise ValueError('Preserve prior coverage')
 dest.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(dest),'births':sum(births.values()),'deploys':len(deploy),'boss_casts':dict(counts),'firstdown_rebirth':bool(phase),'portal_events':len(portal),'ice_created':len(ice),'refusals':len(refused)}))
if __name__=='__main__':main()
