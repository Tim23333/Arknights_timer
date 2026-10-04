"""Actual pillar trait and authored gargoyle meet on the new106-contract core."""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT.parent / 'unpack_work/campaign_c9_foundation_v9_candidate'
sys.path.insert(0, str(RUNTIME)); sys.path.insert(1, str(ROOT))
from ark_sim import Compiler, Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.chapter09_pillar_v1.build_payload import build as pillar, providers as pillar_providers, TRAIT
from tools.chapter09_rock_gargoyle.build_v1 import build as rock, providers as rock_providers


def main():
    core = '56f380fab9715b8edcb589b2c3fc3863d740cb149ab31e19b3f6fe3a1720fcf6'
    assert implementation_digest() == core
    p = pillar(); trait = next(b for b in p['buffs'] if b['id'] == TRAIT)
    gargoyle = rock('enemy_1172_dugago', pillar_trait_buff=TRAIT, dependency_definitions=[trait])
    for name, rows in gargoyle.items():
        if name not in {'manifest', 'schemaVersion', 'scenarioDraft'}:
            p.setdefault(name, []).extend(rows)
    p['scenarioDraft'] = {'id': 'scene/pillar/gargoyle/joint', 'ruleset': 'ruleset/ark_standard',
        'map': {'rows': 5, 'cols': 7}, 'initialEntities': [
            {'definition': 'unit/ch9/pillar/body', 'instanceAlias': 'pillar', 'position': {'row': 2, 'col': 2}},
            {'definition': gargoyle['entities'][0]['id'], 'instanceAlias': 'gargoyle', 'position': {'row': 2, 'col': 3}}],
        'commands': [{'at': 2, 'action': 'skill', 'source': 'pillar', 'ability': 'ability/ch9/pillar/collapse_right'}]}
    reg = {**rock_providers(), **pillar_providers()}
    program = Compiler(providers=reg).compile(p)
    sim = Engine.create(program, providers=reg, seed=90319); sim.advance(30)
    checkpoint = Path(os.environ['ARKSIM_RUN_DIR']) / 'gargoyle.checkpoint.json'
    checkpoint.write_text(json.dumps(sim.checkpoint()), encoding='utf8')
    restored = Engine.restore(program, json.loads(checkpoint.read_bytes()), providers=reg)
    sim.advance(40); restored.advance(40)
    assert sim.checkpoint() == restored.checkpoint() == replay(program, sim.export_replay(), providers=reg).checkpoint()
    assert sim.ctx.get('gargoyle', ('runtime', 'state')) == 'dead'
    assert sim.ctx.resources.current('gargoyle', 'mode') == 3
    assert not [e for e in sim.session.events if e['type'] == 'entity.rebirth.started']
    skips = [e for e in sim.session.events if e['type'] == 'entity.rebirth.skipped']
    assert len(skips) == 1 and skips[0]['time'] == 47
    result = {'passed': True, 'core': core, 'actual_pillar_trait': TRAIT,
        'gargoyle_health': 0, 'gargoyle_mode': 3, 'rebirth_started': False,
        'depletion_source': sim.session.world.resolve('pillar'), 'skip_event_time': 47,
        'actual_CP_head_complete_equal': True, 'whole_stage_verified': False,
        'source_guard': {str(x): hashlib.sha256(x.read_bytes()).hexdigest() for x in
            [Path(__file__), ROOT / 'tools/chapter09_pillar_v1/build_payload.py', ROOT / 'tools/chapter09_rock_gargoyle/build_v1.py']}}
    output = ROOT / 'validation/campaign/chapter09_foundation_v9/pillar_gargoyle.actual.json'
    assert not output.exists()
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
