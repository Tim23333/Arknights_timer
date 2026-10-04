"""Sealed original M96V6 complete-event coverage and honest command outcomes."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/m94_complete_c4'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 original=OUT/'full49_m96_v6.original.json';r=json.loads(original.read_bytes());journal=Path(r['journal']['path']);assert sha(journal)==r['journal']['sha256'];deploy=[];accepted=[];refused=[];starts=[];mon=None;mon_events=[];dp=[];hp=[];SP=[];host=None;root_births={};tiles=0;none=0
 skills={'ability/campaign_myrtle_s2','ability/campaign_bpipe_s3','ability/campaign_chen_s1','ability/liskam_s1','ability/demkni_s3','ability/plosis_s2_first_packet','ability/campaign_angel_s3','ability/campaign_amgoat_s3','ability/kalts_summon','ability/kalts_host_s3','ability/kalts_token_s3_model','ability/lisa_s3','ability/campaign_weedy_s3','ability/cgbird_s3'}
 with journal.open(encoding='utf8') as f:
  for line in f:
   e=json.loads(line);p=e['payload'];kind=e['type']
   if kind=='entity.created':
    if p['definition'].startswith('unit/ch4/'):root_births[p['definition']]=root_births.get(p['definition'],0)+1
    if p['definition']=='unit/kalts_mon3tr_model':assert mon is None;mon=p['source'];mon_events.append(e)
   if kind=='command.accepted':
    accepted.append(e)
    if p['action']['action']=='deploy':deploy.append(e)
    if p['action'].get('alias')=='c409_kalts':host=p['result']
   elif kind=='command.rejected':refused.append(e)
   elif kind=='ability.started' and p['ability'] in skills:starts.append(e)
   elif kind=='resource.changed' and e['time']==3150 and p.get('source')==host and p.get('resource')=='dp':dp.append(e)
   elif kind=='calculation' and p.get('source')==host and p.get('calculation_id')=='resource.recovery' and 3150<=e['time']<=3630 and p.get('trace',{}).get('context',{}).get('resource')=='sp':SP.append(e)
   if mon is not None and (p.get('source')==mon or p.get('target')==mon) and kind in ('ability.started','attack.accepted','damage.accepted','healing.accepted','resource.changed','entity.retired','entity.died'):mon_events.append(e)
   if kind=='calculation' and mon is not None and p.get('source')==mon and p.get('calculation_id')=='resource.capacity' and p.get('trace',{}).get('context',{}).get('resource')=='hp':hp.append(e)
   if kind=='field.triggered':tiles+=1
   elif kind=='damage.accepted' and p.get('source') is None:none+=1
 roster=json.loads((ROOT.parent/'unpack_work/campaign_m94_complete_c4_candidate/stage/level_main_04-09.m96.v6.life99999.runthrough.prepared.json').read_bytes())['scenarioDraft']['roster'];units=sorted({e['payload']['action']['entity'] for e in deploy});assert set(units)==set(roster) and len(units)==12 and sum(root_births.values())==49 and mon is not None
 paid=[e for e in dp if e['payload'].get('delta')==-10];assert len(paid)==1
 packets=[e for e in mon_events if e['type']=='damage.accepted' and e['payload'].get('source')==mon];report={'core':r['implementation'],'source_original_receipt_sha':sha(original),'sealed_journal':r['journal'],'source_module_sha':'2b3804fcd456e456b137b8145afe655d031db4dbf331a6115af3fded168f51e6','all12_first_deploy_accepted_before_terminal':all(e['time']<r['terminal_tick'] for e in deploy),'accepted_first_deploy_units':units,'accepted_deploy_events':deploy,'actual_enemy_births':root_births,'accepted_commands':accepted,'rejected_commands':refused,'actual_skill_started':starts,'mon3tr':{'actor':mon,'owner_deploy_actor':host,'actual_battle_DP_payment':paid,'actual_events':mon_events,'actual_health_capacity_calculations':hp,'actual_outgoing_damage_packets':packets,'host_real_SP_recovery_calculations':SP,'host_S3_started_in_V6':any(e['payload']['ability']=='ability/kalts_host_s3' for e in starts),'followup':'3600 public command precedes same-tick recovery14->15; prepared3601 separate input, no V6 mutation'},'field_triggers':tiles,'NoSource_damage_packets':none,'independent_reference_coverage':'M94 current255 + correct-input full1211 + M96 independent4 control/immunity checks; actual V6 triggers listed above, no implication every selected skill fired','process_terminal':r['terminal_tick'],'whole_process_original_complete':r['process_complete'],'full_checkpoint_replay_receipt_pending':True,'client_verified':False}
 dest=OUT/'m96_v6.original_coverage.json'
 if dest.exists():raise ValueError('Preserve coverage')
 dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'report_sha':sha(dest),'born':sum(root_births.values()),'deploys':len(units),'mon_actor':mon,'mon_damage_packets':len(packets),'field_triggers':tiles,'NoSource_packets':none,'rejections':len(refused)}))
if __name__=='__main__':main()
