"""Separate E-volume run locator, never updates the guarded official registry."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/chapter04_10_full_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=json.loads((OUT/'prepared.json').read_bytes());output=Path('E:/ArkSimEvidence/campaign/04_10_7a04c12a1a4224ee/public_v1.json');locator=OUT/'pending_4_10.public_v1.json'
 if locator.exists():raise ValueError('Preserve prior locator')
 record={'schema':'ark-sim/private-pending-locator/v1','native_id':'level_main_04-10','session_id':98812,'implementation':p['core'],'runtime_root':str(ROOT.parent/'unpack_work/campaign_frost_complete_v5_candidate'),'parent_package':str(Path(p['source_package']).relative_to(ROOT)),'package':str(Path(p['overlay_package']).relative_to(ROOT)),'commands':str(Path(p['commands']).relative_to(ROOT)),'parent_sha':p['source_sha'],'package_sha':p['overlay_sha'],'commands_sha':p['commands_sha'],'input_review_sha':sha(OUT/'input_review.json'),'report':str(output),'full_log':str(OUT/'full.log'),'journal_output_volume':'E: ample volume, actual full journals/CP references stay at their absolute E paths','checkpoint_at':800,'max_ticks':30000,'stage_source_born':43,'exact_variants':7,'fixed_roster':12,'native_slots':10,'native_DP':10,'native_move_multiplier':.5,'seed':14705740,'evidence_helper':'tools/candidates/m77_event_storage/campaign_streaming_evidence_v14.py','helper_sha':'2029677af14d702ef917522be3dd2d348b906366759905af41e6562399df29e9','status':'Only one new 4-10 V15 full original/CP/start replay running; no completion claim','native_parent_restoration':'Old7b5 prefix remains immutable; only life restored3 and goaloverride removed into new native parent, standard apply output verified','official_registry_updated':False,'client_verified':False}
 locator.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'locator':str(locator),'sha':sha(locator)}))
if __name__=='__main__':main()
