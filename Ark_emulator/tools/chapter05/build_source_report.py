"""Chapter5 source evidence and explicit semantic consumer gaps."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT/'packages/campaign/chapter05_reports/source.inventory.json'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def build():
    paths = {name: ROOT/'packages/campaign'/path for name, path in {
        'plan': 'chapter05_plans/source.plan.json', 'enemies': 'chapter05_sources/native.reference.json',
        'environment': 'chapter05_environment/source.reference.json', 'predefines': 'chapter05_predefines/source.reference.json',
        'ordinary': 'chapter05_units/ordinary.reference_model.json'}.items()}
    sources = {k: json.loads(p.read_bytes()) for k, p in paths.items()}
    plan, enemies = sources['plan'], sources['enemies']
    dump = ROOT.parent/'Ark_data/dump.cs'; text = dump.read_text(encoding='utf8')
    names = ['CheckpointType', 'DamageType', 'SideType', 'PlayerSide', 'AbnormalFlag',
             'BuildableType', 'AbilityStandard.SelectTargetSource', 'AbilityStandard.SelectTargetTiming',
             'AbstractAnimatedAbility.TimeMode']
    enums = {}
    for name in names:
        m = re.search(r'^public enum '+re.escape(name)+r'[^\n]*\n\{.*?^\}', text, re.M | re.S)
        if not m: raise ValueError('Native enum source missing: '+name)
        enums[name] = {'line': text[:m.start()].count('\n')+1, 'raw': m.group(),
                       'version_alignment_verified': False, 'runtime_consumer_verified': False}
    bindings = {v['variant_id']: v for v in sources['ordinary']['manifest']['metadata']['variant_bindings']}
    matrix = []
    for vid, v in enemies['variants'].items():
        d = v['native_enemy']['resolved']; gaps = []
        if d['attributes']['hpRecoveryPerSec']: gaps.append('native HP recovery clock/source coefficient')
        if v['passive_and_skill_components']: gaps.append('all passive/skill components and nested buff/BSON consumers')
        if d.get('talentBlackboard'): gaps.append('talent BB consumers')
        if d.get('skills'): gaps.append('DB skill priority/cooldown/initCooldown/SP/branch dispatch')
        if any(n.get('native_class') in ('RangedAttack', 'Heal') for m in v['modes'] for n in m['nodes'].values()):
            gaps.append('ranged/heal source selection, projectile or ally heal dispatch')
        matrix.append({'variant_id': vid, 'ordinary_definition': bindings.get(vid, {}).get('unit_definition'),
                       'all_component_classes': sorted({c['native_class'] for c in enemies['prefabs'][v['prefab_key']]['components'].values()}),
                       'HP_recovery_per_second': d['attributes']['hpRecoveryPerSec'], 'unconsumed_semantic_dependencies': gaps,
                       'source_model_reviewed': False, 'client_verified': False})
    stages = {}
    for name, s in plan['stages'].items():
        n = s['native_document']
        stages[name] = {'wave_spawn_count': s['spawn_count'], 'controls': s['control_count_by_type'],
                        'tile_counts': s['tile_cell_counts'], 'used_checkpoints': s['used_checkpoint_counts'],
                        'predefined_token_count': len(n['predefines']['tokenInsts']),
                        'native_branches': n['branches'], 'options': n['options'],
                        'rune_policy': 'normal difficulty1; FOUR_STAR rows retained, no hard-mode buff applied by this inventory',
                        'complete_stage_implemented': False}
    return {'schema': 'ark-sim/chapter05-source-inventory/v1', 'fixed_commit': plan['fixed_commit'],
            'source_sha256': {k: {'path': p.relative_to(ROOT).as_posix(), 'sha256': sha(p)} for k, p in paths.items()},
            'native_enum_source': {'path': dump.relative_to(ROOT.parent).as_posix(), 'sha256': sha(dump), 'enums': enums},
            'stages': stages, 'semantic_consumer_matrix': matrix,
            'source_conflicts': [sources['predefines']['prefab']['source_policy']],
            'acceptance': {'source_inventory_prepared': True, 'independent_review': False, 'whole_stage_execution': False, 'client_comparison': False}}


if __name__ == '__main__':
    value = build(); OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps({'sha256': sha(OUT), 'variants': len(value['semantic_consumer_matrix']), 'whole_stage_execution': False}))
