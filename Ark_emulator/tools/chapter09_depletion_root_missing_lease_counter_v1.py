"""Probe a single missing-lease edit after an actual public lethal command."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT.parent / 'unpack_work/campaign_c9_depletion_v2_candidate'
sys.path.insert(0, str(CANDIDATE))
sys.path.insert(1, str(ROOT))
from ark_sim import Compiler, Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from chapter09_depletion_root_peer_v2 import contents, plan

assert implementation_digest() == 'aae51de3eef5fcce08eff7b5d18b2dca1cc4b52e8594106091634806dd9d4814'
providers = {**BUILTIN_PROVIDERS, 'peer/depletion': {'callable': plan, 'version': 'independent-1'}}
sim = Engine.create(Compiler(providers=providers).compile(contents()), providers=providers, seed=8723)
sim.session.advance(8)
checkpoint = json.loads(json.dumps(sim.checkpoint()))
assert checkpoint['attribute_cache']['entries'] == []
target = next(e for e in checkpoint['kernel']['world']['entities'] if e['definition_id'] == 'unit/peer/pillar')
lease = target['components']['runtime']['depletion']['lease']
assert lease['actions']['1']['due'] == 97
target['components']['runtime']['depletion']['lease'] = None
accepted = False
error = None
try:
    restored = Engine.restore(sim.program, checkpoint, providers=providers)
    accepted = True
    restored.session.advance(110)
except ValueError as caught:
    error = str(caught)
counter = accepted and restored.ctx.alive('pillar') and restored.ctx.resources.current('pillar', 'health') == 0
report = {'core': implementation_digest(), 'counter_reproduced': counter,
    'restore_accepted': accepted, 'restore_error': error,
    'changed_fields': ['$.kernel.world.entities[pillar].components.runtime.depletion.lease'],
    'source_run': 'Actual public lethal command at7, checkpoint8, declared ready97',
    'cache_fields_removed': False, 'checkpoint_attribute_cache_naturally_empty': True,
    'final_time': restored.session.time if accepted else None,
    'final_state': restored.ctx.depletion.state('pillar') if accepted else None,
    'final_health': restored.ctx.resources.current('pillar', 'health') if accepted else None,
    'final_alive': restored.ctx.alive('pillar') if accepted else None,
    'expected': 'Reject an alive exact-zero owned lifecycle with lost mandatory lease and still-owned original task',
    'source_sha': hashlib.sha256((CANDIDATE / 'ark_sim/domains/depletion.py').read_bytes()).hexdigest()}
output = ROOT / 'validation/campaign/chapter09_depletion_root_peer/missing_lease.counter.v1.json'
assert not output.exists()
output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
print(json.dumps(report, ensure_ascii=False))
