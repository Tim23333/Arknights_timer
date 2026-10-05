"""Small actual-main zero-health timing and checkpoint/replay check."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import ark_sim
from ark_sim import Compiler, Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from ark_sim.tools.replay import replay
from tools.chapter09_depletion_root_peer_v2 import contents, plan
assert Path(ark_sim.__file__).resolve().parent == ROOT / 'ark_sim'
assert implementation_digest() == '4d42e2b6cf646ebe2291d695f82d968e5d4669217069a37bcc8b2babb850f7a4'
registry = {**BUILTIN_PROVIDERS, 'peer/depletion': {'callable': plan, 'version': 'independent-1'}}
sim = Engine.create(Compiler(providers=registry).compile(contents()), providers=registry, seed=8723)
sim.advance(8); restored = Engine.restore(sim.program, sim.checkpoint(), providers=registry)
sim.advance(91); restored.advance(91)
assert sim.ctx.resources.current('pillar', 'health') == 0 and sim.ctx.alive('pillar')
assert sim.ctx.depletion.state('pillar')['stage'] == 'ready'
assert sim.checkpoint() == restored.checkpoint() == replay(sim.program, sim.export_replay(), providers=registry).checkpoint()
output = ROOT / 'validation/campaign/chapter09_pillar_primary_v3/smoke.json'; assert not output.exists()
output.write_text(json.dumps({'passed': True, 'actual_exit': 0, 'primary_core': implementation_digest(),
    'actual_module': ark_sim.__file__, 'CPP_head_full_equal': True, 'health': 0, 'stage': 'ready',
    'whole_stage': False, 'client_verified': False}, indent=2) + '\n', encoding='utf8')
