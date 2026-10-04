"""Native looping branch with explicit run-horizon allocation budget."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'packages/campaign/chapter08_consumers'
SOURCE = BASE / 'bsnake/source.closure.v1.json'
BRANCH = BASE / 'flame/branch.profile.v2.json'
DEVICES = BASE / 'flame/predefines.profile.v2.json'
OUT = BASE / 'flame/loop.profile.v3.json'
MAX_TICKS = 30000


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    source = json.loads(SOURCE.read_bytes())
    components = source['prefab']['components']
    summon = next(row for row in components.values()
                  if row['native_class'] == 'AnimatedActionToOwnerAbility' and row['gameobject_name'] == 'SummonFlame')
    actions = json.loads(summon['raw']['_actions']['SerializedState'])
    move = actions[0]
    assert move['$type'].endswith('MoveNextLevelBranch') and move['_isLoop'] is True
    trigger = next(row for row in components.values()
                   if row['native_class'] == 'LevelBranchTrigger' and row['gameobject_name'] == 'SummonFlame')
    assert trigger['raw']['_isLoop'] == 1
    skill = next(row for row in source['variant']['native_enemy']['resolved']['skills']
                 if row['prefabKey'] == 'SummonFlame')
    assert skill['cooldown'] == 50 and skill['initCooldown'] == 75
    branch = json.loads(BRANCH.read_bytes())
    devices = json.loads(DEVICES.read_bytes())
    runtime = deepcopy(branch['runtime_branch'])
    runtime['bsnake_flame']['loop'] = True
    phases = runtime['bsnake_flame']['phases']
    phase_keys = [[effect['parameters']['key'] for action in phase['actions'] for effect in action['effects']]
                  for phase in phases]
    assert len(phase_keys) == 7 and sum(map(len, phase_keys)) == 35
    assert phase_keys == source['hint_alias_sets7x5']
    # This is a declared scenario ceiling, not a native lifetime stock value.
    # Conservatively assume phase1 ready immediately and no pause between casts.
    # Actual native init75, cast duration and screen pauses can only reduce requests.
    max_requests = 1 + MAX_TICKS // (50 * 30)
    counts = Counter(key for index in range(max_requests) for key in phase_keys[index % len(phases)])
    initial = deepcopy(devices['initial_entities'])
    for item in initial:
        item['reactivation']['max_activations'] = counts[item['registration_key']]
    return {'schema': 'ark-sim/ch8-flame-loop-profile/v3',
            'source_locks': {str(path): sha(path) for path in (SOURCE, BRANCH, DEVICES, Path(__file__))},
            'runtime_branch': runtime, 'initial_entities': initial,
            'native_summon_actions': actions, 'native_branch_trigger': trigger,
            'native_phase_keys': phase_keys,
            'run_horizon_policy': {'max_ticks': MAX_TICKS, 'quantum': 1 / 30,
                                   'native_cooldown_seconds': 50, 'native_initial_cooldown_seconds': 75,
                                   'conservative_max_requests': max_requests,
                                   'budgets_are_native_stock': False,
                                   'ceiling_exhaustion': 'Report incomplete run; never claim native branch completion'},
            'reference_policy': 'Native loop true; fresh entity budgets derived from explicit run ceiling, exact phase order preserved',
            'whole_stage_executed': False, 'client_verified': False}


if __name__ == '__main__':
    value = build()
    assert not OUT.exists()
    OUT.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'sha': sha(OUT), 'max_requests': value['run_horizon_policy']['conservative_max_requests'],
                      'total_allocated_activations': sum(item['reactivation']['max_activations'] for item in value['initial_entities'])}))
