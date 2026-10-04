    def apply_cast_buff(self, source, cast_id, target, definition, stacks=1):
        """Apply/refresh and acquire a lease as one reversible boundary."""
        with self.ctx.session.atomic():
            source = self.ctx.session.world.resolve(source)
            if self._active(source, cast_id) is None:
                raise ValueError('Cast-bound buff requires an active owned cast')
            # Use the domain's normal expiry callbacks and events. Expired UIDs
            # disappear before refresh, so stale cast rows cannot adopt a new life.
            self.ctx.buffs.prune_expired()
            instance = self.ctx.buffs.apply(source, target, definition, stacks)
            self.bind_buff(source, cast_id, target, instance)
            return instance

    def bind_buff(self, source, cast_id, target, instance):
        if instance is None:
            return
        source = self.ctx.session.world.resolve(source)
        target = self.ctx.session.world.resolve(target)
        cast = self._active(source, cast_id)
        if cast is None:
            raise ValueError('Cast-bound buff requires an active owned cast')
        now = self.ctx.session.time
        live = next((buff for buff in self.ctx.get(target, ('buffs', 'instances'), [])
            if buff['id'] == instance and (buff['expires_at'] is None or now < buff['expires_at'])), None)
        if live is None:
            raise ValueError('Cast-bound buff requires a live target instance')
        row = {'target': target, 'instance': instance}
        for entity in self.ctx.session.world.entities():
            for other in entity['components'].get('runtime', {}).get('casts', {}).values():
                if entity['id'] == source and other['id'] == cast_id:
                    continue
                if row in other.get('owned_buffs', []):
                    raise ValueError('Buff lease cannot be shared across active casts')
        owned = cast.setdefault('owned_buffs', [])
        if row not in owned:
            owned.append(row)
            self.ctx.set(source, ('runtime', 'casts', cast_id), cast)

