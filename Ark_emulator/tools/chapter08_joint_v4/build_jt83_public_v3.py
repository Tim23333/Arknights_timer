"""Latest visual source stage with the same legal fixed12 public plan."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.chapter08_joint_v4.build_jt83_draft_v4 import OUT as PARENT, sha

OUT = PARENT.with_name('level_main_08-17.native_draft.v4.life99999.v1.json')
COMMANDS = ROOT / 'scenarios/campaign/chapter08/level_main_08-17/public_plan_v2/commands.json'
PRIOR = ROOT / 'packages/campaign/chapter08_stage_models/level_main_08-17.native_draft.v2.life99999.v1.json'


def build():
    from tools.campaign_runthrough_progress_v5 import validate_native_overlay
    assert sha(PARENT) == 'fdfa0bca0f6034602d1f69630b8727db74c864c226e4de3c17ea3150fae1860a'
    assert sha(COMMANDS) == 'f74bd538a048fb3d07aabee4d185da1e099ad5b5b52f5e570b6657f6844e897c'
    package = json.loads(PARENT.read_bytes())
    old = json.loads(PRIOR.read_bytes())
    assert package['scenarioDraft']['roster'] == old['scenarioDraft']['roster']
    scene = package['scenarioDraft']
    scene['resources']['life'] = old['scenarioDraft']['resources']['life']
    scene['metadata']['runthrough_profile'] = old['scenarioDraft']['metadata']['runthrough_profile']
    package['manifest']['metadata']['goal_base_life_authoring'] = old['manifest']['metadata']['goal_base_life_authoring']
    validate_native_overlay(package, json.loads(PARENT.read_bytes()), COMMANDS)
    return package


if __name__ == '__main__':
    package = build()
    assert not OUT.exists()
    OUT.write_bytes((json.dumps(package, ensure_ascii=False, indent=2) + '\n').encode('utf8'))
    print(json.dumps({'parent_sha': sha(PARENT), 'overlay_sha': sha(OUT),
                      'commands_sha': sha(COMMANDS), 'only_base_life': True,
                      'whole_stage': False}))
