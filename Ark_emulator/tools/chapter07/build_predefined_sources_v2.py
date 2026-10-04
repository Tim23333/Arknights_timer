"""Exact cold-trap and scripted hidden NPC source inventory, never skill[-1]."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from tools.build_chapter01_enemy_sources import NativeAssets, find_templates, bson_source, story_source
from tools.build_chapter02_enemy_sources import geometry_source
from tools.extract_campaign_animation_bindings import character_bindings, library_identity
from tools.normalize_campaign_operators import load_sources
PLAN = ROOT/'packages/campaign/chapter07_plans/source.plan.json'
OUT = ROOT/'packages/campaign/chapter07_predefines/source.v2.reference.json'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def build():
    plan = json.loads(PLAN.read_bytes()); chars, skills, table_lock = load_sources()
    assets = NativeAssets(); keys = {r['inst']['characterKey'] for stage in plan['stages'].values()
        for bucket in ('characterInsts', 'tokenInsts', 'characterCards', 'tokenCards') for r in stage['predefines'].get(bucket) or []}
    prefabs = {}; animations = {}; animation_assets = {}; templates = set(); locks = {PLAN.relative_to(ROOT.parent).as_posix(): sha(PLAN)}
    before = library_identity()
    for key in sorted(keys):
        paths = [p for p in (ROOT.parent/'data/charpack'/(key+'.ab_unpacked')).glob('CAB-*') if not p.name.endswith('.resS')]
        policy = None
        if not paths and key in ('trap_011_ore','trap_012_mine'):
            path = ROOT.parent/'unpack_work/campaign_external/battle_prefabs_tokens.20250327.ab'
            proof = ROOT/'packages/campaign/support_tokens.reference.json'; source = json.loads(proof.read_bytes())['source']
            if sha(path) != source['sha256']: raise ValueError('Frozen official token source drift')
            paths = [path]; locks[proof.relative_to(ROOT.parent).as_posix()] = sha(proof)
            policy = {'status': 'explicit_replaceable_reference', 'official_frozen_source': source,
                'table_commit_alignment_verified': False, 'replacement': 'Frozen 20250327 token package is a replaceable mixed-version source. Fixed56aee tables/local20260831 assets remain separate and no version alignment is asserted.'}
        if len(paths) == 1:
            p = assets.closure(paths[0], key); p['geometry_sources'] = geometry_source(assets, p)
            if policy: p['source_policy'] = policy
            prefabs[key] = p; templates |= find_templates(p)
        else:
            prefabs[key] = {'status': 'missing_or_ambiguous_exact_prefab', 'paths': [str(p) for p in paths]}
        if key.startswith('char_'):
            try: animations[key] = character_bindings(key, animation_assets)
            except (ValueError, KeyError, FileNotFoundError) as error: animations[key] = {'status': 'explicit_animation_gap', 'error': str(error)}
    if library_identity() != before: raise ValueError('Spine library mutation')
    stages = {}; skill_sources = {}; skill_prefabs = {}; stories = {}
    skill_paths = [p for p in (ROOT.parent/'data/battle/prefabs').glob('*skills.ab_unpacked/CAB-*') if not p.name.endswith('.resS')]
    for name, stage in plan['stages'].items():
        records = []
        for bucket in ('characterInsts', 'tokenInsts', 'characterCards', 'tokenCards'):
            for raw in stage['predefines'].get(bucket) or []:
                key = raw['inst']['characterKey']; selected = None
                index = raw['skillIndex']
                if index == -1:
                    selection = {'status': 'native_no_selected_skill', 'policy': 'Preserve -1; never Python negative-index select the final skill'}
                elif type(index) is int and 0 <= index < len(chars[key].get('skills', [])):
                    sid = chars[key]['skills'][index]['skillId']; selected = skills[sid]['levels'][raw['mainSkillLvl']-1]
                    skill_sources[sid] = deepcopy(skills[sid]); selection = {'status': 'exact_selected_skill', 'id': sid, 'level': deepcopy(selected)}
                    prefab_key = selected['prefabId']
                    matches = [p for p in skill_paths if any(o.type.name == 'GameObject' and o.read().m_Name == prefab_key for o in assets.load(p)[0].values())]
                    if len(matches) == 1:
                        closure = assets.closure(matches[0], prefab_key); closure['geometry_sources'] = geometry_source(assets, closure)
                        skill_prefabs[prefab_key] = closure; templates |= find_templates(closure)
                    else: skill_prefabs[prefab_key] = {'status': 'exact_skill_prefab_gap', 'candidate_paths': [str(p) for p in matches]}
                else: raise ValueError('Invalid nonnegative selected skill index')
                records.append({'bucket': bucket, 'raw_native': deepcopy(raw), 'raw_character': deepcopy(chars[key]), 'skill_selection': selection,
                    'hidden_registration_policy': 'source_alias_exact' if raw['alias'] else 'explicit_story_key_reference_required_alias_is_native_null',
                    'runtime_consumed': False})
        controls = [deepcopy(a) for a in stage['actions'] if a['native']['actionType'] != 'SPAWN']
        for action in controls:
            if action['native']['actionType'] == 'STORY':
                key = action['native']['key']
                try: stories[key] = story_source(key)
                except (ValueError, FileNotFoundError, KeyError) as error: stories[key] = {'status': 'explicit_story_source_gap', 'error': str(error)}
        stages[name] = {'native_predefines': deepcopy(stage['predefines']), 'instances': records, 'controls': controls,
            'native_options': deepcopy(stage['options']), 'native_branches': deepcopy(stage['native_document'].get('branches')),
            'source_policy': 'Training slots0/DP0/hidden null-alias records and script controls retained; fixed12 replacement requires explicit review'}
    projectile_keys = set()
    def search_projectiles(value):
        if isinstance(value, dict):
            if value.get('key') == 'projectile' and value.get('valueStr'): projectile_keys.add(value['valueStr'])
            for key, child in value.items():
                if 'projectile' in key.lower() and isinstance(child, str) and child: projectile_keys.add(child)
                if key == 'SerializedState' and isinstance(child, str) and child:
                    search_projectiles(json.loads(child))
                search_projectiles(child)
        elif isinstance(value, list):
            for child in value: search_projectiles(child)
    search_projectiles(prefabs); search_projectiles(skill_prefabs)
    projectile_paths = [p for p in (ROOT.parent/'data/battle/prefabs').glob('*projectiles.ab_unpacked/CAB-*') if not p.name.endswith('.resS')]
    projectiles = {}
    for key in sorted(projectile_keys):
        matches = [p for p in projectile_paths if any(o.type.name == 'GameObject' and o.read().m_Name == key for o in assets.load(p)[0].values())]
        if len(matches) == 1:
            closure = assets.closure(matches[0], key); closure['geometry_sources'] = geometry_source(assets, closure)
            projectiles[key] = closure; templates |= find_templates(closure)
        else: projectiles[key] = {'status': 'explicit_projectile_source_gap', 'paths': [str(p) for p in matches]}
    bson = bson_source(templates)
    def collect(v):
        if isinstance(v, dict):
            if isinstance(v.get('path'), str) and isinstance(v.get('sha256'), str): locks[v['path']] = v['sha256']
            for child in v.values(): collect(child)
        elif isinstance(v, list):
            for child in v: collect(child)
    collect(prefabs); collect(animations); collect(animation_assets); collect(skill_prefabs); collect(projectiles); collect(stories); collect(bson); collect(assets.scripts)
    for name in ('tools/chapter07/build_predefined_sources.py', 'tools/build_chapter01_enemy_sources.py', 'tools/build_chapter02_enemy_sources.py', 'tools/extract_campaign_animation_bindings.py', 'tools/normalize_campaign_operators.py'):
        locks['Ark_emulator/'+name] = sha(ROOT/name)
    return {'schema': 'ark-sim/chapter07-predefined-source/v1', 'source_locks': locks, 'table_sources': table_lock,
        'stages': stages, 'prefabs': prefabs, 'animations': animations, 'animation_assets': animation_assets,
        'skill_tables': skill_sources, 'skill_prefabs': skill_prefabs, 'projectiles': projectiles, 'stories': stories, 'bson_templates': bson,
        'native_monoscripts': assets.scripts, 'runtime_authored': False, 'formal_approved': False, 'whole_stage_executed': False, 'client_verified': False}


if __name__ == '__main__':
    p = build(); OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes((json.dumps(p, ensure_ascii=False, indent=2)+'\n').encode('utf8'))
    print(json.dumps({'sha256': sha(OUT), 'prefabs': list(p['prefabs']), 'stories': list(p['stories']), 'runtime': False}))
