"""Independent live capacity policies; no native HP formula inferred."""
from copy import deepcopy
import pytest
from ark_sim import Compiler, Engine
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay


def model(mode='preserve_absolute', initial=500, *, initial_buff=False):
    actor = {'id': 'unit/capacity_review', 'kind': 'entity', 'tags': ['player'], 'components': {
        'attributes': {'base': {'max_hp': 1000, 'atk': 1, 'def': 0, 'mres': 0}}, 'spatial': {},
        'lifecycle': {'policy': 'policy/ark_lifecycle'},
        'resources': {'hp': {'initial': initial, 'capacity_attribute': 'max_hp', 'role': 'health',
            'parameters': {'capacity_change_mode': mode}}}}}
    if initial_buff:
        actor['components']['buffs'] = {'initial': ['buff/capacity_review']}
    return {'schemaVersion': 2, 'entities': [actor], 'buffs': [{'id': 'buff/capacity_review', 'kind': 'buff',
        'duration_seconds': 1, 'modifiers': [{'attribute': 'max_hp', 'layer': 'direct_ratio', 'value': .5}]}],
        'scenarioDraft': {'id': 'scenario/capacity_review', 'ruleset': 'ruleset/ark_standard', 'map': {'rows': 3, 'cols': 4},
            'dependencies': ['buff/capacity_review'], 'initialEntities': [{'definition': actor['id'], 'instanceAlias': 'actor',
                'position': {'row': 1, 'col': 1}}]}}


def create(data):
    return Engine.create(Compiler().compile(data))


@pytest.mark.parametrize('mode, after, removed', [('preserve_absolute', 500, 500), ('preserve_ratio', 750, 500),
    ('preserve_missing', 1000, 500), ('fill', 1500, 1000)])
def test_explicit_modes_apply_remove_and_no_fake_healing(mode, after, removed):
    sim = create(model(mode))
    sim.ctx.buffs.apply('actor', 'actor', 'buff/capacity_review')
    assert sim.ctx.resources.current('actor', 'hp') == after
    assert sim.ctx.resources.capacity('actor', 'hp') == 1500
    sim.ctx.buffs.remove('actor', 'buff/capacity_review')
    assert sim.ctx.resources.current('actor', 'hp') == removed
    assert not [e for e in sim.session.events if e['type'] == 'healing.accepted']


def test_buff_expiry_clamps_before_next_one_damage_without_inventing_loss():
    sim = create(model(initial=1000))
    sim.ctx.buffs.apply('actor', 'actor', 'buff/capacity_review')
    sim.ctx.resources.adjust('actor', 'hp', value=1400)
    sim.advance(31)
    assert sim.ctx.resources.current('actor', 'hp') == 1000
    sim.ctx.effects.execute('actor', ['actor'], {'op': 'damage', 'damage_type': 'true', 'scale': 0, 'additions': 1})
    assert sim.ctx.resources.current('actor', 'hp') == 999
    assert [e['payload']['amount'] for e in sim.session.events if e['type'] == 'damage.accepted'][-1] == 1


def test_birth_full_only_during_initialization_not_later_buff_application():
    sim = create(model('birth_full', initial=1000, initial_buff=True))
    assert sim.ctx.resources.current('actor', 'hp') == 1500
    sim.ctx.buffs.remove('actor', 'buff/capacity_review')
    sim.ctx.resources.adjust('actor', 'hp', value=400)
    sim.ctx.buffs.apply('actor', 'actor', 'buff/capacity_review')
    assert sim.ctx.resources.current('actor', 'hp') == 400


