"""Independent L1 Boss operands and packets on the actually selected runtime."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT.parent / 'unpack_work/campaign_m54_qualified_visibility_candidate'
CORE = 'e6e0142c9ef9aa2cdcf35188aba0865efba370346eecf1c50750a45f56974b75'
OUT = ROOT / 'validation/campaign/chapter03_boss_peer'
SOURCE = ROOT / 'packages/campaign/chapter03_sources/native.reference.json'
MODEL = ROOT / 'packages/campaign/chapter03_models/skulsr.level1.reference.json'
sys.path.insert(0, str(RUNTIME)); sys.path.insert(1, str(ROOT))
from ark_sim import Compiler, Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered, load_bound
from tools.campaign_streaming_evidence import observations, export_events, write_canonical


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scenario(p, hp=30000, maximum=30000, target=True, hold=False):
    boss = p['entities'][0]['id']
    first = {'definition': boss, 'instanceAlias': 'boss', 'position': {'row': 2, 'col': 0},
             'components': {'attributes': {'base': {'max_hp': maximum}}, 'resources': {'hp': {'current': hp}}}}
    # Health current is runtime-owned; initial current is driven by a public
    # ability below rather than relying on this override.
    first['components'].pop('resources')
    if hold:
        p['buffs'].append({'id': 'buff/peer_start_hold', 'kind': 'buff', 'duration_seconds': 1/30,
                           'control': {'attack': False}})
        first['components']['buffs'] = {'initial': ['buff/peer_start_hold']}
    initial = [first]
    if target:
        p['entities'].append({'id': 'unit/peer_victim', 'kind': 'entity', 'tags': ['player'], 'components': {
            'spatial': {}, 'attributes': {'base': {'max_hp': 20000, 'def': 200, 'mres': 0}},
            'selection_state': {'side': 0, 'motion': 1, 'category': 1},
            'resources': {'hp': {'initial': 20000, 'capacity': 20000, 'role': 'health'}}}})
        initial.append({'definition': 'unit/peer_victim', 'instanceAlias': 'victim', 'position': {'row': 2, 'col': 1}})
    p['entities'].append({'id': 'unit/peer_control', 'kind': 'entity', 'components': {'spatial': {}, 'abilities': ['ability/peer_hp']}})
    p['selectors'].append({'id': 'selector/peer_boss', 'kind': 'selector', 'region': {'type': 'all'}, 'filters': [{'tag': 'enemy'}], 'limit': 1})
    p['abilities'].append({'id': 'ability/peer_hp', 'kind': 'ability', 'selector': 'selector/peer_boss',
                          'activation': {'mode': 'manual', 'on_start': [{'op': 'modify_resource', 'resource': 'hp', 'value': hp}]}, 'timeline': []})
    initial.append({'definition': 'unit/peer_control', 'instanceAlias': 'controller', 'position': {'row': 0, 'col': 0}})
    p['scenarioDraft'] = {'id': 'scene/peer/level1boss', 'ruleset': 'ruleset/ark_standard', 'objectives': {},
                          'map': {'rows': 5, 'cols': 5}, 'initialEntities': initial}
    return p


def run_case(name, p, commands, end, expected):
    program = Compiler().compile(p); s = Engine.create(program, seed=3852)
    for c in commands:
        s.submit({k: v for k, v in c.items() if k != 'at'}, at=c['at'])
    s.advance(7); directory = OUT / name; directory.mkdir(parents=True, exist_ok=True)
    cp = directory / 'checkpoint.ordered.json'; pin = write_ordered(cp, s.checkpoint())
    r = Engine.restore(program, load_bound(cp, pin)); s.advance(end-7); r.advance(end-7)
    hits = [thaw(e) for e in s.session.events if e['type'] == 'damage.accepted']
    actual = [(e['time'], e['payload']['amount']) for e in hits]
    assert len(actual) == len(expected) and all(t == u and abs(x-y) < 1e-8 for (t,x),(u,y) in zip(actual, expected)), (actual, expected)
    original = observations(s); assert original == observations(r) == observations(replay(program, s.export_replay()))
    for filename, value in [('input.json', p), ('commands.json', commands), ('replay.json', s.export_replay()), ('snapshot.json', s.snapshot())]:
        write_canonical(directory / filename, value)
    journal = export_events(directory / 'events.jsonl', s)
    return {'case': name, 'expected_packets': expected, 'actual_packets': actual, 'observations': original,
            'checkpoint_sha256': pin, 'durable_checkpoint_equal': True, 'replay_equal': True, 'journal': journal}


def main():
    import ark_sim
    assert Path(ark_sim.__file__).resolve().parent == RUNTIME / 'ark_sim' and implementation_digest() == CORE
    assert sha(MODEL) == 'c09cc02578055091f1ae465954ecfa484a6cafe21ab5b5b84f3c2deab8380092'
    assert sha(SOURCE) == 'd6a1d5294e1419d6ee41022efa1ef93a0ad44b6effb80c4bdfcf7fc3e7cd1e35'
    guards = [MODEL, SOURCE, Path(__file__)]; before = {str(p): sha(p) for p in guards}
    source = json.loads(SOURCE.read_bytes()); v = next(v for v in source['variants'].values() if v['native_enemy']['native_id'] == 'enemy_1500_skulsr')
    attrs = v['native_enemy']['resolved']['attributes']; bb = {x['key']: x['value'] for x in v['native_enemy']['resolved']['talentBlackboard']}
    assert v['native_enemy']['native_level'] == 1 and (attrs['maxHp'], attrs['atk'], attrs['def'], attrs['magicResistance']) == (30000,1300,240,30)
    assert bb['atkup.hp_ratio'] == .5 and bb['atkup.atk'] == .5
    scale = .25999999046325684; cases = []
    for name, hp, maximum, low in [('equal_half',15000,30000,False), ('below_half',14999,30000,True), ('scaled_maximum',18000,40000,True)]:
        p = scenario(json.loads(MODEL.read_bytes()), hp, maximum, hold=True)
        commands = [{'at': 0, 'action': 'skill', 'source': 'controller', 'ability': 'ability/peer_hp'}]
        atk = attrs['atk'] * (1 + bb['atkup.atk'] if low else 1)
        cases.append(run_case(name,p,commands,26,[(21,atk*scale-200),(24,atk*scale-100)]))
    after = {str(p): sha(p) for p in guards}; assert before == after and implementation_digest() == CORE
    report = {'schema': 'ark-sim/independent-chapter03-boss-review/v1', 'passed': True, 'cases': cases,
              'core_start': CORE, 'core_end': implementation_digest(), 'source_start': before, 'source_end': after,
              'scope': 'Independent DEF200/source L1 operands; equality/below-half/max40000 boundary; individual packets before and after source DEF debuff; public CP and replay',
              'actual_client_verified': False, 'whole_stage_executed': False}
    write_canonical(OUT / 'final_review.json', report); print(json.dumps({'passed': True, 'cases': len(cases)}))


if __name__ == '__main__':
    main()
