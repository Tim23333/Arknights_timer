"""Persist actual Mephi healing/aura, real damage death and dormant witnesses."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
CORE = 'cb321a851dc1ccb373477c73a522fc4ca8c35ce8b1c38d18bbee7e1e028358d7'
OUT = ROOT/'packages/campaign/chapter05_boss/mephi/evidence'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p, v): p.write_text(json.dumps(v, ensure_ascii=False, indent=2)+'\n', encoding='utf8')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--runtime-root', type=Path, default=ROOT.parent/'unpack_work/campaign_m94_complete_c4_candidate')
    args = ap.parse_args(); runtime = args.runtime_root.resolve(); OUT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(runtime))
    import ark_sim
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.tools.replay import replay
    from tools.campaign_ordered_checkpoint import write_ordered, load_bound
    from tools.campaign_streaming_evidence import observations, export_events
    from tools.chapter05.mephi.test_module import fixture_package, char, hp, rate, heals, members
    module = ROOT/'packages/campaign/chapter05_boss/mephi/model.json'
    regen = ROOT/'packages/campaign/chapter05_units/regenerating/model.json'
    tests = ROOT/'packages/campaign/chapter05_boss/mephi/author.tests.json'
    guards = [Path(__file__), ROOT/'tools/chapter05/mephi/build_module.py', ROOT/'tools/chapter05/mephi/test_module.py',
              module, regen, ROOT/'packages/campaign/chapter05_sources/native.reference.json', tests,
              ROOT/'tools/campaign_ordered_checkpoint.py', ROOT/'tools/campaign_streaming_evidence.py']
    before = {str(p): sha(p) for p in guards}
    if Path(ark_sim.__file__).resolve().parent != runtime/'ark_sim' or implementation_digest() != CORE:
        raise ValueError('Frozen M94 only')
    actual_tests = json.loads(tests.read_bytes())
    if actual_tests['exit_code'] != 0 or not actual_tests['passed'] or actual_tests['implementation_after'] != CORE:
        raise ValueError('Actual author tests must pass on fixed core')
    records = []
    for name, options, expected_zomstr, expected_zomsbr, expected_heals, alive in [
        ('alive', {}, 1800, 1320, [(33, 500)], True),
        ('damage_death', {'kill_at': 10}, 1473.3333333333333, 1189.3333333333333, [], False),
        ('dormant_activation', {'mephi_active': False, 'mephi_activate': 20}, 1666.6666666666667, 1266.6666666666667, [(53, 500)], True)]:
        package, gen = fixture_package([char('friend')], regen=[('enemy_1044_zomstr', 'zomstr', 1000, 30),
            ('enemy_1043_zomsbr', 'zomsbr', 1000, 31)], **options)
        path = OUT/(name+'.probe.json'); write(path, package)
        program = Compiler().compile(path, packages=[regen])
        s = Engine.create(program, seed=5510)
        if name == 'damage_death':
            s.submit({'action': 'skill', 'source': 'killer', 'ability': 'ability/test/mephi_kill'}, at=10)
        s.session.advance(5)
        cp = OUT/(name+'.checkpoint.json'); cp_sha = write_ordered(cp, s.checkpoint())
        restored = Engine.restore(program, load_bound(cp, cp_sha))
        s.session.advance(55); restored.session.advance(55)
        record_path = OUT/(name+'.replay.json'); write(record_path, s.export_replay())
        repeated = replay(program, json.loads(record_path.read_bytes()))
        obs = observations(s); restored_obs = observations(restored); repeated_obs = observations(repeated)
        actual = {'mephi_alive': s.ctx.alive('mephi'), 'mephi_hp': hp(s, 'mephi'),
                  'friend_hp': hp(s, 'friend'), 'zomstr_hp': hp(s, 'zomstr'), 'zomsbr_hp': hp(s, 'zomsbr'),
                  'zomstr_rate': rate(s, 'zomstr'), 'zomsbr_rate': rate(s, 'zomsbr'),
                  'zomstr_aura_members': len(members(s, 'zomstr')), 'zomsbr_aura_members': len(members(s, 'zomsbr')),
                  'healing_packets': [(e['time'], e['payload']['amount']) for e in heals(s)],
                  'damage_packets': [(e['time'], e['payload']['amount']) for e in s.session.events if e['type'] == 'damage.accepted']}
        if (abs(actual['zomstr_hp']-expected_zomstr) > 1e-8 or abs(actual['zomsbr_hp']-expected_zomsbr) > 1e-8
                or actual['mephi_alive'] != alive or actual['healing_packets'] != expected_heals or obs != restored_obs or obs != repeated_obs):
            raise ValueError('Actual mechanism/CP/replay differs: '+name)
        journal = export_events(OUT/(name+'.events.jsonl'), s)
        records.append({'name': name, 'end_tick': 60, 'actual': actual,
            'expected': {'zomstr_hp': expected_zomstr, 'zomsbr_hp': expected_zomsbr, 'healing_packets': expected_heals, 'mephi_alive': alive},
            'program': program.fingerprint, 'runtime': s.runtime_fingerprint,
            'package': {'path': str(path), 'sha256': sha(path)}, 'additional_package': {'path': str(regen), 'sha256': sha(regen)},
            'checkpoint': {'path': str(cp), 'sha256': cp_sha, 'tick': 5, 'actually_reloaded': True},
            'replay': {'path': str(record_path), 'sha256': sha(record_path)}, 'journal': journal,
            'observations': obs, 'checkpoint_observations': restored_obs, 'replay_observations': repeated_obs,
            'checkpoint_equal': True, 'replay_equal': True})
    after = {str(p): sha(p) for p in guards}; end_core = implementation_digest()
    report = {'schema': 'ark-sim/chapter05-mephi-author-evidence/v1', 'author_checks_passed': before == after and end_core == CORE,
        'independent_reviewed': False, 'formal_approved': False, 'whole_stage_executed': False, 'actual_client_verified': False,
        'runtime_module': ark_sim.__file__, 'core_start': CORE, 'core_end': end_core,
        'source_at_start': before, 'source_at_completion': after, 'identity_stable': before == after,
        'module_sha256': sha(module), 'actual_pytest': {'path': str(tests), 'sha256': sha(tests), 'actual_exit_code': 0},
        'scope': 'Actual normal Heal33/6s, global ally CHAR HP_RECOVERY multiplier, real HP death and dormant activation; no Faust or whole-stage claim',
        'witnesses': records, 'reference_policies': json.loads(module.read_bytes())['manifest']['metadata']['reference_policies']}
    dest = OUT/'author.evidence.json'; write(dest, report)
    if not report['author_checks_passed']: raise ValueError('Source/core identity drift')
    print(json.dumps({'author_checks_passed': True, 'independent_reviewed': False, 'report_sha256': sha(dest), 'witnesses': len(records)}))


if __name__ == '__main__': main()
