"""Read complete committed JSON lines only; never inject calculations/events."""
import datetime,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/m94_complete_c4';JOURNAL=OUT/'full49_v3.active.jsonl'
def main():
 units={};accepted=[];rejected=[];starts=[];resources=[];last=0;time=0
 with JOURNAL.open(encoding='utf8') as f:
  for line in f:
   if not line.endswith('\n'):break
   e=json.loads(line);last=e['id'];time=e['time'];payload=e['payload']
   if e['type']=='command.accepted':
    accepted.append(e)
    if payload['action']['action']=='deploy':units[payload['result']]=payload['action']['entity']
   elif e['type']=='command.rejected':rejected.append(e)
   elif e['type']=='ability.started':starts.append(e)
   elif e['type'].startswith('resource.') and payload.get('resource') in ('sp','lasso_uses'):resources.append(e)
 automatic=[e for e in starts if e['payload'].get('ability') in ('ability/liskam_s1','ability/campaign_angel_s3','ability/campaign_chen_s1')]
 report={'observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'read_only_live_prefix':True,'not_a_sealed_journal_receipt':True,'last_complete_event_id':last,'last_complete_event_tick':time,'accepted_first_deploy_units':sorted(set(units.values())),'accepted_deploy_actor_bindings':units,'command_rejections':rejected,'automatic_skill_started_witnesses':automatic,'SP_charge_event_count':len(resources),'accepted_command_count':len(accepted),'whole_stage_verified':False}
 path=OUT/'full49_v3.watch_history.jsonl'
 with path.open('a',encoding='utf8') as f:f.write(json.dumps(report,separators=(',',':'))+'\n')
 print(json.dumps({'tick':time,'last_event':last,'first_deploy_units':len(set(units.values())),'rejections':[{'at':e['time'],**e['payload']} for e in rejected],'automatic_skill_starts':[(e['time'],e['payload']) for e in automatic]},ensure_ascii=False))
if __name__=='__main__':main()
