    def bind_buff(self, source, cast_id, target, instance):
        if instance is None:
            return
        cast = self._active(source, cast_id)
        if cast is None:
            raise ValueError('Cast-bound buff requires an active owned cast')
        row = {'target': self.ctx.session.world.resolve(target), 'instance': instance}
        for other in self.ctx.get(source, ('runtime', 'casts'), {}).values():
            if other['id'] != cast_id and row in other.get('owned_buffs', []):
                raise ValueError('Buff lease cannot be shared across active casts')
        owned = cast.setdefault('owned_buffs', [])
        if row not in owned:
            owned.append(row)
            self.ctx.set(source, ('runtime', 'casts', cast_id), cast)

    def _release_cast_buffs(self, source, cast):
        for row in cast.get('owned_buffs', []):
            self.ctx.buffs.remove(row['target'], row['instance'])

    def channel_started(self, source, cast_id):
        cast = self._active(source, cast_id)
        if cast is None or 'pending_channels' not in cast:
            raise ValueError('Owned channel requires explicit wait_for_channels')
        cast['pending_channels'] += 1
        self.ctx.set(source, ('runtime', 'casts', cast_id), cast)

    def channel_finished(self, source, cast_id):
        cast = self._active(source, cast_id)
        if cast is None:
            return
        if cast.get('pending_channels', 0) < 1:
            raise ValueError('Channel completion has no pending owner')
        cast['pending_channels'] -= 1
        self.ctx.set(source, ('runtime', 'casts', cast_id), cast)
        if cast.get('finish_requested') and not cast['pending_channels'] and not cast.get('pending_projectiles', 0):
            self.finish(self.ctx.session, {'source': source, 'cast': cast_id})

