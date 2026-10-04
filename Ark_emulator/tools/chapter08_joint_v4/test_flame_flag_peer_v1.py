"""Independent flag forwarding keeps ordinary modifiers and source damage."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path
import pytest
from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay
from tools.chapter08_flame_device.policies_v1 import providers
from tools.campaign_ordered_checkpoint import write_ordered, load_bound

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / 'packages/campaign/chapter08_consumers/flame/module.v4.joint.json'


def package(explicit_false=True):
    assert hashlib.sha256(MODULE.read_bytes()).hexdigest() == 'fa780e59d9e47067b998a5888d44a56214644808c87b3e83493abc2b81c1762d'
    p = json.loads(MODULE.read_bytes())
    p['rules'].append({'id': 'rule/peer/flame/receiver', 'kind': 'rule', 'contract': 'damage.pipeline',
                      'implementation': {'type': 'provider', 'provider': 'peer.flame.receiver'}})
    p['buffs'].append({'id': 'buff/peer/flame/receiver', 'kind': 'buff',
                       'damage_hooks': [{'phase': 'after', 'rule': 'rule/peer/flame/receiver',
                                        'condition': "inputs.effect.damage_type=='arts'"}]})
    for i, resistance in enumerate((17, 37, 53, 73)):
        p['entities'].append({'id': 'unit/peer/flame/target' + str(i), 'kind': 'entity', 'tags': ['player'],
                              'components': {'attributes': {'base': {'max_hp': 20000, 'atk': 0,
                                                                     'def': 811, 'mres': resistance}},
                                             'resources': {'hp': {'initial': 20000, 'capacity': 20000, 'role': 'health'}},
                                             'spatial': {}, 'selection_state': {'side': 0, 'motion': 1, 'category': 1, 'unit_type': 1},
                                             'buffs': {'initial': ['buff/peer/flame/receiver']},
                                             'lifecycle': {'policy': 'policy/ark_lifecycle'}}})
    p['scenarioDraft'] = {'id': 'scene/peer/flame/flag', 'ruleset': 'ruleset/ark_standard',
                          'map': {'rows': 5, 'cols': 5},
                          'initialEntities': [{'definition': p['entities'][0]['id'], 'instanceAlias': 'device',
                                               'position': {'row': 2, 'col': 2}},
                                              *[{'definition': 'unit/peer/flame/target' + str(i),
                                                 'instanceAlias': 'target' + str(i), 'position': point}
                                                for i, point in enumerate(({'row': 1, 'col': 2}, {'row': 2, 'col': 3},
                                                                           {'row': 3, 'col': 2}, {'row': 2, 'col': 1}))]]}
    if not explicit_false:
        for ability in p['abilities']:
            for entry in ability['timeline']:
                if entry['effect'].get('rules', {}).get('damage.pipeline') == 'rule/ch8/flame/damage':
                    entry['effect']['parameters']['consider_unhurtable'] = True
    return p


def receiver(inputs, params, context):
    effect = inputs['effect']
    result = deepcopy(dict(effect['settlement']))
    allowed = effect.get('parameters', {}).get('consider_unhurtable') is False
    result['accepted'] = result['accepted'] and allowed
    result['amount'] = result['amount'] * .75 if allowed else 0
    return result


@pytest.mark.parametrize('explicit_false', [True, False])
def test_actual_flag_not_all_modifier_bypass_with_four_resistances_CP749_head(tmp_path, explicit_false):
    reg = {**providers(), 'peer.flame.receiver': {'callable': receiver, 'version': '1'}}
    program = Compiler(providers=reg).compile(package(explicit_false))
    s = Engine.create(program, providers=reg, seed=48192)
    s.advance(749)
    f = tmp_path / 'flag749.cp.json'
    pin = write_ordered(f, s.checkpoint())
    r = Engine.restore(program, load_bound(f, pin), providers=reg)
    s.advance(56)
    r.advance(56)
    h = replay(program, s.export_replay(), providers=reg)
    assert s.checkpoint() == r.checkpoint() == h.checkpoint()
    assert list(s.session.events) == list(r.session.events) == list(h.session.events)
    fixed = [event['payload']['amount'] for event in s.session.events
             if event['type'] == 'damage.accepted' and event['payload']['ability'] == 'ability/ch8/flame/explode']
    assert sorted(fixed) == (sorted((622.5, 472.5, 352.5, 202.5)) if explicit_false else [])
    assert s.ctx.resources.current('device', 'hp') == 6000 and not s.ctx.active('device')
