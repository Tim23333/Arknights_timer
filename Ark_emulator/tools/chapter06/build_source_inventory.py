"""Chapter6 complete source footprint and explicit unconsumed capabilities."""
import base64
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'packages/campaign/chapter06_sources/source.inventory.json'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def build():
    paths = {name: ROOT/'packages/campaign'/p for name, p in {
        'plan': 'chapter06_plans/source.plan.json', 'enemies': 'chapter06_sources/native.reference.json',
        'environment': 'chapter06_environment/source.reference.json', 'predefines': 'chapter06_predefines/source.reference.json'}.items()}
    data = {k: json.loads(p.read_bytes()) for k, p in paths.items()}
    plan, enemies, npc = data['plan'], data['enemies'], data['predefines']
    requirements = []
    for vid, v in enemies['variants'].items():
        db = v['native_enemy']['resolved']
        requirements.append({'variant_id': vid, 'native_id': v['native_enemy']['native_id'],
            'exact_reference': v['native_reference'], 'attributes': db['attributes'], 'talent_BB': db.get('talentBlackboard'),
            'DB_skills': db.get('skills'), 'component_consumers': [p['class'] for p in v['passive_and_skill_components']],
            'mode_slots': [{'mode': m['index'], 'slots': {role: {'class': node.get('native_class'),
                'frames': [e['frame'] for e in (node.get('animation_binding') or {}).get('events', []) if e['name'] == 'OnAttack'],
                'projectile': node.get('raw', {}).get('_projectileKey')} for role, node in m['nodes'].items()}} for m in v['modes']],
            'runtime_authored': False})
    db_keys = set()
    def scan(value):
        if isinstance(value, dict):
            if value.get('loadFromDB') and value.get('buffKey'): db_keys.add(value['buffKey'])
            for child in value.values(): scan(child)
        elif isinstance(value, list):
            for child in value: scan(child)
    scan(enemies['prefabs']); scan(enemies['projectiles']); scan(npc['prefabs']); scan(npc['skill_prefabs'])
    buff_path = ROOT.parent/'data/anon_textassets/buff_table352282.dat'; raw = buff_path.read_bytes()
    db_source = {'path': buff_path.relative_to(ROOT.parent).as_posix(), 'sha256': sha(buff_path), 'bytes': len(raw),
        'raw_source_base64': base64.b64encode(raw).decode(), 'required_DB_keys': sorted(db_keys),
        'literal_offsets': {k: raw.find(k.encode()) for k in sorted(db_keys)},
        'source_policy': 'Frozen local binary preserved; full schema/field conversion and table-version alignment still required; no guessed empty Buff substituted'}
    states = {}
    for name, stage in plan['stages'].items():
        n = stage['native_document']
        states[name] = {'spawn_count': stage['spawn_count'], 'spawn_by_key': stage['spawn_by_key'], 'variant_ids': stage['variant_ids'],
            'options': n['options'], 'predefines': n['predefines'], 'branches': n['branches'], 'waves': n['waves'], 'routes': n['routes'],
            'runes': n['runes'], 'map_data': n['mapData'], 'control_counts': stage['control_count_by_type']}
    return {'schema': 'ark-sim/chapter06-complete-source-inventory/v1', 'fixed_commit': plan['fixed_commit'],
        'selected_stage_codes': {'main_06-14': '6-16', 'main_06-15': '6-17'},
        'source_sha256': {k: {'path': p.relative_to(ROOT).as_posix(), 'sha256': sha(p)} for k, p in paths.items()},
        'builder_sha256': sha(Path(__file__)), 'stages': states, 'enemy_consumer_matrix': requirements,
        'BSON_templates': {k: v['parsed'] for k, v in enemies['bson_templates']['templates'].items()},
        'buff_DB_source': db_source,
        'required_semantic_consumers': [
            'Cold DB effects, cold-to-frozen status transition, timing/stack/application and immunity/source qualification',
            'e2c_frozen_atkscale ON_CALCULATE_DAMAGE checks TARGET FROZEN, then source BB 1.5 or2.5; never unconditional self-ATK multiplication',
            'FrostNova2 modes, reborn10s/ATK+.5/invincible20s, normal28-frame projectile and freeze5, skill priority/cooldowns, IceShield and SummonFrosts branch',
            'Snmage coldattack priority0/spCost2 and ReadyEnemySkillEffect/normal20-frame projectile; no invented continuous SP recovery',
            'Snslime ON_OWNER_KILLED requires unsilenced source, actual projectile_snslime damage/cold payload and geometry',
            'Story frstar2_s NeverTrigger and distinct forced IceShield/IceBurst clocks; blood.damage2000 PURE NoSourceDamage without modifier/ignore SP',
            'Two alias-bearing hidden frost traps, branch one phase/two activations, sktok_frosts .8s preDelay and loadFromDB e2c_cold',
            'Fence/teleport exact tile masks, native routes/checkpoints/offsets and controlled transitions',
            '6-17 E2L25 Amiya/Swallow/Blaze normal/talents selected skills -1, native hidden aliasNone story-key activation and source Story scripts',
            '6-17 native training slots0/life1/DP0/cost interval9999; fixed12 overlay is explicit policy conflict, not silently rewritten source'],
        'source_conflicts': [p['source_policy'] for p in npc['prefabs'].values() if p.get('source_policy')],
        'story_sources': {k: {'status': v.get('status'), 'source': v.get('source'), 'command_counts': v.get('command_counts')} for k, v in npc['stories'].items()},
        'runtime_authored': False, 'formal_approved': False, 'whole_stage_executed': False, 'actual_client_verified': False}


if __name__ == '__main__':
    value = build(); OUT.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps({'sha256': sha(OUT), 'variants': len(value['enemy_consumer_matrix']), 'DB_keys': value['buff_DB_source']['required_DB_keys'], 'whole_stage_executed': False}))
