"""Pure, stateless aggregation of accepted game samples.

The service never reads process memory and never owns a last-good cache. It
preserves each producer's original frame and returns one replacement batch to
the publication hook. Current entity layouts exclude roster/history entries.
"""
from __future__ import annotations

import copy
from collections.abc import Mapping

from ..contracts import contract_specs, public_contract_value
from ..field_policy import collection_record


_SPECS = contract_specs()
_INDEPENDENT = frozenset({'stage_global.gameTime', 'stage_global.fixedFrame',
                          'stage_global.stageName', 'stage_global.mapId', 'stage_global.map'})
_SUCCESS = frozenset({'current', 'static'})


def _mapping(value):
    return value if isinstance(value, Mapping) else {}


def _valid_record(record, policy, *, dynamic=False, frame=None):
    record = _mapping(record)
    if type(record.get('generation')) is not int or record.get('generation') != policy.generation:
        return False
    if record.get('collectionState') not in _SUCCESS:
        return False
    if dynamic:
        return (record.get('collectionState') == 'current'
                and type(record.get('sourceFrame')) is int
                and (frame is None or record['sourceFrame'] == frame))
    return True


def _fallback_record(meta, policy, state='current'):
    """Whole-source evidence is allowed only when a producer explicitly accepted it."""
    meta = _mapping(meta)
    if (meta.get('collectionState') not in _SUCCESS
            or meta.get('policyGeneration') != policy.generation):
        return collection_record(None, meta.get('latestKnownFrame'), policy.generation,
                                 'unavailable', 'source_unavailable')
    return collection_record(meta.get('sourceFrame'), meta.get('latestKnownFrame'),
                             policy.generation, state, meta.get('reason', ''),
                             accepted_frame=meta.get('acceptedFrame'))


