"""Read complete live lines; distinguish observed casts/down/portal from definitions."""
import datetime,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/chapter04_10_full_v1';BASE=Path('E:/ArkSimEvidence/campaign/04_10_7a04c12a1a4224ee/public_v1')
def main():
 prepared=json.loads((OUT/'prepared.json').read_bytes());p=json.loads(Path(prepared['overlay_package']).read_bytes());boss_def=next(r['unit_definition'] for r in p['manifest']['metadata']['variant_bindings'] if r['variant_id'].startswith('enemy_1505_frstar@'));boss=None;born={};deploys=[];refused=[];casts=[];boss_events=[];portal=[];last=0;tick=0;types={}
 with BASE.with_suffix('.active.jsonl').open(encoding='utf8') as f:
  for line in f:
   if not line.endswith('\n'):break
   e=json.loads(line);last=e['id'];tick=e['time'];v=e['payload'];kind=e['type'];types[kind]=types.get(kind,0)+1
   if kind=='entity.created':
    if v['definition']==boss_def:boss=v['source']
    if v['definition'].startswith('unit/ch4/'):born[v['definition']]=born.get(v['definition'],0)+1
   elif kind=='command.accepted' and v['action']['action']=='deploy':deploys.append(e)
   elif kind=='command.rejected':refused.append(e)
   if kind=='ability.started':casts.append(e)
   if boss is not None and (v.get('source')==boss or v.get('target')==boss) and (kind.startswith('rebirth.') or kind.startswith('lifecycle.') or kind in ('entity.died','entity.retired','entity.revived','ability.started')):boss_events.append(e)
   if 'portal' in kind or kind in ('movement.visibility_changed','movement.disappeared','movement.appeared','entity.disappeared','entity.appeared'):portal.append(e)
 observed={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'complete_live_lines_only':True,'sealed_final_receipt':False,'sourcepackage':prepared['overlay_sha'],'commands':prepared['commands_sha'],'last_event':last,'tick':tick,'actual_entity_creation_counts':born,'accepted_deploys':deploys,'refused_commands':refused,'actual_ability_started':casts,'actual_boss_events':boss_events,'actual_portal_events':portal,'event_type_counts':types,'not_all_source_mechanisms_claimed_triggered':True,'full_stage_passed':False}
 with (OUT/'watch_history.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(observed,separators=(',',':'))+'\n')
 starts=[e for e in boss_events if e['type']=='ability.started'];print(json.dumps({'tick':tick,'events':last,'accepted_unique_deploys':len({e['payload']['action']['entity'] for e in deploys}),'refusals':[{'at':e['time'],**e['payload']} for e in refused],'boss_actor':boss,'actual_boss_casts':[(e['time'],e['payload']['ability']) for e in starts],'actual_down_rebirth':[(e['time'],e['type']) for e in boss_events if e['type'].startswith('rebirth.') or e['type']=='entity.revived'],'actual_portal_events':len(portal)},ensure_ascii=False))
if __name__=='__main__':main()
