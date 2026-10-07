"""Actual fixed-roster elemental reception, break effects and disk CP/head."""
import json
import os
import hashlib
import traceback
from copy import deepcopy
from pathlib import Path
from ark_sim import Compiler, Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from ark_sim.domains.selection import DEFAULT_STATE
from tools.campaign_ordered_checkpoint import write_ordered, load_bound
from tools.campaign_elemental_receivers_v1.build import ROOT, SOURCE, TABLE, P, DARK, FIRE, mount, providers

OUT = ROOT / 'validation/campaign/elemental_receivers_v1'
LOG = Path(os.environ['ARKSIM_RUN_DIR'])


def fixture(target='unit/char_151_myrtle', packets=()):
    original = json.loads((ROOT / 'packages/campaign/roster/fixed12.m26.reference_module.json').read_bytes())
    definitions = deepcopy(original['definitions'])
    by_id = {d['id']: d for d in definitions}
    # Explicit isolation retains all real owned definitions/events/talents.
    for aid in by_id[target]['components'].get('abilities', []):
        by_id[aid]['activation']['condition'] = 'False'
    definitions += [{'id': 'unit/receiver/probe_source', 'kind': 'entity', 'tags': ['enemy'],
        'components': {'attributes': {'base': {'max_hp': 10000, 'atk': 0, 'def': 0, 'mres': 0}},
            'resources': {'hp': {'role': 'health', 'initial': 10000, 'capacity': 10000}},
            'selection_state': {'side': 1, 'category': 1, 'motion': 1}, 'spatial': {}, 'abilities': [],
            'lifecycle': {'policy': 'policy/ark_lifecycle'}}},
        {'id': 'selector/receiver/actual_operator', 'kind': 'selector', 'region': {'type': 'all'},
         'filters': [{'field': {'path': ['definition_id'], 'equals': target}}, {'state': 'alive'}], 'limit': 1}]
    owned_probe = 'ability/receiver/owned_skill_probe'
    by_id[target]['components']['abilities'].append(owned_probe)
    definitions.append({'id':owned_probe,'kind':'ability','activation':{'mode':'manual','costs':[{'resource':'sp','amount':1}]},'timeline':[{'at':0,'effect':{'op':'emit','target':'source','event':'receiver.skill.probe','payload':{}}}]})
    commands = []
    packet_source = next(d for d in definitions if d['id'] == 'unit/receiver/probe_source')
    for i, (tick, key, amount) in enumerate(packets):
        aid = 'ability/receiver/probe/' + str(i)
        packet_source['components']['abilities'].append(aid)
        definitions.append({'id': aid, 'kind': 'ability', 'activation': {'mode': 'manual'},
            'selector': 'selector/receiver/actual_operator', 'timeline': [{'at': 0, 'effect': {
                'op': 'elemental_damage', 'element': key, 'amount': amount}}]})
        commands.append({'at': tick, 'action': 'skill', 'source': 'source', 'ability': aid})
    package = {'schemaVersion': 2, 'definitions': definitions, 'scenarioDraft': {
        'id': 'scene/receiver/' + target, 'ruleset': 'ruleset/ark_standard', 'map': {'rows': 4, 'cols': 7},
        'resources': {'life': {'initial': 99999, 'capacity': 99999}},
        'initialEntities': [{'definition': target, 'instanceAlias': 'operator', 'position': {'row': 1, 'col': 1}},
                            {'definition': 'unit/receiver/probe_source', 'instanceAlias': 'source', 'position': {'row': 2, 'col': 6}}],
        'commands': commands}}
    mount(package, entities=[target])
    return package


def create(package):
    registry = providers()
    return Engine.create(Compiler(providers=registry).compile(package), providers=registry, seed=71007)


