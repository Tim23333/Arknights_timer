"""Exact activebranch source survives strict conversion, unsupported actions reject."""
import json
from copy import deepcopy
from pathlib import Path
import pytest
from tools.chapter08_joint_v4.active_branches_v1 import compose
from tools.chapter08_joint_v4.build_flame_loop_profile_v1 import OUT as LOOP

ROOT = Path(__file__).resolve().parents[2]


def inputs():
    source = json.loads((ROOT / 'packages/campaign/chapter08_source_prepare/integration/source.plan.v1.json').read_bytes())
    native = deepcopy(source['stages']['level_main_08-17']['native_document'])
    loop = json.loads(LOOP.read_bytes())
    predefined = {'native_predefines': deepcopy(native['predefines']),
                  'initial_entities': deepcopy(loop['initial_entities']), 'card_bindings': [], 'resources': {}}
    bindings = {key: {'unit': 'unit/adapter/' + key, 'motion': 'WALK'} for key in source['stages']['level_main_08-17']['spawn_by_key']}
    return native, loop, predefined, bindings


def test_actual_fullsource_rejects_unconverted_story_or_opera_instead_of_dropping():
    native, loop, predefined, bindings = inputs()
    with pytest.raises(ValueError, match='Native STORY requires source-bound lifecycle profile'):
        compose(native, 'level_main_08-17', bindings, {'tile_telin':{'type':'route_checkpoint_portal','role':'entry'},'tile_telout':{'type':'route_checkpoint_portal','role':'exit'}}, branch_profile=loop, predefined_profile=predefined)


def test_controlled_action_subset_preserves_exact_loop_and_all10source_predefines():
    native, loop, predefined, bindings = inputs()
    # Explicit input subset is a converter fixture, never a complete stage.
    for wave in native['waves']:
        for fragment in wave['fragments']:
            fragment['actions'] = [action for action in fragment['actions'] if action['actionType'] == 'SPAWN']
    scene, controls = compose(native, 'level_main_08-17', bindings, {'tile_telin':{'type':'route_checkpoint_portal','role':'entry'},'tile_telout':{'type':'route_checkpoint_portal','role':'exit'}}, branch_profile=loop, predefined_profile=predefined)
    assert scene['branches'] == loop['runtime_branch']
    assert scene['initialEntities'] == predefined['initial_entities']
    assert len(scene['initialEntities']) == 10 and all(item.get('instanceAlias') is None for item in scene['initialEntities'])
    assert not controls
    assert sum(action['count'] for wave in scene['timeline']['waves'] for fragment in wave['fragments']
               for action in fragment['actions'] if action['kind'] == 'spawn') == 44


def test_changed_native_branchaction_or_foreign_predefined_raw_rejects():
    native, loop, predefined, bindings = inputs()
    native['branches']['bsnake_flame']['phases'][0]['actions'][0]['key'] = 'foreign'
    with pytest.raises(AssertionError):
        compose(native, 'level_main_08-17', bindings, {'tile_telin':{'type':'route_checkpoint_portal','role':'entry'},'tile_telout':{'type':'route_checkpoint_portal','role':'exit'}}, branch_profile=loop, predefined_profile=predefined)
