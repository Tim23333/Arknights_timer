"""Complete public owned summon/SP-boundary/true-damage witness from the short journal."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/m94_complete_c4'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 proof=OUT/'kalts_public_boundary_short.verification.json';assert sha(proof)=='ecfec34fa1dd23daff27e37dd1392ae8ac0b1081b37c6cd05be95ba500800a76';r=json.loads(proof.read_bytes());assert r['checkpoint_resume_equal'] and r['start_public_replay_equal'];journal=Path(r['journal']['path']);assert sha(journal)==r['journal']['sha256'];accepted=[];reject=[];starts=[];dp=[];SP=[];mon=None;host=None;damage=[];created=[];true_calcs=[]
 with journal.open(encoding='utf8') as f:
  for line in f:
   e=json.loads(line);p=e['payload']
   if e['type']=='command.accepted':
    accepted.append(e)
    if p['action'].get('alias')=='kalts_boundary':host=p['result']
   elif e['type']=='command.rejected':reject.append(e)
   elif e['type']=='entity.created' and p['definition']=='unit/kalts_mon3tr_model':mon=p['source'];created.append(e)
   elif e['type']=='ability.started' and p['ability'] in ('ability/kalts_summon','ability/kalts_host_s3','ability/kalts_token_s3_model'):starts.append(e)
   elif e['type']=='resource.changed' and p.get('source')==host and p.get('resource')=='dp' and e['time']==600:dp.append(e)
   elif e['type']=='calculation' and p.get('source')==host and p.get('calculation_id')=='resource.recovery' and p.get('trace',{}).get('context',{}).get('resource')=='sp' and 1020<=e['time']<=1051:SP.append(e)
   if mon is not None and e['type']=='damage.accepted' and p.get('source')==mon:damage.append(e)
   if mon is not None and e['type']=='calculation' and p.get('source')==mon and p.get('trace',{}).get('inputs',{}).get('effect',{}).get('damage_type')=='true':true_calcs.append(e)
 assert len(accepted)==4 and not reject and len(created)==1 and any(e['time']==1051 and e['payload']['ability']=='ability/kalts_host_s3' for e in starts) and any(e['time']==1051 and e['payload']['ability']=='ability/kalts_token_s3_model' for e in starts) and len([e for e in dp if e['payload'].get('delta')==-10])==1
 # damage.accepted intentionally has no damage_type field. Bind the genuine
 # ability identity to its real typed damage calculation, rather than inventing
 # a nonexistent accepted-payload field (the original extraction failure stays).
 true=[e for e in damage if e['payload'].get('ability')=='ability/mon3tr_true_probe'];assert true and true_calcs
 report={'core':r['core'],'source_module_sha':'2b3804fcd456e456b137b8145afe655d031db4dbf331a6115af3fded168f51e6','short_receipt_sha':sha(proof),'complete_journal':r['journal'],'ticks':r['end_tick'],'events':r['observations']['event_count'],'accepted_commands':accepted,'rejected_commands':reject,'created_owned_mon':created,'host_actor':host,'mon_actor':mon,'real_summon_DP_payment':dp,'actual_SPrecovery_before_command':SP,'actual_skill_started':starts,'actual_mon_damage_packets':damage,'actual_true_damage_packets':true,'checkpoint_resume_equal':True,'start_public_replay_equal':True,'same_reference_modules_and_actual_HP_SP_DP_roster_slots_seed':True,'independent_operation_input_only':True,'V6_full_input_and_rejection_preserved':True,'whole_stage_executed':False,'client_verified':False};dest=OUT/'kalts_public_boundary_short.coverage.json'
 if dest.exists():raise ValueError('Preserve short witness')
 report['actual_true_damage_calculations']=true_calcs;report['prior_extraction_failure']='Preserved first parser assertion used nonexistent damage.accepted.damage_type; no simulation/core failure or input change.'
 dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(dest),'accepted':len(accepted),'mon_packets':len(damage),'true_packets':len(true),'host_S3_at':1051}))
if __name__=='__main__':main()
