"""Attribute growth and layers delegate numeric results to rule contracts."""
from ark_sim.contracts.models import FrozenMapping, digest, thaw, freeze
from ark_sim.kernel._data import clone


class _ViewIdentity:
    """Identity comparison that also retains the immutable view."""
    __slots__ = ("view",)

    def __init__(self, view):
        self.view = view

    def __hash__(self):
        return id(self.view)

    def __eq__(self, other):
        return type(other) is _ViewIdentity and self.view is other.view


class AttributeSystem:
    def __init__(self, context):
        self.ctx = context
        self.cache = {}
        self._cache_requests = {}
        self._view_digests = {}
        self._cache_time = None
        self._cache_epoch = None
        context.session.register_atomic_participant('attributes.cache', self._capture_cache, self._rollback_cache)

    def _capture_cache(self):
        """Private trusted savepoint, distinct from untrusted public JSON."""
        active = self._cache_time == self.ctx.session.time and self._cache_epoch == self.ctx.session.cache_epoch
        rows = []
        if active:
            for key, result in self.cache.items():
                saved_live = key[1].view
                try:live = self.ctx.entity(saved_live['id'])
                except (KeyError,ValueError):continue
                # Stale World versions cannot be hit before or after this savepoint.
                if live is not saved_live:continue
                request = self._cache_requests.get(key)
                rows.append((key, result, request,
                    self._view_digests[key[1]]))
        return {'active':active, 'time':self._cache_time, 'rows':rows,
            'last_calculation_event_id':getattr(self.ctx, 'last_calculation_event_id', None)}

    def _rollback_cache(self, saved):
        # Kernel World/ledger/jobs are already restored. Their new immutable
        # World view objects must acquire the same authenticated causal entries.
        # No calculations, public restore calls, events, RNG, or IDs are consumed.
        self.cache, self._cache_requests, self._view_digests = {}, {}, {}
        self.ctx.last_calculation_event_id = saved['last_calculation_event_id']
        if not saved['active']:
            self._cache_time, self._cache_epoch = saved['time'], None
            return
        for key, result, request, saved_digest in saved['rows']:
            saved_live = key[1].view
            live = self.ctx.entity(saved_live['id'])
            if live['version'] != saved_live['version'] or self._view_digest(live) != saved_digest:
                raise ValueError('Atomic attribute cache World view differs from savepoint')
            value, cause = result
            if type(cause) is not int or not 1 <= cause <= len(self.ctx.session._events._records):
                raise ValueError('Atomic attribute cache cause was not restored')
            event = self.ctx.session._events._records[cause-1]
            if event['id'] != cause or event['type'] != 'calculation' or event['payload'].get('calculation_id') != 'attributes.effective':
                raise ValueError('Atomic attribute cache cause identity differs')
            entity = live if key[0].view is saved_live else key[0].view
            rebound = (_ViewIdentity(entity), _ViewIdentity(live), *key[2:])
            self.cache[rebound] = result
            if request is not None:self._cache_requests[rebound] = request
        self._cache_time, self._cache_epoch = self.ctx.session.time, self.ctx.session.cache_epoch

    def initialize(self, definition, components, instance_rules=None):
        attrs = components.setdefault("attributes", {"base": {}})
        attrs.setdefault("base", {})
        attrs.setdefault("modifiers", [])
        growth = definition.get("growth", attrs.get("growth", {}))
        prototype = {"definition_id": definition["id"], "components": components}
        owner_rules = {**definition.get("rules", {}), **(instance_rules or {})}
        for stat, spec in growth.items():
            attrs["base"][stat] = self.ctx.calc("attributes.growth", {
                "base": attrs["base"][stat], "level": spec["level"],
                "growth_parameters": spec.get("parameters", {})}, rule_id=spec.get("rule"),
                component=attrs.get("rules", {}), local=attrs.get("attribute_rules", {}).get(stat, {}),
                scope_extra={"owner": owner_rules},
                extra={"attribute": stat, "owner_definition": definition,
                       "owner": prototype, "source": prototype})

    def value(self, ref, stat, *, ability=None, effect=None, snapshot=None):
        if self.ctx.session._atomic_restore_failure:
            raise RuntimeError('Derived state rollback failed; restore a valid checkpoint before attribute evaluation')
        now, epoch = self.ctx.session.time, getattr(self.ctx.session, "cache_epoch", 0)
        if self._cache_time != now or self._cache_epoch != epoch:
            self.cache.clear()
            self._cache_requests.clear()
            self._view_digests.clear()
            self._cache_time, self._cache_epoch = now, epoch
        live = self.ctx.entity(ref)
        entity = snapshot if snapshot is not None else live
        # Caller-owned mutable historical dictionaries are never memoized.
        # Live views come from World's isolated snapshot API. Own deep-frozen
        # historical views can safely share identity across repeated reads.
        reusable = snapshot is None or snapshot is live or type(snapshot) is FrozenMapping
        scope_key = digest({"ability": ability or {}, "effect": effect or {}}) if ability or effect else None
        key = (_ViewIdentity(entity), _ViewIdentity(live), stat, scope_key, self.ctx.rules.fingerprint)
        if reusable and key in self.cache:
            value, original_event = self.cache[key]
            self.ctx.session.emit("calculation.cached", {"calculation_id": "attributes.effective",
                "owner": live.get("id"), "attribute": stat, "value": value,
                "source_event_id": original_event}, cause=original_event)
            return value
        component = entity["components"].get("attributes", {})
        base = component.get("base", {})
        if stat not in base:
            raise ValueError(f"attribute {stat!r} is absent on {entity['definition_id']}")
        modifiers = [m for m in component.get("modifiers", ()) if m["attribute"] == stat]
        layers = component["layers"] if "layers" in component else self.ctx.program.ruleset.get("attribute_layers", ())
        value = self.ctx.calc("attributes.effective", {"base": base[stat],
             "modifier_layers": modifiers, "order": [{"layer": layer} for layer in layers]}, owner=ref,
             component=component.get("rules", {}), local=component.get("attribute_rules", {}).get(stat, {}),
             ability=ability, effect=effect,
             extra={"owner": entity, "source": entity, "attribute": stat,
                    "attribute_request_scope": scope_key,
                    "attribute_view_digest": self._view_digest(entity),
                    "attribute_live_view_digest": self._view_digest(live),
                    "attribute_sample_time": entity.get("sampled_at", now)})
        if reusable:
            self.cache[key] = (value, getattr(self.ctx, "last_calculation_event_id", None))
            if entity is live:
                self._cache_requests[key] = freeze({'owner': live['id'], 'attribute': stat,
                    'ability': thaw(ability or {}), 'effect': thaw(effect or {})})
        return value

    def _view_digest(self, entity):
        key = _ViewIdentity(entity)
        if key not in self._view_digests:
            self._view_digests[key] = digest(entity)
        return self._view_digests[key]

    def checkpoint_cache(self):
        """Read-only causal records for current live-view cache entries.

        External historical snapshot object identities are not checkpoint state.
        A record binds a current World view and exact request scope to an existing
        calculation event; no query, calculation, or event is executed here.
        """
        session = self.ctx.session
        rows = []
        if self._cache_time == session.time and self._cache_epoch == session.cache_epoch:
            for key, request in self._cache_requests.items():
                live = self.ctx.entity(request['owner'])
                if key[0].view is not live or key[1].view is not live or key not in self.cache:
                    continue
                value, event_id = self.cache[key]
                event = session._events._records[event_id - 1]
                row = {**request, 'view_digest': digest(live), 'view_version': live['version'],
                    'value': thaw(value), 'source_event_id': event_id, 'event_digest': digest(event)}
                row['record_digest'] = digest(row)
                rows.append(row)
        rows.sort(key=lambda row: (row['owner'], row['attribute'], digest({'ability': row['ability'], 'effect': row['effect']})))
        return clone({'schema': 'ark-sim/attribute-cache/v1', 'time': session.time,
            'rules_fingerprint': self.ctx.rules.fingerprint, 'entries': rows})

    def restore_cache(self, data):
        """Validate persisted causes against current pure evaluation and ledger.

        Invalid records reject the checkpoint. Validation emits no events and
        does not consume actor, task, or random state. A missing cache extension
        remains the older checkpoint's safe cache-miss behavior.
        """
        if data is None:
            return
        data = clone(data)
        session = self.ctx.session
        if (not isinstance(data, dict) or set(data) != {'schema','time','rules_fingerprint','entries'}
                or data['schema'] != 'ark-sim/attribute-cache/v1'
                or type(data['time']) is not int or data['time'] != session.time
                or data['rules_fingerprint'] != self.ctx.rules.fingerprint
                or not isinstance(data['entries'], list)):
            raise ValueError('Invalid attribute cache checkpoint identity')
        planned, requests = {}, {}
        for row in data['entries']:
            if (not isinstance(row, dict) or set(row) != {'owner','attribute','ability','effect','view_digest','view_version','value','source_event_id','event_digest','record_digest'}
                    or type(row['owner']) is not int or row['owner'] < 1
                    or not isinstance(row['attribute'], str) or not row['attribute']
                    or not isinstance(row['ability'], dict) or not isinstance(row['effect'], dict)
                    or type(row['view_version']) is not int
                    or type(row['source_event_id']) is not int or row['source_event_id'] < 1
                    or row['record_digest'] != digest({key:value for key,value in row.items() if key != 'record_digest'})):
                raise ValueError('Invalid attribute cache record')
            live = self.ctx.entity(row['owner'])
            if live['version'] != row['view_version'] or digest(live) != row['view_digest']:
                raise ValueError('Attribute cache owner view changed')
            event_id = row['source_event_id']
            if event_id > len(session._events._records):
                raise ValueError('Attribute cache cause event absent')
            event = session._events._records[event_id - 1]
            if (event['id'] != event_id or event['time'] != session.time or event['type'] != 'calculation'
                    or digest(event) != row['event_digest']):
                raise ValueError('Attribute cache cause event identity differs')
            result = self._pure_request(row['owner'], row['attribute'], live, row['ability'], row['effect'])
            from .context import compact_trace
            trace = result.trace if self.ctx.program.ruleset.get('parameters', {}).get('trace_mode', 'compact') == 'full' else compact_trace(result.trace)
            payload = event['payload']
            if (payload.get('calculation_id') != 'attributes.effective'
                    or payload.get('rule_id') != result.rule_id
                    or digest(payload.get('trace')) != digest(trace)
                    or digest(payload.get('value')) != digest(result.value)
                    or digest(row['value']) != digest(result.value)):
                raise ValueError('Attribute cache value, context, or rule differs from current calculation')
            scope_key = digest({'ability': row['ability'], 'effect': row['effect']}) if row['ability'] or row['effect'] else None
            key = (_ViewIdentity(live), _ViewIdentity(live), row['attribute'], scope_key, self.ctx.rules.fingerprint)
            if key in planned:
                raise ValueError('Duplicate attribute cache request')
            planned[key] = (thaw(result.value), event_id)
            requests[key] = freeze({name: row[name] for name in ('owner','attribute','ability','effect')})
        self.cache, self._cache_requests = planned, requests
        self._cache_time, self._cache_epoch = session.time, session.cache_epoch

    def _pure_request(self, ref, stat, entity, ability, effect):
        component = entity['components'].get('attributes', {})
        base = component.get('base', {})
        if stat not in base:
            raise ValueError('Attribute cache stat is absent')
        layers = component.get('layers', self.ctx.program.ruleset.get('attribute_layers', ()))
        inputs = {'base':base[stat], 'modifier_layers':[m for m in component.get('modifiers', ()) if m['attribute'] == stat],
            'order':[{'layer':layer} for layer in layers]}
        scope = {'scenario':self.ctx.program.scenario.get('rules', {}), 'source':{}, 'target':{},
            'owner':self.ctx.definition_bindings(ref), 'component':component.get('rules', {}),
            'attribute_or_resource':component.get('attribute_rules', {}).get(stat, {}),
            'ability':ability.get('rules', {}), 'effect':effect.get('rules', {})}
        context = {'time':self.ctx.session.time, 'seconds':self.ctx.session.time*self.ctx.session.quantum,
            'quantum':self.ctx.session.quantum, 'source':entity, 'target':{}, 'owner':entity,
            'attribute_request_scope':digest({'ability':ability, 'effect':effect}) if ability or effect else None,
            'attribute_view_digest':self._view_digest(entity), 'attribute_live_view_digest':self._view_digest(entity),
            'attribute':stat, 'attribute_sample_time':entity.get('sampled_at', self.ctx.session.time)}
        return self.ctx.rules.evaluate('attributes.effective', inputs, scope=scope, context=context)

    def values(self, ref, *, ability=None, effect=None, snapshot=None):
        entity = snapshot or self.ctx.entity(ref)
        return {key: self.value(ref, key, ability=ability, effect=effect, snapshot=entity)
                for key in entity["components"].get("attributes", {}).get("base", {})}
