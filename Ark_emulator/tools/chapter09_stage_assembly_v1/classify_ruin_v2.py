"""Separate source terrain devices from native wave-enemy accounting tags."""
from copy import deepcopy
import hashlib,json,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))


def main():
    from tools.chapter06_review.stage_converter_v7 import exact
    parent=ROOT/'packages/campaign/chapter09_stage_models/level_main_09-16.native_draft.v1.life99999.json';source=json.loads(parent.read_bytes());result=deepcopy(source)
    target=next(d for d in result['definitions'] if d['id']=='unit/ch9/pillar/ruin');original=deepcopy(target)
    assert target['tags']==['enemy','ruin']
    assert target['components']['selection_state']=={'side':1,'motion':1,'category':4,'unit_type':4}
    assert target['components']['resources']['hp']['initial']==100 and target['components']['attributes']['base']['block_count']==3
    target['tags']=['ruin','terrain_mechanism']
    probe=deepcopy(result);next(d for d in probe['definitions'] if d['id']==target['id'])['tags']=original['tags'];assert exact(probe,source)
    result['manifest']['metadata']['source_device_classification']={'definition':target['id'],'before_tags':original['tags'],'after_tags':target['tags'],
        'side_motion_category_unit_type_unchanged':True,'HP100_block3_terrain_unchanged':True,
        'source':'duruin.transitive.source.v1.json TrapMode; devices with enemy side are not native enemyDbRefs wave births',
        'counter':'validation/campaign/chapter09_stage_assembly/ruin.classification.counter.v1.json'}
    result['manifest']['metadata']['classification_parent_sha']=hashlib.sha256(parent.read_bytes()).hexdigest()
    out=parent.with_name('level_main_09-16.native_draft.v2.life99999.json');assert not out.exists();out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    commands=ROOT/'scenarios/campaign/chapter09/level_main_09-16/public_plan_v1_finite/commands.json';run=deepcopy(result);scene=run['scenarioDraft'];scene['metadata']['runthrough_profile']={'base_life_resource':'life','base_life':99999,'fixed12':deepcopy(scene['roster']),'source_births':34,'deploy_capacity':8,'public_commands_sha256':hashlib.sha256(commands.read_bytes()).hexdigest(),'operator_enemy_HP':'Original exact source module HP','training_deployment_exception':False,'client_verified':False,'accuracy':'Source-reference model; user feedback pending'}
    run['manifest']['metadata']['runthrough_parent_sha']=hashlib.sha256(out.read_bytes()).hexdigest();overlay=out.with_name('level_main_09-16.native_draft.v2.life99999.finite_run_v1.json');assert not overlay.exists();overlay.write_text(json.dumps(run,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    receipt={'parent_sha':hashlib.sha256(parent.read_bytes()).hexdigest(),'classified_package_sha':hashlib.sha256(out.read_bytes()).hexdigest(),'runthrough_package_sha':hashlib.sha256(overlay.read_bytes()).hexdigest(),'commands_sha':hashlib.sha256(commands.read_bytes()).hexdigest(),'definition_tags_only_battle_change':True,'metadata_only_runthrough_overlay':True,'actual_source_side_and_mechanic_fields_preserved':True,'whole_stage':False}
    p=ROOT/'validation/campaign/chapter09_stage_assembly/classification.v2.json';assert not p.exists();p.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8');print(json.dumps(receipt))


if __name__=='__main__':main()
