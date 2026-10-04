"""Prepare exact metadata-only runthrough input and compact public commands."""
import hashlib,json
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m94_complete_c4_candidate';OUT=ROOT/'validation/campaign/m94_complete_c4'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 stage=RUNTIME/'stage/level_main_04-09.m92.first_hit.source_circle.life99999.json';assert sha(stage)=='aadc0e3eb00dd839e1d224f9a72f16ea83d102453b175b2084f062bf53e4512e'
 plan=OUT/'public_fixed12_plan.compact.prepared.json';assert sha(plan)=='67f17ae4af757ec29a36c041e1508f3b712c38633e121888f30394ce145592d1'
 p=json.loads(stage.read_bytes());old=deepcopy(p);scene=p['scenarioDraft'];scene.setdefault('metadata',{})['runthrough_profile']={'base_life_resource':'life','base_life':99999,'fixed12':deepcopy(scene['roster']),'operator_enemy_HP':'Keep exact authored selected-module HP','source_births':49,'variants':7,'heatfields':8,'deploy_capacity':8,'policies':deepcopy(p['manifest']['metadata']['model_policies']),'client_verified':False}
 check=deepcopy(p);del check['scenarioDraft']['metadata']['runthrough_profile'];assert check==old
 package=RUNTIME/'stage/level_main_04-09.m94.runthrough.prepared.json';commands=OUT/'compact.commands.prepared.json';receipt=OUT/'runthrough_launch.prepared.json'
 if any(x.exists() for x in (package,commands,receipt)):raise ValueError('Preserve previous inputs')
 package.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');commands.write_text(json.dumps(json.loads(plan.read_bytes())['commands'],indent=2)+'\n',encoding='utf8',newline='')
 helper=ROOT/'tools/candidates/m77_event_storage/campaign_streaming_evidence_v14.py';entry=ROOT/'tools/run_campaign_disk_runthrough_v15.py'
 report={'status':'Prepared; await independent M93/M92/current mechanism acceptance and compact public execution receipts before full49birth execution','core':'cb321a851dc1ccb373477c73a522fc4ca8c35ce8b1c38d18bbee7e1e028358d7','runtime_root':str(RUNTIME),'package':str(package),'package_sha':sha(package),'commands':str(commands),'commands_sha':sha(commands),'helper':str(helper),'helper_sha':sha(helper),'entry':str(entry),'entry_sha':sha(entry),'suggested_checkpoint_at':800,'suggested_max_ticks':12000,'original_stage_sha':sha(stage),'actual_diff':['scenarioDraft.metadata.runthrough_profile'],'whole_stage_executed':False}
 receipt.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'package_sha':sha(package),'commands_sha':sha(commands),'launch_receipt_sha':sha(receipt)}))
if __name__=='__main__':main()
