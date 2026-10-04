"""Bind actual mocock/crossbow sources to generic persistent projectile profiles."""
from copy import deepcopy
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.build_chapter01_stage_models import encoded, sha

PINS = {
    'level_main_01-11': ('packages/campaign/chapter01_stage_models/m21/level_main_01-11.partial.json', '2fd475a0491c86b0ab8d48ff1a17b983e5156d23bc5ea20a77782c8484e77e33'),
    'level_main_01-12': ('packages/campaign/chapter01_stage_models/m21/level_main_01-12.partial.json', '9aa6f6b6aceb2eb1f2ced0013025765742f305d2b31dbf045e6c13201424154d'),
    'enemy_source': ('packages/campaign/chapter01_sources/native.reference.json', 'a242f94040c7f96d175056e6ceffa285ea10f60bec00db1ab7f354fe0739b0cd'),
    'npc_source': ('packages/campaign/chapter01_predefines/native.reference.json', '15eb6edf057af42e1c03acf441cc44852f1a3b4aefd511dd23428fcead1413e6'),
}
CORE = 'c069e0206c076b429750b3fd97a507c54fb8e34fee51376c2f979f434151b95e'
RUNTIME = ROOT.parent/'unpack_work/campaign_m21_integration_candidate'
OUT = ROOT/'packages/campaign/chapter01_stage_models/m22'


