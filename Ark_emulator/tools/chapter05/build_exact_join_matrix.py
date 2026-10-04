"""Complete C5 union8/stage4+6 source join; no subset or stage acceptance."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT/'packages/campaign/chapter05_plans/source.plan.json'
SOURCE = ROOT/'packages/campaign/chapter05_sources/native.reference.json'
OUT = ROOT/'packages/campaign/chapter05_plans/exact_join.preparation.json'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def build():
    plan = json.loads(PLAN.read_bytes()); source = json.loads(SOURCE.read_bytes())
    if len(plan['variants']) != 8 or set(plan['variants']) != set(source['variants']): raise ValueError('Complete union8 source required')
    locks = {PLAN.relative_to(ROOT).as_posix(): sha(PLAN), SOURCE.relative_to(ROOT).as_posix(): sha(SOURCE)}
    observed = {}; candidates = {}
    paths = [ROOT/'packages/campaign'/p for p in (
        'chapter05_units/ordinary.reference_model.json', 'chapter05_units/regenerating/model.json',
        'chapter05_units/special/model.reference.json', 'chapter05_boss/mephi/model.json',
        'chapter05_boss/faust/complete.v2.reference.json')]
    for path in paths:
        if not path.exists():
            observed[path.relative_to(ROOT).as_posix()] = {'status': 'missing_required_candidate_not_empty'}; continue
        d = json.loads(path.read_bytes()); meta = d.get('manifest', {}).get('metadata', {}); name = path.relative_to(ROOT).as_posix()
        locks[name] = sha(path)
        observed[name] = {'sha256': sha(path), 'package_id': d.get('manifest', {}).get('id'),
            'claimed_status': meta.get('status'), 'required_runtime_claim': meta.get('required_runtime'),
            'candidate_only': True, 'formal_approval_inferred': False}
        bindings = meta.get('variant_bindings', [])
        for b in bindings:
            if b.get('variant_id') in plan['variants']:
                candidates.setdefault(b['variant_id'], []).append({'path': name, 'sha256': sha(path), 'unit_definition': b.get('unit_definition')})
        if meta.get('native_variant_id') in plan['variants']:
            candidates.setdefault(meta['native_variant_id'], []).append({'path': name, 'sha256': sha(path), 'unit_definition': d['entities'][0]['id']})
        for unit in d.get('entities', []):
            m = unit.get('metadata', {}); vid = m.get('native_variant_id') or m.get('variant_id')
            if vid in plan['variants'] and not any(c['path'] == name for c in candidates.get(vid, [])):
                candidates.setdefault(vid, []).append({'path': name, 'sha256': sha(path), 'unit_definition': unit['id']})
    variants = {}
    for vid, v in plan['variants'].items():
        sv = source['variants'][vid]; native = v['native_enemy']; d = native['resolved']
        variants[vid] = {'native_reference': deepcopy(v['native_reference']), 'resolved_DB': deepcopy(d),
            'stages': deepcopy(v['stages']), 'spawn_by_stage': {k: s['spawn_by_key'].get(native['native_id'], 0) for k, s in plan['stages'].items()},
            'native_frame_nodes': [{'mode': m['index'], 'nodes': {role: {'class': n.get('native_class'),
                'path_id': n.get('path_id'), 'OnAttack': [e['frame'] for e in (n.get('animation_binding') or {}).get('events', []) if e['name'] == 'OnAttack']}
                for role, n in m['nodes'].items()}} for m in sv['modes']],
            'extra_passive_skill_classes': [p['class'] for p in sv['passive_and_skill_components']],
            'source_module_candidates': candidates.get(vid, []),
            'join_status': 'candidate_bindings_require_peer_and_composition' if candidates.get(vid) else 'explicit_unbound_source_variant',
            'peer_approved_by_this_matrix': False}
    stages = {}
    for level, stage in plan['stages'].items():
        n = stage['native_document']; aliases = {p['alias'] for p in n['predefines']['tokenInsts'] if p['alias'] is not None}
        branches = {}
        for key, branch in (n.get('branches') or {}).items():
            actions = [a for phase in branch['phases'] for a in phase['actions']]
            activations = [a for a in actions if a['actionType'] == 'ACTIVATE_PREDEFINED']
            if any(a['key'] not in aliases for a in activations): raise ValueError('Branch references missing hidden predefine')
            branches[key] = {'raw': deepcopy(branch), 'phase_count': len(branch['phases']), 'action_count': len(actions),
                             'activation_count': sum(a['count'] for a in activations), 'activation_keys': [a['key'] for a in activations]}
        used = {}
        for index in stage['used_routes']:
            ids = sorted({a['variant_id'] for a in stage['actions'] if a.get('variant_id') and a['native']['routeIndex'] == index})
            used[str(index)] = {'raw': deepcopy(n['routes'][index]), 'variants': ids,
                'checkpoint_types': dict(Counter(c['type'] for c in n['routes'][index].get('checkpoints') or []))}
        stages[level] = {'variant_ids': deepcopy(stage['variant_ids']), 'exact_variant_count': len(stage['variant_ids']),
            'spawn_count': stage['spawn_count'], 'spawn_by_key': deepcopy(stage['spawn_by_key']), 'options': deepcopy(n['options']),
            'map_data': deepcopy(n['mapData']), 'used_routes': used, 'all_native_routes': deepcopy(n['routes']),
            'all_native_waves': deepcopy(n['waves']), 'runes': deepcopy(n['runes']), 'optional_runes': deepcopy(n.get('optionalRunes')),
            'predefines': deepcopy(n['predefines']), 'hard_predefines': deepcopy(n.get('hardPredefines')),
            'token_count': len(n['predefines']['tokenInsts']), 'hidden_token_count': sum(p['hidden'] for p in n['predefines']['tokenInsts']),
            'control_actions': [deepcopy(a) for a in stage['actions'] if a['native']['actionType'] != 'SPAWN'],
            'branches': branches, 'whole_stage_executed': False}
    if (stages['level_main_05-09']['exact_variant_count'], stages['level_main_05-09']['spawn_count']) != (4, 51): raise ValueError('5-9 exact inventory changed')
    if (stages['level_main_05-10']['exact_variant_count'], stages['level_main_05-10']['spawn_count']) != (6, 73): raise ValueError('5-10 exact inventory changed')
    if stages['level_main_05-10']['branches']['faust_ballis']['phase_count'] != 7 or stages['level_main_05-10']['hidden_token_count'] != 10:
        raise ValueError('Full Faust branch/hidden predefines source required')
    predef = ROOT/'packages/campaign/chapter05_predefines/source.reference.json'
    if not predef.exists(): raise ValueError('Predefined source cannot silently disappear')
    locks[predef.relative_to(ROOT).as_posix()] = sha(predef)
    pv = json.loads(predef.read_bytes())
    locks[Path(__file__).relative_to(ROOT).as_posix()] = sha(Path(__file__))
    return {'schema': 'ark-sim/chapter05-exact-join-preparation/v1', 'fixed_commit': plan['fixed_commit'],
        'source_locks': locks, 'chapter_union_variant_count': 8, 'stages': stages, 'variants': variants,
        'observed_source_modules': observed, 'predefined_source_policy': pv['prefab'].get('source_policy'),
        'explicit_pending': ['Ballista complete source consumer, startup/hidden alias activation and branch integration pending',
            'Module core/provider identity and namespace/source-stat equality must be verified at composition',
            'Independent peer reports and complete-stage execution required; this matrix never approves a candidate',
            'Full normal-rune policy, control and route semantics, fixed roster/base-only overrides must survive exact stage join'],
        'whole_stage_executed': False, 'independent_reviewed': False, 'actual_client_verified': False}


if __name__ == '__main__':
    result = build(); OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps({'sha256': sha(OUT), 'union': 8, 'stage_variants': {k: v['exact_variant_count'] for k, v in result['stages'].items()},
        'explicit_unbound': [k for k, v in result['variants'].items() if not v['source_module_candidates']], 'whole_stage_executed': False}))
