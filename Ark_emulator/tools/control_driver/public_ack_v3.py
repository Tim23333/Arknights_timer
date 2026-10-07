"""Same V2 ACK policy, with bounded reads of the actual owned event journal.

The driver only retains awaited-dialogue records and its finite ACK ledger.
Source identity is separately pinned; POLICY intentionally remains V2 because
submission clocks and public commands are unchanged.
"""
from copy import deepcopy


def integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(label + ' must be a strict integer')
    return value


def records(simulation, start=0):
    """Hold the idle executor boundary, read each original record exactly once."""
    session = simulation.session
    integer(start, 'event cursor')
    with session._lock:
        if session._advancing or session._atomic_depth:
            raise RuntimeError('Driver observations require an idle executor boundary')
        owned = session._events._records
        end = len(owned)
        if start > end:
            raise ValueError('Event cursor exceeds the actual boundary')
        for index in range(start, end):
            # Disk __getitem__ verifies the owned offset/hash and complete value.
            yield owned[index]


class PublicAckDriver:
    POLICY = 'external_dialogue_observation_plus_one_tick/v2'

    def __init__(self, simulation, state=None):
        self.simulation = simulation
        self.cursor = 0
        self.submitted = []
        if state is None:
            return
        if not isinstance(state, dict) or set(state) != {'policy', 'program', 'runtime', 'at', 'cursor', 'submitted'}:
            raise ValueError('Exact driver checkpoint fields required')
        if state['policy'] != self.POLICY or state['program'] != simulation.program.fingerprint or state['runtime'] != simulation.runtime_fingerprint:
            raise ValueError('Driver policy/program/runtime identity differs')
        if integer(state['at'], 'driver time') != simulation.session.time:
            raise ValueError('Driver clock differs')
        cursor = integer(state['cursor'], 'event cursor')
        if cursor != len(simulation.session._events._records):
            raise ValueError('Saved driver must consume the complete idle event boundary')
        submitted = state['submitted']
        if not isinstance(submitted, list):
            raise ValueError('Ack ledger must be an array')
        awaits = [event for event in records(simulation) if event['type'] == 'control.awaiting_ack']
        if len(submitted) != len(awaits):
            raise ValueError('Ack ledger does not cover actual waiting events')
        commands = simulation.export_replay()['commands']
        for item, event in zip(submitted, awaits):
            if not isinstance(item, dict) or set(item) != {'event', 'control', 'step', 'submitted_at', 'at'}:
                raise ValueError('Exact ack ledger fields required')
            for key in ('event', 'step', 'submitted_at', 'at'):
                integer(item[key], key, 1 if key == 'event' else 0)
            value = event['payload']
            if (item['event'] != event['id'] or item['control'] != value['control'] or item['step'] != value['step']
                    or not isinstance(item['control'], str) or not item['control'].startswith('control/')):
                raise ValueError('Ack ledger differs from actual observed control/step/event')
            if item['submitted_at'] < event['time'] or item['submitted_at'] > state['at'] or item['at'] != item['submitted_at'] + 1:
                raise ValueError('Ack submission/response clock differs')
            action = {'action': 'control_ack', 'control': item['control'], 'step': item['step']}
            matches = [row for row in commands if row['action'] == action and row['at'] == item['at'] and row['submitted_at'] == item['submitted_at']]
            if len(matches) != 1:
                raise ValueError('Ack absent or ambiguous in actual public replay ledger')
        if len({item['event'] for item in submitted}) != len(submitted):
            raise ValueError('Duplicate observed ack event')
        self.cursor = cursor
        self.submitted = deepcopy(submitted)

    def observe(self):
        sim = self.simulation
        for event in records(sim, self.cursor):
            if event['type'] != 'control.awaiting_ack':
                continue
            value = event['payload']
            eid = integer(event['id'], 'event ID', 1)
            step = integer(value['step'], 'ack step')
            if not isinstance(value['control'], str) or not value['control'].startswith('control/'):
                raise ValueError('Actual observed control instance required')
            if any(item['event'] == eid for item in self.submitted):
                raise ValueError('Duplicate observed event')
            at = sim.session.time + 1
            sim.submit({'action': 'control_ack', 'control': value['control'], 'step': step}, at=at)
            self.submitted.append({'event': eid, 'control': value['control'], 'step': step,
                                   'submitted_at': sim.session.time, 'at': at})
        # Like V2, commands emitted by submit belong to this closed boundary.
        self.cursor = len(sim.session._events._records)

    def advance_to(self, until):
        integer(until, 'end tick')
        if until < self.simulation.session.time:
            raise ValueError('Past tick')
        self.observe()
        while self.simulation.session.time < until:
            self.simulation.session.advance(1)
            self.observe()

    def checkpoint(self):
        if len(self.simulation.session._events._records) != self.cursor:
            raise ValueError('Observe the complete idle boundary before saving driver state')
        return {'policy': self.POLICY, 'program': self.simulation.program.fingerprint,
                'runtime': self.simulation.runtime_fingerprint, 'at': self.simulation.session.time,
                'cursor': self.cursor, 'submitted': deepcopy(self.submitted)}
