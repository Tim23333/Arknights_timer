    def _owned_callback(self, task, task_seq, due, phase):
        # Actual Session dispatch identity, not a caller-copied payload, owns
        # execution. Direct/manual or duplicated scheduled invocations are stale.
        key = self.ctx.session._active_key
        return (task is not None and key is not None and self.ctx.session.time == due
                and key[1] == self.ctx.session.scheduler.rank(phase) and key[3] == task_seq)

    def pulse(self, session, payload):
        with session.atomic():
            field = self.current(payload['uid'])
            if (field is None or not field['active'] or field['generation'] != payload['generation']
                    or field.get('packet_chain') is not None or payload.get('sequence') != field['sequence']
                    or not self._owned_callback(field['task'], field.get('task_seq'), field['due'], 0)):
                return
            if self.ctx.state().get('finished'):
                self.remove(field['uid'])
                return
            members = self.members(field)
            data = self.state()
            data['fields'][field['uid']].update(task=None, task_seq=None, due=None,
                sequence=field['sequence'] + 1,
                packet_chain={'token': None, 'generation': field['generation'],
                    'sequence': field['sequence'], 'members': members, 'cursor': 0})
            self.save(data)
            event = self.ctx.emit('field.triggered', {'source': None, 'field_uid': field['uid'],
                'cell': field['cell'], 'sequence': field['sequence'], 'members': members})
            live = self.current(field['uid'])
            if (live is None or not live['active'] or live['generation'] != field['generation']
                    or live.get('packet_chain') is None or self.ctx.state().get('finished')):
                if self.ctx.state().get('finished'):
                    self._stop_all()
                return
            data = self.state()
            data['fields'][field['uid']]['packet_chain']['token'] = event
            data.setdefault('packet_queue', []).append(field['uid'])
            self.save(data)
            self._schedule_dispatch()

    def _schedule_dispatch(self):
        data = self.state()
        if data.get('packet_dispatch') is not None or not data.get('packet_queue'):
            return
        if self.ctx.state().get('finished'):
            self._stop_all()
            return
        uid = data['packet_queue'][0]
        field = data['fields'][uid]
        chain = field['packet_chain']
        now = self.ctx.session.time
        # One global FIFO; a later phase leaves the complete current-stage
        # reaction/ability/delay0 closure to the existing scheduler naturally.
        previous = data.get('packet_phase', self.ctx._base_effect_phase)
        if data.get('packet_frame') != now:
            previous = self.ctx._base_effect_phase
        active = self.ctx.session._active_key
        phase = max(previous, self.ctx._base_effect_phase,
                    active[1] if active is not None else self.ctx._base_effect_phase) + 1
        task_seq = self.ctx.session.scheduler._next_seq
        payload = {'uid': uid, 'generation': chain['generation'], 'token': chain['token'],
                   'cursor': chain['cursor']}
        task = self.ctx.session.schedule('domain.field.packet', payload, now, phase=phase)
        data.update(packet_frame=now, packet_phase=phase, packet_dispatch={**payload,
            'task': task, 'task_seq': task_seq, 'due': now, 'phase': phase})
        self.save(data)

    def packet(self, session, payload):
        with session.atomic():
            data = self.state()
            owner = data.get('packet_dispatch')
            if (owner is None or any(payload.get(key) != owner[key]
                    for key in ('uid', 'generation', 'token', 'cursor')) or
                    not self._owned_callback(owner['task'], owner['task_seq'], owner['due'], owner['phase'])):
                return
            data['packet_dispatch'] = None
            self.save(data)
            # A preceding legal callback may have changed objective resources.
            # Resolve that terminal state before permitting another damage packet.
            self.ctx.lifecycle.tick(session)
            if self.ctx.state().get('finished'):
                self._stop_all()
                return
            field = self.current(owner['uid'])
            chain = field.get('packet_chain') if field is not None else None
            if (field is None or not field['active'] or chain is None or
                    field['generation'] != owner['generation'] or chain['token'] != owner['token']):
                self._discard_chain(owner['uid'])
                self._schedule_dispatch()
                return
            members = chain['members']
            effects = field['profile']['effects']
            size = len(members) * len(effects)
            if chain['cursor'] < size:
                index = chain['cursor']
                ref = members[index % len(members)]
                effect = effects[index // len(members)]
                # Every individual packet sees live field/membership/availability
                # after all previous lower-stage callbacks have executed.
                if ref in self.members(field):
                    request = thaw(effect)
                    request['origin'] = {**field['profile']['origin'], **request.get('origin', {}),
                        'field_uid': field['uid'], 'cell': field['cell'],
                        'trigger_sequence': chain['sequence']}
                    self.ctx.effects.execute(None, [ref], request, cause=chain['token'])
                live = self.current(field['uid'])
                if self.ctx.state().get('finished'):
                    self._stop_all()
                    return
                if (live is None or not live['active'] or live['generation'] != field['generation']
                        or live.get('packet_chain') is None):
                    self._discard_chain(field['uid'])
                    self._schedule_dispatch()
                    return
                data = self.state()
                data['fields'][field['uid']]['packet_chain']['cursor'] += 1
                self.save(data)
                # Even the last damage packet has a completion task at a later
                # stage; callbacks may remove/finish before next-clock sampling.
                self._schedule_dispatch()
                return
            self._discard_chain(field['uid'])
            self.plan(field['uid'], 'next')
            self._schedule_dispatch()

    def _discard_chain(self, uid):
        data = self.state()
        if uid in data['fields']:
            data['fields'][uid]['packet_chain'] = None
        data['packet_queue'] = [key for key in data.get('packet_queue', []) if key != uid]
        self.save(data)

    def _stop_all(self):
        for uid, field in self.state()['fields'].items():
            if field['active']:
                self.remove(uid)
