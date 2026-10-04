"""Persist bounded author witnesses for peer review; never approve a stage."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
CORE = 'cb321a851dc1ccb373477c73a522fc4ca8c35ce8b1c38d18bbee7e1e028358d7'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runtime-root', type=Path, default=ROOT.parent/'unpack_work/campaign_m94_complete_c4_candidate')
    ap.add_argument('--output-directory', type=Path, default=ROOT/'packages/campaign/chapter05_reports/regenerating')
    args = ap.parse_args(); runtime = args.runtime_root.resolve(); out = args.output_directory.resolve()
    out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(runtime))
    import ark_sim
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.tools.replay import replay
    from tools.campaign_ordered_checkpoint import write_ordered, load_bound
    from tools.campaign_streaming_evidence import observations, export_events
    from tools.chapter05.tests.test_regenerating_units import fixture_package
    if Path(ark_sim.__file__).resolve().parent != runtime/'ark_sim' or implementation_digest() != CORE:
        raise ValueError('Exact frozen M94 required')
    guards = [Path(__file__), ROOT/'tools/chapter05/build_regenerating_units.py',
              ROOT/'tools/chapter05/tests/test_regenerating_units.py',
              ROOT/'packages/campaign/chapter05_units/regenerating/model.json',
              ROOT/'packages/campaign/chapter05_sources/native.reference.json',
              ROOT/'packages/campaign/chapter05_units/ordinary.reference_model.json',
              ROOT/'tools/campaign_ordered_checkpoint.py', ROOT/'tools/campaign_streaming_evidence.py',
              ROOT/'tools/run_candidate_pytest.py', out/'author.tests.json']
    before = {str(p): sha(p) for p in guards}
    test_report = json.loads((out/'author.tests.json').read_bytes())
    if not test_report['passed'] or test_report['implementation_after'] != CORE or test_report['exit_code'] != 0:
        raise ValueError('Actual author pytest pass required')
    records = []
    for native, expected in [('enemy_1044_zomstr', 1166.6666666666667), ('enemy_1043_zomsbr', 1006.6666666666667)]:
        package = fixture_package(native, dormant=True, activate_at=20)
        pkg_path = out/(native+'.probe.json'); write(pkg_path, package)
        program = Compiler().compile(pkg_path)
        s = Engine.create(program, seed=5501)
        s.submit({'action': 'skill', 'source': 'probe', 'ability': 'ability/regen_probe_damage'}, at=30)
        s.session.advance(17)
        cp_path = out/(native+'.checkpoint.json'); cp_sha = write_ordered(cp_path, s.checkpoint())
        restored = Engine.restore(program, load_bound(cp_path, cp_sha))
        s.session.advance(43); restored.session.advance(43)
        replay_path = out/(native+'.replay.json'); write(replay_path, s.export_replay())
        repeated = replay(program, json.loads(replay_path.read_bytes()))
        obs = observations(s); restored_obs = observations(restored); replay_obs = observations(repeated)
        actual = s.ctx.resources.current('enemy', 'hp')
        if abs(actual-expected) > 1e-8 or obs != restored_obs or obs != replay_obs:
            raise ValueError('Actual numeric/CP/replay witness differs')
        journal = export_events(out/(native+'.events.jsonl'), s)
        records.append({'native_id': native, 'expected_final_hp': expected, 'actual_final_hp': actual,
            'end_tick': s.session.time, 'activation_tick': 20, 'incoming_damage_tick': 30, 'incoming_damage_amount': 100,
            'program': program.fingerprint, 'runtime': s.runtime_fingerprint,
            'package': {'path': str(pkg_path), 'sha256': sha(pkg_path)},
            'checkpoint': {'path': str(cp_path), 'sha256': cp_sha, 'tick': 17, 'loaded_from_actual_file': True},
            'replay': {'path': str(replay_path), 'sha256': sha(replay_path)}, 'journal': journal,
            'observations': obs, 'checkpoint_observations': restored_obs, 'replay_observations': replay_obs,
            'checkpoint_equal': True, 'replay_equal': True})
    after = {str(p): sha(p) for p in guards}
    final_core = implementation_digest()
    report = {'schema': 'ark-sim/chapter05-regeneration-author-evidence/v1',
        'author_checks_passed': before == after and final_core == CORE, 'independent_reviewed': False,
        'formal_approved': False, 'whole_stage_executed': False, 'actual_client_verified': False,
        'runtime_module': ark_sim.__file__, 'core_start': CORE, 'core_end': final_core,
        'source_at_start': before, 'source_at_completion': after, 'identity_stable': before == after,
        'actual_pytest_report': {'path': str(out/'author.tests.json'), 'sha256': sha(out/'author.tests.json'), 'exit_code': 0},
        'witnesses': records,
        'model_boundaries': ['HP fixture1000 exposes recovery without altering shipped maxHP6000/2500',
                            'ASPD windup scaling is an explicit model; native method/clamp/client comparison pending',
                            'Local prefab/Spine versions not verified against fixed DB commit; no external token candidate needed here',
                            'Mephisto aura and whole-stage dependencies are outside this two-variant module']}
    report_path = out/'author.evidence.json'; write(report_path, report)
    if not report['author_checks_passed']: raise ValueError('Evidence source/core identity drift')
    print(json.dumps({'author_checks_passed': True, 'independent_reviewed': False,
                      'report': str(report_path), 'report_sha256': sha(report_path), 'witnesses': len(records)}))


if __name__ == '__main__': main()
