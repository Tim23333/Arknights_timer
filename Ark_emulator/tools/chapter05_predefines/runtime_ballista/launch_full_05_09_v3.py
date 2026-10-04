"""Launch one frozen5-9 disk proof only after actual short input receipt."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 outdir=ROOT/'validation/campaign/chapter05_public_v3'
 short=json.loads((outdir/'level_main_05-09.prefix900.verification.json').read_bytes())
 assert short['CP_resume_equal'] and short['start_public_replay_equal'] and short['guard_before']==short['guard_after']
 row=next(x for x in json.loads((outdir/'prepared_commands.json').read_bytes())['cases'] if x['native_id']=='level_main_05-09')
 package=Path(row['overlay']);commands=Path(row['commands']);assert sha(package)==row['overlay_sha'] and sha(commands)==row['commands_sha']
 helper=ROOT/'tools/candidates/m77_event_storage/campaign_streaming_evidence_v14.py';helperpin='2029677af14d702ef917522be3dd2d348b906366759905af41e6562399df29e9';assert sha(helper)==helperpin
 output=Path('E:/ArkSimEvidence/campaign/05_09_8fa4e36752e92f7d/public_v1.json');assert not output.exists() and not output.with_suffix('.active.jsonl').exists()
 args=[sys.executable,str(ROOT/'tools/run_campaign_disk_runthrough_v15.py'),'--runtime-root',str(ROOT.parent/'unpack_work/campaign_chapter05_complete_v3_candidate'),'--expected-core',short['core'],'--package',str(package),'--commands',str(commands),'--output',str(output),'--evidence-helper',str(helper),'--helper-sha256',helperpin,'--max-ticks','30000','--checkpoint-at','800']
 locator=outdir/'pending_05_09_full_v1.json';assert not locator.exists()
 locator.write_text(json.dumps({'role':'pending launch, not passed evidence','output':str(output),'package_sha':sha(package),'commands_sha':sha(commands),'short_receipt_sha':sha(outdir/'level_main_05-09.prefix900.verification.json'),'core':short['core'],'argv':args,'registry_modified':False},indent=2)+'\n',encoding='utf8',newline='')
 print(json.dumps({'launch':args,'locator_sha':sha(locator)}),flush=True)
 raise SystemExit(subprocess.call(args,cwd=ROOT))
if __name__=='__main__':main()