def cpp(package, end, pins, label):
    forward = create(package)
    forward.advance(end)
    resumed = create(package)
    records = []
    for tick in pins:
        resumed.advance(tick - resumed.session.time)
        path = LOG / (label + str(tick) + '.checkpoint.json')
        pin = write_ordered(path, resumed.checkpoint())
        resumed = Engine.restore(resumed.program, load_bound(path, pin), providers=providers())
        records.append({'tick': tick, 'sha256': pin})
    resumed.advance(end - resumed.session.time)
    head = replay(forward.program, forward.export_replay(), providers=providers())
    assert forward.checkpoint() == resumed.checkpoint() == head.checkpoint()
    assert list(forward.session.events) == list(resumed.session.events) == list(head.session.events)
    return forward, records


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    paths = [SOURCE, TABLE, Path(__file__), ROOT / 'tools/campaign_elemental_receivers_v1/build.py',
             ROOT / 'packages/campaign/roster/fixed12.m26.reference_module.json']
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    before = {str(path): sha(path) for path in paths}
    report = {'schema': 'ark-sim/elemental-receivers-author/v1', 'source_before': before,
              'whole_stage': False, 'client_verified': False, 'results': [], 'facts': {}, 'comparison_exclusions': []}
    def basic():
        package = fixture(packets=[(5, 'DARK', 113)])
        sim, cps = cpp(package, 70, [4, 6], 'basic')
        state = sim.ctx.get('operator', ('runtime', 'elemental'))
        report['facts']['basic'] = {'state': state, 'HP': sim.ctx.resources.current('operator', 'hp'), 'cps': cps}
        assert state['remaining'] == {'FIRE': 1000, 'DARK': 887} and state['break'] is None
        assert sim.ctx.resources.current('operator', 'hp') == 1565
    def fire():
        package = fixture('unit/char_107_liskam', [(5, 'FIRE', 1000)])
        probe = create(package)
        original_hp = probe.ctx.resources.current('operator', 'hp')
        original_res = probe.ctx.attributes.value('operator', 'mres')
        probe.advance(6)
        reduced_res = probe.ctx.attributes.value('operator', 'mres')
        expected = 1200 * (1 - min(100, max(0, reduced_res)) / 100)
        actual_hp = probe.ctx.resources.current('operator', 'hp')
        losses = [thaw(e) for e in probe.session.events if e['type'] == 'damage.accepted' and e['payload'].get('source_policy') == 'none']
        report['facts']['fire'] = {'original_HP': original_hp, 'original_res': original_res,
                                 'reduced_res': reduced_res, 'HP': actual_hp, 'expected_loss': expected, 'events': losses}
        assert reduced_res == original_res - 20 and actual_hp == original_hp - expected
        sim, cps = cpp(package, 307, [4, 6, 304, 305], 'fire')
        report['facts']['fire']['cps'] = cps
        assert sim.ctx.get('operator', ('runtime', 'elemental'))['remaining'] == {'FIRE': 1000, 'DARK': 1000}
        assert sim.ctx.attributes.value('operator', 'mres') == original_res
    def dark():
        package = fixture('unit/char_107_liskam', [(5, 'DARK', 1000), (8, 'FIRE', 1000)])
        package['scenarioDraft']['scheduledEffects']=[{'at':3,'effect':{'op':'modify_resource','target':2,'resource':'sp','value':20}},{'at':15,'effect':{'op':'modify_resource','target':2,'resource':'sp','delta':5,'parameters':{'respect_recovery_freeze':True}}}]
        package['scenarioDraft']['commands'] += [{'at':11,'action':'skill','source':'operator','ability':'ability/receiver/owned_skill_probe'},{'at':456,'action':'skill','source':'operator','ability':'ability/receiver/owned_skill_probe'}]
        probe = create(package)
        hp = probe.ctx.resources.current('operator', 'hp')
        res = probe.ctx.attributes.value('operator', 'mres')
        sp = probe.ctx.resources.current('operator', 'sp')
        initial_paid_SP = min(20, probe.ctx.resources.capacity('operator','sp'))
        probe.advance(40)
        losses = [thaw(e) for e in probe.session.events if e['type'] == 'damage.accepted' and e['payload'].get('source_policy') == 'none']
        report['facts']['dark_probe'] = {'HP': probe.ctx.resources.current('operator', 'hp'),
            'initial_HP': hp, 'res': res, 'initial_SP': sp, 'configured_SP_at3':initial_paid_SP, 'SP40': probe.ctx.resources.current('operator', 'sp'),
            'flags': probe.ctx.spatial.selection_state('operator', DEFAULT_STATE)['abnormal_flags'],
            'state': probe.ctx.get('operator', ('runtime', 'elemental')), 'events': losses}
        assert probe.ctx.get('operator', ('runtime', 'elemental'))['remaining']['FIRE'] == 1000
        assert len(losses) == 2 and all(e['payload']['source'] is None for e in losses)
        assert report['facts']['dark_probe']['HP'] == hp - 2 * 100 * (1 - res / 100)
        assert probe.ctx.resources.current('operator', 'sp') == initial_paid_SP - 2
        assert any(e['type']=='command.rejected' and e['time']==11 for e in probe.session.events)
        assert any(e['type']=='resource.recovery_suppressed' and e['time']==15 for e in probe.session.events)
        sim, cps = cpp(package, 457, [4, 6, 34, 454, 455], 'dark')
        all_losses = [thaw(e) for e in sim.session.events if e['type'] == 'damage.accepted' and e['payload'].get('source_policy') == 'none']
        report['facts']['dark_end'] = {'HP': sim.ctx.resources.current('operator', 'hp'), 'events': all_losses, 'cps': cps,
            'state': sim.ctx.get('operator', ('runtime', 'elemental'))}
        assert sim.ctx.resources.current('operator','sp') == initial_paid_SP - 15 - 1
        assert any(e['type']=='receiver.skill.probe' and e['time']==456 for e in sim.session.events)
        assert len(all_losses) == 15 and sim.ctx.resources.current('operator', 'hp') == hp - 15 * 100 * (1 - res / 100)
        assert sim.ctx.get('operator', ('runtime', 'elemental'))['break'] is None
        assert sim.ctx.get('operator', ('runtime', 'elemental'))['remaining'] == {'FIRE': 1000, 'DARK': 1000}
    for name, fn in [('actual_fixed_operator113_no_recovery_CPP', basic), ('fire_reduce_RES_before_source_free1200_CPP', fire),
                     ('dark15sec_SP_block_drain_and_DOT_lock_reset_CPP', dark)]:
        try:
            fn()
            report['results'].append({'case': name, 'passed': True})
        except Exception:
            report['results'].append({'case': name, 'passed': False, 'error': traceback.format_exc()})
        report['source_after'] = {str(path): sha(path) for path in paths}
        report['source_guard_equal'] = before == report['source_after']
        report['actual_exit'] = 0 if all(row['passed'] for row in report['results']) and report['source_guard_equal'] else 1
        (OUT / 'author.actual.v4.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'actual_exit': report['actual_exit'], 'results': report['results']}))
    return report['actual_exit']


if __name__ == '__main__':
    raise SystemExit(main())
