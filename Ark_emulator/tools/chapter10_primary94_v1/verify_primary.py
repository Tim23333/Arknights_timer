"""Fresh-import production EP and chain checks after exact byte promotion."""
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import ark_sim
from ark_sim import Compiler, Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import digest, thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered, load_bound
from tools.chapter10_primary94_v1.promote import NEW, inventory


def proof(package, label, at, end, command=None):
    program = Compiler().compile(package)
    sim = Engine.create(program, seed=9471)
    if command is not None:
        sim.submit(command, at=1)
    sim.advance(at)
    path = Path(os.environ['ARKSIM_RUN_DIR']) / (label + '.checkpoint.json')
    pin = write_ordered(path, sim.checkpoint())
    restored = Engine.restore(program, load_bound(path, pin))
    assert restored.checkpoint() == sim.checkpoint()
    sim.advance(end - at);restored.advance(end - at)
    head = replay(program, sim.export_replay())
    assert sim.checkpoint() == restored.checkpoint() == head.checkpoint()
    assert list(sim.session.events) == list(restored.session.events) == list(head.session.events)
    return sim, {'complete_CP_head_equal': True, 'checkpoint_sha256': pin,
                 'complete_checkpoint_digest': digest(sim.checkpoint()), 'event_count': len(sim.session.events)}


def main():
    path = ROOT / 'validation/campaign/chapter10_primary94_v1/actual.primary.v1.json'
    if path.exists():
        raise FileExistsError(path)
    assert Path(ark_sim.__file__).resolve().parent == ROOT / 'ark_sim' and implementation_digest() == NEW
    before = inventory(ROOT / 'ark_sim')
    result = {'schema': 'ark-sim/primary-fresh-import-check/v1', 'core': NEW, 'passed': False,
              'source_before': before, 'whole_stage': False, 'client_verified': False}
    try:
        from tools.campaign_elemental_lease_v4.fixture import package as elemental
        ep, ep_proof = proof(elemental(), 'elemental', 10, 130)
        state = thaw(ep.ctx.get('target', ('runtime', 'elemental')))
        assert state['remaining'] == {'EMBER': 733, 'VOID': 1031} and state['break'] is None
        starts = [thaw(e) for e in ep.session.events if e['type'] == 'elemental.break.started']
        assert len(starts) == 1 and starts[0]['payload']['due'] == 92
        result['elemental'] = {**ep_proof, 'state': state, 'owned_due': 92}
        from tools.chapter10_chain_v1.fixture import package as chain
        sim, chain_proof = proof(chain(), 'chain', 43, 100,
                                 {'action': 'skill', 'source': 'source', 'ability': 'ability/chain/probe'})
        actual = []
        for i in range(5):
            hp = sim.ctx.resources.current('target' + str(i), 'hp')
            remaining = sim.ctx.get('target' + str(i), ('runtime', 'elemental', 'remaining', 'DARK'))
            health_loss = 550 * .85 ** i if i < 4 else 0
            ep_loss = health_loss * .3
            assert abs((10000 - hp) - health_loss) < 1e-8 and abs((10000 - remaining) - ep_loss) < 1e-8
            actual.append({'target': i, 'HP': hp, 'DARK_remaining': remaining,
                           'expected_health_loss': health_loss, 'expected_EP_loss': ep_loss})
        result['chain'] = {**chain_proof, 'all_five_targets': actual}
        result['passed'] = True
    except Exception:
        result['error'] = traceback.format_exc()
    result['source_after'] = inventory(ROOT / 'ark_sim')
    result['core_at_completion'] = implementation_digest()
    result['actual_modules'] = {name: str(Path(module.__file__).resolve()) for name, module in sys.modules.items()
                               if name.startswith('ark_sim') and getattr(module, '__file__', None)}
    result['identity_stable'] = (before == result['source_after'] and result['core_at_completion'] == NEW
                                 and all(Path(p).is_relative_to(ROOT / 'ark_sim') for p in result['actual_modules'].values()))
    result['actual_exit'] = 0 if result['passed'] and result['identity_stable'] else 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf8')
    print(json.dumps({'passed': result['passed'], 'actual_exit': result['actual_exit'], 'error': result.get('error')}))
    return result['actual_exit']


if __name__ == '__main__':
    raise SystemExit(main())
