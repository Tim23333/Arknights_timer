    def remove(self, uid):
        field = self.current(uid)
        if field is None:
            return
        with self.ctx.session.atomic():
            data = self.state()
            owner = data.get('packet_dispatch')
            tasks = []
            if field.get('task') is not None:
                tasks.append(field['task'])
            if owner is not None and owner['uid'] == uid:
                tasks.append(owner['task'])
                data['packet_dispatch'] = None
            # Cancel only identities owned by this field, never inspect/execute
            # arbitrary queued callbacks or erase journal evidence.
            pending = self.ctx.session.scheduler._tasks
            for task in tasks:
                if task in pending:
                    self.ctx.session.cancel(task)
            data['fields'][uid].update(active=False, generation=field['generation'] + 1,
                task=None, task_seq=None, due=None, packet_chain=None)
            data['packet_queue'] = [key for key in data.get('packet_queue', []) if key != uid]
            self.save(data)
            if not self.ctx.state().get('finished'):
                self._schedule_dispatch()

