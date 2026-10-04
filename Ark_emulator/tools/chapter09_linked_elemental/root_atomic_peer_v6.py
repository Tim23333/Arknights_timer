"""Fresh joint-core nested rollback check with different runtime values."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT.parent / 'unpack_work/campaign_c9_foundation_v6_candidate'
sys.path.insert(0, str(RUNTIME)); sys.path.insert(1, str(ROOT))
from ark_sim import Compiler, Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import Intent, thaw


def main():
    expected = 'a8a22012563653020b3e7cce311128f3147f1cb88a1769f9abd8d9bb6d376c03'
    assert implementation_digest() == expected
    data = {'schemaVersion': 2, 'entities': [{'id': 'unit/root/cache', 'kind': 'entity', 'components': {
        'attributes': {'base': {'atk': 731, 'mres': 37, 'def': 191}},
        'spatial': {}}}], 'scenarioDraft': {'id': 'scene/root/cache', 'ruleset': 'ruleset/ark_standard',
        'map': {'rows': 1, 'cols': 2}, 'initialEntities': [{'definition': 'unit/root/cache', 'instanceAlias': 'owner'}]}}
    sim = Engine.create(Compiler().compile(data), seed=72615)
    sim.advance(7)
    sim.ctx.attributes.value('owner', 'atk'); sim.ctx.attributes.value('owner', 'mres')
    sim.session.random.sample('root_existing')
    before = sim.checkpoint()
    cause = next(e['id'] for e in reversed(sim.session.events)
                 if e['type'] == 'calculation' and e['payload'].get('calculation_id') == 'attributes.effective'
                 and e['payload'].get('trace', {}).get('context', {}).get('attribute') == 'mres')
    original = ValueError('outer root error')
    try:
        with sim.session.atomic():
            sim.ctx.set('owner', ('attributes', 'base', 'mres'), 43)
            sim.ctx.attributes.value('owner', 'mres')
            try:
                with sim.session.atomic():
                    sim.ctx.set('owner', ('attributes', 'base', 'atk'), 997)
                    sim.ctx.attributes.value('owner', 'atk')
                    sim.session.random.sample('root_rolled_back')
                    raise ValueError('inner root error')
            except ValueError:
                pass
            assert sim.ctx.attributes.value('owner', 'atk') == 731
            assert sim.ctx.attributes.value('owner', 'mres') == 43
            raise original
    except ValueError as caught:
        assert caught is original
    assert sim.checkpoint() == before
    restored = Engine.restore(sim.program, json.loads(json.dumps(before)))
    assert sim.ctx.attributes.value('owner', 'mres') == restored.ctx.attributes.value('owner', 'mres') == 37
    assert sim.session.events[-1]['cause'] == restored.session.events[-1]['cause'] == cause
    assert sim.checkpoint() == restored.checkpoint()
    session = sim.session; saved = session.checkpoint()
    primary = ValueError('root restore primary')
    session.register_atomic_participant('root_impure_restore', lambda: None,
        lambda state: session.emit('root.invalid.restore', {}))
    try:
        with session.atomic():
            raise primary
    except ValueError as caught:
        assert caught is primary and caught.__cause__ is not None
    else:
        raise AssertionError('impure restore succeeded')
    for action in (lambda: session.schedule('root.invalid', {}, session.time),
                   lambda: session.emit('root.invalid', {}),
                   lambda: sim.ctx.set('owner', ('attributes', 'base', 'atk'), 5),
                   lambda: session.random.sample('root.invalid')):
        try:
            action()
        except RuntimeError:
            pass
        else:
            raise AssertionError('failed restore allowed public mutation')
    session.restore(saved)
    assert session.checkpoint() == saved
    result = {'passed': True, 'core': expected, 'nested_rollback_complete_checkpoint_equal': True,
              'real_restored_cache_cause_equal': True, 'impure_restore_rejected_and_public_writes_blocked': True,
              'valid_restore_repairs': True, 'whole_stage_verified': False,
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    output = ROOT / 'validation/campaign/chapter09_foundation_v6/root_atomic_peer.json'
    assert not output.exists()
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
