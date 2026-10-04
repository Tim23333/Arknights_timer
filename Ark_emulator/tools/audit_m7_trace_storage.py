"""Small read-only trace duplication audit; never changes engine trace policy."""
import argparse
from collections import Counter
from collections.abc import Mapping
import ctypes
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ark_sim import Compiler, Engine
from ark_sim.contracts import thaw
from ark_sim.contracts.models import FrozenMapping
from ark_sim.domains.context import compact_trace


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rss():
    if sys.platform != 'win32':
        return None
    class Counters(ctypes.Structure):
        _fields_ = [('cb', ctypes.c_ulong), ('PageFaultCount', ctypes.c_ulong)] + [
            (x, ctypes.c_size_t) for x in ('PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
            'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]
    value = Counters();value.cb = ctypes.sizeof(value)
    handle = ctypes.windll.kernel32.GetCurrentProcess
    handle.restype = ctypes.c_void_p
    if not ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.c_void_p(handle()), ctypes.byref(value), value.cb):
        return None
    return {'working_set_bytes': value.WorkingSetSize, 'private_commit_bytes': value.PagefileUsage}


def tree_counts(value):
    containers, entities, casts = 0, 0, 0
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, Mapping):
            containers += 1
            entities += 'definition_id' in item and 'components' in item
            casts += isinstance(item.get('id'), str) and item['id'].startswith('cast/')
            stack.extend(item.values())
        elif isinstance(item, (list, tuple)):
            containers += 1;stack.extend(item)
    return {'containers': containers, 'embedded_entities': entities, 'embedded_casts': casts}


def run(ticks):
    package = ROOT / 'validation/campaign/m7_00_10_frozen_exploratory_20261002.package.json'
    commands = ROOT / 'validation/campaign/m7_00_10_frozen_exploratory_20261002.commands.json'
    program = Compiler().compile(json.loads(package.read_bytes()))
    sim = Engine.create(program, seed=953816614)
    for entry in json.loads(commands.read_bytes()):
        action = dict(entry);at = action.pop('at');sim.submit(action, at=at)
    before = rss();sim.advance(ticks);after = rss()
    prefix_event_count = len(sim.session.events)
    # Separate bounded sensitivity probe, not an altered stage execution claim.
    # Make the actual selected Myrtle skill ready, then sample one real active
    # cast view. The stage-prefix journal statistics above remain unchanged.
    entity = sim.ctx.entity('myrtle')
    before_cast_shape = tree_counts(entity)
    sim.ctx.resources.adjust('myrtle', 'sp', value=24)
    sim.ctx.abilities.start('myrtle', 'ability/campaign_myrtle_s2')
    active = sim.ctx.entity('myrtle')
    cast_view = compact_trace({'inputs': {'source': active, 'target': active}, 'context': {'source': active}})
    active_cast_probe = {'method': 'actual selected skill start after explicit SP24 adjustment in isolated audit process',
        'not_stage_progress_evidence': True, 'entity_before': before_cast_shape, 'entity_active': tree_counts(active),
        'two_entity_inputs_compacted': tree_counts(cast_view),
        'compacted_json_bytes': len(json.dumps(cast_view, ensure_ascii=False, separators=(',', ':')).encode('utf8'))}
    counter, size, totals = Counter(), Counter(), Counter()
    biggest = []
    for event in sim.session.events[:prefix_event_count]:
        counter[event['type']] += 1
        raw_bytes = len(json.dumps(thaw(event), ensure_ascii=False, separators=(',', ':')).encode('utf8'))
        size[event['type']] += raw_bytes
        if event['type'] in ('calculation', 'policy'):
            shape = tree_counts(event['payload']);totals.update(shape)
            biggest.append({'event_type': event['type'], 'serialized_bytes': raw_bytes, **shape})
    entities = sim.session.world.entities()
    entity = next(x for x in entities if x['definition_id'].startswith('unit/') and 'components' in x)
    wrapped = compact_trace({'inputs': {'source': entity, 'target': entity}, 'context': {'source': entity}})
    assert type(entity) is FrozenMapping
    assert wrapped['inputs']['source'] is not entity
    assert wrapped['inputs']['source'] is not wrapped['inputs']['target']
    assert 'source_id' in wrapped['context'] and 'source' not in wrapped['context']
    return {'schema': 'ark-sim/m7-trace-storage-readonly-audit/v1', 'ticks': ticks,
        'package_sha256': sha(package), 'commands_sha256': sha(commands), 'runtime_fingerprint': sim.runtime_fingerprint,
        'readonly': True, 'does_not_change_core_or_trace_policy': True,
        'rss_before': before, 'rss_after': after, 'event_count': sum(counter.values()),
        'event_types': dict(counter), 'serialized_event_bytes_by_type': dict(size),
        'trace_embedded_shape_totals': dict(totals), 'largest_trace_events': sorted(biggest, key=lambda x: -x['serialized_bytes'])[:8],
        'controlled_active_cast_probe': active_cast_probe,
        'identity_probe': {'frozen_world_entity_reused_in_compact_inputs': False, 'two_equal_input_entities_share_container': False,
            'context_entity_collapsed_to_id': True, 'entity_tree_shape': tree_counts(entity)},
        'code_hashes': {f: sha(ROOT/f) for f in ('ark_sim/domains/context.py', 'ark_sim/kernel/_data.py',
            'ark_sim/kernel/events.py', 'ark_sim/rules/runtime.py')},
        'limitations': ['tiny prefix; not a full-run RSS explanation', 'serialized bytes are not retained Python heap bytes',
            'same semantic trace policy kept; no storage optimization is implemented here']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ticks', type=int, default=30)
    parser.add_argument('--output', type=Path, default=ROOT/'validation/campaign/m7_trace_storage_audit_20261002.json')
    args = parser.parse_args()
    if not 1 <= args.ticks <= 180:
        raise ValueError('audit prefix must stay between1 and180 ticks')
    value = run(args.ticks)
    args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'ticks': value['ticks'], 'events': value['event_count'], 'rss_after': value['rss_after'],
        'trace_shape': value['trace_embedded_shape_totals'], 'output': str(args.output)}))
