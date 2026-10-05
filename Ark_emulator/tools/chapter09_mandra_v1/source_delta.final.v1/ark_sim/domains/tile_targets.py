"""Pure tile queries, accepted-cast sampling and non-terrain deployment occupancy.

Tiles are coordinates, never fabricated actor IDs. All policy expressions use
the same bounded expression interpreter as other content conditions.
"""
import math
from collections.abc import Mapping
from ark_sim.contracts import thaw
from ark_sim.rules.expressions import Expression, evaluate_expression
from ark_sim.rules.numeric import validate_data
from .spatial import project_cell


def validate_selector(spec):
    if not isinstance(spec, Mapping) or set(spec)-{'eligibility_expression','parameters','limit','selection','stream','accept_input','require_owned_task'} or not {'eligibility_expression','parameters','limit','selection','stream'}<=set(spec):
        raise ValueError('tile_selector requires explicit expression/parameters/limit/selection/stream')
    if 'accept_input' in spec and type(spec['accept_input']) is not bool:raise ValueError('Tile selector input opt-in must be strict bool')
    if 'require_owned_task' in spec and type(spec['require_owned_task']) is not bool:raise ValueError('Tile task opt-in must be strict bool')
    Expression(spec['eligibility_expression'])
    if not isinstance(spec['parameters'], Mapping):
        raise ValueError('tile selector parameters must be data')
    validate_data(spec['parameters'])
    if type(spec['limit']) is not int or not 0 <= spec['limit'] <= 10000:
        raise ValueError('tile selector limit must be bounded nonnegative integer')
    if spec['selection'] not in ('row_major', 'uniform_without_replacement'):
        raise ValueError('unsupported tile selection policy')
    if spec['selection'] == 'row_major':
        if spec['stream'] is not None:
            raise ValueError('row-major tile selection cannot declare an unused RNG stream')
    elif not isinstance(spec['stream'], str) or not spec['stream']:
        raise ValueError('random tile selection requires an explicit stream')


def validate_occupancy(spec):
    if not isinstance(spec, Mapping) or set(spec) != {'blocks_deployment', 'exclusive', 'targetable', 'withdrawable'} or any(
            type(v) is not bool for v in spec.values()):
        raise ValueError('tile_occupancy requires strict blocks_deployment/exclusive/targetable/withdrawable booleans')


def occupants(ctx, cell):
    """Active actor roots; physical contact/collider membership is a separate rule."""
    result = []
    for actor in ctx.session.world.entities():
        if not ctx.active(actor['id']):
            continue
        position = actor['components'].get('spatial', {}).get('position')
        if position is not None and project_cell(position) == (cell['row'], cell['col']):
            result.append(thaw(actor))
    return result


def blocks_deployment(ctx, cell):
    return any(a['components'].get('tile_occupancy', {}).get('blocks_deployment', False)
               for a in occupants(ctx, cell))


def validate_placement(ctx, spec, position, exclude=None):
    validate_occupancy(spec)
    if not isinstance(position, Mapping) or set(position) != {'row', 'col'} or any(
            type(position[k]) is not int for k in ('row', 'col')) or not ctx.spatial.grid.inside(
                position['row'], position['col']):
        raise ValueError('tile occupancy requires an integer cell inside map')
    if spec['exclusive'] and any(a['id'] != exclude and a['components'].get('tile_occupancy')
                                 for a in occupants(ctx, position)):
        raise ValueError('tile already contains an active tile occupancy token')


def query(ctx, source, spec, input_payload=None):
    """Read-only row-major candidate list; no RNG, events, tasks or World writes."""
    validate_selector(spec)
    source = ctx.session.world.resolve(source)
    source_view = thaw(ctx.entity(source))
    grid = ctx.spatial.grid
    candidates = []
    for row in range(grid.rows):
        for col in range(grid.cols):
            cell = {'row': row, 'col': col}
            actors = occupants(ctx, cell)
            # Classification is an explicit typed projection, independent of
            # player deployment capability or actor/character IDs. Content
            # decides which side/type combinations are excluded.
            from .selection import DEFAULT_STATE
            states=[ctx.spatial.selection_state(a['id'],DEFAULT_STATE) for a in actors]
            side_bits=sorted({(s['side'],bit) for s in states for bit in (1,2,4) if s['unit_type'] & bit})
            inputs = {'source': source_view, 'cell': cell, 'tile': grid.tile(row, col),
                      'occupants': actors, 'occupant_count': len(actors),
                      'occupant_selection_states':states, 'occupied_side_unit_type_bits':[list(pair) for pair in side_bits],
                      'deployment_blocked': any(a['components'].get('deployable') or
                          a['components'].get('tile_occupancy', {}).get('blocks_deployment', False)
                          for a in actors)}
            if spec.get('accept_input'):
                if not isinstance(input_payload,Mapping) or set(input_payload)!={'target','position'} or type(input_payload['target']) is not int or input_payload['target']<1 or not isinstance(input_payload['position'],Mapping) or set(input_payload['position'])!={'row','col'} or any(type(v) not in (int,float) or not math.isfinite(v) for v in input_payload['position'].values()):raise ValueError('Input tile selector requires captured actor/root position')
                inputs['input']=thaw(input_payload)
            accepted = evaluate_expression(spec['eligibility_expression'], inputs,
                spec['parameters'], {'time': ctx.session.time, 'quantum': ctx.session.quantum})
            if type(accepted) is not bool:
                raise ValueError('tile eligibility expression must return a strict boolean')
            if accepted:
                candidates.append(cell)
    return candidates


