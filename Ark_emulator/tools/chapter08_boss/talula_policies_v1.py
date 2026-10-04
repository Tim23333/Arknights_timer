"""Pure configurable dual attacks, current taunt ordering and native eligibility."""


def decision(inputs, params, context):
    key = 'combat' if inputs['blocked_by'] is not None else 'attack'
    busy = bool(inputs['cast_groups']['normal'])
    eligible = bool(inputs['eligible_ids'][key])
    return {'move': inputs['blocked_by'] is None and not eligible and not busy, 'attack': eligible and not busy}


def score(inputs, params, context):
    attrs = inputs['candidate']['components'].get('attributes', {})
    modifiers = [m for m in attrs.get('modifiers', []) if m['attribute'] == 'taunt_level']
    taunt = context.calculate('attributes.effective', {'base': attrs.get('base', {}).get('taunt_level', 0),
        'modifier_layers': modifiers, 'order': [{'layer': x} for x in ('flat','direct_ratio','final_ratio')]},
        rule_id='rule/ark_attribute_layers').value
    return inputs['distance']-taunt*100000


def providers():
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    return {**BUILTIN_PROVIDERS, 'reference.c8.talula.dual_attack': {'callable': decision, 'version': '1'},
        'reference.c8.talula.taunt': {'callable': score, 'version': '1'}}