def test_aura_leave_removes_only_its_hp_layer_and_applies_ratio_policy():
    data = model('preserve_ratio')
    parent = deepcopy(data['entities'][0]);parent['id'] = 'unit/capacity_emitter';parent['tags'] = ['emitter']
    parent['components']['resources']['hp']['initial'] = 1000
    parent['components']['buffs'] = {'initial': ['buff/capacity_emitter']}
    data['entities'].append(parent)
    data['buffs'][0].pop('duration_seconds')
    data['buffs'][0]['stacking'] = {'mode': 'independent'}
    data['buffs'].append({'id': 'buff/capacity_emitter', 'kind': 'buff',
        'aura': {'selector': 'selector/capacity_members', 'buff': 'buff/capacity_review'}})
    data['selectors'] = [{'id': 'selector/capacity_members', 'kind': 'selector', 'region': {'type': 'radius', 'radius': 1},
        'filters': [{'tag': 'player'}, {'state': 'alive'}], 'limit': None}]
    data['scenarioDraft']['initialEntities'].append({'definition': parent['id'], 'instanceAlias': 'parent', 'position': {'row': 1, 'col': 2}})
    sim = create(data)
    assert sim.ctx.resources.current('actor', 'hp') == 750
    sim.ctx.movement.displace('actor', 'actor', {'position': {'row': 1, 'col': 0}}, {})
    assert sim.ctx.resources.current('actor', 'hp') == 500
    assert sim.ctx.resources.capacity('actor', 'hp') == 1000


def test_custom_capacity_change_rule_and_runtime_failure_are_atomic():
    data = model()
    data['rules'] = [{'id': 'rule/capacity_custom', 'kind': 'calculation_rule', 'contract': 'resource.capacity_change',
        'implementation': {'type': 'expression', 'expression': 'inputs.current + 17'}}]
    data['entities'][0]['components']['resources']['hp']['capacity_change_rule'] = 'rule/capacity_custom'
    sim = create(data)
    sim.ctx.buffs.apply('actor', 'actor', 'buff/capacity_review')
    assert sim.ctx.resources.current('actor', 'hp') == 517
    data['rules'][0]['implementation']['expression'] = 'inputs.current / (inputs.old_capacity - 1000)'
    sim = create(data)
    before = sim.checkpoint()
    with pytest.raises(ValueError):
        sim.ctx.buffs.apply('actor', 'actor', 'buff/capacity_review')
    assert sim.checkpoint() == before


def test_capacity_policy_result_zero_really_causes_lifecycle_death():
    data = model()
    data['rules'] = [{'id': 'rule/capacity_zero', 'kind': 'calculation_rule', 'contract': 'resource.capacity_change',
        'implementation': {'type': 'expression', 'expression': '0'}}]
    data['entities'][0]['components']['resources']['hp']['capacity_change_rule'] = 'rule/capacity_zero'
    sim = create(data)
    sim.ctx.buffs.apply('actor', 'actor', 'buff/capacity_review')
    assert sim.ctx.resources.current('actor', 'hp') == 0
    assert sim.ctx.alive('actor') is False
    assert sim.ctx.get('actor', ('runtime', 'state')) == 'dead'


def test_dynamic_capacity_tick_uses_cached_old_capacity_for_ratio():
    sim = create(model('preserve_ratio', initial=400))
    sim.ctx.set('actor', ('attributes', 'base', 'max_hp'), 2000)
    sim.advance(1)
    assert sim.ctx.resources.current('actor', 'hp') == 800
    sim.ctx.set('actor', ('attributes', 'base', 'max_hp'), 500)
    sim.advance(1)
    assert sim.ctx.resources.current('actor', 'hp') == 200
    assert sim.ctx.resources.capacity('actor', 'hp') == 500


def test_custom_removal_failure_restores_applied_buff_capacity_jobs_and_events():
    data = model()
    data['rules'] = [{'id': 'rule/capacity_remove_failure', 'kind': 'calculation_rule', 'contract': 'resource.capacity_change',
        'implementation': {'type': 'expression', 'expression': 'inputs.current if inputs.new_capacity > inputs.old_capacity else inputs.current / 0'}}]
    data['entities'][0]['components']['resources']['hp']['capacity_change_rule'] = 'rule/capacity_remove_failure'
    sim = create(data)
    sim.ctx.buffs.apply('actor', 'actor', 'buff/capacity_review')
    before = sim.checkpoint()
    with pytest.raises(ValueError):
        sim.ctx.buffs.remove('actor', 'buff/capacity_review')
    assert sim.checkpoint() == before


