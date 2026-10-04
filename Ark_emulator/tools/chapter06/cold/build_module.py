"""Source cold5/cold10 requests, typed statuses and TARGET FROZEN multipliers."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'packages/campaign/chapter06_cold/model.json'
SOURCE = OUT.with_name('source.decoded.json')
COLD = 'buff/ch6/cold/e2c_cold'
FROZEN = 'buff/ch6/cold/e2c_freeze'
APPLICATION = 'rule/ch6/cold/application'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def build():
    src = json.loads(SOURCE.read_bytes()); rows = src['rows']
    if rows['e2c_cold']['row_offset'] != 19324 or rows['e2c_freeze']['row_offset'] != 19536: raise ValueError('Typed source calibration differs')
    duration_rule = 'rule/ch6/cold/status_duration'
    p = {'schemaVersion': 2, 'manifest': {'id': 'package/chapter06/cold/source_consumer', 'requires': ['preset/ark_standard'],
        'metadata': {'source_locks': {str(SOURCE.relative_to(ROOT)): sha(SOURCE)}, 'builder_sha256': sha(Path(__file__)),
            'required_generic_capabilities': ['buff.application', 'damage.request typed source/target selection projection'],
            'formal_approved': False, 'independent_reviewed': False, 'whole_stage_executed': False, 'client_verified': False,
            'policies': {'duration': 'Incoming exact5/10 BB seconds times effective one_minus_status_resistance; YES/AUTOMATIC Frozen status resistant. Zero lifetime is not a literal zero duration',
                'cold': 'COLD23, ASPD additive-30 normalized-.3; existing cold/frozen ->freeze if FROZEN16 not immune, then clear other cold/frozen handles across sources',
                'refresh': 'Current incoming duration replaces expiration on same definition/target independent of source; maxStack1',
                'immunity': 'Cold23 immune rejects pure application. Frozen16 immune retains/refreshed Cold; contribution/control gates dynamically honor immunities, clocks keep running',
                'control': 'Frozen stops move/attack/abilities and interrupts current casts; bind rule/ch6/cold/frozen_recovery to source SP resource to freeze recovery. HP recovery is not disabled by this SP binding',
                'cold_plus_frozen': 'Cold removed during freeze; new cold while frozen refreshes frozen from the current incoming source duration. Native resistance/refresh precise calibration remains replaceable',
                'scope': 'Reusable e2c source5/10 and TARGETFROZEN attack scale; NPC story control and complete stages separate'} }},
        'rules': [
            {'id': APPLICATION, 'kind': 'rule', 'contract': 'buff.application', 'dependencies': [duration_rule],
             'implementation': {'type': 'provider', 'provider': 'reference.c6.cold_application'},
             'parameters': {'cold': COLD, 'frozen': FROZEN, 'duration_rule': duration_rule}},
            {'id': duration_rule, 'kind': 'calculation_rule', 'contract': 'buff.duration',
             'implementation': {'type': 'expression', 'expression': 'inputs.buff_parameters.duration_seconds * inputs.buff_parameters.status_duration_factor'}},
            {'id': 'rule/ch6/cold/frozen_recovery', 'kind': 'rule', 'contract': 'resource.recovery_freeze', 'metadata': {'recovery_freeze_authority': 'final_override'},
             'implementation': {'type': 'provider', 'provider': 'reference.c6.frozen_recovery'}, 'parameters': {'frozen': FROZEN}},
            {'id': 'rule/ch6/cold/cold_active', 'kind': 'rule', 'contract': 'buff.applicability',
             'implementation': {'type': 'expression', 'expression': 'inputs.owner.components.runtime.alive and 23 not in inputs.status.abnormal_immunes'}},
            {'id': 'rule/ch6/cold/frozen_active', 'kind': 'rule', 'contract': 'buff.applicability',
             'implementation': {'type': 'expression', 'expression': 'inputs.owner.components.runtime.alive and 16 not in inputs.status.abnormal_immunes'}}],
        'buffs': [
            {'id': COLD, 'kind': 'buff', 'duration_seconds': 10, 'active_rule': 'rule/ch6/cold/cold_active',
             'stacking': {'mode': 'refresh', 'identity': ['definition', 'target'], 'max_stacks': 1},
             'selection_flags': {'abnormal_flags': [23]}, 'modifiers': [{'attribute': 'attack_speed_ratio', 'layer': 'flat', 'value': -.3}]},
            {'id': FROZEN, 'kind': 'buff', 'duration_seconds': 10, 'active_rule': 'rule/ch6/cold/frozen_active',
             'control_rule': 'rule/ch6/cold/frozen_active', 'stacking': {'mode': 'refresh', 'identity': ['definition', 'target'], 'max_stacks': 1},
             'selection_flags': {'abnormal_flags': [16]}, 'control': {'move': False, 'attack': False, 'abilities': False, 'interrupt': True}}],
        'abilities': [], 'selectors': [{'id': 'selector/ch6/cold/receiver', 'kind': 'selector', 'region': {'type': 'all'}, 'filters': [{'tag': 'cold_receiver'}, {'state': 'alive'}], 'limit': 1}]}
    for seconds in (5,10):
        p['abilities'].append({'id': 'ability/ch6/cold/apply'+str(seconds), 'kind': 'ability', 'activation': {'mode': 'manual'},
            'selector': 'selector/ch6/cold/receiver', 'timeline': [{'at': 0, 'effect': {'op': 'buff_application', 'application_rule': APPLICATION,
                'allowed': [COLD, FROZEN], 'parameters': {'duration_seconds': seconds}}}]})
    for ratio in (1.5, 2.5):
        rule = 'rule/ch6/cold/frozen_atkscale'+str(ratio)
        p['rules'].append({'id': rule, 'kind': 'rule', 'contract': 'damage.request',
            'implementation': {'type': 'provider', 'provider': 'reference.c6.frozen_atkscale'}, 'parameters': {'atk_scale': ratio}})
        p['buffs'].append({'id': 'buff/ch6/cold/frozen_atkscale'+str(ratio), 'kind': 'buff', 'damage_hooks': [{'phase': 'before', 'rule': rule}]})
    return p


if __name__ == '__main__':
    p = build(); OUT.write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    print(json.dumps({'sha256': sha(OUT), 'source5_10_requests': True, 'runtime_model': True, 'formal_approved': False}))
