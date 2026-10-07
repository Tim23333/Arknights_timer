"""Content reference ordering: live attribute layers, integer taunt then distance.

Comparator native method body remains pending. No unit/Buff IDs are special cased.
"""
def score(inputs, params, context):
    a = inputs['candidate']['components'].get('attributes', {})
    value = context.calculate('attributes.effective', {
        'base': a.get('base', {}).get('taunt_level', 0),
        'modifier_layers': [m for m in a.get('modifiers', ()) if m['attribute'] == 'taunt_level'],
        'order': [{'layer': x} for x in params['attribute_layers']]},
        rule_id='rule/ark_attribute_layers').value
    return inputs['distance'] - params['taunt_weight'] * value

def providers():
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    return {**BUILTIN_PROVIDERS, 'reference.ch7.live_taunt_score': {'callable': score, 'version': '1.0.0'}}
