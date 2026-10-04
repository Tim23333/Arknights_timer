"""Explicit headless input adapter; acknowledgements enter only via submit()."""
from copy import deepcopy


def integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(label + ' must be a strict integer')
    return value


class PublicAckDriver:
    POLICY = 'external_dialogue_observation_plus_one_tick/v1'

    def __init__(self, simulation, state=None):
        self.simulation = simulation
        if state is None:
            self.cursor = 0
            self.submitted = []
        else:
            if state.get('policy') != self.POLICY:
                raise ValueError('Ack policy identity differs')
            if state.get('program') != simulation.program.fingerprint or state.get('runtime') != simulation.runtime_fingerprint:
                raise ValueError('Ack state simulation identity differs')
            if state.get('at') != simulation.session.time:
                raise ValueError('Ack state clock differs')
            self.cursor = integer(state['cursor'], 'event cursor')
            self.submitted = deepcopy(state['submitted'])
            if not isinstance(self.submitted, list):
                raise ValueError('Submitted ack ledger must be an array')
            record = simulation.export_replay()['commands']
            for item in self.submitted:
                integer(item['event'], 'event ID', 1)
                integer(item['step'], 'ack step')
                matches = [row for row in record if row['at'] == item['at'] and row['submitted_at'] == item['submitted_at']
                           and row['action'] == {'action':'control_ack','control':item['control'],'step':item['step']}]
                if len(matches) != 1:
                    raise ValueError('Saved ack absent or ambiguous in actual replay ledger')
        count = sum(1 for _ in simulation.session._events.iter_records())
        if self.cursor > count:
            raise ValueError('Ack cursor exceeds saved journal')

    def observe(self):
        sim = self.simulation
        # The existing immutable incremental EventLog API avoids full snapshots.
        events = list(sim.session._events.iter_records(self.cursor))
        for event in events:
            self.cursor += 1
            if event['type'] != 'control.awaiting_ack':
                continue
            value = event['payload']
            eid = integer(event['id'], 'event ID', 1)
            step = integer(value['step'], 'ack step')
            if not isinstance(value['control'], str) or not value['control'].startswith('control/'):
                raise ValueError('Ack requires the observed actual control instance')
            if any(item['event'] == eid for item in self.submitted):
                raise ValueError('Observed ack event already submitted')
            at = sim.session.time + 1
            sim.submit({'action':'control_ack', 'control':value['control'], 'step':step}, at=at)
            self.submitted.append({'event':eid, 'control':value['control'], 'step':step,
                                   'submitted_at':sim.session.time, 'at':at})

    def advance_to(self, until):
        integer(until, 'end tick')
        if until < self.simulation.session.time:
            raise ValueError('Cannot drive to a past tick')
        self.observe()
        while self.simulation.session.time < until:
            self.simulation.session.advance(1)
            self.observe()

    def checkpoint(self):
        return {'policy':self.POLICY, 'program':self.simulation.program.fingerprint,
                'runtime':self.simulation.runtime_fingerprint, 'at':self.simulation.session.time,
                'cursor':self.cursor, 'submitted':deepcopy(self.submitted)}
