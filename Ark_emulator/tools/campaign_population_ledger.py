"""Separate actual runtime populations without treating every birth as a wave.

Wave provenance currently uses the timeline's stored timing origins. This is
a declared-model diagnostic, not a recovered native creation-path proof.
"""
from collections import Counter
from collections.abc import Mapping


def population(sim):
    groups={key:[] for key in ('wave_enemies','non_wave_enemies','registered_predefines','player_owned','public_deployments','tile_field_owners','other_entities')}
    registry=sim.ctx.state().get('predefined_registry',{})
    registered={ref:key for key,ref in registry.items()}
    for entity in sim.session.world.entities():
        if entity['definition_id']=='system/battle':continue
        ref=entity['id'];components=entity['components'];runtime=components.get('runtime',{})
        origins=components.get('spatial',{}).get('timing_origins');ownership=components.get('ownership',{})
        row={'id':ref,'definition':entity['definition_id'],'alive':sim.ctx.alive(ref),'active':sim.ctx.active(ref),
             'state':runtime.get('state'),'owner':ownership.get('owner'),'registration_key':registered.get(ref),
             'wave_timing_origins':dict(origins) if isinstance(origins,Mapping) else None}
        if 'tile_field_owner' in entity['tags']:group='tile_field_owners'
        elif ref in registered:group='registered_predefines'
        elif 'enemy' in entity['tags']:group='wave_enemies' if isinstance(origins,Mapping) and all(k in origins for k in ('wave_start','fragment_start','action_start')) else 'non_wave_enemies'
        elif ownership.get('owner') is not None:group='player_owned'
        elif runtime.get('deployed'):group='public_deployments'
        else:group='other_entities'
        groups[group].append(row)
    return {'schema':'ark-sim/population-ledger/v1','groups':groups,
            'counts':{key:len(rows) for key,rows in groups.items()},
            'wave_births_by_definition':dict(Counter(r['definition'] for r in groups['wave_enemies'])),
            'non_wave_births_by_definition':dict(Counter(r['definition'] for r in groups['non_wave_enemies'])),
            'scope':'Actual World ownership/registration/timeline-origin diagnostic; unproved native hidden spawns remain pending',
            'actual_game_accuracy_verified':False}
