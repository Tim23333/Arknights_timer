"""Declared finite impact chains; one owned projectile and one waiting cast.

No content IDs or native enemy constants live in this module. Selection reads
current candidates at the actual impact anchor. Every future callback is tied
to an actual issued task, and full instance proofs survive public checkpoints.
"""
from collections.abc import Mapping
from contextlib import contextmanager
import math
from ark_sim.contracts import thaw, digest


def validate(spec, projectile):
    required = {'selector', 'maximum_targets', 'attenuation', 'selection_origin',
                'no_repeat', 'lifetime', 'scale_fields'}
    if not isinstance(spec, Mapping) or set(spec) != required:
        raise ValueError('Finite projectile chain requires exact declared fields')
    if not isinstance(spec['selector'], str) or not spec['selector']:
        raise ValueError('Chain requires an exact current next-selector reference')
    if type(spec['maximum_targets']) is not int or not 1 <= spec['maximum_targets'] <= 64:
        raise ValueError('Chain requires a finite positive target bound up to 64')
    if type(spec['attenuation']) not in (int, float) or not math.isfinite(spec['attenuation']) or not 0 < spec['attenuation'] <= 1:
        raise ValueError('Chain attenuation requires a finite positive ratio at most one')
    if spec['selection_origin'] != 'impact_position' or spec['no_repeat'] is not True or spec['lifetime'] != 'whole_chain':
        raise ValueError('Chain requires actual impact origin, no repetitions and whole-chain lifetime')
    allowed = [('scale',), ('health_effect', 'scale'),
               ('element_effect', 'parameters', 'attack_scale')]
    paths = spec['scale_fields']
    if not isinstance(paths, (list, tuple)) or not paths or len(paths) > 3:
        raise ValueError('Chain requires bounded explicit numeric packet scale paths')
    if any(not isinstance(p, (list, tuple)) or tuple(p) not in allowed for p in paths) or len({tuple(p) for p in paths}) != len(paths):
        raise ValueError('Chain numeric scaling path is not a declared damage/EP scale')
    if (projectile['max_hits'] != 1 or projectile['can_hit_same_target'] is not False or
            projectile['stop_after_max'] is not True or projectile['stop_after_first'] is not False or
            projectile['collision'].get('allow_other_targets', False) or
            projectile['lifecycle']['hit_on_reach'] is not True or
            projectile['lifecycle']['finish_on_reach'] is not True):
        raise ValueError('Chain legs require one captured target and one actual reach impact')