def test_capacity_expiry_checkpoint_and_command_replay_keep_profile_identity():
    data = model('preserve_ratio')
    data['abilities'] = [{'id': 'ability/capacity_review', 'kind': 'ability', 'activation': {'mode': 'manual',
        'on_start': [{'op': 'apply_buff', 'target': 'source', 'buff': 'buff/capacity_review'}]}, 'timeline': []}]
    data['entities'][0]['components']['abilities'] = ['ability/capacity_review']
    program = Compiler().compile(data)
    sim = Engine.create(program)
    sim.submit({'action': 'skill', 'source': 'actor', 'ability': 'ability/capacity_review'})
    sim.advance(15)
    restored = Engine.restore(program, sim.checkpoint())
    sim.advance(20);restored.advance(20)
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    assert first_difference(sim.snapshot(), replay(program, sim.export_replay()).snapshot()) is None


def time_attributes(inputs, params, context):
    return inputs['base'] + context['time'] * 100 if context['attribute'] == 'max_hp' else inputs['base']


def provider_program(data, descriptor=None):
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    providers = {'review/time_attributes': {'callable': time_attributes, 'version': 'independent-review/1', **(descriptor or {})}}
    program = Compiler(providers={**BUILTIN_PROVIDERS, **providers}).compile(data)
    return program, providers


def test_custom_attributes_provider_time_without_static_descriptor_keeps_polling_and_replay():
    data = model('preserve_ratio')
    data['rules'] = [{'id': 'rule/review_time_attributes', 'kind': 'calculation_rule', 'contract': 'attributes.effective',
        'implementation': {'type': 'provider', 'provider': 'review/time_attributes'}}]
    data['entities'][0]['rules'] = {'attributes.effective': 'rule/review_time_attributes'}
    program, providers = provider_program(data)
    sim = Engine.create(program, providers=providers)
    sim.advance(2)
    assert sim.ctx.resources.current('actor', 'hp') == 550
    restored = Engine.restore(program, sim.checkpoint(), providers=providers)
    sim.advance(2);restored.advance(2)
    assert sim.ctx.resources.current('actor', 'hp') == 650
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    assert first_difference(sim.snapshot(), replay(program, sim.export_replay(), providers=providers).snapshot()) is None


def test_provider_static_dependency_descriptor_changes_locked_program_identity():
    data = model()
    data['rules'] = [{'id': 'rule/review_time_attributes', 'kind': 'calculation_rule', 'contract': 'attributes.effective',
        'implementation': {'type': 'provider', 'provider': 'review/time_attributes'}}]
    data['entities'][0]['rules'] = {'attributes.effective': 'rule/review_time_attributes'}
    unknown, _ = provider_program(data)
    declared, _ = provider_program(data, {'attribute_time_dependency': 'modifiers'})
    assert unknown.fingerprint != declared.fingerprint


def test_dynamic_input_index_capacity_expression_cannot_be_treated_as_parameter_only():
    data = model('preserve_ratio')
    spec = data['entities'][0]['components']['resources']['hp']
    spec.pop('capacity_attribute')
    spec['capacity_rule'] = 'rule/review_dynamic_index'
    data['rules'] = [{'id': spec['capacity_rule'], 'kind': 'calculation_rule', 'contract': 'resource.capacity',
        'parameters': {'key': 'attributes', 'field': 'max_hp'},
        'implementation': {'type': 'expression', 'expression': 'inputs[params.key][params.field]'}}]
    sim = create(data)
    sim.ctx.set('actor', ('attributes', 'base', 'max_hp'), 2000)
    sim.advance(1)
    assert sim.ctx.resources.current('actor', 'hp') == 1000
    assert sim.ctx.get('actor', ('resources', 'hp', 'observed_capacity')) == 2000


def test_graph_capacity_with_time_keeps_polling_even_without_capacity_attribute():
    data = model('preserve_ratio')
    spec = data['entities'][0]['components']['resources']['hp']
    spec.pop('capacity_attribute')
    spec['capacity_rule'] = 'rule/review_graph_capacity'
    data['rules'] = [{'id': spec['capacity_rule'], 'kind': 'calculation_rule', 'contract': 'resource.capacity',
        'implementation': {'type': 'graph', 'nodes': [{'id': 'capacity', 'expression': 'inputs.attributes.max_hp + context.time * 100'}],
            'output': 'nodes.capacity'}}]
    sim = create(data)
    sim.advance(3)
    assert sim.ctx.get('actor', ('resources', 'hp', 'observed_capacity')) == 1200
    assert sim.ctx.resources.current('actor', 'hp') == 600


