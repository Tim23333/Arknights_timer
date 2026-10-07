"""Declared tile mechanics consume route checkpoints, never tile ID guesses."""
from collections.abc import Mapping
from ark_sim.contracts import thaw
from ark_sim.rules.numeric import validate_data
from .spatial import project_cell

def validate_profiles(value):
    if not isinstance(value,Mapping):raise ValueError('map.tile_mechanics requires a mapping of tile keys to profiles')
    for key,p in value.items():
        if not isinstance(key,str) or not key:raise ValueError('tile mechanic key must be a nonempty string')
        if isinstance(p,Mapping) and p.get('type')=='declared_static_tile':
            if set(p)!={'type','expected_options','expected_blackboard','expected_effects'}:raise ValueError('declared static tile requires exact source options/blackboard/effects')
            options=p['expected_options']
            if not isinstance(options,Mapping) or set(options)!={'buildableType','passableMask','heightType'}:raise ValueError('static tile options require explicit build/pass/height')
            from .terrain import validate_values
            validate_values(options)
            if p['expected_blackboard'] not in (None,{},[]) or p['expected_effects'] not in (None,{},[]):raise ValueError('static tile cannot consume nonempty blackboard/effects')
            continue
        if isinstance(p,Mapping) and p.get('type')=='periodic_effect_field':
            from .periodic_fields import validate_profile
            validate_profile(p);continue
        if isinstance(p,Mapping) and p.get('type')=='contact_lifecycle':
            from .tile_contacts import validate_profile
            validate_profile(p)
            continue
        if isinstance(p,Mapping) and p.get('type')=='occupancy_buff_field':
            if set(p)!={'type','definition','expected_blackboard'}:raise ValueError('tile field profile needs explicit definition and blackboard binding')
            if not isinstance(p['definition'],str) or not p['definition']:raise ValueError('tile field entity reference required')
            if not isinstance(p['expected_blackboard'],Mapping):raise ValueError('tile field expected blackboard must be a mapping')
            validate_data(p['expected_blackboard'],'tile field blackboard')
            continue
        if not isinstance(p,Mapping) or set(p)-{'type','role','rule','parameters'}:raise ValueError('tile mechanic unknown profile fields')
        if p.get('type')!='route_checkpoint_portal' or p.get('role') not in ('entry','exit'):raise ValueError('unsupported tile mechanic profile/role')
        if p.get('rule') is not None and (not isinstance(p['rule'],str) or not p['rule']):raise ValueError('tile mechanic rule requires definition ID')
        if 'parameters' in p and not isinstance(p['parameters'],Mapping):raise ValueError('tile mechanic parameters must be data mapping')
        validate_data(p.get('parameters',{}),'tile mechanic parameters')

def descriptor(grid,position):
    row,col=project_cell(position)
    tile=grid.tile(row,col);key=tile.get('tileKey','tile_floor');profile=grid.tile_mechanics.get(key)
    return {'cell':{'row':row,'col':col},'tile_key':key,'tile_options':tile,'profile':thaw(profile) if profile else None}

def paired_rule(entry,exit,fallback):
    entry=entry if entry and entry.get('type')=='route_checkpoint_portal' else None
    exit=exit if exit and exit.get('type')=='route_checkpoint_portal' else None
    rules={p.get('rule') for p in (entry,exit) if p and p.get('rule')}
    if len(rules)>1:raise ValueError('portal entry/exit declare conflicting transition rules')
    return next(iter(rules)) if rules else fallback

def validate_pair(entry,exit):
    entry=entry if entry and entry.get('type')=='route_checkpoint_portal' else None
    exit=exit if exit and exit.get('type')=='route_checkpoint_portal' else None
    if not entry and not exit:return False
    if not entry or not exit or entry['role']!='entry' or exit['role']!='exit':
        raise ValueError('route portal requires paired entry and exit tile profiles')
    return True
