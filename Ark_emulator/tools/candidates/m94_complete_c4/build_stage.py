"""Compose M94 exact C4 content, then author only goal-required base life99999."""
import argparse,json,subprocess,sys,hashlib
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m94_complete_c4_candidate';OUT=ROOT/'validation/campaign/m94_complete_c4'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--expected-core',required=True);args=ap.parse_args();native=RUNTIME/'stage/level_main_04-09.m92.first_hit.source_circle.native_life.json';authored=RUNTIME/'stage/level_main_04-09.m92.first_hit.source_circle.life99999.json'
 if native.exists() or authored.exists():raise ValueError('New authored stage only')
 subprocess.run([sys.executable,str(ROOT/'tools/build_chapter04_09_stage.py'),'--runtime-root',str(RUNTIME),'--expected-core',args.expected_core,'--dmage-module',str(ROOT/'packages/campaign/chapter04_dmage/module.combat_guard.reference.json'),'--dmage-sha256','0833e8e9601fc390486b72a0878c6e94229d28bfef084b741127764c32b64465','--demon-phase','first_hit','--demon-sha256','39a96185a08a6f24015d7d60fd2694bba452d3a1f98997546e9f35c62b9ad08e','--range-policy','source_circle','--output',str(native)],cwd=ROOT,check=True)
 p=json.loads(native.read_bytes());assert p['scenarioDraft']['parameters']['deploy_capacity']==8;original=deepcopy(p);life=deepcopy(p['scenarioDraft']['resources']['life']);p['scenarioDraft']['resources']['life'].update(initial=99999,capacity=99999)
 p['manifest']['metadata']['goal_base_life_authoring']={'native':life,'selected_initial':99999,'selected_capacity':99999,'authoring':'User-authorized campaign base life policy; operators and enemies retain exact selected module HP.'}
 check=deepcopy(p);check['scenarioDraft']['resources']['life']=life;del check['manifest']['metadata']['goal_base_life_authoring'];assert check==original
 sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT));from ark_sim import Compiler;from ark_sim.adapters.api import implementation_digest
 assert implementation_digest()==args.expected_core;Compiler().compile(p)
 authored.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
 receipt={'core':args.expected_core,'native_stage_sha':sha(native),'life99999_stage_sha':sha(authored),'actual_diff':['scenarioDraft.resources.life.initial','scenarioDraft.resources.life.capacity','manifest.metadata.goal_base_life_authoring'],'map_timeline_cost_DP_roster_and_8fields_unchanged':True,'whole_stage_executed':False,'client_verified':False}
 dest=OUT/'stage_authoring.json';dest.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps(receipt))
if __name__=='__main__':main()
