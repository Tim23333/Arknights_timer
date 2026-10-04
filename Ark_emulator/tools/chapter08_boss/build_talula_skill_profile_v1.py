"""Bind actual prefab skills by key; preserve whole-array resolver discrepancy."""
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.chapter08_boss.build_talula_threshold_v3 import SOURCE, sha
from tools.extract_campaign_animation_bindings import resolve_animation

OUT = ROOT/'packages/campaign/chapter08_consumers/boss/talula.skills.source.v1.json'


def build():
    path = SOURCE/'enemies.native.v1.json'
    assert sha(path) == '9b2a5b1b0d2dfe623421596181a3fc6462ccd4f9cf660cba6f4e75120600941e'
    d = json.loads(path.read_bytes())
    v = d['variants']['enemy_1503_talula@0/5e75f6c67ed9421f']
    pf = d['prefabs'][v['prefab_key']]
    db = {}
    for row in v['native_enemy']['raw_rows']:
        for skill in row['enemyData'].get('skills') or []:
            db[skill['prefabKey']] = deepcopy(skill)
    overrides = v['native_reference']['overwrittenData']['skills']
    assert len(overrides) == 1 and overrides[0]['prefabKey'] == 'DanceFire'
    assert set(db) == {'DragonFire','DanceFire','DragonFire[Half]','DanceFire[Half]'}
    effective = deepcopy(db)
    for row in overrides:
        assert row['prefabKey'] in effective
        effective[row['prefabKey']] = deepcopy(row)
    a = d['animations'][v['prefab_key']]
    records = {}
    for key, skill in effective.items():
        wrappers = [c for c in pf['components'].values() if c['native_class'] == 'EnemySkill' and c['gameobject_name'] == key]
        assert len(wrappers) == 1
        wrapper = wrappers[0]
        nodes = [c for c in pf['components'].values() if c['gameobject_path_id'] == wrapper['gameobject_path_id'] and c['native_class'] in ('MeleeAttack','EmptyAnimatedAbility')]
        assert len(nodes) == 1
        node = nodes[0]
        trigger = pf['components'][str(wrapper['raw']['_trigger']['m_PathID'])]
        selector = pf['components'][str(node['raw']['_selector']['m_PathID'])]
        binding = resolve_animation(node['raw']['_animKey'], a['animator']['fields']['_animations'], a['parsed'])
        assert binding['status'] == 'native_binding_resolved'
        records[key] = {'native_DB_skill':db[key], 'stage_override':next((r for r in overrides if r['prefabKey'] == key),None),
            'selected_skill':skill, 'wrapper':wrapper, 'node':node, 'trigger':trigger, 'selector':selector, 'animation_binding':binding,
            'mode':1 if '[Half]' in key else 0, 'runtime_authored':False}
    assert [(effective[k]['cooldown'],effective[k]['initCooldown']) for k in ('DragonFire','DanceFire','DragonFire[Half]','DanceFire[Half]')] == [(19,19),(40,160),(7,7),(15,15)]
    return {'schema':'ark-sim/chapter08-talula-skill-source/v1', 'source_pins':{path.relative_to(ROOT).as_posix():sha(path),Path(__file__).relative_to(ROOT).as_posix():sha(Path(__file__))},
        'source_native_resolved_skills_whole_array':v['native_enemy']['resolved']['skills'], 'raw_DB_skills':db,
        'stage_overrides':overrides, 'selected_effective_skills':records,
        'reference_policy':'Per-Prefab EnemySkill references retain original DB skill configurations; explicit stage key overrides only matching DanceFire. Existing offline merge_defined replaces array wholesale, its output remains preserved as a source-resolution discrepancy. This source-specific consumer recipe does not mutate generic resolver or frozen source.',
        'native_methods_verified':False, 'independent_reviewed':False, 'runtime_authored':False, 'whole_stage_executed':False}


if __name__ == '__main__':
    p = build()
    assert not OUT.exists()
    OUT.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
    print(json.dumps({'sha':sha(OUT),'skills':len(p['selected_effective_skills'])}))
