"""Independent exact-zero lifecycle checks; no author fixture imports."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
OBSERVATIONS = []


def plan(inputs, params, context):
    request = inputs['request']
    assert context['owner']['id'] == inputs['target']['id']
    assert context['source']['id'] == inputs['source']['id']
    assert context['time'] == inputs['clock']['time']
    assert request['source_snapshot']['definition_id'] == 'unit/peer/striker'
    if inputs['state']['stage'] == 'intact' and request['operation'] == 'damage':
        assert request['health_before'] == 37 and request['health_after'] == 0
        assert request['actual_health_loss'] == 37 and request['requested_change'] == -65
        if params.get('nested_clock'):
            ticks = context.calculate('time.quantize', {
                'seconds': 3, 'quantum': inputs['clock']['quantum'],
                'rounding': {'mode': 'ceil'}}).value
            assert ticks == 180
        OBSERVATIONS.append({'time': context['time'], 'request_loss': 37})
        return {'action': 'defer', 'stage': 'broken', 'actions': ['enter', 'ready']}
    return {'action': 'none', 'stage': inputs['state']['stage'], 'actions': []}


def contents(fault=False, nested_clock=False):
    enter = [{'op': 'apply_buff', 'buff': 'buff/peer/damaged'}]
    if fault:
        enter.append({'op': 'random', 'stream': 'peer_fault', 'probability': 1,
                      'on_success': [{'op': 'modify_resource', 'resource': 'absent', 'amount': 1}]})
    data = {'schemaVersion': 2,
        'rules': [{'id': 'rule/peer/depletion', 'kind': 'rule', 'contract': 'resource.depletion',
                   'implementation': {'type': 'provider', 'provider': 'peer/depletion'}}],
        'buffs': [{'id': 'buff/peer/damaged', 'kind': 'buff',
                   'selection_flags': {'abnormal_flags': [5, 2, 15]}},
                  {'id': 'buff/peer/ready', 'kind': 'buff'}],
        'entities': [
            {'id': 'unit/peer/striker', 'kind': 'entity', 'tags': ['enemy'], 'components': {
                'attributes': {'base': {'max_hp': 911, 'atk': 65, 'def': 0, 'mres': 0}},
                'resources': {'health': {'role': 'health', 'initial': 911, 'capacity': 911}},
                'spatial': {}, 'abilities': ['ability/peer/hit']}},
            {'id': 'unit/peer/pillar', 'kind': 'entity', 'tags': ['peer_pillar'], 'components': {
                'attributes': {'base': {'max_hp': 37, 'atk': 12345, 'def': 0, 'mres': 0}},
                'resources': {'health': {'role': 'health', 'initial': 37, 'capacity': 37}},
                'spatial': {}, 'lifecycle': {'policy': 'policy/ark_lifecycle'},
                'depletion': {'resource': 'health', 'rule': 'rule/peer/depletion',
                    'initial_stage': 'intact', 'parameters': {'nested_clock': nested_clock},
                    'stages': {'intact': {'active': True, 'selectable': True},
                               'broken': {'active': False, 'selectable': False},
                               'ready': {'active': True, 'selectable': True}},
                    'actions': {'enter': {'at_seconds': 0, 'effects': enter},
                        'ready': {'at_seconds': 3, 'next_stage': 'ready', 'effects': [
                            {'op': 'remove_buff', 'buff': 'buff/peer/damaged'},
                            {'op': 'apply_buff', 'buff': 'buff/peer/ready'}]}}}}}],
        'selectors': [{'id': 'selector/peer/pillar', 'kind': 'selector',
                       'region': {'type': 'all'}, 'filters': [{'tag': 'peer_pillar'}, {'state': 'alive'}],
                       'limit': 1}],
        'abilities': [{'id': 'ability/peer/hit', 'kind': 'ability', 'activation': {'mode': 'manual'},
                       'selector': 'selector/peer/pillar', 'timeline': [
                           {'at': 0, 'effect': {'op': 'damage', 'damage_type': 'true', 'scale': 1}}]}],
        'scenarioDraft': {'id': 'scene/peer/depletion', 'ruleset': 'ruleset/ark_standard',
            'map': {'rows': 3, 'cols': 5}, 'initialEntities': [
                {'definition': 'unit/peer/striker', 'instanceAlias': 'striker', 'position': {'row': 1, 'col': 0}},
                {'definition': 'unit/peer/pillar', 'instanceAlias': 'pillar', 'position': {'row': 1, 'col': 2}}],
            'commands': [{'at': 7, 'action': 'skill', 'source': 'striker', 'ability': 'ability/peer/hit'}]}}
    if nested_clock:
        data['rules'].append({'id': 'rule/peer/doubleclock', 'kind': 'rule', 'contract': 'time.quantize',
            'implementation': {'type': 'expression', 'expression': 'ceil(inputs.seconds / inputs.quantum) * 2'}})
        data['scenarioDraft']['rules'] = {'time.quantize': 'rule/peer/doubleclock'}
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--expected-core', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    runtime = args.runtime_root.resolve()
    sys.path.insert(0, str(runtime))
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    from ark_sim.tools.replay import replay
    from ark_sim.contracts import digest
    assert implementation_digest() == args.expected_core
    providers = {**BUILTIN_PROVIDERS, 'peer/depletion': {'callable': plan, 'version': 'independent-1'}}
    files = [p for p in (runtime / 'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py', '.json')]
    files.append(Path(__file__))
    guard = lambda: {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    before = guard()
    results, artifacts = [], []
    logdir = Path(os.environ['ARKSIM_RUN_DIR'])

    def create(**kwargs):
        return Engine.create(Compiler(providers=providers).compile(contents(**kwargs)), providers=providers, seed=8723)

    def cp(sim):
        return json.loads(json.dumps(sim.checkpoint()))

    def broken(**kwargs):
        sim = create(**kwargs); sim.session.advance(8)
        state = sim.ctx.depletion.state('pillar')
        assert state['stage'] == 'broken' and state['lease']['started'] == 7
        assert sim.ctx.resources.current('pillar', 'health') == 0 and sim.ctx.alive('pillar')
        assert not sim.ctx.active('pillar') and not sim.ctx.effect_target_available('pillar')
        assert sim.session.export_checkpoint()['world']['attribute_cache'] == {}
        return sim

    def disk_replay(custom):
        sim = broken(nested_clock=custom)
        due = 187 if custom else 97
        assert sim.ctx.depletion.state('pillar')['lease']['actions']['1']['due'] == due
        checkpoint = cp(sim)
        path = logdir / ('custom.checkpoint.json' if custom else 'ordinary.checkpoint.json')
        path.write_text(json.dumps(checkpoint), encoding='utf8')
        restored = Engine.restore(sim.program, json.loads(path.read_bytes()), providers=providers)
        sim.session.advance(due - sim.session.time)
        restored.session.advance(due - restored.session.time)
        assert sim.ctx.depletion.state('pillar')['stage'] == 'broken'
        sim.session.advance(1); restored.session.advance(1)
        assert sim.ctx.depletion.state('pillar')['stage'] == 'ready'
        assert sim.ctx.resources.current('pillar', 'health') == 0
        assert sim.ctx.active('pillar') and sim.ctx.effect_target_available('pillar')
        assert cp(sim) == cp(restored)
        head = replay(sim.program, sim.export_replay(), providers=providers)
        assert cp(head) == cp(sim)
        artifacts.append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                          'cpp_equal': True, 'head_equal': True, 'end_digest': digest(cp(sim)), 'due': due})

    def tamper():
        sim = broken(); checkpoint = cp(sim)
        entity = next(e for e in checkpoint['kernel']['world']['entities'] if e['definition_id'] == 'unit/peer/pillar')
        row = entity['components']['runtime']['depletion']['lease']['actions']['1']
        row['due'] = 9
        next(t for t in checkpoint['kernel']['scheduler']['tasks'] if t['id'] == row['task'])['at'] = 9
        try: Engine.restore(sim.program, checkpoint, providers=providers)
        except ValueError: return
        raise AssertionError('Coherent action/queue due tamper accepted')

    def forged():
        sim = broken(); before = cp(sim); owner = sim.session.world.resolve('pillar')
        sim.ctx.depletion._dispatch(owner, 1, '1')
        sim.ctx.depletion.action(sim.session, {'target': owner, 'generation': 1, 'slot': 1})
        assert cp(sim) == before
        try:
            sim.ctx.effects.execute(owner, [owner], {'op': 'emit', 'event': 'peer.forged'},
                                    cast={'depletion_action': {'owner': owner, 'generation': 1, 'slot': '1'}})
        except ValueError: pass
        else: raise AssertionError('Forged cast acquired callback permission')
        assert cp(sim) == before

    def late_fault():
        sim = create(fault=True); before = cp(sim)
        try: sim.ctx.effects.execute('striker', ['pillar'], {'op': 'damage', 'damage_type': 'true', 'scale': 1})
        except ValueError: pass
        else: raise AssertionError('Fault did not reach late callback')
        assert cp(sim) == before
        assert not sim.ctx.depletion._attacks and not sim.ctx.depletion._callbacks and not sim.ctx.depletion._deliveries

    def retire():
        sim = broken(); sim.ctx.lifecycle.retire('pillar', 'withdrawn')
        checkpoint = cp(sim); restored = Engine.restore(sim.program, checkpoint, providers=providers)
        sim.session.advance(100); restored.session.advance(100)
        assert cp(sim) == cp(restored) and not sim.ctx.alive('pillar')
        assert not [e for e in sim.session.events if e['type'] == 'depletion.action.executed' and e['payload']['slot'] == '1']

    def raw_resource():
        sim = create(); sim.ctx.resources.adjust('pillar', 'health', value=0, source='striker')
        assert not sim.ctx.alive('pillar') and sim.ctx.depletion.state('pillar')['lease'] is None
        assert not any(e['type'] == 'depletion.started' for e in sim.session.events)

    for name, fn in [('actual_zero_three_seconds_cpp_full_head', lambda: disk_replay(False)),
                     ('nested_context_custom_clock_cpp_full_head', lambda: disk_replay(True)),
                     ('coherent_due_queue_tamper_with_natural_empty_cache', tamper),
                     ('direct_dispatch_and_forged_callback_rejected', forged),
                     ('late_rng_callback_fault_atomic_rollback', late_fault),
                     ('retirement_cancels_due_and_checkpoint_restore', retire),
                     ('raw_resource_zero_does_not_borrow_attack_authority', raw_resource)]:
        try: fn(); results.append({'case': name, 'passed': True})
        except Exception as error:
            results.append({'case': name, 'passed': False, 'error': str(error), 'traceback': traceback.format_exc()})
    after = guard()
    report = {'schema': 'ark-sim/depletion-root-independent/v1', 'core': implementation_digest(),
        'actual_exit': 0 if all(x['passed'] for x in results) and before == after else 1,
        'results': results, 'source_guard_start': before, 'source_guard_end': after,
        'identity_stable': before == after, 'artifacts': artifacts,
        'comparison': 'Complete checkpoints including state, tasks, RNG, events, caches, calculation context/value/cause; no field exclusions',
        'provider_observations': OBSERVATIONS, 'whole_pillar': False, 'whole_enemy': False, 'client_verified': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    assert not args.output.exists()
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'actual_exit': report['actual_exit'], 'cases': len(results),
                      'failed': [r['case'] for r in results if not r['passed']], 'output': str(args.output)}))
    return report['actual_exit']


if __name__ == '__main__':
    raise SystemExit(main())