@pytest.mark.parametrize('context_name', ['context', 'ctx'])
def test_both_supported_context_names_make_capacity_expression_time_dependent(context_name):
    data = model('preserve_ratio')
    spec = data['entities'][0]['components']['resources']['hp']
    spec.pop('capacity_attribute');spec['capacity'] = 1000
    spec['capacity_rule'] = 'rule/review_context_capacity'
    data['rules'] = [{'id': spec['capacity_rule'], 'kind': 'calculation_rule', 'contract': 'resource.capacity',
        'implementation': {'type': 'expression', 'expression': 'inputs.capacity_parameters.capacity + ' + context_name + '.time * 100'}}]
    sim = create(data)
    sim.advance(3)
    assert sim.ctx.get('actor', ('resources', 'hp', 'observed_capacity')) == 1200
    assert sim.ctx.resources.current('actor', 'hp') == 600


def test_runtime_capacity_rule_override_invalidates_static_skip_signature():
    data = model('preserve_ratio')
    spec = data['entities'][0]['components']['resources']['hp']
    spec.pop('capacity_attribute');spec['capacity'] = 1000
    data['rules'] = [{'id': 'rule/review_static_capacity', 'kind': 'calculation_rule', 'contract': 'resource.capacity',
        'implementation': {'type': 'expression', 'expression': 'inputs.capacity_parameters.capacity'}},
        {'id': 'rule/review_attribute_capacity', 'kind': 'calculation_rule', 'contract': 'resource.capacity',
        'implementation': {'type': 'expression', 'expression': 'inputs.attributes.max_hp'}}]
    data['entities'][0]['rules'] = {'resource.capacity': 'rule/review_static_capacity'}
    data['scenarioDraft']['dependencies'] += ['rule/review_attribute_capacity']
    sim = create(data)
    sim.advance(1)
    sim.ctx.set('actor', ('runtime', 'rule_bindings'), {'resource.capacity': 'rule/review_attribute_capacity'})
    sim.ctx.set('actor', ('attributes', 'base', 'max_hp'), 2000)
    sim.advance(1)
    assert sim.ctx.resources.current('actor', 'hp') == 1000
    assert sim.ctx.get('actor', ('resources', 'hp', 'observed_capacity')) == 2000


def test_attribute_layer_order_change_is_part_of_capacity_dirty_signature():
    data = model('preserve_ratio')
    attributes = data['entities'][0]['components']['attributes']
    attributes['layers'] = ['flat']
    attributes['modifiers'] = [{'attribute': 'max_hp', 'layer': 'direct_ratio', 'value': .5}]
    sim = create(data)
    assert sim.ctx.resources.current('actor', 'hp') == 500
    sim.ctx.set('actor', ('attributes', 'layers'), ['flat', 'direct_ratio'])
    sim.advance(1)
    assert sim.ctx.get('actor', ('resources', 'hp', 'observed_capacity')) == 1500
    assert sim.ctx.resources.current('actor', 'hp') == 750


def test_builtin_layer_provider_delegate_rule_time_dependency_is_not_static():
    data = model('preserve_ratio')
    data['entities'][0]['components']['attributes']['modifiers'] = [{'attribute': 'max_hp', 'layer': 'flat', 'value': 0}]
    data['entities'][0]['rules'] = {'attributes.modifier_layer': 'rule/review_time_layer'}
    data['rules'] = [{'id': 'rule/review_time_layer', 'kind': 'calculation_rule', 'contract': 'attributes.modifier_layer',
        'implementation': {'type': 'expression', 'expression': 'inputs.value + inputs.layer_parameters.additive + context.time*100'}}]
    sim = create(data)
    sim.advance(3)
    assert sim.ctx.get('actor', ('resources', 'hp', 'observed_capacity')) == 1200
    assert sim.ctx.resources.current('actor', 'hp') == 600


