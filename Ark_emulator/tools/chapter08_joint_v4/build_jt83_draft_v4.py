"""Rebuild exact native JT8-3 with frozen visual Boss on foundation82db."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT.parent / 'unpack_work/campaign_campaign_foundation_v5_candidate'
CORE = '82db6a9db5ddd3a4c3c58f05b04e773419312ae77d5fc086fbb98a7a984bf8ae'
OUT = ROOT / 'packages/campaign/chapter08_stage_models/level_main_08-17.native_draft.v4.json'


def sha(path):
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def providers():
    from tools.chapter08_joint_v4.build_jt83_draft_v3 import providers as registry
    return registry()


def build():
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    from tools.chapter08_joint_v4 import build_jt83_draft_v3 as previous
    from tools.chapter08_joint_v4.build_bsnake_visual_join_v1 import OUT as boss
    assert implementation_digest() == CORE
    parent_path = previous.OUT
    old_core, old_base = previous.CORE, previous.BASE
    assert old_core == '4bf1cc96ae41f2850b645c25d772ada1d472f7b0202127fff340a4fc2b0b04c3'

    class SourcePaths:
        # Preserve the converter's exact native map, wave and field checks.
        def __truediv__(self, relative):
            return boss if relative == 'bsnake/four_modes.wave_source.v5.json' else old_base / relative

    try:
        previous.CORE, previous.BASE = CORE, SourcePaths()
        result = previous.build()
    finally:
        previous.CORE, previous.BASE = old_core, old_base
    old = json.loads(parent_path.read_bytes())
    assert result['scenarioDraft'] == old['scenarioDraft']
    prior_definitions = {row['id']: row for row in old['definitions']}
    new_definitions = {row['id']: row for row in result['definitions']}
    owner = 'unit/ch8/bsnake/cadb87696bef4de2'
    assert all(new_definitions[key] == value for key, value in prior_definitions.items() if key != owner)
    assert set(prior_definitions) <= set(new_definitions)
    result['manifest']['id'] = 'package/ch8/jt83/native_draft_v4_visual_foundation'
    meta = result['manifest']['metadata']
    meta['source_locks'].update({str(path): sha(path) for path in (parent_path, Path(previous.__file__), Path(__file__))})
    meta['visual_foundation_binding'] = {
        'old_stage_sha': sha(parent_path), 'new_boss_sha': sha(boss),
        'scene_fields_and_original_nonboss_definitions_unchanged': True,
        'added_definition_ids': sorted(set(new_definitions) - set(prior_definitions)),
        'joint_source_gate_pending': True, 'whole_stage_executed': False,
    }
    Compiler(providers=providers()).compile(result)
    return result


if __name__ == '__main__':
    sys.path.insert(0, str(RUNTIME))
    sys.path.insert(1, str(ROOT))
    result = build()
    assert not OUT.exists()
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf8'))
    print(json.dumps({'sha': sha(OUT), 'core': CORE, 'births': 44,
                      'definitions': len(result['definitions']), 'actual_compile': True,
                      'whole_stage': False}))
