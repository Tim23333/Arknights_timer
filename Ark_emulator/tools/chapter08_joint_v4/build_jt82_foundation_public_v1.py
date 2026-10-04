"""Create the new life-only overlay without changing the fixed public plan."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.chapter08_joint_v4.build_jt82_foundation_v1 import OUT as PARENT, sha

OUT = PARENT.with_name('level_main_08-16.native_draft.v7.life99999.v1.json')
COMMANDS = ROOT / 'scenarios/campaign/chapter08/level_main_08-16/public_plan_v4/commands.json'
PRIOR = ROOT / 'packages/campaign/chapter08_stage_models/level_main_08-16.native_draft.v6.life99999.v1.json'


def build():
    from tools.campaign_runthrough_progress_v5 import validate_native_overlay
    package = json.loads(PARENT.read_bytes())
    old_overlay = json.loads(PRIOR.read_bytes())
    assert sha(COMMANDS) == 'f2f73ffd663595c144e98be848d5d820eb5f9a589877c13e20f4320da8f70c24'
    package['scenarioDraft'] = old_overlay['scenarioDraft']
    package['manifest']['metadata']['goal_base_life_authoring'] = old_overlay['manifest']['metadata']['goal_base_life_authoring']
    validate_native_overlay(package, json.loads(PARENT.read_bytes()), COMMANDS)
    assert package['definitions'] == old_overlay['definitions']
    return package


if __name__ == '__main__':
    package = build()
    assert not OUT.exists()
    OUT.write_bytes((json.dumps(package, ensure_ascii=False, indent=2) + '\n').encode('utf8'))
    print(json.dumps({'parent_sha': sha(PARENT), 'overlay_sha': sha(OUT),
                      'commands_sha': sha(COMMANDS), 'only_base_life': True,
                      'whole_stage': False}))
