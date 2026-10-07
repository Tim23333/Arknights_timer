"""Root-owned native parent death/birth oracle on indexed-event successor."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import traceback

ROOT = Path(__file__).resolve().parents[2]
CORE = '12e1e1adf291a505443980bca51046c725382d82fd458e4adbc4482bcf1b9183'


def main():
    parser = argparse.ArgumentParser();parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True);args = parser.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    runtime = args.runtime_root.resolve();sys.path.insert(0, str(runtime));sys.path.insert(1, str(ROOT))
    import ark_sim
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.contracts import thaw, digest
    from ark_sim.tools.replay import replay
    from tools.campaign_ordered_checkpoint import write_ordered, load_bound
    from tools.chapter10_bloodline_v1.build import build, entity_id, providers
    assert implementation_digest() == CORE and Path(ark_sim.__file__).resolve().parent == runtime / 'ark_sim'
    package = build('enemy_1222_dpvt')
    parent = entity_id('enemy_1222_dpvt');child = entity_id('enemy_1220_dzoms')
    package['entities'].append({'id': 'unit/rootlookup/hitter', 'kind': 'entity', 'tags': ['player'],
                                'components': {'attributes': {'base': {'max_hp': 9911, 'atk': 20000, 'def': 41, 'mres': 0}},
                                               'resources': {'hp': {'role': 'health', 'initial': 9911, 'capacity': 9911}},
                                               'selection_state': {'side': 0, 'motion': 1, 'category': 1}, 'spatial': {},
                                               'abilities': ['ability/rootlookup/kill'], 'lifecycle': {'policy': 'policy/ark_lifecycle'}}})
    package['selectors'].append({'id': 'selector/rootlookup/parent', 'kind': 'selector', 'region': {'type': 'all'},
                                 'filters': [{'field': {'path': ['definition_id'], 'equals': parent}}, {'state': 'alive'}], 'limit': 1})
    package['abilities'].append({'id': 'ability/rootlookup/kill', 'kind': 'ability', 'activation': {'mode': 'manual'},
                                 'selector': 'selector/rootlookup/parent', 'timeline': [{'at': 0, 'effect': {'op': 'damage', 'damage_type': 'true', 'scale': 1}}]})
    package['scenarioDraft'] = {'id': 'scene/rootlookup/nativebirth', 'ruleset': 'ruleset/ark_standard',
                                'map': {'rows': 5, 'cols': 9}, 'resources': {'life': {'initial': 99999, 'capacity': 99999}},
                                'objectives': {'type': 'waves', 'life_resource': 'life'},
                                'initialEntities': [{'definition': 'unit/rootlookup/hitter', 'instanceAlias': 'hitter', 'position': {'row': 4, 'col': 8}}],
                                'commands': [{'at': 17, 'action': 'skill', 'source': 'hitter', 'ability': 'ability/rootlookup/kill'}],
                                'timeline': {'policy': 'managed_clear', 'negative_timeout_policy': 'wait_for_clear', 'waves': [{'fragments': [{'actions': [
                                    {'kind': 'spawn', 'count': 1, 'managed': True, 'blocks_wave': True,
                                     'spawn': {'definition': parent, 'instanceAlias': 'parent', 'position': {'row': 1, 'col': 2},
                                               'route': {'motionMode': 'WALK', 'startPosition': {'row': 1, 'col': 2}, 'endPosition': {'row': 1, 'col': 8},
                                                         'checkpoints': [{'type': 'WAIT_FOR_SECONDS', 'time': 5, 'position': {'row': 1, 'col': 2}}]}}}]}]}]}}
    guards = [Path(__file__), ROOT / 'tools/chapter10_bloodline_v1/build.py', ROOT / 'tools/campaign_ordered_checkpoint.py']
    guards += [p for p in (runtime / 'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py', '.json')]
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    before = {str(p): sha(p) for p in guards}
    result = {'schema': 'ark-sim/root-native-indexed-birth-peer/v1', 'core': CORE, 'passed': False,
              'source_before': before, 'whole_stage': False, 'client_verified': False}
    try:
        seed = 215;registry = providers();program = Compiler(providers=registry).compile(package)
        a = Engine.create(program, seed=seed, providers=registry);a.session.advance(18)
        assert a.ctx.state()['kills'] == 1 and a.ctx.state()['pending_waves'] == 1 and not a.ctx.state()['finished']
        path = Path(os.environ['ARKSIM_RUN_DIR']) / 'native18.checkpoint.json'
        pin = write_ordered(path, a.checkpoint());b = Engine.restore(program, load_bound(path, pin), providers=registry)
        a.session.advance(52);b.session.advance(52);h = replay(program, a.export_replay(), providers=registry)
        assert a.checkpoint() == b.checkpoint() == h.checkpoint()
        assert list(a.session.events) == list(b.session.events) == list(h.session.events)
        born = [thaw(e) for e in a.session.events if e['type'] == 'descendant.born']
        assert len(born) == 1 and born[0]['time'] == 47 and born[0]['payload']['definition'] == child
        actor = a.ctx.entity(born[0]['payload']['child'])
        assert actor['components']['spatial']['movement']['wait_until'] == 150
        assert actor['components']['spatial']['route']['endPosition'] == {'row': 1, 'col': 8}
        assert a.ctx.state()['timeline']['members'][str(actor['id'])]['wave'] == 0
        spec = a.ctx.definition('parent')['components']['lifecycle']['death_spawns']['actions'][0]
        stream = spec['placement']['stream']
        rng_seed = int.from_bytes(hashlib.sha256(json.dumps([seed, stream], separators=(',', ':'), ensure_ascii=False).encode()).digest(), 'big')
        rng = random.Random(rng_seed);expected = [rng.random(), rng.random()]
        samples = [e['value'] for e in thaw(a.session.random.snapshot())['samples'] if e['stream'] == stream]
        assert samples == expected
        bounds = spec['placement']['random_range'];position = born[0]['payload']['position']
        assert position['row'] == 1 + (2 * expected[0] - 1) * bounds['row']
        assert position['col'] == 2 + (2 * expected[1] - 1) * bounds['col']
        result.update(passed=True, death_tick=17, birth_tick=47, inherited_wait=150,
                      actual_position=position, independent_RNG=expected, managed_wave=0,
                      checkpoint_sha256=pin, complete_CP_head_equal=True, full_checkpoint_digest=digest(a.checkpoint()))
    except Exception:result['error'] = traceback.format_exc()
    result['source_after'] = {str(p): sha(p) for p in guards}
    result['identity_stable'] = before == result['source_after'] and implementation_digest() == CORE
    result['actual_exit'] = 0 if result['passed'] and result['identity_stable'] else 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'passed': result['passed'], 'actual_exit': result['actual_exit'], 'error': result.get('error')}))
    return result['actual_exit']


if __name__ == '__main__':raise SystemExit(main())
