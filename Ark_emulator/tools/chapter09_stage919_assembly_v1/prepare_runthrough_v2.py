"""Metadata-only runthrough profile over the already life99999 source input."""
from copy import deepcopy
import hashlib,json,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))


def main():
    from tools.chapter06_review.stage_converter_v7 import exact
    parent=ROOT/'packages/campaign/chapter09_stage_models/level_main_09-17.native_draft.v2.life99999.json';commands=ROOT/'scenarios/campaign/chapter09/level_main_09-17/public_plan_v1_finite/commands.json'
    original=json.loads(parent.read_bytes());p=deepcopy(original);scene=p['scenarioDraft'];assert scene['resources']['life']=={'initial':99999,'capacity':99999}
    scene['metadata']['runthrough_profile']={'base_life_resource':'life','base_life':99999,'fixed12':deepcopy(scene['roster']),
        'source_births':63,'deploy_capacity':9,'public_commands_sha256':hashlib.sha256(commands.read_bytes()).hexdigest(),
        'operator_enemy_HP':'Original exact source module HP','training_deployment_exception':False,'client_verified':False,
        'accuracy':'Source-reference model; user feedback pending'}
    p['manifest']['metadata']['runthrough_parent_sha']=hashlib.sha256(parent.read_bytes()).hexdigest()
    restored=deepcopy(p);del restored['scenarioDraft']['metadata']['runthrough_profile'];del restored['manifest']['metadata']['runthrough_parent_sha'];assert exact(restored,original)
    out=parent.with_name('level_main_09-17.native_draft.v2.life99999.finite_run_v1.json');assert not out.exists();out.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    receipt={'parent_sha':hashlib.sha256(parent.read_bytes()).hexdigest(),'overlay_sha':hashlib.sha256(out.read_bytes()).hexdigest(),
        'commands_sha':hashlib.sha256(commands.read_bytes()).hexdigest(),'only_metadata_profile_added':True,'all_battle_inputs_type_exact_unchanged':True,
        'base_life':99999,'squad12':True,'source_births':63,'slots':9,'DP10':True,'whole_stage':False}
    folder=ROOT/'validation/campaign/chapter09_stage919_assembly';p=folder/'runthrough.overlay.v2.json';assert not p.exists();p.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8');print(json.dumps(receipt))


if __name__=='__main__':main()
