"""Base-life99999 changes the runthrough end criterion, not actor HP or damage."""
import json
from pathlib import Path
import subprocess
import sys
from tools.build_campaign_runthrough_input import apply, encoded, ROOT


def fixture():
    return {'schemaVersion': 2, 'manifest': {'id': 'package/leak_flow', 'requires': ['preset/ark_standard'], 'metadata': {'pending_model_gaps': []}},
        'entities': [{'id': 'unit/enemy', 'kind': 'entity', 'tags': ['enemy', 'ground'], 'components': {
            'attributes': {'base': {'max_hp': 10, 'move_speed': 30}}, 'resources': {'hp': {'initial': 10, 'capacity': 10, 'role': 'health'}},
            'spatial': {}, 'lifecycle': {'policy': 'policy/ark_lifecycle', 'leak_loss': 1}}}],
        'scenarioDraft': {'id': 'scenario/leak_flow', 'ruleset': 'ruleset/ark_standard', 'seed': 99,
            'map': {'rows': 1, 'cols': 2}, 'resources': {'life': {'initial': 1, 'capacity': 1}},
            'objectives': {'type': 'waves', 'life_resource': 'life'}, 'metadata': {},
            'timeline': {'policy': 'managed_clear', 'negative_timeout_policy': 'wait_for_clear', 'waves': [{'fragments': [{'actions': [
                {'kind': 'spawn', 'count': 3, 'interval_seconds': .1, 'spawn': {'definition': 'unit/enemy', 'position': {'row': 0, 'col': 0},
                    'route': {'motionMode': 'WALK', 'startPosition': {'row': 0, 'col': 0}, 'endPosition': {'row': 0, 'col': 1}, 'checkpoints': []}}}]}]}]}}}


def test_unit_definitions_native_waves_and_original_life_are_preserved():
    original = fixture(); modified = apply(original, 'test-source')
    assert original['scenarioDraft']['resources']['life']['initial'] == 1
    assert modified['scenarioDraft']['resources']['life'] == {'initial': 99999, 'capacity': 99999}
    assert modified['entities'] == original['entities']
    assert modified['scenarioDraft']['timeline'] == original['scenarioDraft']['timeline']
    assert modified['scenarioDraft']['metadata']['runthrough_profile']['native_life_spec'] == {'initial': 1, 'capacity': 1}


def test_three_leaks_complete_process_with_exact_checkpoint_and_replay(tmp_path):
    from ark_sim.adapters.api import implementation_digest
    import ark_sim
    runtime = Path(ark_sim.__file__).resolve().parents[1]
    package = tmp_path/'input.json'; package.write_bytes(encoded(apply(fixture(), 'test-source')))
    commands = tmp_path/'commands.json'; commands.write_text('[]\n', encoding='utf8')
    output = tmp_path/'result.json'
    subprocess.run([sys.executable, str(ROOT/'tools/run_campaign_runthrough.py'), '--runtime-root', str(runtime),
        '--expected-core', implementation_digest(), '--package', str(package), '--commands', str(commands), '--output', str(output),
        '--max-ticks', '100', '--checkpoint-at', '2'], cwd=ROOT, check=True, capture_output=True)
    result = json.loads(output.read_bytes())
    assert result['passed'] and result['process_complete'] and result['identity_stable']
    assert result['state']['kills'] == 0 and result['state']['leaks'] == 3 and result['state']['pending_waves'] == 0
    assert result['base_life_final'] == 99996
    assert result['checkpoint_equal'] is True and result['replay_equal'] is True
    assert result['actual_game_accuracy_verified'] is False
