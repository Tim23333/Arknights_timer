"""Actual native bigforce field consumes its operand and current occupancy."""
import sys
import json
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent / 'unpack_work/campaign_c9_foundation_v9_candidate')); sys.path.insert(1, str(ROOT))
from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay
from tools.chapter09_pillar_v1.bigforce import build, providers, profile


def test_base_force_one_native_cell_and_remove_when_leave_disk_cpp_head(tmp_path):
    p = build()
    p['entities'].append({'id': 'unit/bigforce/player', 'kind': 'entity', 'tags': ['player'], 'components': {
        'attributes': {'base': {'base_force_level': 2.0}}, 'selection_state': {'side': 0, 'motion': 1, 'category': 1},
        'spatial': {}, 'abilities': ['ability/bigforce/leave']}})
    p['abilities'] = [{'id': 'ability/bigforce/leave', 'kind': 'ability', 'activation': {'mode': 'manual'},
        'timeline': [{'at': 0, 'effect': {'op': 'move', 'target': 'source', 'position': {'row': 0, 'col': 1}}}]}]
    p['scenarioDraft'] = {'id': 'scene/bigforce', 'ruleset': 'ruleset/ark_standard',
        'map': {'rows': 1, 'cols': 2, 'tiles': [{'tileKey': 'tile_bigforce', 'buildableType': 2,
            'passableMask': 2, 'blackboard': [{'key': 'base_force_level', 'value': 1.0}]}, {'tileKey': 'tile_floor'}],
            'tile_mechanics': {'tile_bigforce': profile()}}, 'initialEntities': [{'definition': 'unit/bigforce/player',
                'instanceAlias': 'player', 'position': {'row': 0, 'col': 0}}],
        'commands': [{'at': 3, 'action': 'skill', 'source': 'player', 'ability': 'ability/bigforce/leave'}]}
    pr = Compiler(providers=providers()).compile(p); sim = Engine.create(pr, providers=providers())
    assert sim.ctx.attributes.value('player', 'base_force_level') == 3
    sim.advance(2); path = tmp_path / 'field.checkpoint.json'; path.write_text(json.dumps(sim.checkpoint()), encoding='utf8')
    resumed = Engine.restore(pr, json.loads(path.read_bytes()), providers=providers()); sim.advance(3); resumed.advance(3)
    assert sim.checkpoint() == resumed.checkpoint()
    assert sim.ctx.attributes.value('player', 'base_force_level') == 2
    public = Engine.create(pr, providers=providers()); public.advance(5)
    head = replay(pr, public.export_replay(), providers=providers())
    assert public.checkpoint() == head.checkpoint()
    assert public.ctx.attributes.value('player', 'base_force_level') == head.ctx.attributes.value('player', 'base_force_level') == 2
    assert public.checkpoint() == head.checkpoint()


def test_unbound_blackboard_rejected():
    p = build(); p['scenarioDraft'] = {'id': 'scene/bigforce/bad', 'ruleset': 'ruleset/ark_standard',
        'map': {'rows': 1, 'cols': 1, 'tiles': [{'tileKey': 'tile_bigforce', 'blackboard': {'base_force_level': 2.0}}],
                'tile_mechanics': {'tile_bigforce': profile()}}}
    with pytest.raises(ValueError):
        Engine.create(Compiler(providers=providers()).compile(p), providers=providers())
