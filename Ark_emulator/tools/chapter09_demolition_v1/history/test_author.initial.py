"""Actual public card commands, source hit-time members, and disk/full-head gates."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--expected-core', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    runtime = args.runtime_root.resolve(); sys.path.insert(0, str(runtime)); sys.path.insert(1, str(ROOT))
    import ark_sim
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.tools.replay import replay
    from ark_sim.contracts import digest
    from tools.chapter09_demolition_v1.build import build, providers, BODY, STOCK, PREFIX
    assert Path(ark_sim.__file__).resolve().parent == runtime / 'ark_sim'
    assert implementation_digest() == args.expected_core
    log = Path(os.environ['ARKSIM_RUN_DIR'])
    sources = [Path(__file__), ROOT / 'tools/chapter09_demolition_v1/build.py',
               ROOT / 'packages/campaign/chapter09_source_prepare/predefines.native.v3.json',
               ROOT / 'tools/build_weedy_skill_recipe.py', ROOT / 'ark_emulator/consts.py']
    sources += [p for p in (runtime / 'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py', '.json')]
    guard = lambda: {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    start = guard(); results = []; artifacts = []

    def actor(name, side=1, motion=1, free=False, flags=(), mass=6):
        return {'id': 'unit/demolition/test/' + name, 'kind': 'entity', 'tags': [name], 'components': {
            'attributes': {'base': {'max_hp': 17003, 'atk': 0, 'def': 9999, 'mres': 99, 'mass_level': mass}},
            'resources': {'hp': {'initial': 17003, 'capacity': 17003, 'role': 'health'}},
            'spatial': {}, 'selection_state': {'side': side, 'motion': motion, 'category': 1,
                'unit_type': 2 if side == 1 else 1, 'target_free': free, 'abnormal_flags': list(flags)},
            'lifecycle': {'policy': 'policy/ark_lifecycle'}}}

    def fixture(direction='right', *, pillar=False, commands=None, mass=6):
        module = None; abilities = None
        if pillar:
            module = json.loads((ROOT / 'packages/campaign/chapter09_consumers/pillar_lifecycle_v1/module.v1.json').read_bytes())
            abilities = {d: 'ability/ch9/pillar/collapse_' + d for d in ('right', 'left', 'up', 'down')}
        p = build(pillar_abilities=abilities)
        dr, dc = {'right': (0, 1), 'left': (0, -1), 'up': (-1, 0), 'down': (1, 0)}[direction]
        p['entities'].append(actor('enemy', mass=mass))
        entities = [{'definition': 'unit/demolition/test/enemy', 'instanceAlias': 'enemy',
                     'position': {'row': 4 + dr, 'col': 4 + dc}}]
        if module:
            for key in ('rules', 'buffs', 'abilities', 'entities'):
                p[key] += deepcopy(module.get(key, []))
            entities.append({'definition': 'unit/ch9/pillar/body', 'instanceAlias': 'pillar',
                             'position': {'row': 4 + dr, 'col': 4 + dc}})
        p['scenarioDraft'] = {'id': 'scene/demolition/' + direction + str(pillar), 'ruleset': 'ruleset/ark_standard',
            'cards': [BODY], 'map': {'rows': 9, 'cols': 9}, 'resources': {
                'dp': {'initial': 50, 'capacity': 99}, 'life': {'initial': 99999, 'capacity': 99999},
                STOCK: {'initial': 2, 'capacity': 2}}, 'parameters': {'deploy_capacity': 1},
            'initialEntities': entities, 'commands': commands or [
                {'at': 0, 'action': 'deploy', 'definition': BODY, 'alias': 'device',
                 'position': {'row': 4, 'col': 4}, 'facing': direction}]}
        return p

    def registry(pillar=False):
        if pillar:
            from tools.chapter09_pillar_lifecycle_v1.build import providers as extra
            return {**providers(), **extra()}
        return providers()

    def create(p, pillar=False):
        reg = registry(pillar); return Engine.create(Compiler(providers=reg).compile(p), providers=reg, seed=91835)

    def proof(p, label, *, split=17, end=90, pillar=False):
        s = create(p, pillar); s.advance(split)
        path = log / (label + '.checkpoint.json'); path.write_text(json.dumps(s.checkpoint()), encoding='utf8')
        r = Engine.restore(s.program, json.loads(path.read_bytes()), providers=registry(pillar))
        s.advance(end - split); r.advance(end - split)
        h = replay(s.program, s.export_replay(), providers=registry(pillar))
        assert s.checkpoint() == r.checkpoint() == h.checkpoint()
        artifacts.append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'CPP_head_full_equal': True, 'end_digest': digest(s.checkpoint())})
        return s

    def directions():
        for direction in ('right', 'left', 'up', 'down'):
            p = fixture(direction); s = create(p); s.advance(35)
            assert s.ctx.resources.current('enemy', 'hp') == 17003
            assert s.ctx.alive('device')
            s.advance(1)
            assert s.ctx.resources.current('enemy', 'hp') == 15003 and not s.ctx.alive('device')
            hits = [e for e in s.session.events if e['type'] == 'damage.accepted']
            assert len(hits) == 1 and hits[0]['time'] == 35
            assert s.ctx.resources.current('system/battle', STOCK) == 1
            assert s.ctx.resources.current('system/battle', 'dp') == 45
            assert s.ctx.state()['deployments'][BODY]['ready_at'] == 150
            assert s.ctx.state()['deployments'][BODY]['count'] == 1
            proof(p, direction)

    def masks_live_hit():
        p = fixture(); p['entities'] += [actor('fly', motion=2), actor('ally', side=0),
                                        actor('free', free=True), actor('invisible', flags=(9,))]
        p['scenarioDraft']['initialEntities'] += [
            {'definition': 'unit/demolition/test/' + name, 'instanceAlias': name, 'position': {'row': 4, 'col': 5}}
            for name in ('fly', 'ally', 'free', 'invisible')]
        s = proof(p, 'masks')
        assert [s.ctx.resources.current(name, 'hp') for name in ('enemy', 'fly', 'ally', 'free', 'invisible')] == [15003, 17003, 17003, 15003, 17003]
        p = fixture(); p['abilities'].append({'id': 'ability/demolition/test/leave', 'kind': 'ability',
            'activation': {'mode': 'manual'}, 'timeline': [{'at': 0, 'effect': {'op': 'move', 'target': 'source',
                'position': {'row': 6, 'col': 6}}}]})
        p['entities'][1]['components']['abilities'] = ['ability/demolition/test/leave']
        p['scenarioDraft']['commands'].append({'at': 30, 'action': 'skill', 'source': 'enemy', 'ability': 'ability/demolition/test/leave'})
        s = proof(p, 'hit_time_leave'); assert s.ctx.resources.current('enemy', 'hp') == 17003

    def push_and_bonus():
        p = fixture(mass=1); s = proof(p, 'push', split=36, end=90)
        expected = 5 + 1.56247
        assert abs(s.ctx.get('enemy', ('spatial', 'position'))['col'] - expected) < 1e-9
        p = fixture(mass=2); p['entities'][0]['components']['attributes']['base']['base_force_level'] = 1
        s = proof(p, 'force_bonus', split=36, end=90)
        assert abs(s.ctx.get('enemy', ('spatial', 'position'))['col'] - expected) < 1e-9

    def stock_cooldown():
        p = fixture(commands=[
            {'at': at, 'action': 'deploy', 'definition': BODY, 'alias': 'device' + str(at),
             'position': {'row': 4, 'col': 4}, 'facing': 'right'} for at in (0, 149, 150, 300)])
        s = proof(p, 'stock_cooldown', split=100, end=340)
        accepted = [e for e in s.session.events if e['type'] == 'command.accepted']
        rejected = [e for e in s.session.events if e['type'] == 'command.rejected']
        assert [e['time'] for e in accepted] == [0, 150] and [e['time'] for e in rejected] == [149, 300]
        assert s.ctx.resources.current('system/battle', STOCK) == 0
        assert s.ctx.resources.current('system/battle', 'dp') == 40

    def source_withdraw():
        p = fixture(); p['scenarioDraft']['commands'].append({'at': 20, 'action': 'withdraw', 'source': 'device'})
        s = proof(p, 'early_withdraw')
        assert s.ctx.resources.current('enemy', 'hp') == 17003
        assert not any(e['type'] == 'damage.accepted' for e in s.session.events)

    def pillar_direct():
        for direction in ('right', 'left', 'up', 'down'):
            p = fixture(direction, pillar=True); s = proof(p, 'pillar_' + direction, end=90, pillar=True)
            assert s.ctx.resources.current('pillar', 'hp') == 5000 and not s.ctx.alive('pillar')
            starts = [e for e in s.session.events if e['type'] == 'ability.started' and e['payload']['ability'] == 'ability/ch9/pillar/collapse_' + direction]
            assert len(starts) == 1 and starts[0]['time'] == 35
            assert len([e for e in s.session.world.entities() if e['definition_id'] == 'unit/ch9/pillar/ruin']) == 2

    def custom_damage():
        p = fixture(); p['rules'].append({'id': 'rule/demolition/test/flat', 'kind': 'rule', 'contract': 'damage.pipeline',
            'implementation': {'type': 'expression', 'expression': "{'accepted': True, 'amount': 271, 'allocations': [], 'events': []}"}})
        blast = next(a for a in p['abilities'] if a['id'].endswith('/blast'))
        blast['timeline'][0]['effects'][0]['effects'][0]['rules'] = {'damage.pipeline': 'rule/demolition/test/flat'}
        s = proof(p, 'custom_damage'); assert s.ctx.resources.current('enemy', 'hp') == 17003 - 271

    for name, fn in [('four_direction_native_hp_cost_stock_predelay', directions), ('native_masks_and_hit_time_selection', masks_live_hit),
                     ('source_force_one_and_cell_bonus_push', push_and_bonus), ('stock_two_deploy_cooldown_and_zero_slots', stock_cooldown),
                     ('early_withdraw_cancels_unlaunched_payload', source_withdraw), ('supplied_pillar_dependency_direct_collapse', pillar_direct),
                     ('local_damage_formula_is_replaceable', custom_damage)]:
        try: fn(); results.append({'case': name, 'passed': True})
        except Exception as error: results.append({'case': name, 'passed': False, 'error': str(error), 'traceback': traceback.format_exc()})
    end = guard(); output = {'schema': 'ark-sim/ch9-demolition-author/v1', 'core': implementation_digest(),
        'actual_exit': 0 if all(x['passed'] for x in results) and start == end else 1,
        'results': results, 'artifacts': artifacts, 'source_before': start, 'source_after': end,
        'source_guard_equal': start == end, 'comparison_exclusions': [], 'whole_stage': False, 'client_verified': False}
    args.output.parent.mkdir(parents=True, exist_ok=True); assert not args.output.exists()
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'actual_exit': output['actual_exit'], 'cases': len(results), 'failed': [x['case'] for x in results if not x['passed']]}))
    return output['actual_exit']


if __name__ == '__main__':
    raise SystemExit(main())
