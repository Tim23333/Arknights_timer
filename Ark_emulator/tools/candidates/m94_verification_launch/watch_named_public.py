"""Read-only current named full-run deploy/skill/control/SP witnesses."""
import argparse,datetime,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/m94_complete_c4'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--label',required=True);args=ap.parse_args();assert Path(args.label).name==args.label;journal=OUT/(args.label+'.active.jsonl');units={};accepted=[];refused=[];started=[];SP=[];last=0;tick=0
 with journal.open(encoding='utf8') as f:
  for line in f:
   if not line.endswith('\n'):break
   e=json.loads(line);last=e['id'];tick=e['time'];p=e['payload']
   if e['type']=='command.accepted':
    accepted.append(e)
    if p['action']['action']=='deploy':units[p['result']]=p['action']['entity']
   elif e['type']=='command.rejected':refused.append(e)
   elif e['type']=='ability.started':started.append(e)
   elif e['type']=='calculation' and p.get('calculation_id')=='resource.recovery' and p.get('trace',{}).get('context',{}).get('resource')=='sp' and p.get('source') in units:
    i=p['trace']['inputs'];SP.append({'id':e['id'],'time':e['time'],'actor':p['source'],'unit':units[p['source']],'rule':p['rule_id'],'before':i['current'],'computed':p['value'],'actual_rate':i.get('attributes',{}).get('sp_recovery_rate')})
 selected={'ability/campaign_myrtle_s2','ability/campaign_bpipe_s3','ability/campaign_chen_s1','ability/liskam_s1','ability/demkni_s3','ability/plosis_s2_first_packet','ability/campaign_angel_s3','ability/campaign_amgoat_s3','ability/kalts_summon','ability/kalts_host_s3','ability/kalts_token_s3_model','ability/lisa_s3','ability/campaign_weedy_s3','ability/cgbird_s3'};witnesses=[e for e in started if e['payload'].get('ability') in selected]
 report={'observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'label':args.label,'read_only_complete_live_lines':True,'sealed_receipt':False,'last_event':last,'tick':tick,'accepted_first_deploys':units,'accepted_commands':accepted,'rejected_commands':refused,'actual_skill_started':witnesses,'actual_operator_sp_calculations':SP,'all12_first_deployed':len(set(units.values()))==12,'whole_stage_passed':False}
 with (OUT/(args.label+'.watch_history.jsonl')).open('a',encoding='utf8') as f:f.write(json.dumps(report,separators=(',',':'))+'\n')
 print(json.dumps({'tick':tick,'last_event':last,'first_deploy_count':len(set(units.values())),'refused':[{'time':e['time'],**e['payload']} for e in refused],'started':[(e['time'],e['payload']['ability'],e['payload']['source']) for e in witnesses],'last_operator_SP':SP[-4:]},ensure_ascii=False))
if __name__=='__main__':main()
