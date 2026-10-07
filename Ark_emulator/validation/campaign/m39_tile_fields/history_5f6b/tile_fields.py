"""Generic authored tile fields represented by explicit Buff owner entities."""
from collections.abc import Mapping
from ark_sim.contracts import thaw


def board(tile):
    raw=tile.get('blackboard')
    if raw is None:return {}
    if isinstance(raw,Mapping):return dict(raw)
    if not isinstance(raw,(list,tuple)):raise ValueError('tile field blackboard must be a mapping or entry list')
    result={}
    for entry in raw:
        if not isinstance(entry,Mapping) or set(entry)-{'key','value','valueStr'} or not isinstance(entry.get('key'),str) or not entry['key']:
            raise ValueError('tile field blackboard entry malformed')
        if entry['key'] in result:raise ValueError('tile field duplicate blackboard key')
        if entry.get('valueStr') is not None:raise ValueError('tile field string blackboard needs an explicit adapter')
        result[entry['key']]=entry['value']
    return result


def validate_data(tile,profile):
    actual=board(tile);expected=profile['expected_blackboard']
    if set(actual)!=set(expected) or any(type(actual[k]) is not type(expected[k]) or actual[k]!=expected[k] for k in actual):
        raise ValueError('tile field blackboard is not fully bound by its explicit profile')
    if tile.get('effects'):raise ValueError('tile field graphic/effect data requires an explicit effect adapter')


def validate_definitions(definitions,scene):
    for key,profile in scene.get('map',{}).get('tile_mechanics',{}).items():
        if profile['type']!='occupancy_buff_field':continue
        definition=definitions[profile['definition']]
        if definition['kind']!='entity':raise ValueError('tile field definition must be an entity')
        components=definition.get('components',{})
        if set(components.get('spatial',{})) - {'coordinate_space','position','facing','parameters'}:
            raise ValueError('static tile field owner spatial motion/route/driver is forbidden')
        if 'tile_field_owner' not in definition.get('tags',[]) or set(definition.get('tags',[])) & {'enemy','player','campaign_roster'}:
            raise ValueError('tile field owner requires explicit noncombat field tag')
        if any(components.get(k) for k in ('abilities','behavior','deployable','ownership','terrain_overlays')):
            raise ValueError('tile field owner must be static without combat/deployment/ownership/terrain mechanics')
        initial=components.get('buffs',components.get('buff_container',{})).get('initial',[])
        if not initial or not any(definitions[bid].get('aura') for bid in initial):
            raise ValueError('tile field owner needs an explicit parent aura Buff')
    def visit(value):
        if isinstance(value,Mapping):
            reference=value.get('definition')
            if isinstance(reference,str) and reference in definitions and definitions[reference].get('kind')=='entity':
                from ..content.overlays import merge
                definition=definitions[reference]
                components=merge(thaw(definition.get('components',{})),thaw(value.get('components',{})))
                if value.get('route') is not None:
                    components.setdefault('spatial',{})['route']=thaw(value['route'])
                if 'tile_field_owner' in definition.get('tags',[]) and value.get('parameters',{}).get('owner') is not None:
                    raise ValueError('static tile field instance owner parameter is forbidden')
                validate_effective_owner(definitions,definition,components,value.get('tags',definition.get('tags',[])))
            for key,child in value.items():
                if key not in ('metadata','parameters','payload','inputs','expected_blackboard'):visit(child)
        elif isinstance(value,(list,tuple)):
            for child in value:visit(child)
    visit(scene)


def validate_effective_owner(definitions,definition,components,tags):
    if 'tile_field_owner' not in definition.get('tags',[]):
        if 'tile_field_owner' in tags:
            raise ValueError('ordinary actor cannot acquire the reserved tile field role')
        return
    if 'tile_field_owner' not in tags or set(tags)&{'enemy','player','campaign_roster'}:
        raise ValueError('static tile field runtime role cannot be overridden')
    if set(components.get('spatial',{}))-{'coordinate_space','position','facing','parameters'}:
        raise ValueError('static tile field effective spatial driver is forbidden')
    if any(components.get(key) for key in ('abilities','behavior','deployable','ownership','terrain_overlays')):
        raise ValueError('static tile field effective combat/deployment/ownership override is forbidden')
    initial=components.get('buffs',components.get('buff_container',{})).get('initial',[])
    if not initial or not any(definitions[bid].get('aura') for bid in initial):
        raise ValueError('static tile field effective parent aura is absent')


def initialize(ctx):
    map_definition=ctx.program.scenario.get('map',{});profiles=map_definition.get('tile_mechanics',{})
    if not any(p['type']=='occupancy_buff_field' for p in profiles.values()):return
    fields={}
    with ctx.session.atomic():
        for index,tile in enumerate(map_definition['tiles']):
            profile=profiles.get(tile.get('tileKey'))
            if not profile or profile['type']!='occupancy_buff_field':continue
            validate_data(tile,profile);row,col=divmod(index,map_definition['cols'])
            ref=ctx.lifecycle.create(profile['definition'],{'row':row,'col':col},deployed=False)
            fields[f'{row}:{col}']={'owner':ref,'tile_key':tile['tileKey'],'definition':profile['definition'],
                'source_blackboard':board(tile),'source_tile':thaw(tile)}
        ctx.state_update(tile_fields=fields)
