"""Offline native ballista dependency closure; source versions stay explicit."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.build_chapter01_enemy_sources import NativeAssets, find_templates, bson_source
from tools.build_chapter02_enemy_sources import geometry_source
from tools.normalize_campaign_operators import load_sources

PLAN = ROOT/'packages/campaign/chapter05_plans/source.plan.json'
OUT = ROOT/'packages/campaign/chapter05_predefines/source.reference.json'
CID = 'trap_007_ballis'


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    plan = json.loads(PLAN.read_bytes())
    chars, skills, table_lock = load_sources()
    char = chars[CID]
    assets = NativeAssets()
    candidate = ROOT.parent/'unpack_work/campaign_external/battle_prefabs_tokens.20250327.ab'
    proof_path = ROOT/'packages/campaign/support_tokens.reference.json'
    proof = json.loads(proof_path.read_bytes())['source']
    if sha(candidate) != proof['sha256']:
        raise ValueError('Frozen official token source drift')
    prefab = assets.closure(candidate, CID)
    prefab['geometry_sources'] = geometry_source(assets, prefab)
    prefab['source_policy'] = {
        'status': 'explicit_replaceable_reference_candidate',
        'version': 'official_20250327_tokens',
        'alignment_with_fixed_table_commit_verified': False,
        'replacement_rule': 'Replace with exact table-aligned token asset and rebuild; never silently identify old asset as the fixed table version',
        'download_proof': proof,
    }
    selected = skills['sktok_ballis']['levels'][0]
    skill_paths = [p for p in (ROOT.parent/'data/battle/prefabs').glob('*skills.ab_unpacked/CAB-*') if not p.name.endswith('.resS')]
    matches = [p for p in skill_paths if any(o.type.name == 'GameObject' and o.read().m_Name == selected['prefabId'] for o in assets.load(p)[0].values())]
    if len(matches) == 1:
        skill_prefab = assets.closure(matches[0], selected['prefabId'])
        skill_prefab['geometry_sources'] = geometry_source(assets, skill_prefab)
    else:
        skill_prefab = {'status': 'exact_skill_prefab_missing_or_ambiguous', 'candidates': [str(p) for p in matches]}
    projectile_paths = [p for p in (ROOT.parent/'data/battle/prefabs').glob('*projectiles.ab_unpacked/CAB-*') if not p.name.endswith('.resS')]
    projectile_matches = [p for p in projectile_paths if any(o.type.name == 'GameObject' and o.read().m_Name == 'projectile_ballis' for o in assets.load(p)[0].values())]
    if len(projectile_matches) != 1:
        raise ValueError('Exact ballista projectile source missing or ambiguous')
    projectile = assets.closure(projectile_matches[0], 'projectile_ballis')
    projectile['geometry_sources'] = geometry_source(assets, projectile)
    templates = bson_source(find_templates(prefab) | find_templates(skill_prefab) | find_templates(projectile))
    locks = {'Ark_emulator/packages/campaign/chapter05_plans/source.plan.json': sha(PLAN),
             'Ark_emulator/packages/campaign/support_tokens.reference.json': sha(proof_path)}
    def collect(value):
        if isinstance(value, dict):
            if isinstance(value.get('path'), str) and isinstance(value.get('sha256'), str): locks[value['path']] = value['sha256']
            for child in value.values(): collect(child)
        elif isinstance(value, list):
            for child in value: collect(child)
    collect(prefab); collect(skill_prefab); collect(projectile); collect(templates); collect(assets.scripts)
    for p in (Path(__file__), ROOT/'tools/build_chapter01_enemy_sources.py', ROOT/'tools/build_chapter02_enemy_sources.py', ROOT/'tools/normalize_campaign_operators.py'):
        locks[p.relative_to(ROOT.parent).as_posix()] = sha(p)
    return {'schema': 'ark-sim/chapter05-predefined-source/v1', 'source_locks': locks,
            'table_sources': table_lock, 'raw_character': char, 'selected_skill_id': 'sktok_ballis',
            'selected_skill_level': selected, 'prefab': prefab, 'skill_prefab': skill_prefab, 'projectile': projectile,
            'bson_templates': templates, 'native_monoscripts': assets.scripts,
            'stages': {key: {'predefines': deepcopy(s['predefines']), 'control_actions': [a for a in s['actions'] if a['native']['actionType'] != 'SPAWN']} for key, s in plan['stages'].items()},
            'semantic_gaps': ['token asset version conflict explicitly replaceable', 'hidden alias activation and native wave control timing',
                              'level6 exact stat interpolation and selected skill SP clock', 'TrapMode tile rewrite and obstacle semantics',
                              'skill projectile, collision filters, life span, buffs and native enums require consumer review'],
            'runtime_authored': False, 'formal_approved': False, 'actual_client_verified': False}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true'); args = ap.parse_args()
    p = build(); raw = (json.dumps(p, ensure_ascii=False, indent=2)+'\n').encode('utf8')
    if args.check:
        if OUT.read_bytes() != raw: raise ValueError('Predefined source drift')
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True); OUT.write_bytes(raw)
    print(json.dumps({'sha256': sha(OUT), 'skill_prefab_status': p['skill_prefab'].get('status', 'exact_native_closure'), 'runtime': False}))