def select(ctx, source, spec, candidates, cause=None):
    """Commit samples only within the caller's accepted-activation transaction."""
    validate_selector(spec)
    pool = thaw(candidates)
    result, samples = [], []
    for _ in range(min(spec['limit'], len(pool))):
        if spec['selection'] == 'uniform_without_replacement':
            sample = ctx.session.random.sample(spec['stream'])
            if type(sample) not in (int, float) or not math.isfinite(sample) or not 0 <= sample < 1:
                raise ValueError('tile RNG sample must be finite in [0,1)')
            index = math.floor(sample * len(pool))
            samples.append({'value': sample, 'pool_size': len(pool), 'index': index})
        else:
            index = 0
        result.append(pool.pop(index))
    ctx.emit('tile.selection', {'source': source, 'candidates': thaw(candidates),
        'selected': result, 'selection': spec['selection'], 'stream': spec['stream'],
        'samples': samples, 'parameters': thaw(spec['parameters'])}, cause)
    return result


def validate_effect(effect):
    if set(effect) - {'op', 'definition', 'parameters'} or not isinstance(effect.get('definition'), str):
        raise ValueError('spawn_on_tiles requires definition and explicit parameters')
    p = effect.get('parameters')
    if not isinstance(p, Mapping) or set(p) != {'cells', 'recheck', 'occupant_expression',
            'occupant_parameters', 'instant_kill', 'on_owner_retire'}:
        raise ValueError('spawn_on_tiles requires explicit capture/recheck/occupant/kill/ownership policies')
    if p['cells'] != 'captured' or type(p['recheck']) is not bool:
        raise ValueError('spawn_on_tiles requires captured cells and strict recheck bool')
    Expression(p['occupant_expression'])
    if not isinstance(p['occupant_parameters'], Mapping):
        raise ValueError('tile occupant parameters must be data')
    validate_data(p['occupant_parameters'])
    from .rebirth import validate_kill
    validate_kill(p['instant_kill'])
    if p['on_owner_retire'] not in ('retain', 'remove'):
        raise ValueError('tile token on_owner_retire must be explicit retain/remove')


def spawn_on_tiles(ctx, source, effect, ability, cast, cause=None):
    validate_effect(effect)
    if 'tile_targets' not in cast or 'tile_selector' not in ability:
        raise ValueError('spawn_on_tiles requires a real tile-target ability cast')
    active=ctx.get(source,('runtime','casts',cast.get('id')),None)
    if (not isinstance(active,Mapping) or type(cast.get('source')) is not int or cast.get('source')!=source or
            cast.get('ability')!=ability.get('id') or type(cast.get('generation')) is not int or
            active.get('source')!=source or active.get('ability')!=ability.get('id') or active.get('generation')!=cast.get('generation') or
            active.get('tile_targets')!=thaw(cast['tile_targets'])):
        raise ValueError('spawn_on_tiles requires an active owned cast with original captured tile targets')
    if ability['tile_selector'].get('require_owned_task'):
        task=ctx.session.current_task
        if (not task or task['kind']!='domain.ability.effect' or task['id'] not in active.get('tasks',[]) or
                task['at']!=ctx.session.time or task['phase']!=ctx.session.scheduler.rank(ctx.effect_phase) or
                task['payload'].get('source')!=source or task['payload'].get('cast')!=active.get('id') or
                active.get('source')!=source or active.get('ability')!=ability.get('id')):
            raise ValueError('Tile effect requires current scheduled task of actual owned cast')
    options = effect['parameters']
    def lease_active():
        current=ctx.get(source,('runtime','casts',cast['id']),None)
        return (ctx.active(source) and not ctx.state().get('finished') and isinstance(current,Mapping)
            and current.get('ability')==active['ability'] and current.get('generation')==active['generation']
            and current.get('tile_targets')==active['tile_targets'])
    eligible = query(ctx, source, ability['tile_selector'],cast.get('event_payload')) if options['recheck'] else None
    for cell in active['tile_targets']:
        if not lease_active():
            return
        if eligible is not None and cell not in eligible:
            ctx.emit('tile.effect_rejected', {'source': source, 'cell': cell, 'reason': 'eligibility_changed'}, cause)
            continue
        captured = occupants(ctx, cell)
        selected = []
        for actor in captured:
            accepted = evaluate_expression(options['occupant_expression'],
                {'source': thaw(ctx.entity(source)), 'candidate': actor, 'cell': cell},
                options['occupant_parameters'], {'time': ctx.session.time})
            if type(accepted) is not bool:
                raise ValueError('tile occupant expression must return strict boolean')
            if accepted:
                selected.append(actor['id'])
        for target in selected:
            if not lease_active():
                return
            if ctx.active(target):
                ctx.rebirth.instant_kill(source, target, options['instant_kill'], ability, cast, cause)
        if not lease_active():
            return
        token = ctx.lifecycle.create(effect['definition'], dict(cell), owner=source,
            on_owner_retire=options['on_owner_retire'])
        ctx.emit('tile.token_created', {'source': source, 'token': token,
            'cell': cell, 'occupants': selected, 'definition': effect['definition']}, cause)
