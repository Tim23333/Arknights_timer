"""Explicit native-card deployment control fixture and fixed12 stage overlay.

The native fixture implements deck/deployment controls only, not card combat.
"""
from copy import deepcopy
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.build_chapter01_stage_models import encoded, sha, native_locks
from tools.normalize_campaign_operators import interpolate, half_away_integer, ROUNDING_PROFILE, load_sources

SOURCE = ROOT/'packages/campaign/chapter01_sources/native.reference.json'
SOURCE_SHA = 'a242f94040c7f96d175056e6ceffa285ea10f60bec00db1ab7f354fe0739b0cd'
INPUT = ROOT/'packages/campaign/chapter01_stage_models/m22/level_main_01-11.partial.json'
INPUT_SHA = 'ad147b19e709d6dbd0f935c6a4aeb80e5f8dddad744af4ad0829f583cb8dc262'
CORE = '0258f171d31daffb7b917e2ebad2603505e5fa762e99ef4a71b3b30342d62381'
RUNTIME = ROOT.parent/'unpack_work/campaign_m23_roster_candidate'
OUT = ROOT/'packages/campaign/chapter01_stage_models/m23'


def source_cards():
    if sha(SOURCE) != SOURCE_SHA: raise ValueError('native card source drift')
    reference = json.loads(SOURCE.read_bytes()); stage = reference['stages']['level_main_01-11']
    cards = stage['native_level_document']['predefines']['characterCards']
    if len(cards) != 12: raise ValueError('native card inventory changed')
    return stage, deepcopy(cards)


def apply_fixed12_overlay(package):
    stage, cards = source_cards(); p = deepcopy(package)
    fixed = p['scenarioDraft']['roster']
    if len(fixed) != 12 or len(set(fixed)) != 12: raise ValueError('fixed deck must contain12 unique definitions')
    defs = {e['id']: e for e in p['entities']}
    if not all('campaign_roster' in defs[key].get('tags', []) for key in fixed): raise ValueError('fixed deck substituted unknown config')
    profile = {'id': 'explicit_fixed12_training_test_overlay_v1', 'selection': 'fixed12_test_override',
        'native_cards': cards, 'selected_definitions': list(fixed), 'native_training_deck_legal': False,
        'source_training_flag': stage['native_level_document']['options']['isTrainingLevel'],
        'native_predefined_cards_selectable': stage['native_level_document']['options']['isPredefinedCardsSelectable'],
        'execution': 'scenario.roster contains only selected12; public deploy rejects all other loaded definitions',
        'native_card_combat_implemented': False}
    p['manifest']['metadata']['roster_selection_profile'] = profile
    p['manifest']['metadata']['required_runtime'] = CORE
    p['manifest']['metadata']['builder_sha256'] = sha(Path(__file__))
    p['manifest']['metadata']['source_locks'][INPUT.relative_to(ROOT).as_posix()] = INPUT_SHA
    p['manifest']['metadata']['pending_model_gaps'] = [gap for gap in p['manifest']['metadata']['pending_model_gaps']
        if gap != 'native_training_cards_and_fixed12_explicit_composition']
    p['manifest']['metadata']['pending_model_gaps'].append('explicit_training_test_override_controls_require_independent_review')
    p['scenarioDraft']['metadata']['roster_selection_profile'] = deepcopy(profile)
    p['manifest']['id'] += '/m23_roster'
    p['scenarioDraft']['id'] += '/m23_roster'
    return p