class StageGlobalStateService:
    """One invocation consumes source-owned, unfiltered canonical snapshots."""

    def build(self, reader_result, clock_payload, stage_payload, enemies_payload,
              characters_payload, policy, *, runtime_frame=None,
              frame_consistent=None, source_epoch=None):
        raw = _mapping(reader_result)
        meta = _mapping(raw.get('meta'))
        values = dict(_mapping(raw.get('values')))
        records = copy.deepcopy(dict(_mapping(raw.get('field_states'))))
        clock, stage = _mapping(clock_payload), _mapping(stage_payload)
        consistent = meta.get('frameConsistent', True) if frame_consistent is None else frame_consistent
        consistent = consistent is True
        frames = {item.get('sourceFrame') for item in records.values()
                  if isinstance(item, Mapping) and item.get('collectionState') == 'current'
                  and type(item.get('sourceFrame')) is int}
        if runtime_frame is None:
            runtime_frame = meta.get('runtimeFrame', next(iter(frames)) if len(frames) == 1 else None)
        if type(runtime_frame) is not int:
            runtime_frame = None
        for key in ('gameTime', 'fixedFrame'):
            target, source = f'stage_global.{key}', f'battle.{key}'
            source_record = _mapping(clock.get('fieldStates')).get(source)
            if source_record is not None:
                values[target] = clock.get(key)
                records[target] = copy.deepcopy(source_record)
        identity_id = 'stage_global.stageName'
        if not (values.get(identity_id) is not None
                and _valid_record(records.get(identity_id), policy)):
            stage_record = (_mapping(stage.get('fieldStates')).get('stage.stage')
                            or _fallback_record(stage.get('meta'), policy, 'static'))
            # A source discovered later can supply identity; a failed/old stage
            # cannot rescue unavailable reader data. Epochs are checked below.
            info = _mapping(stage.get('stage')) if _valid_record(stage_record, policy) else {}
            if info:
                values[identity_id] = {
                    'stageName': info.get('name', info.get('stageName')),
                    'stageId': info.get('stageId'), 'levelId': info.get('levelId')}
                records[identity_id] = copy.deepcopy(stage_record)
        for key, payload, domain in (('enemyLayout', enemies_payload, 'enemy'),
                                      ('allyLayout', characters_payload, 'character')):
            field_id = 'stage_global.' + key
            if policy.enabled(field_id):
                values[field_id], records[field_id] = self._layout(payload, domain, policy, runtime_frame)

        # Explicit epoch mismatches invalidate every source, not only runtime.
        # The owner still checks session identity at the atomic publication lock.
        inputs = (raw, clock, stage, _mapping(enemies_payload), _mapping(characters_payload))
        epochs = {source.get('source_epoch', _mapping(source.get('meta')).get('sourceEpoch'))
                  for source in inputs}
        epochs.discard(None)
        epoch_mismatch = (len(epochs) > 1 or
                          (source_epoch is not None and any(epoch != source_epoch for epoch in epochs)))
        result_values, result_records = {}, {}
        for spec in _SPECS:
            field_id = spec['id']
            incoming = _mapping(records.get(field_id))
            record = dict(incoming) if incoming else collection_record(
                None, meta.get('latestKnownFrame'), policy.generation, 'unavailable', 'read_failed')
            if not policy.enabled(field_id):
                record = collection_record(None, meta.get('latestKnownFrame'), policy.generation,
                                           'not_collected', 'not_collected')
            elif epoch_mismatch:
                record = collection_record(None, meta.get('latestKnownFrame'), policy.generation,
                                           'unavailable', 'source_changed')
            elif type(record.get('generation')) is not int or record.get('generation') != policy.generation:
                record = collection_record(None, meta.get('latestKnownFrame'), policy.generation,
                                           'unavailable', 'policy_changed')
            elif record.get('collectionState') not in _SUCCESS | {'historical', 'unavailable', 'not_collected'}:
                record = collection_record(None, meta.get('latestKnownFrame'), policy.generation,
                                           'unavailable', 'read_failed')
            elif not consistent and field_id not in _INDEPENDENT:
                record.update(collectionState='unavailable', reason='inconsistent_capture')
            elif record.get('collectionState') == 'historical':
                record.update(collectionState='unavailable', reason='source_unavailable')
            elif field_id not in _INDEPENDENT and record.get('collectionState') == 'static':
                record.update(collectionState='unavailable', reason='source_unavailable')
            elif (field_id not in _INDEPENDENT and record.get('collectionState') == 'current'
                  and not _valid_record(record, policy, dynamic=True, frame=runtime_frame)):
                record.update(collectionState='unavailable', reason='inconsistent_capture')
            good = record.get('collectionState') in _SUCCESS
            value = public_contract_value(field_id, values.get(field_id)) if good else None
            if good and value is None and record.get('reason') not in spec['null_reasons']:
                record.update(collectionState='unavailable', reason='read_failed')
            result_values[field_id] = value
            result_records[field_id] = record
        source_frames = {record.get('sourceFrame') for record in result_records.values()
                         if record.get('collectionState') in _SUCCESS}
        source_frames.discard(None)
        latest = [record.get('latestKnownFrame') for record in result_records.values()
                  if type(record.get('latestKnownFrame')) is int]
        batch_meta = {'sourceFrame': next(iter(source_frames)) if len(source_frames) == 1 else None,
                      'runtimeFrame': runtime_frame, 'latestKnownFrame': max(latest) if latest else None,
                      'frameConsistent': bool(consistent), 'policyGeneration': policy.generation}
        if isinstance(meta.get('configurationRevision'), str):
            batch_meta['configurationRevision'] = meta['configurationRevision']
        return {'values': result_values, 'field_states': result_records, 'batch_meta': batch_meta}

    def _layout(self, payload, domain, policy, runtime_frame):
        payload = _mapping(payload)
        meta = _mapping(payload.get('meta'))
        frame = meta.get('sourceFrame')
        available = (isinstance(payload.get('items'), list)
                     and meta.get('frameConsistent') is True and type(frame) is int
                     and meta.get('collectionState', 'current') != 'unavailable'
                     and meta.get('policyGeneration', policy.generation) == policy.generation
                     and (runtime_frame is None or runtime_frame == frame))
        if not available:
            return None, collection_record(None, meta.get('latestKnownFrame'), policy.generation,
                                            'unavailable', 'source_unavailable')
        result = []
        for item in payload['items']:
            item = _mapping(item)
            if (not isinstance(item.get('id'), str) or not item['id']
                    or (domain == 'enemy' and item.get('lifecycle') != 'active')
                    or (domain == 'character' and item.get('alive') is False)):
                continue
            row = {'id': item['id'], 'fieldStates': {}}
            states = _mapping(item.get('fieldStates'))

            def leaf(source_key, output_key, value, dynamic=False):
                field_id = f'{domain}.{source_key}'
                evidence = states.get(field_id)
                if policy.enabled(field_id) and _valid_record(evidence, policy, dynamic=dynamic, frame=frame):
                    if value is not None:
                        row[output_key] = copy.deepcopy(value)
                    row['fieldStates'][field_id] = copy.deepcopy(evidence)

            leaf('name', 'name', item.get('name'))
            if domain == 'enemy':
                # The current collection establishes membership; individual
                # position/action leaves still require actual successful reads.
                row['lifecycle'] = 'active'
                leaf('eid', 'enemyId', item.get('enemyId'))
                leaf('pos', 'position', item.get('position'), True)
                leaf('precise_pos', 'precisePosition', item.get('precisePosition'), True)
                action = _mapping(item.get('action'))
                leaf('action_state', 'rawStateCode', action.get('state_id'), True)
                leaf('action_state', 'stateName', action.get('state_name'), True)
            else:
                leaf('cid', 'characterId', item.get('characterId'))
                leaf('kind', 'kind', item.get('kind'))
                position = _mapping(item.get('position'))
                grid = {'row': position.get('row'), 'col': position.get('col')}
                if all(type(value) is int for value in grid.values()):
                    leaf('pos', 'grid', grid, True)
                direction = item.get('direction')
                if type(direction) is int and 0 <= direction <= 3:
                    leaf('direction', 'direction', direction, True)
                    leaf('direction', 'directionName', ('上', '右', '下', '左')[direction], True)
            result.append(row)
        return result, collection_record(frame, meta.get('latestKnownFrame'), policy.generation,
                                          'current', accepted_frame=meta.get('acceptedFrame', frame))
