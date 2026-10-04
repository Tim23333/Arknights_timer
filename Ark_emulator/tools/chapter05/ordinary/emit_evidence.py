"""Persist actual ordinary-two evidence without rewriting the source module."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'packages/campaign/chapter05_reports/ordinary_actual'
CORE = 'cb321a851dc1ccb373477c73a522fc4ca8c35ce8b1c38d18bbee7e1e028358d7'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p, v): p.write_text(json.dumps(v, ensure_ascii=False, indent=2)+'\n', encoding='utf8')


def main():
    sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT.parent/'unpack_work/campaign_m94_complete_c4_candidate'))
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.tools.replay import replay
    from tools.campaign_ordered_checkpoint import write_ordered, load_bound
    from tools.campaign_streaming_evidence import observations, export_events
    from tools.chapter05.ordinary.test_actual import fixture_package, MODULE, PIN, hp
    if implementation_digest() != CORE or sha(MODULE) != PIN: raise ValueError('Frozen core/module required')
    OUT.mkdir(parents=True, exist_ok=True)
    guards = [Path(__file__), ROOT/'tools/chapter05/ordinary/test_actual.py', MODULE,
        ROOT/'packages/campaign/chapter05_sources/native.reference.json', OUT/'author.tests.json',
        ROOT/'tools/campaign_ordered_checkpoint.py', ROOT/'tools/campaign_streaming_evidence.py']
    before = {str(p): sha(p) for p in guards}
    tests = json.loads((OUT/'author.tests.json').read_bytes())
    if not tests['passed'] or tests['exit_code'] != 0 or tests['implementation_after'] != CORE: raise ValueError('Actual author tests required')
    records = []
    for native, maxhp in [('enemy_1037_lunsbr', 3200), ('enemy_1030_wteeth', 5000)]:
        for case in ('blocked_damage', 'dead', 'route_exit'):
            package = fixture_package(native, initial_hp=200 if case == 'dead' else None, objectives=case == 'route_exit')
            name = native+'.'+case; path = OUT/(name+'.probe.json'); write(path, package)
            program = Compiler().compile(path); s = Engine.create(program, seed=5520)
            if case != 'route_exit':
                s.submit({'action': 'deploy', 'definition': 'unit/test/plain_blocker', 'alias': 'blocker', 'position': {'row': 0, 'col': 0}}, at=0)
                s.submit({'action': 'skill', 'source': 'blocker', 'ability': 'ability/test/plain_damage'}, at=5)
            s.session.advance(2)
            cp = OUT/(name+'.checkpoint.json'); cp_sha = write_ordered(cp, s.checkpoint())
            restored = Engine.restore(program, load_bound(cp, cp_sha))
            end = 240 if case == 'route_exit' else 121
            s.session.advance(end-2); restored.session.advance(end-2)
            replay_path = OUT/(name+'.replay.json'); write(replay_path, s.export_replay())
            repeated = replay(program, json.loads(replay_path.read_bytes()))
            obs = observations(s); cp_obs = observations(restored); rp_obs = observations(repeated)
            expected_hp = maxhp if case == 'route_exit' else 0 if case == 'dead' else maxhp-200
            if hp(s) != expected_hp or obs != cp_obs or obs != rp_obs: raise ValueError('Actual witness mismatch: '+name)
            actual = {'enemy_hp': hp(s), 'alive': s.ctx.alive('enemy'), 'enemy_state': s.ctx.get('enemy', ('runtime', 'state')),
                'dp': s.ctx.resources.current('system/battle', 'dp'), 'life': s.ctx.resources.current('system/battle', 'life'),
                'kills': s.ctx.state()['kills'], 'leaks': s.ctx.state()['leaks'], 'finished': s.ctx.state()['finished'],
                'damage_packets': [(e['time'], e['payload']['source'], e['payload']['target'], e['payload']['amount']) for e in s.session.events if e['type'] == 'damage.accepted']}
            if case == 'route_exit' and (actual['leaks'] != 1 or actual['life'] != 99998): raise ValueError('Actual source leak loss differs')
            if case != 'route_exit' and actual['dp'] != 13: raise ValueError('Actual deploy payment differs')
            records.append({'name': name, 'native_id': native, 'case': case, 'actual': actual, 'end_tick': end,
                'program': program.fingerprint, 'runtime': s.runtime_fingerprint,
                'package': {'path': str(path), 'sha256': sha(path)}, 'checkpoint': {'path': str(cp), 'sha256': cp_sha, 'tick': 2, 'actually_reloaded': True},
                'replay': {'path': str(replay_path), 'sha256': sha(replay_path)}, 'journal': export_events(OUT/(name+'.events.jsonl'), s),
                'observations': obs, 'checkpoint_observations': cp_obs, 'replay_observations': rp_obs, 'checkpoint_equal': True, 'replay_equal': True})
    after = {str(p): sha(p) for p in guards}; core_end = implementation_digest()
    report = {'schema': 'ark-sim/chapter05-ordinary-author-evidence/v1', 'author_checks_passed': before == after and core_end == CORE,
        'core_start': CORE, 'core_end': core_end, 'module_sha256': sha(MODULE), 'source_at_start': before, 'source_at_completion': after,
        'identity_stable': before == after, 'actual_pytest_exit': 0, 'witnesses': records,
        'independent_reviewed': False, 'formal_approved': False, 'whole_stage_executed': False, 'client_verified': False,
        'scope': 'Existing exact ordinary2 bytes; actual blocked attacks, public incoming damage/payment/death/route and full public replay; no regeneration driver'}
    dest = OUT/'author.evidence.json'; write(dest, report)
    if not report['author_checks_passed']: raise ValueError('Source/core drift')
    print(json.dumps({'author_checks_passed': True, 'module_unchanged': sha(MODULE) == PIN, 'witnesses': len(records), 'report_sha256': sha(dest)}))


if __name__ == '__main__': main()
