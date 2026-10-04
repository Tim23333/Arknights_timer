"""Attach native Default tracking and Reborn release Buff lifecycles."""
import json
import hashlib
import sys
from pathlib import Path
from copy import deepcopy

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT.parent / 'unpack_work/campaign_wave_track_v3_candidate'
CORE = '65897b66ed666f844c029780174af7764101111392d983441f5ff98009891dea'
BASE = ROOT / 'packages/campaign/chapter08_consumers/bsnake'
PARENT = BASE / 'four_modes.module.v2.json'
SOURCE = BASE / 'source.closure.v1.json'
OUT = BASE / 'four_modes.wave_source.v3.json'
TRACK = 'buff/ch8/source/bsnake_t[track_at_next_wave]'
RELEASE = 'buff/ch8/source/bsnake_t[release_wave]'
BGM = 'buff/ch8/source/bsnake_t[bgm]'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ancestor_path(source, component):
    hierarchy = {row['path_id']: row for row in source['prefab']['hierarchy']}
    current, parts = component['gameobject_path_id'], []
    while current in hierarchy:
        row = hierarchy[current]
        parts.append(row['name'])
        current = row['parent_path_id']
    return '/'.join(reversed(parts))


def request(node):
    assert node['_sourceType'] == 'BUFF_OWNER'
    return {'op': 'finish_timeline_wave', 'target': 'source', 'parameters': {
        'finish_and_skip': node['_finishAndSkip'], 'track_source_at_next_wave': node['_trackSourceAtNextWave'],
        'track_source_wave_delta': node['_trackSourceAtWaveDelta'],
        'track_all_managed_at_next_wave': node['_trackAllManagedEnemiesAtNextWave']}}


def build():
    source = json.loads(SOURCE.read_bytes())
    components = source['prefab']['components']
    track = components['-1968419998014933628']
    release = components['-8748329441790102140']
    bgm = components['-4499604213228538492']
    paths = {name: ancestor_path(source, row) for name, row in (('track', track), ('release', release), ('bgm', bgm))}
    assert paths['track'].endswith('/Modes/Default/Talent/TrackAtNextWave')
    assert paths['release'].endswith('/Modes/Reborn/Talent/ReleaseWave')
    assert paths['bgm'].endswith('/Modes/Default/Talent/Reborn')
    templates = source['BSON']['templates']
    true_node = templates['track_at_next_wave_when_buff_finish']['parsed']['eventToActions']['ON_BUFF_FINISH'][0]
    false_node = templates['finish_current_wave_when_buff_finish']['parsed']['eventToActions']['ON_BUFF_FINISH'][0]
    bgm_node = templates['play_bgm_when_buff_finish']['parsed']['eventToActions']['ON_BUFF_FINISH'][0]
    assert true_node['_trackSourceAtNextWave'] is True and false_node['_trackSourceAtNextWave'] is False
    assert bgm_node['_needSourceStateRunning'] is True
    p = json.loads(PARENT.read_bytes())
    definitions = {row['id']: row for row in p['definitions']}
    owner = definitions['unit/ch8/bsnake/cadb87696bef4de2']['components']
    owner['buffs']['initial'] += [TRACK, BGM]
    assert TRACK not in owner['rebirth']['retain_buffs'] and RELEASE not in owner['rebirth']['retain_buffs']
    definitions[TRACK] = {'id': TRACK, 'kind': 'buff', 'on_remove': [request(true_node)],
                          'metadata': {'native_component': track, 'ancestor_path': paths['track']}}
    definitions[RELEASE] = {'id': RELEASE, 'kind': 'buff', 'on_remove': [request(false_node)],
                            'metadata': {'native_component': release, 'ancestor_path': paths['release']}}
    definitions[BGM] = {'id': BGM, 'kind': 'buff', 'on_remove': [{'op': 'emit', 'target': 'source',
                            'event': 'source.bsnake.bgm.observed',
                            'payload': {'bgm_key': source['consumer_merged_BB12']['reborn.bgm']['valueStr']}}],
                        'metadata': {'native_component': bgm, 'ancestor_path': paths['bgm'],
                                     'policy': 'Real Default→firstrebirth clearing while actoralivewaiting; audio observation only'}}
    first = definitions['buff/ch8/source/bsnake_s[screen_attack]']
    first['on_remove'].append({'op': 'apply_buff', 'target': 'source', 'buff': RELEASE})
    p['manifest']['id'] = 'package/ch8/bsnake/four_modes_wave_source_v3'
    meta = p['manifest']['metadata']
    meta['required_runtime'] = CORE
    meta['source_locks'].update({str(path.resolve()): sha(path) for path in (PARENT, SOURCE, Path(__file__))})
    meta['native_wave_talent_paths'] = paths
    meta['native_wave_requests'] = {'first_Default_true': request(true_node), 'second_Reborn_false': request(false_node)}
    meta['scope'] = 'Fourmode7row source graph plus literal DefaultTrue tracking/firstdeath and RebornFalse release/seconddeath; fullstage admission pending'
    meta['pending_required'] = ['Full native JT8-3 source44birth/map/opera/story conversion',
                                'Source mode scheduling/clock/visibility independent complete join',
                                'Firstsource raw .5 vs site100% recovery conflict explicitly preserved',
                                'Reference visual aura bookkeeping/control profile closure']
    p['definitions'] = list(definitions.values())
    return p


if __name__ == '__main__':
    sys.path.insert(0, str(RUNTIME))
    sys.path.insert(1, str(ROOT))
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    from tools.chapter08_joint_v4.build_bsnake_partial_join_v1 import providers
    assert implementation_digest() == CORE
    p = build()
    loop = json.loads((BASE.parent / 'flame/loop.profile.v3.json').read_bytes())
    fixture = deepcopy(p)
    fixture['definitions'].append({'id': 'unit/ch8/flame/level1', 'kind': 'entity', 'components': {'spatial': {}}})
    fixture['scenarioDraft'] = {'id': 'scene/bsnake/wavesource_compile', 'ruleset': 'ruleset/ark_standard',
        'map': {'rows': 9, 'cols': 15}, 'branches': loop['runtime_branch'], 'initialEntities': loop['initial_entities'],
        'timeline': {'policy': 'managed_clear', 'negative_timeout_policy': 'wait_for_clear',
                     'waves': [{'max_wait_seconds': -1, 'fragments': [{'actions': [{'kind': 'spawn', 'spawn': {
                         'definition': 'unit/ch8/bsnake/cadb87696bef4de2', 'instanceAlias': 'boss', 'position': {'row': 4, 'col': 10}}}]}]}]}}
    Compiler(providers=providers()).compile(fixture)
    assert not OUT.exists()
    OUT.write_text(json.dumps(p, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'sha': sha(OUT), 'definitions': len(p['definitions']), 'actual_compile': True}))
