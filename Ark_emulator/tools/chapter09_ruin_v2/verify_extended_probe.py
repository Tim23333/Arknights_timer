"""Actual native melee destroys ally rubble; full disk CP/head retain every field."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[2]
CORE = '2c385c9c4a9e383988a3ff8d8d96827f0e473dde0630a3d6d92aa35c5f0dccb0'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.runtime_root.resolve())); sys.path.insert(1, str(ROOT))
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.contracts import digest, thaw
    from ark_sim.tools.replay import replay
    from tools.chapter09_ruin_v2.build import providers
    from tools.chapter09_ruin_v2.build import BODY, build
    from tools.campaign_ordered_checkpoint import write_ordered, load_bound
    assert implementation_digest() == CORE
    log = Path(os.environ['ARKSIM_RUN_DIR'])
    report = {'core': CORE, 'passed': False, 'cases': []}
    paths = [Path(__file__), ROOT / 'tools/chapter09_ruin_v2/build.py',
             ROOT / 'packages/campaign/chapter09_consumers/ruin/module.v2.json']
    paths += [p for p in (args.runtime_root.resolve() / 'ark_sim').rglob('*')
              if p.is_file() and p.suffix in ('.py', '.json') and 'validation' not in p.parts]
    guard = lambda: {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    report['guards_start'] = guard()

    def fixture(old=False):
        native = ROOT / 'packages/campaign/chapter09_consumers/ordinary/enemy_1165_duhond.module.v1.json'
        p = json.loads(native.read_bytes())
        module = build()
        if old:
            previous = json.loads((ROOT / 'packages/campaign/chapter09_stage_models/level_main_09-16.native_draft.v2.life99999.json').read_bytes())
            module = {'definitions': [deepcopy(next(d for d in previous['definitions'] if d['id'] == BODY))]}
        p.setdefault('definitions', []).extend(module['definitions'])
        uid = p['entities'][0]['id']
        route = {'startPosition': {'row': 1, 'col': 2}, 'endPosition': {'row': 1, 'col': 4},
                 'motionMode': 0, 'checkpoints': []}
        p['scenarioDraft'] = {'id': 'scene/ch9/ruin/actual/' + str(old), 'ruleset': 'ruleset/ark_standard',
            'map': {'rows': 3, 'cols': 5}, 'objectives': {},
            'initialEntities': [{'definition': BODY, 'instanceAlias': 'ruin', 'position': {'row': 1, 'col': 2}},
                                {'definition': uid, 'instanceAlias': 'enemy', 'position': {'row': 1, 'col': 2}, 'route': route}]}
        return p

    try:
        old = Engine.create(Compiler(providers=providers()).compile(fixture(True)), providers=providers())
        old.advance(100)
        assert old.ctx.resources.current('ruin', 'hp') == 100 and old.ctx.spatial.blocked_by('enemy') is not None
        assert not any(e['type'] == 'ability.started' for e in old.session.events)
        report['cases'].append({'case': 'true_previous_content_counter', 'end_tick': 100,
            'ruin_HP': 100, 'enemy_still_blocked': True, 'actual_ability_starts': 0})
        p = fixture(); program = Compiler(providers=providers()).compile(p)
        a = Engine.create(program, providers=providers()); a.advance(10)
        checkpoint = log / 'before_native_hit.checkpoint.json'
        pin = write_ordered(checkpoint, a.checkpoint())
        b = Engine.restore(program, load_bound(checkpoint, pin), providers=providers())
        a.advance(110); b.advance(110)
        head = replay(program, a.export_replay(), providers=providers())
        assert a.checkpoint() == b.checkpoint() == head.checkpoint()
        assert list(a.session.events) == list(b.session.events) == list(head.session.events)
        assert not a.ctx.alive('ruin') and a.ctx.spatial.blocked_by('enemy') is None
        assert a.ctx.state()['kills'] == 0
        deaths = [thaw(e) for e in a.session.events if e['type'] == 'entity.died']
        hits = [thaw(e) for e in a.session.events if e['type'] == 'damage.accepted']
        report['actual_hit_probe'] = hits
        report['event_types'] = sorted({x['type'] for x in a.session.events})
        assert len(hits) == 1 and hits[0]['time'] == 18 and hits[0]['payload']['amount'] == 300
        report['cases'].append({'case': 'actual_duhond_combat_and_route_release', 'end_tick': 120,
            'CPP_head_full_equal': True, 'ruin_dead': True, 'native_enemy_kills': 0,
            'enemy_blocker': None, 'native_damage_events': hits, 'death_events': deaths,
            'final_checkpoint_digest': digest(a.checkpoint()), 'checkpoint_sha': pin})
        # Immune environmental NoSource packet, ordinary packet still applies.
        env = fixture(); env['scenarioDraft']['initialEntities'] = env['scenarioDraft']['initialEntities'][:1]
        env['scenarioDraft']['scheduledEffects'] = [{'at': 5, 'effect': {
            'op': 'no_source_damage', 'target': 2, 'damage_type': 'true', 'fixed_amount': 19,
            'attack_type': 'NONE', 'damage_without_modify': False, 'ignore_for_sp': True,
            'node_is_env_damage': True, 'env_blackboard_injected': False, 'environmental': True,
            'origin': {'kind': 'native_environment_test'}, 'rules': {'damage.pipeline': 'rule/ruin/test/packet'}}},
            {'at': 6, 'effect': {'op': 'no_source_damage', 'target': 2, 'damage_type': 'true', 'fixed_amount': 19,
            'attack_type': 'NONE', 'damage_without_modify': False, 'ignore_for_sp': True,
            'node_is_env_damage': False, 'env_blackboard_injected': False, 'environmental': False,
            'origin': {'kind': 'ordinary_source_none_test'}, 'rules': {'damage.pipeline': 'rule/ruin/test/packet'}}}]
        env['rules'].append({'id': 'rule/ruin/test/packet', 'kind': 'rule', 'contract': 'damage.pipeline',
            'implementation': {'type': 'graph', 'nodes': [{'id': 'packet',
            'expression': "{'accepted': True, 'amount': inputs.effect.fixed_amount, 'allocations': [], 'events': []}"}], 'output': 'nodes.packet'}})
        pr = Compiler(providers=providers()).compile(env); e = Engine.create(pr, providers=providers()); e.advance(4)
        assert e.session.world.resolve('ruin') == 2
        q = log/'env.checkpoint.json'; epin=write_ordered(q,e.checkpoint()); er=Engine.restore(pr,load_bound(q,epin),providers=providers())
        e.advance(4);er.advance(4);eh=replay(pr,e.export_replay(),providers=providers());assert e.checkpoint()==er.checkpoint()==eh.checkpoint()
        assert e.ctx.resources.current('ruin','hp')==81
        packets=[thaw(x) for x in e.session.events if x['type']=='damage.accepted']
        assert [(x['time'],x['payload']['amount']) for x in packets]==[(5,0),(6,19)]
        from ark_sim.domains.selection import DEFAULT_STATE
        state=e.ctx.spatial.selection_state('ruin',DEFAULT_STATE)
        assert state['abnormal_immunes']==[0,12,16] and state['abnormal_combo_immunes']==[0]
        report['cases'].append({'case':'native_environment_mask_and_immunity','actual_HP':81,'packets':packets,'full_CPP_head_equal':True,'projected_state':state})
        stage=ROOT/'packages/campaign/chapter09_stage_models/level_main_09-16.native_draft.v4.life99999.json'
        actual_program=Compiler(providers=providers()).compile(stage)
        report['stage_actual_compiled']={'sha':hashlib.sha256(stage.read_bytes()).hexdigest(),'definitions':len(actual_program.definitions),'program':actual_program.fingerprint}
        report['guards_end'] = guard(); assert report['guards_start'] == report['guards_end']
        report.update(passed=True, actual_exit=0, whole_stage=False, client_verified=False)
    except Exception as error:
        report.update(actual_exit=1, error=str(error), traceback=traceback.format_exc())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists(): raise FileExistsError(args.output)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'passed': report['passed'], 'actual_exit': report['actual_exit'], 'error': report.get('error')}))
    return report['actual_exit']


if __name__ == '__main__':
    raise SystemExit(main())
