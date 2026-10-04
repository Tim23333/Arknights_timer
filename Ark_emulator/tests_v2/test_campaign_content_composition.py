import json
from copy import deepcopy
from pathlib import Path

import pytest

from tools.campaign_content_composition import compose_modules, reachable_content


ROOT = Path(__file__).resolve().parents[1]


def roster_source():
    source = json.loads((ROOT / 'packages/campaign/chapter01_stage_models/m26/level_main_01-12.partial.json').read_bytes())
    old = source.pop('scenarioDraft')
    scene = {key: deepcopy(old[key]) for key in ('ruleset', 'roster', 'rules', 'resources', 'parameters')}
    scene['id'] = 'scene/test/independent_roster_closure'
    return source, scene


def test_actual_fixed12_closure_excludes_previous_chapter_and_controls():
    from ark_sim import Compiler
    source, scene = roster_source()
    package, report = reachable_content(scene, [('m26_reference_roster', source)])
    definitions = {row['id']: row for row in package['definitions']}
    assert len(scene['roster']) == 12
    assert set(scene['roster']) <= set(definitions)
    entity_ids = {key for key, row in definitions.items() if row['kind'] == 'entity'}
    assert entity_ids == set(scene['roster']) | {'unit/campaign_weedy_cannon', 'unit/kalts_mon3tr_model', 'unit/support_night_bird'}
    assert not any(row['kind'] == 'control' for row in definitions.values())
    assert 'unit/chapter01_w' in report['removed_ids']
    assert 'unit/chapter01_emp' in report['removed_ids']
    assert not any('enemy_' in identifier for identifier in entity_ids)
    program = Compiler().compile(package)
    # Raw attributes/selected abilities are byte-for-value preserved.
    for unit in source['entities']:
        if unit['id'] in scene['roster']:
            assert definitions[unit['id']] == unit
            assert program.definitions[unit['id']]['components']['resources']['hp']['initial'] == unit['components']['resources']['hp']['initial']


def test_equal_duplicate_allowed_but_conflicting_duplicate_rejected():
    a = {'entities': [{'id': 'unit/test_same', 'kind': 'entity', 'tags': ['ground']}]}
    definitions, provenance = compose_modules([('left', a), ('right', deepcopy(a))])
    assert len(definitions) == 1
    assert [entry['module'] for entry in provenance['unit/test_same']] == ['left', 'right']
    b = deepcopy(a); b['entities'][0]['tags'] = ['fly']
    with pytest.raises(ValueError, match='Conflicting definition'):
        compose_modules([('left', a), ('right', b)])


def test_explicit_replacement_requires_identity_reason_and_source():
    unit = {'id': 'unit/test_replace', 'kind': 'entity', 'tags': ['ground']}
    replacement = {**unit, 'tags': ['fly']}
    modules = [('old', {'entities': [unit]})]
    with pytest.raises(ValueError, match='reason and source'):
        compose_modules(modules, {unit['id']: {'definition': replacement}})
    with pytest.raises(ValueError, match='identity or kind'):
        compose_modules(modules, {unit['id']: {'definition': {**replacement, 'kind': 'buff'}, 'reason': 'source correction', 'source': 'pinned_source'}})
    definitions, provenance = compose_modules(modules, {unit['id']: {'definition': replacement, 'reason': 'source correction', 'source': 'pinned_source'}})
    assert definitions[unit['id']] == replacement
    assert provenance[unit['id']][-1]['replacement']['source'] == 'pinned_source'


def test_missing_required_ability_stays_a_compile_error():
    from ark_sim import CompileError
    source, scene = roster_source()
    source['abilities'] = [row for row in source['abilities'] if row['id'] != 'ability/campaign_myrtle_s2']
    with pytest.raises(CompileError, match='Missing reference'):
        reachable_content(scene, [('incomplete_reference', source)])
