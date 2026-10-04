"""Pure source selector marker gates and lexicographic HATE, no World writes."""
def live(actor, key, now):
    return any(b['definition'] == key and b.get('applicability', {}).get('active', True)
               and (b['expires_at'] is None or now < b['expires_at'])
               for b in actor['components'].get('buffs', {}).get('instances', []))

def eligibility(inputs, params, context):
    base = context.calculate('targeting.eligibility', inputs, rule_id=params['base']).value
    if not base['accepted']: return dict(base)
    present = live(inputs['candidate'], params['timer'], context['time'])
    return {'accepted': present != params['exclude'], 'reason': 'native_dragon_fire_marker_gate'}

def selection(inputs, params, context):
    rows = []
    for actor in inputs['candidates']:
        a = actor['components'].get('attributes', {})
        value = context.calculate('attributes.effective', {
            'base': a.get('base', {}).get('taunt_level', 0),
            'modifier_layers': [m for m in a.get('modifiers', []) if m['attribute'] == 'taunt_level'],
            'order': [{'layer': v} for v in ('flat', 'direct_ratio', 'final_ratio')]},
            rule_id='rule/ark_attribute_layers').value if params['hate'] else 0
        rows.append((-value, actor['id']))
    rows.sort()
    count = inputs['limits']['count']
    return [x[1] for x in rows[:len(rows) if count is None else count]]

def recovery(inputs, params, context):
    q = context['quantum']; speed = max(inputs['attributes']['attack_speed_ratio'], .01)
    frames = context.calculate('time.quantize', {'seconds': params['full_seconds']/speed,
        'quantum': q, 'rounding': {'mode': 'ceil'}}).value
    cooldown = context.calculate('time.quantize', {'seconds': inputs['recovery_parameters']['seconds'],
        'quantum': q, 'rounding': {'mode': 'ceil'}}).value
    return max(0, cooldown-frames)*q

def providers():
    from tools.chapter08_buff_lifetime.talula_providers_v1 import providers as parent
    return {**parent(), **{name: {'callable': fn, 'version': '1'} for name, fn in (
        ('reference.c8.bsnake.skills.eligibility', eligibility),
        ('reference.c8.bsnake.skills.selection', selection),
        ('reference.c8.bsnake.skills.recovery', recovery))}}