def build(level):
    sources = {}
    for key, (path, pin) in PINS.items():
        if sha(ROOT/path) != pin: raise ValueError('frozen ranged input drift: '+path)
        sources[key] = json.loads((ROOT/path).read_bytes())
    p = sources[level]; profiles = {}; source_locks = {}
    import UnityPy
    environments = {}
    for name, record, movement_kind in (
        ('mocock', sources['enemy_source']['projectiles']['projectile_mocock'], 'ParacurveMovement'),
        ('crossbow', sources['npc_source']['projectile'], 'AdvancedMovement')):
        asset = ROOT.parent/record['source']['path']; pin = record['source']['sha256']
        if sha(asset) != pin: raise ValueError('actual projectile asset drift')
        if asset not in environments: environments[asset] = {obj.path_id: obj for obj in UnityPy.load(str(asset)).objects}
        relevant = {kind: [(pid, item) for pid, item in record['components'].items() if item['native_class'] == kind]
            for kind in ('SimpleProjectile', movement_kind)}
        if any(len(rows) != 1 for rows in relevant.values()): raise ValueError('projectile component closure ambiguous')
        for rows in relevant.values():
            pid, item = rows[0]
            if environments[asset][int(pid)].read_typetree() != item['raw']: raise ValueError('actual projectile typetree drift')
        simple = relevant['SimpleProjectile'][0][1]['raw']; mover = relevant[movement_kind][0][1]['raw']
        if (simple['_canHitSameTargetMultipleTimes'], simple['_maxHitNum'], simple['_stopAfterMaxHit'], simple['_stopAfterFirstHit'],
            simple['_stopWhenSourceInvalid'], simple['_alwaysHitTraceTargetInTheEnd']) != (0, 1, 1, 0, 0, 1):
            raise ValueError('unsupported source projectile lifecycle flags')
        if mover['_flyToTargetLocationOnly'] != 0 or mover['_forceReachedWhenTimeup'] != 1:
            raise ValueError('source target-follow/expiry profile changed')
        if name == 'crossbow' and (mover['_moveType'] != 1 or mover['_addInertia'] or mover['_useDynamicSpeed']):
            raise ValueError('unsupported AdvancedMovement source mode')
        if name == 'mocock' and (mover['_useRandomHeight'] or mover['_randomInverseParacurve']):
            raise ValueError('source random arc requires explicit RNG model')
        template = deepcopy(next(d for d in p['projectiles'] if d['id'] == 'projectile/chapter01_w/normal'))
        template['id'] = 'projectile/chapter01/'+name
        template['motion']['parameters'].update(speed=mover['_speed'], raise_height=mover.get('_raiseHeight', 0),
            height_threshold=mover.get('_noRaiseHeightThreshold', 0))
        template['lifetime_seconds'] = simple['_lifeTime']
        template['metadata'] = {'native_source': deepcopy(record), 'fresh_component_path_ids': [rows[0][0] for rows in relevant.values()],
            'profile': 'sample_each_tick_planar_homing_and_relative_swept_trace_point_v1', 'client_body_calibrated': False,
            'native_movement_kind': movement_kind, 'native_method_body_and_3D_collision': 'client_pending',
            'source_cast_end_cleanup_policy': 'retain detached launched instance; native notClear flag body pending'}
        p['projectiles'].append(template); profiles[name] = template['id']; source_locks['../'+record['source']['path']] = pin
    replacements = 0
    for ability in p['abilities']:
        if ability['id'] in ('ability/enemy_1028_mocock/ch1_model_normal', 'ability/enemy_1028_mocock_2/ch1_model_normal'):
            name = 'mocock'
        elif ability['id'] == 'ability/ch1_predefined_adnach_normal': name = 'crossbow'
        else: continue
        ability.get('parameters', {}).pop('projectile_speed', None)
        for entry in ability['timeline']:
            effect = entry['effect']
            if effect['op'] != 'damage': raise ValueError('expected exact source ordinary damage signal')
            effect['projectile_definition'] = profiles[name]
            effect['read_mode'] = {'source_attributes': 'at_hit', 'target_attributes': 'at_hit'}
            replacements += 1
        ability.setdefault('metadata', {})['persistent_projectile_profile'] = profiles[name]
        profile = ability['metadata'].get('profile')
        if profile is not None:
            profile['flight_profile'] = {'id': 'persistent_planar_homing_visual_arc_v1',
                'source': profiles[name], 'position_sample': 'each logical projectile step',
                'source_attributes': 'at_hit', 'target_attributes': 'at_hit',
                'collision': 'relative swept trace point; native body pending', 'client_verified': False}
            profile['model_gap'] = [gap for gap in profile.get('model_gap', []) if gap not in {
                'native_paracurve_collision_and_curved_path', 'native_projectile_expiry_after_dynamic_chase'}]
            profile.setdefault('client_pending', []).append('native_cast_end_projectile_cleanup_and_3D_body')
    if replacements != 3: raise ValueError('ranged ability inventory changed')
    meta = p['manifest']['metadata']; meta.update(builder_sha256=sha(Path(__file__)), required_runtime=CORE,
        ranged_projectile_profiles=profiles)
    meta['source_locks'].update({path: pin for path, pin in PINS.values()}); meta['source_locks'].update(source_locks)
    meta['pending_model_gaps'] = [gap for gap in meta['pending_model_gaps'] if gap != 'ranged_enemy_persistent_tracking_and_collision']
    meta['pending_model_gaps'].append('new_mocock_crossbow_tracking_profiles_require_independent_execution')
    p['manifest']['id'] += '/m22_ranged'
    p['scenarioDraft']['id'] += '/m22_ranged'
    return p


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--check', action='store_true'); args = parser.parse_args()
    sys.path.insert(0, str(RUNTIME))
    import ark_sim
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    if Path(ark_sim.__file__).resolve().parent != RUNTIME/'ark_sim' or implementation_digest() != CORE:
        raise RuntimeError('wrong frozen integration runtime')
    OUT.mkdir(parents=True, exist_ok=True); results = []
    for level in ('level_main_01-11', 'level_main_01-12'):
        p = build(level); program = Compiler().compile(p); output = OUT/(level+'.partial.json')
        if args.check:
            if output.read_bytes() != encoded(p): raise ValueError('ranged profile output drift')
        else: output.write_bytes(encoded(p))
        results.append({'level': level, 'definitions': len(program.definitions), 'sha256': sha(output), 'whole_stage': False})
    print(json.dumps({'implementation': CORE, 'stages': results}))
