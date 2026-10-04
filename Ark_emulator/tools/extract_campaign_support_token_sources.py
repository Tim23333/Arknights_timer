"""Exact default token references from a pinned official external aggregate AB."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.extract_campaign_animation_bindings import local, unity_payload, parse_spine, resolve_animation, library_identity

SOURCE = ROOT.parent / 'unpack_work/campaign_external/battle_prefabs_tokens.20250327.ab'
OUTPUT = ROOT / 'packages/campaign/support_tokens.reference.json'
EXPECTED_SHA = 'b9f16db4bfc8e8c880a0f90a1a7a74eda3b47c2188d0a151e5239d154716d475'
EXPECTED_MD5 = '9e1440026259ebe74be054962e2bd656'
TOKENS = ('token_10002_kalts_mon3tr', 'token_10009_weedy_cannon', 'token_10003_cgbird_bird')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    import UnityPy
    raw = SOURCE.read_bytes()
    if len(raw) != 9824830 or hashlib.sha256(raw).hexdigest() != EXPECTED_SHA or hashlib.md5(raw).hexdigest() != EXPECTED_MD5:
        raise ValueError('pinned official token bundle bytes identity mismatch')
    objects = {o.path_id: o for o in UnityPy.load(str(SOURCE)).objects}
    trees = {}
    def tree(uid):
        if uid not in trees:
            trees[uid] = objects[uid].read_typetree()
        return trees[uid]
    def pointer(value):
        return tree(local(value))
    def refs(value):
        if isinstance(value, dict):
            if 'm_FileID' in value and 'm_PathID' in value:
                if value['m_FileID'] == 0 and value['m_PathID']:
                    yield value['m_PathID']
            else:
                for child in value.values():
                    yield from refs(child)
        elif isinstance(value, list):
            for child in value:
                yield from refs(child)
    result = {'schema': 'ark-sim/support-token-sources/v1', 'status': 'external2025_source_profile',
        'source_version_matches_local': False, 'client_validated': False,
        'source': {'official_manifest_commit': 'f9453cd31ec03aad10be4409af95eb1ac2fdee5f',
            'version_id': '25-03-27-16-19-10-4d4819', 'manifest_name': 'battle/prefabs/[uc]tokens.ab',
            'bytes': len(raw), 'sha256': EXPECTED_SHA, 'md5': EXPECTED_MD5,
            'download_proof': json.loads((ROOT / 'validation/campaign/token_bundle_source_20261002.json').read_bytes())},
        'extractor_sha256': sha(Path(__file__)), 'reader_identity': library_identity(), 'tokens': {}}
    from tools.build_kalts_skill_recipe import decode_bson_document, BUFF_SOURCE
    bson = unity_payload(BUFF_SOURCE.read_bytes())
    templates, spans = decode_bson_document(bson)
    lo, hi = spans[('kalts_token_death_rattle_projectile',)]
    result['death_template'] = {'source_sha256': sha(BUFF_SOURCE), 'parsed': templates['kalts_token_death_rattle_projectile'],
        'raw_bson_base64': base64.b64encode(bson[lo:hi]).decode(), 'sha256': hashlib.sha256(bson[lo:hi]).hexdigest()}
    table_path = ROOT.parent / 'unpack_work/campaign_tables/character_table.json'
    characters = json.loads(table_path.read_bytes())
    result['token_character_table'] = {'source_sha256': sha(table_path), 'tokens': {cid: characters[cid] for cid in TOKENS}}
    for cid in TOKENS:
        roots = [uid for uid, o in objects.items() if o.type.name == 'GameObject' and tree(uid)['m_Name'] == cid]
        if len(roots) != 1:
            raise ValueError('exact default token GameObject is absent or ambiguous')
        uid = roots[0]
        components = [pointer(x['component']) for x in tree(uid)['m_Component'] if objects[local(x['component'])].type.name == 'MonoBehaviour']
        entity_roots = [x for x in components if '_modes' in x and '_animator' in x]
        if len(entity_roots) != 1:
            raise ValueError('exact token entity root ambiguous')
        entity = entity_roots[0]
        animator = pointer(entity['_animator'])
        faces = {'single': animator['_skeleton']} if '_skeleton' in animator else {'front': animator['_front']['skeleton'], 'back': animator['_back']['skeleton']}
        skeletons = {}
        for face, reference in faces.items():
            renderer = pointer(reference)
            data_reference = renderer['skeletonDataAsset']
            data_asset = pointer(data_reference)
            text_uid = local(data_asset['skeletonJSON'])
            text = tree(text_uid)
            payload = unity_payload(objects[text_uid].get_raw_data())
            if text['m_Name'] != cid + '.skel':
                raise ValueError('default token uses a different skin skeleton')
            skeletons[face] = {'renderer_path_id': local(reference), 'data_asset_path_id': local(data_reference),
                'text_asset_path_id': text_uid, 'native_name': text['m_Name'], 'payload_base64': base64.b64encode(payload).decode(),
                'payload_sha256': hashlib.sha256(payload).hexdigest(), 'parsed': parse_spine(payload)}
        modes = []
        for index, mode_ref in enumerate(entity['_modes']):
            mode = pointer(mode_ref)
            if mode['_attack']['m_PathID'] == 0 and mode['_attackTrigger']['m_PathID'] == 0:
                modes.append({'mode_index': index, 'mode_path_id': local(mode_ref), 'mode_fields': mode,
                    'native_attack_absent': True, 'exact_bindings': {}})
                continue
            attack = pointer(mode['_attack'])
            trigger = pointer(mode['_attackTrigger'])
            key = attack['_animKey']
            bindings = {face: resolve_animation(key, animator['_animations'], skel['parsed']) for face, skel in skeletons.items()}
            modes.append({'mode_index': index, 'mode_path_id': local(mode_ref), 'mode_fields': mode,
                'attack_path_id': local(mode['_attack']), 'attack_fields': attack,
                'trigger_path_id': local(mode['_attackTrigger']), 'trigger_fields': trigger, 'exact_bindings': bindings})
        pending = [uid]
        frozen = {}
        allowed = {'GameObject', 'Transform', 'RectTransform', 'MonoBehaviour', 'MonoScript'}
        while pending:
            current = pending.pop()
            if current in frozen or current not in objects or objects[current].type.name not in allowed:
                continue
            native_tree = tree(current)
            frozen[current] = {'unity_type': objects[current].type.name, 'fields': native_tree}
            pending.extend(refs(native_tree))
        result['tokens'][cid] = {'root_gameobject_path_id': uid, 'entity_fields': entity,
            'animator_fields': animator, 'skeletons': skeletons, 'modes': modes, 'linked_native_components': frozen,
            'pending': ['external2025_vs_local2026_version_match', 'native_FSM_signal_animation_scaling_and_first_clock',
                'projectile_callback_and_full_native_token_lifecycle']}
    return json.loads(json.dumps(result))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    value = build()
    if args.check:
        if json.loads(OUTPUT.read_bytes()) != value:
            raise ValueError('token source mapping, payload or reader identity changed')
    else:
        OUTPUT.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'output': str(OUTPUT), 'tokens': list(value['tokens']), 'status': value['status']}))


if __name__ == '__main__':
    main()
