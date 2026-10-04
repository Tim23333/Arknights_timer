"""Modulo7 phase uses one explicit bounds rule; no sequential condition mutation."""
import hashlib
import json
from pathlib import Path
from copy import deepcopy
from tools.chapter08_joint_v4.build_summon_hint_v1 import OUT as PARENT, SOURCE, LOOP, ROOT, SUMMON

OUT = PARENT.with_name('summon_hint.module.v2.json')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def phase_bounds(inputs, parameters, context):
    value = inputs['candidate']
    if type(value) not in (int, float) or int(value) != value or not 0 <= value <= 7:
        raise ValueError('Hint phase requires exact finite modulo7 counter')
    return {'accepted': True, 'value': value % 7, 'overflow': 0}


def providers():
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    return {**BUILTIN_PROVIDERS, 'reference.bsnake.hint_phase_bounds': {'callable': phase_bounds, 'version': '1'}}


def build():
    p = json.loads(PARENT.read_bytes())
    p['manifest']['id'] = 'package/ch8/bsnake/summon_hint_v2'
    meta = p['manifest']['metadata']
    meta['source_locks'].update({str(path): sha(path) for path in (PARENT, Path(__file__))})
    rule = 'rule/ch8/bsnake/hint_phase_bounds'
    meta['resources_required']['hint_phase']['bounds_rule'] = rule
    p['rules'] = [{'id': rule, 'kind': 'rule', 'contract': 'resource.bounds',
                   'implementation': {'type': 'provider', 'provider': 'reference.bsnake.hint_phase_bounds'}}]
    ability = next(row for row in p['abilities'] if row['id'] == SUMMON)
    effects = ability['timeline'][0]['effects']
    assert effects[1]['resource'] == effects[2]['resource'] == 'hint_phase'
    effects[1].pop('condition')
    effects.pop(2)
    return p


if __name__ == '__main__':
    assert not OUT.exists()
    OUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(sha(OUT))