def native_deployment_fixture():
    stage, cards = source_cards(); tables, _, _ = load_sources(); entities = []; asset_locks = {}
    import UnityPy
    cache = {}
    for card in cards:
        cfg = card['inst']; cid = cfg['characterKey']; row = stage['predefined_character_sources'][cid]
        if tables[cid] != row: raise ValueError('native card table mismatch')
        if cfg['phase'] != 'PHASE_0' or cfg['potentialRank'] != 0 or card['hidden']:
            raise ValueError('unconverted native card config')
        if any(card[key] is not None for key in ('overrideSkillBlackboard', 'overrideTalents', 'uniEquipIds', 'tmplId')):
            raise ValueError('native card overrides require explicit conversion')
        base, _ = interpolate(row['phases'][0]['attributesKeyFrames'], cfg['level'])
        favor, _ = interpolate(row['favorKeyFrames'], cfg['favorPoint'])
        stats = {}
        for name, value in base.items():
            if isinstance(value, bool):
                if favor[name] is not False: raise ValueError('unconverted favor immunity')
                stats[name] = value
            else:
                value += favor[name]; stats[name] = half_away_integer(value) if name in ROUNDING_PROFILE['integer_attributes'] else float(value)
        prefab = stage['predefined_prefab_sources'][cid]; asset = ROOT.parent/prefab['source']['path']
        if sha(asset) != prefab['source']['sha256']: raise ValueError('card prefab drift')
        if asset not in cache: cache[asset] = {o.path_id: o for o in UnityPy.load(str(asset)).objects}
        characters = [(pid, c) for pid, c in prefab['components'].items() if c['native_class'] == 'Character']
        if len(characters) != 1: raise ValueError('native card Character ambiguity')
        pid, component = characters[0]; raw = component['raw']
        if cache[asset][int(pid)].read_typetree() != raw: raise ValueError('actual card Character typetree mismatch')
        capacity = raw['_occupiedRemainingCharacterCnt']
        if type(capacity) is not int or capacity < 0: raise ValueError('native card capacity type')
        entities.append({'id': 'unit/native_training/'+cid, 'kind': 'entity', 'tags': ['player', 'native_training_card'],
            'components': {'attributes': {'base': {'max_hp': stats['maxHp'], 'atk': stats['atk'], 'def': stats['def'],
                'mres': stats['magicResistance'], 'deploy_cost': stats['cost'], 'block_count': stats['blockCnt']}},
                'resources': {'hp': {'initial': stats['maxHp'], 'capacity': stats['maxHp'], 'role': 'health'}},
                'spatial': {}, 'deployable': {'policy': 'policy/ark_ground_deploy', 'base_cost': stats['cost'],
                    'capacity': capacity, 'terrain': 'ground' if row['position'] == 'MELEE' else 'high',
                    'cooldown_seconds': stats['respawnTime'], 'refund_ratio': raw['_withdrawCostRecoverRatio'],
                    'parameters': {'advanced_build_mask': raw['_buildCondition']['advancedBuildableMask']}}},
            'metadata': {'native_id': cid, 'native_card': deepcopy(card), 'config': deepcopy(cfg), 'source_stats': stats,
                'scope': 'deck/deployment control fixture only; combat/skills/talents absent deliberately and not claimed'}})
        asset_locks['../'+prefab['source']['path']] = prefab['source']['sha256']
    return {'schemaVersion': 2, 'manifest': {'id': 'package/native_training_card_control_fixture', 'version': '1', 'requires': ['preset/ark_standard'],
        'metadata': {'source_sha256': SOURCE_SHA, 'source_asset_locks': asset_locks, 'builder_sha256': sha(Path(__file__)),
            'scope': 'native12 source configurations and actual deployment membership/cost/capacity only',
            'whole_stage': False, 'native_card_combat_implemented': False}}, 'entities': entities,
        'scenarioDraft': {'id': 'scenario/native_training_card_control', 'ruleset': 'ruleset/ark_standard',
            'map': {'rows': 3, 'cols': 4, 'tiles': [{'tileKey': 'tile_floor', 'buildableType': 3, 'passableMask': 1} for _ in range(12)]},
            'roster': [e['id'] for e in entities], 'resources': {'dp': {'initial': 99, 'capacity': 99}},
            'parameters': {'deploy_capacity': stage['native_level_document']['options']['characterLimit']}, 'objectives': {},
            'metadata': {'native_source_cards': cards, 'whole_stage': False, 'test_scope': 'deployment-only control scene'}}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--check', action='store_true'); args = parser.parse_args()
    if sha(INPUT) != INPUT_SHA: raise ValueError('frozen fixed12 input drift')
    sys.path.insert(0, str(RUNTIME))
    import ark_sim
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    if Path(ark_sim.__file__).resolve().parent != RUNTIME/'ark_sim' or implementation_digest() != CORE: raise RuntimeError('wrong roster candidate')
    OUT.mkdir(parents=True, exist_ok=True); results = []
    for name, value in [('level_main_01-11.partial.json', apply_fixed12_overlay(json.loads(INPUT.read_bytes()))),
                        ('native_card_deployment_fixture.json', native_deployment_fixture())]:
        program = Compiler().compile(value); output = OUT/name
        if args.check:
            if output.read_bytes() != encoded(value): raise ValueError('roster output drift')
        else: output.write_bytes(encoded(value))
        results.append({'file': name, 'definitions': len(program.definitions), 'sha256': sha(output), 'whole_stage': False})
    print(json.dumps({'implementation': CORE, 'outputs': results}))