def time_aggregation(inputs, params, context):
    return {'additive': context['time'] * 100, 'ratio': 0, 'factor': 1}


def test_builtin_layer_provider_custom_aggregator_time_dependency_is_not_static():
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    data = model('preserve_ratio')
    data['entities'][0]['components']['attributes']['modifiers'] = [{'attribute': 'max_hp', 'layer': 'flat', 'value': 0}]
    data['entities'][0]['rules'] = {'attributes.effective': 'rule/review_custom_aggregation'}
    data['rules'] = [{'id': 'rule/review_custom_aggregation', 'kind': 'calculation_rule', 'extends': 'rule/ark_attribute_layers',
        'parameters': {'aggregator': {'provider': 'review/time_aggregation'}}}]
    providers = {'review/time_aggregation': {'callable': time_aggregation, 'version': 'independent-review/1'}}
    program = Compiler(providers={**BUILTIN_PROVIDERS, **providers}).compile(data)
    sim = Engine.create(program, providers=providers)
    sim.advance(3)
    assert sim.ctx.get('actor', ('resources', 'hp', 'observed_capacity')) == 1200
    assert sim.ctx.resources.current('actor', 'hp') == 600


def test_capacity_signature_rolls_back_and_restored_session_sees_next_change():
    data = model('preserve_ratio')
    data['rules'] = [{'id': 'rule/review_reject_capacity', 'kind': 'calculation_rule', 'contract': 'resource.capacity_change',
        'implementation': {'type': 'expression', 'expression': 'inputs.current / 0'}}]
    data['scenarioDraft']['dependencies'] += ['rule/review_reject_capacity']
    program = Compiler().compile(data)
    sim = Engine.create(program)
    before = sim.checkpoint()
    with pytest.raises(ValueError):
        with sim.session.atomic():
            sim.ctx.set('actor', ('attributes', 'base', 'max_hp'), 2000)
            sim.ctx.set('actor', ('resources', 'hp', 'spec', 'capacity_change_rule'), 'rule/review_reject_capacity')
            sim.ctx.resources.sync_capacities('actor')
    assert sim.checkpoint() == before
    sim.ctx.set('actor', ('attributes', 'base', 'max_hp'), 2000)
    restored = Engine.restore(program, sim.checkpoint())
    sim.advance(1);restored.advance(1)
    assert sim.ctx.resources.current('actor', 'hp') == 1000
    assert first_difference(sim.snapshot(), restored.snapshot()) is None


def no_capacity_change_ruleset(data):
    from ark_sim.content.compiler import PRESET_PATH
    import json
    ruleset = deepcopy(json.loads(PRESET_PATH.read_bytes())['rulesets'][0])
    ruleset['id'] = 'ruleset/review_without_capacity_change'
    ruleset['bindings'].pop('resource.capacity_change')
    data['rulesets'] = [ruleset]
    data['scenarioDraft']['ruleset'] = ruleset['id']
    return data


def test_legacy_ruleset_dynamic_capacity_without_new_contract_clamps_then_counts_next_hit():
    data = model(initial=1000)
    data['entities'][0]['components']['resources']['hp']['parameters'].pop('capacity_change_mode')
    data = no_capacity_change_ruleset(data)
    sim = create(data)
    sim.ctx.buffs.apply('actor', 'actor', 'buff/capacity_review')
    sim.ctx.resources.adjust('actor', 'hp', value=1400)
    sim.ctx.buffs.remove('actor', 'buff/capacity_review')
    assert sim.ctx.resources.current('actor', 'hp') == 1000
    sim.ctx.effects.execute('actor', ['actor'], {'op': 'damage', 'damage_type': 'true', 'scale': 0, 'additions': 1})
    assert sim.ctx.resources.current('actor', 'hp') == 999
    assert [e['payload']['amount'] for e in sim.session.events if e['type'] == 'damage.accepted'][-1] == 1


def test_explicit_capacity_profile_without_binding_is_compile_error_not_legacy_fallback():
    data = no_capacity_change_ruleset(model('preserve_ratio'))
    with pytest.raises(ValueError, match='capacity_change'):
        Compiler().compile(data)
