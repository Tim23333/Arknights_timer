"""Sourced dkmage chain fragment; assembly keeps all other native ownership.

This fragment covers the attack/projectile only. Deathrattle, movement, behavior
selection and other source nodes must be supplied by the stage composition.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tools.chapter10_chain_v1.fixture import package

ROOT = Path(__file__).resolve().parents[2]
VARIANT = 'enemy_1225_dkmage_2@0/b565434d1aca5835'


def build_fragment():
    evidence = json.loads((ROOT/'validation/campaign/chapter10_chain_v1/native_source.v1.json').read_bytes())
    for filename, expected in evidence['source_files'].items():
        if hashlib.sha256(Path(filename).read_bytes()).hexdigest() != expected:
            raise ValueError('Native dkmage chain source drift: '+filename)
    native = json.loads((ROOT/'packages/campaign/chapter10_source_prepare/enemies.native.v1.json').read_bytes())
    resolved = native['variants'][VARIANT]['native_enemy']['resolved']
    attributes = resolved['attributes']
    bb = {row['key']:row['value'] for row in resolved['talentBlackboard']}
    p = package()
    p['projectiles'][0]['chain']['maximum_targets'] = int(bb['epdamage.attack@max_target'])
    p['projectiles'][0]['chain']['attenuation'] = bb['epdamage.attack@chain.atk_scale']
    p['selectors'][0]['region']['radius'] = resolved['rangeRadius']
    p['selectors'][1]['region']['radius'] = bb['epdamage.attack@projectile_range']
    a = p['abilities'][0]
    a['activation'] = {'mode':'automatic_attack','interval_seconds':attributes['baseAttackTime']}
    a['timeline'][0]['at'] = evidence['selected_reference_profile']['OnAttack_frame']
    a['duration_seconds'] = evidence['selected_reference_profile']['full_frame']/30
    a['timeline'][0]['effect']['element_effect']['parameters']['ratio'] = bb['epdamage.attack@ep_damage_ratio']
    # _useCachedAtkOnly=0 maps to actual current source/target at each impact.
    if evidence['attack']['raw']['_useCachedAtkOnly'] != 0:
        raise ValueError('Native cached source attack requires another declared profile')
    if evidence['attack']['raw']['_waitForProjectileInvalid'] != 1:
        raise ValueError('Native attack lacks whole-projectile completion ownership')
    rename = lambda text:text.replace('/chain/probe','/c10/dkmage_chain').replace('/chain/first','/c10/dkmage_chain/first').replace('/chain/next','/c10/dkmage_chain/next')
    def names(value):
        if isinstance(value,str):return rename(value)
        if isinstance(value,list):return [names(v) for v in value]
        if isinstance(value,dict):return {k:names(v) for k,v in value.items()}
        return value
    fragment = names({key:p[key] for key in ('rules','selectors','abilities','projectiles')})
    source_attributes = {'max_hp':attributes['maxHp'],'atk':attributes['atk'],'def':attributes['def'],
        'mres':attributes['magicResistance'],'move_speed':attributes['moveSpeed'],
        'attack_interval':attributes['baseAttackTime'],'attack_speed_ratio':attributes['attackSpeed']/100}
    provenance = {'variant':VARIANT,'source_files':evidence['source_files'],
        'native_attack':deepcopy(evidence['attack']),'selected_profile':evidence['selected_reference_profile'],
        'raw_float_profile_preserved':evidence['raw_float_profile_preserved'],
        'source_attributes':source_attributes,'native_class':evidence['attack']['native_class'],
        'scope':'attack and finite chained projectile only; other source nodes retained by assembler',
        'actual_game_accuracy_verified':False}
    return fragment, provenance


def mount(data, source_entity):
    """Append sourced definitions without deleting any existing ability/node."""
    fragment, provenance = build_fragment()
    for kind,definitions in fragment.items():
        existing = {d['id'] for d in data.get(kind,[])}
        if any(d['id'] in existing for d in definitions):
            raise ValueError('Native chain mount collides with existing '+kind)
        data.setdefault(kind,[]).extend(deepcopy(definitions))
    source_entity['components'].setdefault('abilities',[]).append('ability/c10/dkmage_chain')
    return provenance
