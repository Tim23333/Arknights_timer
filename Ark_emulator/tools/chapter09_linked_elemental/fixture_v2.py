"""Native FIRE packet prototype; full Flame ownership and DeadBoom remain separate."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'packages/campaign/chapter09_source_prepare/enemies.native.v1.json'


def fixture(capacity=1000, duration=1.5, hp=5000, resistance=20, integral=False):
    source = json.loads(SOURCE.read_bytes())
    row = next(v for v in source['variants'].values() if v['prefab_key'] == 'enemy_1173_duspfr')
    native = row['native_enemy']['resolved']
    skill = next(s for s in native['skills'] if s['prefabKey'] == 'Flame')
    bb = {r['key']: r['value'] for r in skill['blackboard']}
    assert (native['attributes']['atk'], bb['atk_scale'], bb['ep_damage_ratio'], bb['hit_interval']) == (500, .12, .06, .5)
    def rule(name, contract, expression):
        return {'id': 'rule/linked/' + name, 'kind': 'rule', 'contract': contract,
                'implementation': {'type': 'expression', 'expression': expression}}
    rules = [rule('capacity', 'elemental.capacity', 'inputs.parameters.capacity'),
             rule('loss', 'elemental.loss', 'max(0, inputs.request.raw_amount*(1-inputs.parameters.resistance*.01))'),
             rule('recovery', 'elemental.recovery', 'inputs.current'),
             rule('duration', 'elemental.break_duration', 'inputs.parameters.break_duration_seconds'),
             rule('eligible', 'elemental.eligibility', "'neutral' not in inputs.target.tags"),
             rule('packet', 'elemental.packet', 'inputs.source_attributes.atk * inputs.request.parameters.ep_ratio'),
             {'id': 'rule/linked/motion', 'kind': 'rule', 'contract': 'projectile.trajectory',
              'implementation': {'type': 'provider', 'provider': 'model.linked.homing'}}]
    effect = {'op': 'elemental_attack',
              'health_effect': {'op': 'damage', 'damage_type': 'arts', 'scale': bb['atk_scale'],
                                'read_mode': {'source_attributes': 'at_hit', 'target_attributes': 'at_hit'}},
              'element_effect': {'op': 'elemental_damage', 'element': 'FIRE',
                                 'amount_rule': 'rule/linked/packet', 'parameters': {'ep_ratio': bb['ep_damage_ratio']}}}
    profile = {'capacity': capacity, 'resistance': 0, 'recovery_rate': 0, 'break_duration_seconds': 10,
               'rules': {'elemental.capacity': 'rule/linked/capacity', 'elemental.loss': 'rule/linked/loss',
                         'elemental.recovery': 'rule/linked/recovery', 'elemental.break_duration': 'rule/linked/duration'},
               'on_break': [{'op': 'emit', 'event': 'linked.break'}], 'on_end': []}
    return {'schemaVersion': 2, 'rules': rules,
            'definitions': [{'id': 'attachment/linked/fire', 'kind': 'attachment',
                'duration_seconds': duration, 'flight_lifetime_seconds': 5,
                'step_interval_seconds': 1/30, 'hit_interval_seconds': bb['hit_interval'], 'refresh_interval_seconds': 1,
                'motion': {'rule': 'rule/linked/motion', 'parameters': {'mode': 'homing', 'speed': 10}},
                'target_buff': 'buff/linked/marker', 'effect': effect, 'damage_integral': integral,
                'source_cancel_flags': [0, 12], 'ignored_owned_source_flags': [],
                'force_reach_on_timeout': True,
                'lifecycle': {'source_invalid': 'cancel', 'target_invalid': 'cancel',
                              'source_hidden': 'cancel', 'target_hidden': 'cancel'},
                'max_packets': None, 'completion_blocking': False, 'source_recovery_buff': None, 'recovery_on': []}],
            'buffs': [{'id': 'buff/linked/marker', 'kind': 'buff', 'stacking': {'mode': 'independent'}}],
            'selectors': [{'id': 'selector/linked/target', 'kind': 'selector', 'region': {'type': 'all'},
                           'filters': [{'tag': 'player'}, {'state': 'alive'}], 'limit': 1}],
            'abilities': [{'id': 'ability/linked/fire', 'kind': 'ability', 'activation': {'mode': 'manual'},
                           'wait_for_channels': True, 'selector': 'selector/linked/target',
                           'timeline': [{'at': 0, 'effect': {'op': 'begin_attachment', 'attachment': 'attachment/linked/fire'}}]}],
            'entities': [{'id': 'unit/linked/source', 'kind': 'entity', 'tags': ['enemy'], 'components': {
                'attributes': {'base': {'max_hp': 8000, 'atk': 500, 'def': 400, 'mres': 0,
                                       'attack_interval': 2, 'attack_speed_ratio': 1}},
                'resources': {'hp': {'role': 'health', 'initial': 8000, 'capacity': 8000}},
                'selection_state': {'side': 1, 'motion': 1, 'category': 1, 'unit_type': 2, 'abnormal_flags': []},
                'abilities': ['ability/linked/fire'], 'spatial': {}, 'lifecycle': {'policy': 'policy/ark_lifecycle'}}},
                {'id': 'unit/linked/target', 'kind': 'entity', 'tags': ['player'], 'components': {
                    'attributes': {'base': {'max_hp': hp, 'atk': 0, 'def': 137, 'mres': resistance}},
                    'resources': {'hp': {'role': 'health', 'initial': hp, 'capacity': hp}},
                    'spatial': {}, 'lifecycle': {'policy': 'policy/ark_lifecycle'},
                    'elemental': {'eligibility_rule': 'rule/linked/eligible', 'elements': {'FIRE': profile}}}}],
            'scenarioDraft': {'id': 'scene/linked', 'ruleset': 'ruleset/ark_standard', 'map': {'rows': 1, 'cols': 4},
                'initialEntities': [{'definition': 'unit/linked/source', 'instanceAlias': 'source', 'position': {'row': 0, 'col': 0}},
                                    {'definition': 'unit/linked/target', 'instanceAlias': 'target', 'position': {'row': 0, 'col': 1}}]}}


def providers():
    from ark_sim.domains.projectile_profiles import trajectory
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    return {**BUILTIN_PROVIDERS, 'model.linked.homing': {'callable': trajectory, 'version': 'planar-homing-v1'}}