class FiniteProjectileChains:
    def __init__(self, projectiles):
        self.projectiles = projectiles
        self.ctx = projectiles.ctx
        self._owned_hits = []

    def _packet(self, x, multiplier):
        packet = thaw(x['chain']['base_effect'])
        for path in self.projectiles._definition(x)['chain']['scale_fields']:
            parent = packet
            for key in path[:-1]:
                if not isinstance(parent, dict) or key not in parent:
                    raise ValueError('Chain declared scale path missing from actual packet')
                parent = parent[key]
            value = parent.get(path[-1])
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError('Chain packet scale must be a finite nonnegative number')
            parent[path[-1]] = value * multiplier
        return packet

    def initialize(self, x, definition):
        validate(definition['chain'], definition)
        task = self.ctx.session._active_task
        if task is None or task['kind'] != 'domain.ability.effect' or task['payload'].get('source') != x['source'] or task['payload'].get('cast') != x['cast'].get('id'):
            raise ValueError('Chain launch requires an actual owned public cast effect task')
        active = self.ctx.get(x['source'], ('runtime', 'casts'), {}).get(x['cast']['id'])
        if (not active or task['id'] not in active['tasks'] or active['ability'] != x['ability']['id'] or
                task['at'] != self.ctx.session.time or task['phase'] != self.ctx.effect_phase):
            raise ValueError('Chain launch differs from its current owned cast generation')
        def declared_packets(value):
            if isinstance(value, Mapping):
                packet = thaw(value)
                projectile = packet.pop('projectile_definition', None)
                if packet.get('op') == 'elemental_attack':
                    projectile = packet['health_effect'].pop('projectile_definition', projectile)
                if projectile == definition['id']:
                    yield packet
                for child in value.values():
                    yield from declared_packets(child)
            elif isinstance(value, (list, tuple)):
                for child in value:
                    yield from declared_packets(child)
        if x['effect'] not in list(declared_packets(task['payload']['effect'])):
            raise ValueError('Chain packet is not declared by the actual owned effect task')
        x['chain'] = {'hop': 0, 'multiplier': 1, 'visited': [], 'base_effect': thaw(x['effect']),
                      'base_cast': thaw(x['cast']), 'history': [], 'pending': None,
                      'launch_source': self.ctx.capture_view(x['source']),
                      'launch_target': self.ctx.capture_view(x['trace_target']),
                      'launch_task': thaw(task), 'step_task': None, 'expire_task': None,
                      'next_task': None, 'proof_event': None}
        self._packet(x, 1)
        event = self.ctx.emit('projectile.chain.launched', {
            'projectile': x['id'], 'definition': definition['id'], 'source': x['source'],
            'target': x['trace_target'], 'declared': thaw(definition['chain']),
            'source_view': x['chain']['launch_source'], 'target_view': x['chain']['launch_target'],
            'cast': x['chain']['base_cast'], 'ability': thaw(x['ability']),
            'packet': x['chain']['base_effect'], 'launch_task': thaw(task),
            'start': thaw(x['start']), 'born': x['born'], 'expires': x['expires'],
            'quantum': self.ctx.session.quantum, 'program': self.ctx.program.fingerprint,
            'random': self.ctx.session.random.snapshot()}, x['cause'])
        x['chain']['launch_event'] = event

    def issued(self, x, job, role):
        if 'chain' not in x:
            return
        task = next(thaw(t) for t in self.ctx.session.scheduler.pending if t['id'] == job)
        event = self.ctx.emit('projectile.chain.task.issued', {
            'projectile': x['id'], 'hop': x['chain']['hop'], 'role': role, 'task': task,
            'launch_event': x['chain']['launch_event'],
            'clock': {'time': self.ctx.session.time, 'next_id': job,
                      'next_seq': task['seq'], 'phase': self.ctx.effect_phase}}, x['chain']['launch_event'])
        x['chain'][role + '_task'] = {'task': task, 'issued_event': event}

    def seal(self, x):
        if 'chain' not in x:
            return
        record = thaw(x)
        record['chain'].pop('proof_event', None)
        event = self.ctx.emit('projectile.chain.state', {'projectile': x['id'], 'record': record,
            'fingerprint': digest(record), 'time': self.ctx.session.time,
            'random': self.ctx.session.random.snapshot()}, x['chain']['launch_event'])
        x['chain']['proof_event'] = event
        self.projectiles._put(x)

    def check_task(self, x, payload, role):
        if 'chain' not in x:
            return
        lease = x['chain'].get(role + '_task')
        task = self.ctx.session._active_task
        if not lease or task is None or thaw(task) != lease['task'] or thaw(payload) != task['payload'] or task['at'] != self.ctx.session.time:
            raise ValueError('Chain callback has no matching actual owned task lease')
        events = self.ctx.session._events._records
        issued = events[lease['issued_event'] - 1]
        if issued['type'] != 'projectile.chain.task.issued' or thaw(issued['payload']['task']) != lease['task'] or issued['payload']['projectile'] != x['id']:
            raise ValueError('Chain callback task differs from actual issuance lineage')

    @contextmanager
    def hit(self, x, target):
        if 'chain' not in x:
            yield
            return
        role='expire' if self.ctx.session._active_task and self.ctx.session._active_task['kind']=='domain.projectile.expire' else 'step'
        self.check_task(x, self.ctx.session._active_task['payload'] if self.ctx.session._active_task else {}, role)
        if target != x['trace_target'] or target in x['chain']['visited'] or x['chain']['pending'] is not None:
            raise ValueError('Chain impact requires the current captured unvisited target')
        token = {'projectile': x['id'], 'hop': x['chain']['hop'], 'target': target,
                 'active_task': self.ctx.session._active_task['id']}
        self._owned_hits.append(token)
        try:
            yield
        finally:
            assert self._owned_hits.pop() is token

    def impact(self, x, definition, target, hit_event):
        expected = {'projectile': x['id'], 'hop': x['chain']['hop'], 'target': target,
                    'active_task': self.ctx.session._active_task['id'] if self.ctx.session._active_task else None}
        if not self._owned_hits or self._owned_hits[-1] != expected:
            raise ValueError('Chain impact requires the actual owned hit execution scope')
        event = self.ctx.session._events._records[hit_event - 1]
        if (event['type'] != 'projectile.hit' or event['time'] != self.ctx.session.time or
                event['payload']['projectile'] != x['id'] or event['payload']['target'] != target):
            raise ValueError('Chain impact differs from its actual health/EP hit event')
        chain = x['chain']
        chain['visited'].append(target)
        row = {'hop': chain['hop'], 'target': target, 'multiplier': chain['multiplier'],
               'impact': thaw(x['position']), 'at': self.ctx.session.time, 'hit_event': hit_event,
               'source': self.ctx.capture_view(x['source']), 'target_view': self.ctx.capture_view(target),
               'permission_task': thaw(chain['step_task']), 'random': self.ctx.session.random.snapshot()}
        chain['history'].append(row)
        if len(chain['visited']) >= definition['chain']['maximum_targets'] or self.ctx.session.time >= x['expires']:
            return False
        chain['pending'] = row
        job = self.ctx.session.schedule('domain.projectile.chain.next',
            {'projectile': x['id'], 'hop': chain['hop'], 'hit_event': hit_event},
            self.ctx.session.time + 1, phase=self.ctx.effect_phase)
        x['jobs'].append(job)
        self.issued(x, job, 'next')
        self.seal(x)
        return True

    def _select(self, x, definition, anchor):
        selector_id = definition['chain']['selector']
        selector, source, candidates = self.ctx.spatial._candidate_input(x['source'], selector_id)
        source = thaw(source)
        source['components'].setdefault('spatial', {})['position'] = thaw(anchor)
        excluded = set(x['chain']['visited'])
        radius=selector['region']['radius']
        candidates = [e for e in candidates if e['id'] not in excluded and self.ctx.selectable(e['id']) and self.ctx.effect_target_available(e['id']) and e['components'].get('spatial',{}).get('position') is not None and math.hypot(e['components']['spatial']['position']['row']-anchor['row'],e['components']['spatial']['position']['col']-anchor['col'])<=radius]
        ids = self.ctx.provider(selector.get('provider', 'ark.selector.grid'),
            {'source': source, 'candidates': candidates, 'region': thaw(selector.get('region', {}))}, selector.get('parameters', {}))
        allowed = {e['id'] for e in candidates}
        if not isinstance(ids, (list, tuple)) or any(type(ref) is not int or ref not in allowed for ref in ids):
            raise ValueError('Chain selector returned an undeclared or repeated candidate')
        eligible = []
        for ref in ids:
            if selector.get('exclude_abnormal_flags'):
                from .selection import DEFAULT_STATE
                if set(selector['exclude_abnormal_flags']) & set(self.ctx.spatial.selection_state(ref, DEFAULT_STATE)['abnormal_flags']):
                    self.ctx.emit('projectile.chain.candidate.rejected', {'projectile': x['id'], 'target': ref, 'reason': 'excluded_abnormal_flag'})
                    continue
            if not self.ctx.spatial.available(x['source'], ref, selector, x['ability'], x['effect'], observable=True):
                continue
            spec = selector.get('eligibility')
            if spec:
                states = {'source': self.ctx.spatial.selection_state(x['source'], spec['parameters']['defaults']),
                          'candidate': self.ctx.spatial.selection_state(ref, spec['parameters']['defaults'])}
                inputs = {'source': source, 'candidate': self.ctx.entity(ref),
                    'selector': {**thaw(selector), 'healing': False}, 'parameters': thaw(spec['parameters']),
                    'selection_states': states}
                if spec.get('include_candidate_tile'):
                    from ark_sim.domains.movement import project_cell
                    cell = project_cell(self.projectiles._position(ref))
                    if not self.ctx.spatial.grid.inside(*cell):
                        raise ValueError('Chain candidate tile requires an inside-map current cell')
                    inputs['candidate_spatial_tile'] = {'cell': {'row': cell[0], 'col': cell[1]}, 'tile': self.ctx.spatial.grid.tile(*cell)}
                decision = self.ctx.calc('targeting.eligibility', inputs, source=x['source'], target=ref, rule_id=spec['rule'])
                if not isinstance(decision, dict) or set(decision) != {'accepted', 'reason'} or type(decision['accepted']) is not bool:
                    raise ValueError('Chain eligibility requires strict current accepted/reason')
                if not decision['accepted']:
                    self.ctx.emit('projectile.chain.candidate.rejected', {'projectile': x['id'], 'target': ref, 'reason': decision['reason']})
                    continue
            eligible.append(ref)
        scores={}
        for ref in eligible:
            position=self.projectiles._position(ref)
            distance=math.hypot(position['row']-anchor['row'],position['col']-anchor['col'])
            candidate=self.ctx.entity(ref)
            scores[str(ref)]=self.ctx.calc('targeting.score',{'candidate':candidate,'source':source,
                'distance':distance,'tags':[{'tag':tag} for tag in candidate['tags']],'states':{}},
                source=x['source'],target=ref,ability=x['ability'],effect=x['effect'],extra={'healing':False,'health_ratio':1})
        samples=[]
        if selector.get('ordering')=='random' and eligible:
            stream=selector.get('parameters',{}).get('random_stream')
            if not stream:raise ValueError('Chain random ordering requires a declared RNG stream')
            samples=[{'value':self.ctx.session.random.sample(stream)}]
        selected=self.ctx.calc('targeting.selection',{'candidates':[self.ctx.entity(ref) for ref in eligible],
            'scores':scores,'samples':samples,'limits':{'count':1}},source=x['source'],ability=x['ability'],effect=x['effect'],extra={'ordering':selector.get('ordering')})
        if not isinstance(selected,(list,tuple)) or len(selected)>1 or any(ref not in eligible for ref in selected):
            raise ValueError('Chain selection returned an undeclared current eligible target')
        chosen=selected[0] if selected else None
        self.ctx.emit('projectile.chain.selection', {'projectile': x['id'], 'anchor': thaw(anchor),
            'source': source, 'candidate_views': [self.ctx.capture_view(ref) for ref in ids],
            'eligible': eligible, 'excluded': sorted(excluded), 'selected': chosen,
            'time': self.ctx.session.time, 'random': self.ctx.session.random.snapshot()}, x['chain']['pending']['hit_event'])
        return chosen

    def next(self, session, payload):
        with session.atomic():
            x = self.projectiles._get(payload['projectile'])
            if not x or x['state'] != 'active':
                raise ValueError('Chain next callback has no active owned projectile')
            self.check_task(x, payload, 'next')
            definition = self.projectiles._definition(x)
            row = x['chain']['pending']
            if row is None or payload != {'projectile': x['id'], 'hop': x['chain']['hop'], 'hit_event': row['hit_event']}:
                raise ValueError('Chain next callback differs from actual impact lineage')
            invalid = self.projectiles._invalid_policy(x, definition)
            # The hit target may have died because the actual health packet.
            # A successful impact still authorizes selection from its saved point.
            if invalid not in (None, 'target_invalid', 'target_hidden'):
                self.projectiles._finish(x, invalid)
                return
            if session.time >= x['expires'] or self.ctx.state().get('finished'):
                self.projectiles._finish(x, 'expired' if session.time >= x['expires'] else 'battle_terminal')
                return
            chosen = self._select(x, definition, row['impact'])
            if chosen is None:
                self.projectiles._finish(x, 'chain_no_target')
                return
            chain = x['chain']
            chain['hop'] += 1
            chain['multiplier'] = definition['chain']['attenuation'] ** chain['hop']
            chain['pending'] = None
            chain['next_task'] = None
            x['trace_target'] = chosen
            x['attachment_target'] = chosen
            x['start'] = thaw(row['impact'])
            x['position'] = thaw(row['impact'])
            x['last_target'] = self.projectiles._position(chosen)
            x['previous_target'] = thaw(x['last_target'])
            x['last_tick'] = session.time
            x['motion_state'] = {}
            x['effect'] = self._packet(x, chain['multiplier'])
            x['cast']['launch_target_snapshots'][str(chosen)] = self.ctx.capture_view(chosen)
            x['jobs'] = [job for job in x['jobs'] if job in {t['id'] for t in session.scheduler.pending}]
            self.projectiles._schedule_step(x, session.time + 1)
            self.seal(x)

    def validate_restored(self):
        events = self.ctx.session._events._records
        tasks = {t['id']: thaw(t) for t in self.ctx.session.scheduler.pending}
        expected_tasks = set()
        for x in self.projectiles._state()['instances'].values():
            if 'chain' not in x:
                continue
            definition = self.projectiles._definition(x)
            validate(definition['chain'], definition)
            chain = x['chain']
            proof = events[chain['proof_event'] - 1]
            record = thaw(x)
            record['chain'].pop('proof_event', None)
            if proof['type'] != 'projectile.chain.state' or proof['payload']['projectile'] != x['id'] or thaw(proof['payload']['record']) != record or proof['payload']['fingerprint'] != digest(record):
                raise ValueError('Restored chain differs from its actual full instance proof')
            launch = events[chain['launch_event'] - 1]
            if launch['type'] != 'projectile.chain.launched' or launch['payload']['declared'] != definition['chain'] or launch['payload']['program'] != self.ctx.program.fingerprint:
                raise ValueError('Restored chain declaration/program differs')
            if thaw(launch['payload']['source_view']) != chain['launch_source'] or thaw(launch['payload']['packet']) != chain['base_effect'] or thaw(launch['payload']['cast']) != chain['base_cast']:
                raise ValueError('Restored original source snapshot/packet/cast differs')
            visited = [r['target'] for r in chain['history']]
            if visited != chain['visited'] or len(set(visited)) != len(visited) or len(visited) > definition['chain']['maximum_targets']:
                raise ValueError('Restored chain actual hit history/repetition differs')
            for index, row in enumerate(chain['history']):
                hit = events[row['hit_event'] - 1]
                if hit['type'] != 'projectile.hit' or hit['time'] != row['at'] or hit['payload']['projectile'] != x['id'] or hit['payload']['target'] != row['target'] or hit['payload']['hit_count'] != index + 1 or row['multiplier'] != definition['chain']['attenuation'] ** index:
                    raise ValueError('Restored chain actual impact/scale lineage differs')
            if x['state'] == 'active':
                required=('expire', 'next' if chain['pending'] is not None else 'step')
                if any(not chain.get(role+'_task') or chain[role+'_task']['task']['id'] not in tasks for role in required):
                    raise ValueError('Restored active chain lost a required owned future task')
                if x['effect'] != self._packet(x, chain['multiplier']):
                    raise ValueError('Restored current packet scale differs from finite declaration')
                for role in ('step', 'expire', 'next'):
                    lease = chain.get(role + '_task')
                    if not lease or lease['task']['id'] not in tasks:
                        continue
                    task = lease['task']
                    issued = events[lease['issued_event'] - 1]
                    if tasks[task['id']] != task or issued['type'] != 'projectile.chain.task.issued' or thaw(issued['payload']['task']) != task or issued['payload']['clock']['next_id'] != task['id'] or issued['payload']['clock']['next_seq'] != task['seq'] or task['phase'] != self.ctx.effect_phase:
                        raise ValueError('Restored chain owned scheduled task differs')
                    expected_tasks.add(task['id'])
        for task in tasks.values():
            if task['kind'] == 'domain.projectile.chain.next' and task['id'] not in expected_tasks:
                raise ValueError('Restored chain next task has no actual finite owner')
