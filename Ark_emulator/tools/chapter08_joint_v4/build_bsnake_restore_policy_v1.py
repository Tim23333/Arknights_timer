"""Use documented full first restoration; keep unresolved raw recharge parameter."""
import hashlib
import json
from pathlib import Path
from copy import deepcopy

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'packages/campaign/chapter08_consumers/bsnake'
PARENT = BASE / 'four_modes.wave_source.v3.json'
OUT = BASE / 'four_modes.wave_source.v4.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    p = json.loads(PARENT.read_bytes())
    definitions = {row['id']: row for row in p['definitions']}
    entity = definitions['unit/ch8/bsnake/cadb87696bef4de2']
    rebirth = entity['components']['rebirth']
    assert rebirth['restore_ratio'] == .5
    rule = definitions[rebirth['restore_rule']]
    assert rule['implementation']['expression'] == 'inputs.parameters.capacity * inputs.parameters.ratio if context.rebirth.count == 1 else 0'
    rule['implementation']['expression'] = 'inputs.parameters.capacity if context.rebirth.count == 1 else 0'
    rule['metadata'] = {'reference_policy': 'Documentedfirstrestoration full effectiveHP; actualsecondrestore0. Rawrecharge.5 kept separately, not proven finalhpRatio.'}
    p['manifest']['id'] = 'package/ch8/bsnake/four_modes_wave_source_v4_full_restore'
    meta = p['manifest']['metadata']
    meta['source_locks'].update({str(path.resolve()): sha(path) for path in (PARENT, Path(__file__))})
    meta['first_restoration_policy'] = {
        'default': 'Full effective maxHP after native reborn_up modifiers; 75000 at selected source level',
        'restore_seconds': 5, 'raw_hpRechargeRatio': .5, 'raw_parameter_modified': False,
        'raw_to_final_ratio_proven': False,
        'source_schema': 'Unit.RebornData has hpRatio and hpRechargeRatio separate; RebornTalent.ModifyHpRatio; RebornState recover tween data',
        'reference_url': 'https://prts.wiki/w/%E7%A7%91%E8%A5%BF%E5%88%87',
        'old_37500_evidence': 'Literalparameter policy history only; not native finalHP proof',
        'final_restoration': 'OriginalextraPreset0 remains exact0',
    }
    meta['pending_required'] = [value for value in meta['pending_required'] if 'Firstsource raw .5' not in value]
    meta['pending_required'].append('Independent documentedfullHP policy/first75000 runtime/sourcejoin proof')
    return p


if __name__ == '__main__':
    assert not OUT.exists()
    OUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(sha(OUT))
