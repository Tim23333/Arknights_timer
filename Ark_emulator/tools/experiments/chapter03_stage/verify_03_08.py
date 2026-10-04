"""Source-bound 3-8 join and actual short execution; no whole-stage claim."""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT.parent / 'unpack_work/campaign_m54_qualified_visibility_candidate'
CORE = 'e6e0142c9ef9aa2cdcf35188aba0865efba370346eecf1c50750a45f56974b75'
PACKAGE = ROOT / 'packages/campaign/chapter03_stage_models/level_main_03-08.m54.reference_model.json'
PIN = '1af6b6efc48caf472394f732e44d21ca7a324717a888e77b2cd6329d282f61f8'
OUT = ROOT / 'validation/campaign/chapter03_stage/03_08_m54_short'
sys.path.insert(0, str(RUNTIME))
sys.path.insert(1, str(ROOT))
from ark_sim import Compiler, Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered, load_bound
from tools.campaign_streaming_evidence import observations, export_events, write_canonical


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    import ark_sim
    assert Path(ark_sim.__file__).resolve().parent == RUNTIME / 'ark_sim'
    assert implementation_digest() == CORE and sha(PACKAGE) == PIN
    guards = [PACKAGE, Path(__file__), ROOT / 'tools/build_chapter03_08_stage.py',
              ROOT / 'packages/campaign/chapter03_plans/source.plan.json']
    before = {str(p): sha(p) for p in guards}
    p = json.loads(PACKAGE.read_bytes()); scene = p['scenarioDraft']
    definitions = {d['id']: d for d in p['definitions']}
    counts = Counter(); controls = Counter()
    for wave in scene['timeline']['waves']:
        for fragment in wave['fragments']:
            for action in fragment['actions']:
                raw = action['metadata']['native_action']
                assert action['count'] == raw['count']
                assert action['managed'] == raw['managedByScheduler']
                assert action['blocks_fragment'] == raw['blockFragment']
                if action['kind'] == 'spawn':
                    counts[action['spawn']['definition']] += action['count']
                else:
                    controls[raw['actionType']] += action['count']
    assert sum(counts.values()) == 63 and len(counts) == 8
    assert controls == {'PREVIEW_CURSOR': 1, 'DISPLAY_ENEMY_INFO': 2}
    bindings = p['manifest']['metadata']['variant_bindings']
    assert len(bindings) == 8 and {r['unit_definition'] for r in bindings} == set(counts)
    boss = next(r for r in bindings if r['native_reference']['id'] == 'enemy_1500_skulsr')
    assert boss['native_reference']['level'] == 1
    assert definitions[boss['unit_definition']]['components']['resources']['hp']['initial'] == 30000
    fly = next(r for r in bindings if r['native_reference']['id'] == 'enemy_1005_yokai')
    assert fly['native_reference']['level'] == 1
    assert definitions[fly['unit_definition']]['components']['resources']['hp']['initial'] == 1870
    assert all(definitions[r['unit_definition']]['components']['selection_state']['motion'] == (2 if r['native_motion'] == 'FLY' else 1) for r in bindings)
    assert scene['initialEntities'] == [] and len(scene['roster']) == 12
    assert not any('trap_005_sensor' in key or 'trap_001_crate' in key for key in definitions)
    assert scene['resources'] == {'dp': {'initial': 10, 'capacity': 99, 'recovery_rate': 1.0,
                                         'recovery': {'mode': 'periodic', 'interval_seconds': 1.0}},
                                   'life': {'initial': 3, 'capacity': 3}}
    field_cells = [(i // 11, i % 11) for i, t in enumerate(scene['map']['tiles']) if t['tileKey'] == 'tile_defup']
    assert field_cells == [(1, 9), (2, 7), (3, 5), (4, 5), (5, 7), (6, 9)]
    assert all(not r['active'] for r in scene['metadata']['rune_policy'])
    program = Compiler().compile(p); s = Engine.create(program, seed=scene['seed'])
    commands = [{'at': 0, 'action': 'deploy', 'definition': 'unit/char_151_myrtle', 'alias': 'myrtle',
                 'position': {'row': 2, 'col': 7}, 'facing': 'left'}]
    for c in commands:
        s.submit({k: v for k, v in c.items() if k != 'at'}, at=c['at'])
    s.advance(50)
    # AttributeSystem.value is an observed calculation, not a read-only query.
    # Inspect the actual field modifier and already emitted effective values;
    # extra host calculations are not public commands and cannot be replayed.
    myrtle = s.session.world.resolve('myrtle')
    modifiers = s.ctx.get(myrtle, ('attributes', 'modifiers'))
    assert [m['value'] for m in modifiers if m['attribute'] == 'def' and m['layer'] == 'flat'] == [200.0]
    fields = [e for e in s.session.world.entities() if e['definition_id'] == 'unit/ch3/field/defup']
    assert len(fields) == 6
    OUT.mkdir(parents=True, exist_ok=True)
    cp = OUT / 'checkpoint.ordered.json'; cp_sha = write_ordered(cp, s.checkpoint())
    restored = Engine.restore(program, load_bound(cp, cp_sha)); s.advance(170); restored.advance(170)
    original = observations(s)
    repeated = replay(program, s.export_replay())
    checks = {'original': original, 'restored': observations(restored), 'replayed': observations(repeated)}
    if not checks['original'] == checks['restored'] == checks['replayed']:
        failed_dir = OUT / 'history_first_failure'
        failed_dir.mkdir(exist_ok=True)
        for name, sim in [('original', s), ('restored', restored), ('replayed', repeated)]:
            write_canonical(failed_dir / (name + '.snapshot.json'), sim.snapshot())
            export_events(failed_dir / (name + '.events.jsonl'), sim)
        write_canonical(failed_dir / 'comparison.json', checks)
        write_canonical(failed_dir / 'input.json', p)
        write_canonical(failed_dir / 'replay.json', s.export_replay())
        raise AssertionError('3-8 short durable continuation/replay differs: ' + json.dumps(checks))
    results = [thaw(e) for e in s.session.events if e['type'] in ('command.accepted', 'command.rejected')]
    assert len(results) == 1 and results[0]['type'] == 'command.accepted'
    for name, value in [('input.json', p), ('commands.json', commands), ('replay.json', s.export_replay()), ('snapshot.json', s.snapshot())]:
        write_canonical(OUT / name, value)
    journal = export_events(OUT / 'events.jsonl', s)
    after = {str(p): sha(p) for p in guards}; assert before == after and implementation_digest() == CORE
    report = {'schema': 'ark-sim/chapter03-stage-short-review/v1', 'passed': True,
              'core_start': CORE, 'core_end': implementation_digest(), 'source_start': before, 'source_end': after,
              'declared_births': dict(counts), 'native_controls': dict(controls), 'defup_cells': field_cells,
              'commands_observed': results, 'end_tick': 220, 'observations': original, 'journal': journal,
              'durable_checkpoint_equal': True, 'checkpoint_sha256': cp_sha, 'replay_equal': True,
              'whole_stage_executed': False, 'actual_client_verified': False}
    write_canonical(OUT / 'final_review.json', report)
    print(json.dumps({'passed': True, 'births': 63, 'variants': 8, 'end_tick': 220, 'events': original['event_count']}))


if __name__ == '__main__':
    main()
