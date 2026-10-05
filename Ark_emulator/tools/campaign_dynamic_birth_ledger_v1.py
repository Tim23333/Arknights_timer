"""Authenticate finite declared death descendants without filtering enemy actors.

This is a completion audit. Full snapshot/event/continuation equality remains
the evidence helper's separate responsibility and is never reduced here.
"""
from collections import Counter
from collections.abc import Mapping
from ark_sim.contracts import thaw, digest


def audit_births(program, actors, state, events):
    definitions = program.definitions
    native = Counter()
    for wave in program.scenario['timeline']['waves']:
        for fragment in wave['fragments']:
            for action in fragment['actions']:
                if action['kind'] == 'spawn':
                    native[action['spawn']['definition']] += action.get('count', 1)
    enemies = {actor['id']: actor for actor in actors if 'enemy' in actor['tags']}
    observed = Counter(actor['definition_id'] for actor in enemies.values())
    created, deaths, issued, born, slots, terminal = {}, {}, {}, {}, {}, None
    # Keep only calculations in the current tick for issuance references; this
    # does not change the original event stream or the later equality checks.
    current_tick, calculations = None, {}
    previous_id = -1
    for frozen in events:
        event = thaw(frozen)
        if event['id'] <= previous_id:
            raise ValueError('Birth audit requires the complete ordered event stream')
        previous_id = event['id']
        if current_tick != event['time']:
            current_tick, calculations = event['time'], {}
        kind, body = event['type'], event['payload']
        if kind == 'calculation':
            calculations[event['id']] = event
        elif kind == 'entity.created':
            actor_id = body['target']
            if actor_id in created:
                raise ValueError('Duplicate actual actor creation')
            created[actor_id] = (body['definition'], event['time'], event['id'])
        elif kind == 'entity.died':
            deaths[event['id']] = event
        elif kind == 'scenario.finished' and terminal is None:
            terminal = event['time']
        elif kind == 'descendant.issued':
            source, signature = body['source'], body['stamp']
            parent = enemies.get(source)
            if parent is None or signature['id'] != source or signature['definition'] != parent['definition_id']:
                raise ValueError('Descendant issuer is not an actual enemy parent')
            death = deaths.get(body['death_event'])
            if death is None or death['payload']['target'] != source or event.get('cause') != death['id'] or death['time'] != event['time']:
                raise ValueError('Descendant issuance lacks the actual same-tick causal death')
            declared = definitions[parent['definition_id']]['components']['lifecycle'].get('death_spawns')
            if declared is None or thaw(declared) != body['spec'] or digest(declared) != body['spec_digest']:
                raise ValueError('Descendant spec differs from compiled parent declaration')
            snapshot = body['snapshot']
            if snapshot['id'] != source or snapshot['definition_id'] != parent['definition_id']:
                raise ValueError('Descendant death snapshot identity differs')
            if terminal is not None:
                raise ValueError('Descendant issuance after actual terminal event')
            epoch = (source, signature['life'], signature['death'])
            if epoch in issued:
                raise ValueError('Duplicate descendant death epoch')
            issued[epoch] = event
            declared_rows = {action['key']: action for action in declared['actions']}
            if not body['rows']:
                raise ValueError('Issued descendant ledger must contain actual finite reservations')
            for row in body['rows']:
                action = declared_rows.get(row['action'])
                if action is None or type(row['index']) is not int or not 0 <= row['index'] < action['count'] or row['slot'] != action['key'] + '/' + str(row['index']):
                    raise ValueError('Descendant slot is outside its finite authored action')
                slot = (event['id'], row['slot'])
                if slot in slots:
                    raise ValueError('Duplicate descendant slot reservation')
                decision = calculations.get(row['decision_event'])
                timing = calculations.get(row['timing_event'])
                if decision is None or decision['payload']['calculation_id'] != 'lifecycle.death_emission' or decision['payload']['rule_id'] != action['rule'] or decision['payload']['source'] != source or decision['payload']['value'] is not True:
                    raise ValueError('Descendant slot lacks its actual declared decision calculation')
                if timing is None or timing['payload']['calculation_id'] != 'time.quantize' or type(timing['payload']['value']) is not int or timing['payload']['value'] < 0 or row['due'] != event['time'] + timing['payload']['value']:
                    raise ValueError('Descendant due differs from actual timing calculation')
                if row['status'] != 'pending' or row['child'] is not None:
                    raise ValueError('Descendant issuance must reserve a pending child')
                slots[slot] = {'issued': event, 'row': row, 'action': thaw(action)}
        elif kind == 'descendant.born':
            key = (body['issued_event'], body['slot'])
            reservation = slots.get(key)
            if reservation is None or key in born:
                raise ValueError('Actual descendant born without one unique issued slot')
            origin, row, action = reservation['issued'], reservation['row'], reservation['action']
            original = origin['payload']
            child = body['child']
            if event.get('cause') != origin['id'] or body['source'] != original['source'] or body['source_stamp'] != original['stamp'] or body['death_event'] != original['death_event']:
                raise ValueError('Actual descendant causal identity differs')
            if body['definition'] != action['definition'] or child not in enemies or enemies[child]['definition_id'] != action['definition']:
                raise ValueError('Actual descendant is not the declared real enemy actor')
            if event['time'] != row['due'] or child not in created or created[child][0] != action['definition'] or created[child][1] != event['time'] or created[child][2] >= event['id']:
                raise ValueError('Actual descendant creation/due event order differs')
            expected_member = original['membership'] if action['managed'] == 'inherit_source' else None
            if body['managed_membership'] != expected_member or body['route_inherited'] != bool(action['inherit_route'] and original['snapshot']['components']['spatial'].get('route')):
                raise ValueError('Actual descendant route or managed origin differs')
            lineage = enemies[child]['components']['runtime'].get('spawn_lineage')
            expected_lineage = {'source_stamp': original['stamp'], 'issued_event': origin['id'], 'death_event': original['death_event'], 'slot': row['slot'], 'parent': original['source']}
            if thaw(lineage) != expected_lineage or child in {entry['child'] for entry in born.values()}:
                raise ValueError('Actual descendant lineage or actor uniqueness differs')
            if terminal is not None:
                raise ValueError('Actual descendant born after the actual terminal event')
            born[key] = {'child': child, 'definition': action['definition'], 'event': event['id']}
    if set(slots) != set(born):
        raise ValueError('Declared descendant reservations are incomplete at final audit')
    descendants = Counter(entry['definition'] for entry in born.values())
    actual_native = Counter(actor['definition_id'] for actor in enemies.values()
                            if actor['id'] not in {entry['child'] for entry in born.values()})
    # No births are removed from observed totals: the partition must exactly
    # equal native authored population plus independently authenticated children.
    if actual_native != native or observed != native + descendants:
        raise ValueError('Actual enemy population differs from native plus authenticated descendants')
    for actor in enemies.values():
        if actor['id'] not in created or created[actor['id']][0] != actor['definition_id']:
            raise ValueError('Final enemy actor has no actual creation event')
        lineage = actor['components'].get('runtime', {}).get('spawn_lineage')
        if lineage is not None and actor['id'] not in {entry['child'] for entry in born.values()}:
            raise ValueError('Unaccounted actual descendant lineage')
    ledger = state.get('death_spawns', {})
    actual_keys = set()
    for epoch, event in issued.items():
        key = str(epoch[0]) + '/' + str(epoch[2])
        actual_keys.add(key)
        entry = ledger.get(key)
        if entry is None or entry['issued_event'] != event['id'] or entry['death_event'] != event['payload']['death_event'] or entry['stamp'] != event['payload']['stamp']:
            raise ValueError('Final death ledger differs from actual issuance')
        if len(entry['rows']) != len(event['payload']['rows']):
            raise ValueError('Final death ledger reservation count differs')
        for row in entry['rows']:
            actual = born.get((event['id'], row['slot']))
            if row['status'] != 'born' or actual is None or row['child'] != actual['child']:
                raise ValueError('Final death ledger lacks an actual completed child')
    if set(ledger) != actual_keys or state['timeline'].get('descendant_pending'):
        raise ValueError('Final descendant ledger has orphan entries or pending births')
    return {'schema': 'ark-sim/dynamic-birth-audit/v1', 'passed': True,
            'native_births': dict(native), 'authenticated_descendants': dict(descendants),
            'actual_births': dict(observed), 'actual_total': sum(observed.values()),
            'issued_death_epochs': len(issued), 'completed_descendant_slots': len(born),
            'terminal_tick': terminal, 'population_filtered': False}
