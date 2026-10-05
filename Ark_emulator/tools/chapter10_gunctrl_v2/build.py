"""Native cannon area eligibility, using the existing generic qualified area."""
import hashlib
import json
from pathlib import Path
from copy import deepcopy
from tools.chapter10_gunctrl_v1 import build as original
from ark_sim.domains.selection import DEFAULT_STATE

ROOT = Path(__file__).resolve().parents[2]


def providers():
    return original.providers()


def build(stage='level_main_10-14', *, manfred_sp_binding=None, require_complete=False):
    package = original.build(stage, manfred_sp_binding=manfred_sp_binding, require_complete=require_complete)
    native = json.loads(original.SOURCE.read_bytes())
    selector = next(c['raw'] for c in native['projectiles']['projectile_gunctrl']['components'].values()
                    if c['native_class'] == 'AdvancedSelector')
    configuration = {k: deepcopy(v) for k, v in selector.items() if k.startswith('_')}
    member_rule = next(r for r in package['rules'] if r['id'] == 'rule/' + original.P + 'members')
    member_rule['implementation']['provider'] = 'ark.area.qualified_cell_offsets'
    member_rule['parameters']['eligibility'] = {
        'rule': 'rule/' + original.P + 'eligibility',
        'parameters': {'source_configuration': configuration, 'side_policy': 'relative_ally_enemy',
                       'neutral_policy': 'reject', 'defaults': deepcopy(DEFAULT_STATE)}}
    package['manifest']['id'] += '/native_area_v2'
    metadata = package['manifest']['metadata']
    metadata['source_locks'][str(Path(__file__))] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    metadata['native_area_selector'] = configuration
    metadata['reference_policy']['area'] = (
        'Exact native x-2 offsets and AdvancedSelector via the generic qualified-cell provider; '
        'all declared side/motion/category/free/camouflage/invisible switches are evaluated at impact')
    metadata['previous_consumer_counter'] = 'validation/campaign/chapter10_gunctrl_peer_v1/counter.ally_free.v1.json'
    return package


if __name__ == '__main__':
    output = ROOT / 'packages/campaign/chapter10_consumers/gunctrl_v2'
    output.mkdir(parents=True, exist_ok=True)
    for stage in ('level_main_10-14', 'level_main_10-15'):
        (output / (stage + '.module.v2.json')).write_text(
            json.dumps(build(stage), ensure_ascii=False, indent=2) + '\n', encoding='utf8')
