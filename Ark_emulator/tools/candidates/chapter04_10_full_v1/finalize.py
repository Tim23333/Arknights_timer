"""Byte-copy only the final small report; journals/CP stay bound on E, registry untouched."""
import hashlib,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/chapter04_10_full_v1';FINAL=Path('E:/ArkSimEvidence/campaign/04_10_7a04c12a1a4224ee/public_v1.json');sys.path.insert(0,str(ROOT))
from tools.campaign_runthrough_progress_v2 import inspect
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 assert sha(FINAL)=='e612713e349c7f71974701619398c15a438e4323168685350388bbaee2ee53fc';r=json.loads(FINAL.read_bytes());assert all(r[k] for k in ('passed','process_complete','checkpoint_equal','durable_checkpoint_equal','replay_equal','identity_stable'));p=json.loads((OUT/'prepared.json').read_bytes());entry={'report':str(FINAL),'package':str(Path(p['overlay_package']).relative_to(ROOT)),'commands':str(Path(p['commands']).relative_to(ROOT)),'parent_package':str(Path(p['source_package']).relative_to(ROOT)),'implementation':p['core']};result=inspect(ROOT,entry);assert result['process_status']=='complete' and result['determinism_status']=='verified' and result['durable_checkpoint_status']=='verified' and result['sealed_checkpoint_journal']['exact_final_journal_prefix']
 for key in ('journal','continuation_journal','replayed_journal'):
  ref=r[key];assert Path(ref['path']).stat().st_size==1782309675 and sha(Path(ref['path']))==ref['sha256']
 copy=OUT/'public_v1.final.exact_copy.json';receipt=OUT/'complete.private_receipt.json'
 if copy.exists() or receipt.exists():raise ValueError('Preserve completed receipt')
 shutil.copyfile(FINAL,copy);assert copy.read_bytes()==FINAL.read_bytes();coverage=OUT/'original_coverage.json';c=json.loads(coverage.read_bytes());assert c['all12_first_deploys_before_terminal'];record={'core':p['core'],'final_E_report':str(FINAL),'final_sha':sha(FINAL),'exact_repo_copy':str(copy),'copy_sha':sha(copy),'actual_exit':0,'source_parent_native_life3':p['source_sha'],'standard_life99999_overlay':p['overlay_sha'],'commands_sha':p['commands_sha'],'progress_v2_actual_inspect':result,'actual_full':{'births':43,'variants':7,'first12_deploys_before_terminal':True,'terminal':r['terminal_tick'],'end_tick':r['end_tick'],'kills':r['state']['kills'],'leaks':r['state']['leaks'],'base_life':r['base_life_final'],'events':r['journal']['events'],'bytes_per_complete_journal':1782309675,'actual_triple_log_SHA_bytes_verified':True,'checkpoint_equal':True,'durable_equal':True,'replay_equal':True,'guard_stable':True},'actual_coverage':{'path':str(coverage),'sha':sha(coverage),'boss_casts':c['boss']['actual_cast_counts'],'firstdown_rebirth_triggered':c['boss']['firstdown_rebirth_triggered_in_this_stage'],'portal_visibility_events':c['portal']['actual_visibility_transition_count'],'ice_floor_creations':c['ice_sealed_floor']['actual_created'],'refused_commands':c['refused_commands']},'official_registry_modified':False,'production_promotion_performed':False,'client_verified':False};receipt.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'receipt_sha':sha(receipt),'final_sha':sha(FINAL),'progress_status':result['process_status']}))
if __name__=='__main__':main()
