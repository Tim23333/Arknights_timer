"""Bind audit trace to actual immutable800 disk checkpoint journal, not live tail."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/trace_audit/05_09_cp800_prefix100k_v1'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def main():
 assert not OUT.exists();OUT.mkdir(parents=True);cp=Path('E:/ArkSimEvidence/campaign/05_09_8fa4e36752e92f7d/public_v1.checkpoint.json');data=json.loads(cp.read_bytes());assert data['kernel']['time']==800;ref=data['kernel']['events']['reference'];source=Path(ref['path']);assert source.stat().st_size==ref['bytes'] and sha(source)==ref['sha256'];prefix=OUT/'events.exact_prefix.jsonl';n=0;last=None
 with source.open('rb') as f,prefix.open('xb') as out:
  for line in f:
   e=json.loads(line);assert e['id']==n+1;out.write(line);n+=1;last=e
   if n==100000:break
 assert n==100000;locator=ROOT/'validation/campaign/chapter05_public_v3/pending_05_09_full_v1.json';launch=json.loads(locator.read_bytes());command=Path('scenarios/campaign/chapter05/level_main_05-09/combined_v3/public_fixed12.compact_v1.commands.json');package=Path('packages/campaign/chapter05_stage_models/combined_v3/level_main_05-09.life99999.json');assert sha(ROOT/package)==launch['package_sha'] and sha(ROOT/command)==launch['commands_sha'];r={'source_actual_disk_checkpoint':str(cp),'checkpoint_sha':sha(cp),'kernel_time':800,'program_fingerprint':data['program_fingerprint'],'runtime_fingerprint':data['runtime_fingerprint'],'complete_immutable_checkpoint_journal':ref,'complete_journal_actual_sha_bytes_verified':True,'actual_prefix_path':str(prefix),'prefix_sha':sha(prefix),'prefix_bytes':prefix.stat().st_size,'prefix_events':n,'last_prefix_event':{'id':last['id'],'time':last['time'],'type':last['type']},'core':launch['core'],'package_sha':launch['package_sha'],'commands_sha':launch['commands_sha'],'launch_locator_sha':sha(locator),'prefix_raw_bytes_unmodified':True,'numeric_full_acceptance':False,'client_verified':False};dest=OUT/'trace_identity.json';dest.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'identity_sha':sha(dest),'prefix_sha':sha(prefix),'events':n,'last_tick':last['time']}))
if __name__=='__main__':main()
