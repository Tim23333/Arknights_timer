"""Explicit field recovery driver for units occupying source healing tiles."""
from copy import deepcopy


def adapt_unit(unit,source):
    result=deepcopy(unit);components=result['components'];health=[key for key,spec in components.get('resources',{}).items() if spec.get('role')=='health']
    if len(health)!=1:raise ValueError('Tile recovery adapter requires one explicit health resource')
    key=health[0];spec=components['resources'][key]
    if spec.get('recovery_rate',0)!=0 or spec.get('recovery_rule') or spec.get('recovery'):
        raise ValueError('Existing HP recovery requires an explicit composition rule, not overwrite')
    attributes=components['attributes']['base']
    if attributes.get('hp_ratio_recovery',0)!=0:raise ValueError('Existing ratio recovery needs explicit composition')
    attributes['hp_ratio_recovery']=0
    spec.update(recovery_rule='rule/ch2/tile_hp_ratio_recovery',recovery={'mode':'continuous'})
    result.setdefault('metadata',{})['tile_recovery_adapter']={'source':deepcopy(source),
        'rule':'rule/ch2/tile_hp_ratio_recovery','effective_max_hp':True,'driver':'continuous quantum',
        'permission':'regeneration independent from normal healing, declared reference policy',
        'original_hp_and_capacity_unchanged':True}
    return result
