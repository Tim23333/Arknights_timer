"""Separate pending M94 locator; never mutates the official campaign registry."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/m94_complete_c4'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 path=OUT/'pending_registry_m94.json'
 if path.exists():raise ValueError('Preserve prior locator; write a later explicit revision')
 files=['freeze_core.json','verification_current_run3.json','baseline','baseline_verification.json','compact_public1600.verification.json','compact.commands.public_v3.json','activation_audit.public_v3.json','runthrough_launch.public_v3.prepared.json'];proofs={name:sha(OUT/name) for name in files}
 record={'scope':'Independent pending M94 locator, not an official stage completion registration','core':'cb321a851dc1ccb373477c73a522fc4ca8c35ce8b1c38d18bbee7e1e028358d7','actual_passed':{'current_cases':255,'baseline':'Fresh complete 0-1 11kill0leak181937events, CP/replay, custom850/60 actualexit0','compact1600':'Five accepted first deployments,74677events,ordered800CP/start public replay exact,24field triggers/4NoSource packets'},'full_suite':{'session_id':19124,'report':str(OUT/'full_verification.json'),'log':str(OUT/'full_suite.log'),'status':'Running; no inherited pass'},'full4_9':{'session_id':29858,'report':str(OUT/'full49_v3.json'),'log':str(OUT/'full49_v3.log'),'core':'cb321a851dc1ccb373477c73a522fc4ca8c35ce8b1c38d18bbee7e1e028358d7','package_sha':'046c5f77d5c8f071c5b4ea56b6dfec1459a26101894ce5dfd968a41757dbdbc5','commands_sha':proofs['compact.commands.public_v3.json'],'checkpoint_at':800,'max_ticks':12000,'status':'Single bounded-disk original+CP+public replay full proof running; pending terminal and exact49 births/first12 accepted identities'},'stopped_duplicate_prefix':{'session_id':91159,'pid':182668,'reason':'Explicit targeted Stop-Process after Root authorized full49 run and required only one bounded disk run; preserve journal/CP/log','last_logged_tick':2500,'last_logged_events':180682,'passed':False},'proofs':proofs,'registry_modified':False,'whole_stage_passed':False,'client_verified':False}
 path.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'locator':str(path),'sha':sha(path)}))
if __name__=='__main__':main()
