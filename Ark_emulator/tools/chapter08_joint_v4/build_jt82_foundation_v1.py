"""Bind the exact JT8-2 source composition to the combined foundation."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT.parent / 'unpack_work/campaign_campaign_foundation_v5_candidate'
CORE = '82db6a9db5ddd3a4c3c58f05b04e773419312ae77d5fc086fbb98a7a984bf8ae'
OUT = ROOT / 'packages/campaign/chapter08_stage_models/level_main_08-16.native_draft.v7.json'
PRIOR = ROOT / 'packages/campaign/chapter08_stage_models/level_main_08-16.native_draft.v6.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def providers():
    from tools.chapter08_stage_join.runner_providers_v2 import providers as registry
    return registry()


def build():
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    from tools.chapter08_joint_v2 import build_jt82_v1 as previous
    assert implementation_digest() == CORE
    # The converter still performs its native-field checks and compiles all
    # reachable definitions. Only its expected runtime binding is updated.
    assert previous.CORE == 'a6ca7396556624768da2f83680ae34ad632d36dfa85f646916edbd1ee85f0128'
    old_core = previous.CORE
    try:
        previous.CORE = CORE
        package = previous.build()
    finally:
        previous.CORE = old_core
    old = json.loads(PRIOR.read_bytes())
    assert package['definitions'] == old['definitions']
    assert package['scenarioDraft'] == old['scenarioDraft']
    package['manifest']['id'] = 'package/ch8/native_draft/jt82_v7_foundation'
    meta = package['manifest']['metadata']
    meta['source_locks'].update({str(path): sha(path) for path in
                                (Path(previous.__file__), Path(__file__), PRIOR)})
    meta['builder_sha'] = sha(Path(__file__))
    meta['foundation_binding'] = {
        'runtime': CORE, 'source_definitions_and_scene_equal_to_v6': True,
        'old_v6_sha': sha(PRIOR), 'new_runtime_evidence_pending': True,
        'old_full_run_not_migrated': True,
        'scope': 'D12 dynamic historical buff clocks and original 32 births; source admission and whole execution pending',
    }
    Compiler(providers=providers()).compile(package)
    return package


if __name__ == '__main__':
    sys.path.insert(0, str(RUNTIME))
    sys.path.insert(1, str(ROOT))
    package = build()
    assert not OUT.exists()
    OUT.write_bytes((json.dumps(package, ensure_ascii=False, indent=2) + '\n').encode('utf8'))
    print(json.dumps({'sha': sha(OUT), 'core': CORE, 'births': 32,
                      'definitions': len(package['definitions']), 'actual_compile': True,
                      'whole_stage': False}))
