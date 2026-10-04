"""Exercise the promoted main import path and preserve only a compact receipt."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ark_sim
from ark_sim import Compiler, Engine
from ark_sim.adapters.api import implementation_digest
from tools.chapter09_ability_clock_v1.flame_channel import package, providers

assert Path(ark_sim.__file__).resolve().parent == ROOT / 'ark_sim'
assert implementation_digest() == 'f0c2944cc89788b9277cbafe55ba1d9dcbdfe1e2f29c3619ce3fd1da9a6b7e9c'
sim = Engine.create(Compiler(providers=providers()).compile(package()), providers=providers())
sim.advance(319)
updates = [(event['time'], event['payload']['ready_at']) for event in sim.session.events
           if event['type'] == 'ability.cooldown.updated']
assert updates == [(0, 0), (180, 480), (318, 618)]
assert sim.ctx.resources.current('target', 'hp') == 19040
assert sim.ctx.get('target', ('runtime', 'elemental', 'remaining', 'FIRE')) == 400
assert not sim.ctx.get('source', ('runtime', 'casts'))
output = ROOT / 'validation/campaign/chapter09_channel_map_primary_v1/smoke.json'
assert not output.exists()
output.write_text(json.dumps({'passed': True, 'actual_exit': 0, 'core': implementation_digest(),
    'actual_import': ark_sim.__file__, 'cooldown_updates': updates,
    'health_final': 19040, 'elemental_remaining': 400, 'casts_released': True,
    'whole_enemy': False, 'whole_stage': False, 'client_verified': False}, indent=2) + '\n', encoding='utf8')
print(json.dumps({'passed': True, 'output': str(output)}))
