"""Source identity plus independent arithmetic on two sealed native prefixes."""
import hashlib
import inspect
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT.parent / 'unpack_work/campaign_campaign_foundation_v5_candidate'
CORE = '82db6a9db5ddd3a4c3c58f05b04e773419312ae77d5fc086fbb98a7a984bf8ae'
OUT = ROOT / 'validation/trace_audit/chapter08_native_prefix_v3'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    sys.path.insert(0, str(RUNTIME))
    sys.path.insert(1, str(ROOT))
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.contracts import thaw
    from tools.trace_audit.chapter08_stream_v2 import audit
    from tools.chapter08_stage_join.runner_providers_v2 import providers as jt82
    from tools.chapter08_joint_v4.build_jt83_draft_v4 import providers as jt83
    assert implementation_digest() == CORE
    assert not OUT.exists()
    OUT.mkdir(parents=True)
    rows = []
    pins = {str(path): sha(path) for path in (Path(__file__),
        ROOT / 'tools/trace_audit/chapter08_stream_v2.py', ROOT / 'tools/trace_audit/chapter08_arithmetic_v2.py')}
    cases = [
        ('JT8-2', 'level_main_08-16.native_draft.v7.life99999.v1.json', jt82,
         Path('E:/ArkSimEvidence/campaign/JT8_2_82db_native_v7/full_v1.checkpoint.json')),
        ('JT8-3', 'level_main_08-17.native_draft.v4.life99999.v1.json', jt83,
         Path('E:/ArkSimEvidence/campaign/JT8_3_82db_native_v4/full_v2.checkpoint.json')),
    ]
    for name, filename, factory, checkpoint in cases:
        package_path = ROOT / 'packages/campaign/chapter08_stage_models' / filename
        pins[str(package_path)] = sha(package_path)
        pins[str(checkpoint)] = sha(checkpoint)
        package = json.loads(package_path.read_bytes())
        saved = json.loads(checkpoint.read_bytes())
        registry = factory()
        for entry in registry.values():
            callback = entry.get('callable', entry.get('evaluate')) if isinstance(entry, dict) else entry
            source = inspect.getsourcefile(callback)
            if source:
                pins[source] = sha(source)
        sim = Engine.create(Compiler(providers=registry).compile(package), providers=registry,
                            seed=package['scenarioDraft']['seed'])
        assert sim.runtime_fingerprint == saved['runtime_fingerprint']
        rules = sim.ctx.rules
        definition_map = {key: thaw(value) for key, value in rules.rules.items()}
        identities = {key: thaw(value[2]) for key, value in rules.providers.items()}
        row = audit(saved['kernel']['events']['reference'], definition_map,
                    rules.rule_fingerprints, identities, rules.fingerprint, saved['kernel']['quantum'])
        row.update(stage=name, package_sha=sha(package_path), checkpoint_sha=sha(checkpoint),
                   source_runtime_matches_checkpoint=True, clock=saved['kernel']['time'])
        rows.append(row)
    assert all(sha(path) == value for path, value in pins.items())
    result = {'passed': all(row['passed_subset'] for row in rows), 'core': CORE, 'pins': pins,
              'rows': rows, 'whole_stage': False, 'all_intermediate_fields_verified': False,
              'client_verified': False}
    target = OUT / 'verification.json'
    target.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf8'))
    print(json.dumps({'passed': result['passed'], 'sha': sha(target),
                      'checked_calculations': [sum(row['checked_rules'].values()) for row in rows]}))
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
