"""Verify actual triple journals and standard source provenance; registry untouched."""
import argparse,hashlib,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/chapter05_public_v3';sys.path.insert(0,str(ROOT))
from tools.campaign_runthrough_progress_v2 import inspect
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--stage',choices=['05-09','05-10'],required=True);ap.add_argument('--actual-exit',type=int,required=True);a=ap.parse_args();assert a.actual_exit==0
 row=next(r for r in json.loads((OUT/'prepared_commands.json').read_bytes())['cases'] if r['native_id']=='level_main_'+a.stage);final=Path('E:/ArkSimEvidence/campaign')/(a.stage.replace('-','_')+'_8fa4e36752e92f7d')/'public_v1.json';r=json.loads(final.read_bytes());assert all(r[k] for k in ('passed','process_complete','checkpoint_equal','durable_checkpoint_equal','replay_equal','identity_stable'));assert r['package_sha256']==row['overlay_sha'] and r['commands_sha256']==row['commands_sha']
 entry={'report':str(final),'package':str(Path(row['overlay']).relative_to(ROOT)),'commands':str(Path(row['commands']).relative_to(ROOT)),'parent_package':str(Path(row['parent']).relative_to(ROOT)),'implementation':r['implementation']};result=inspect(ROOT,entry);assert result['process_status']=='complete' and result['determinism_status']=='verified' and result['durable_checkpoint_status']=='verified' and result['sealed_checkpoint_journal']['exact_final_journal_prefix']
 for k in ('journal','continuation_journal','replayed_journal'):
  ref=r[k];p=Path(ref['path']);assert p.stat().st_size==ref['bytes'] and sha(p)==ref['sha256']
 coverage=OUT/(a.stage+'.original_coverage_v1.json');c=json.loads(coverage.read_bytes());assert c['all12_first_deploys_before_terminal'] and sum(c['native_births'].values())==row['births']
 copy=OUT/(a.stage+'.final.exact_copy.json');receipt=OUT/(a.stage+'.complete.private_receipt.json');assert not copy.exists() and not receipt.exists();shutil.copyfile(final,copy);assert sha(copy)==sha(final)
 record={'stage':row['native_id'],'actual_exit':a.actual_exit,'core':r['implementation'],'E_final':str(final),'final_sha':sha(final),'exact_repo_copy':str(copy),'copy_sha':sha(copy),'source_native_parent_sha':row['parent_sha'],'standard_overlay_sha':row['overlay_sha'],'commands_sha':row['commands_sha'],'progress_v2_actual_inspect':result,'full_native_births':row['births'],'all12_first_deploys_before_terminal':True,'native_DP':row['native_DP'],'native_slots':row['native_slots'],'terminal':c['terminal'],'full_event_count':r['journal']['events'],'actual_triple_journal_SHA_bytes_verified':True,'coverage_path':str(coverage),'coverage_sha':sha(coverage),'actual_ballista_launches':len(c['ballista']['actual_projectile_launches']),'actual_ballista_damage_events':len(c['ballista']['actual_accepted_damage']),'actual_branch_activation_events':c['actual_branch_activation_events'],'refused_commands':c['refused_commands'],'registry_modified':False,'production_promotion_performed':False,'client_verified':False};receipt.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'receipt_sha':sha(receipt),'final_sha':sha(final),'progress':result['process_status']}))
if __name__=='__main__':main()
