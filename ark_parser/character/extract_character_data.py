#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract Arknights character-side tables to JSON (research artifact).

Reads the Arknights custom FlatBuffers variant (see ark_parser/enemy/
extract_enemy_data.py for the base reader and format notes).

CharacterData field ids follow the C# declaration order (dump.cs:165178),
verified against amiya/kalts/svash2/kroos/texas in the raw binary.

Outputs (relative to this file):
  data/characters.json    all character_table entries (named fields + nested)
  data/skills.json        skill_table entries (skillId -> levels)
  data/devices.json       token/trap/device subset + classification
  data/battle_equip.json  battle_equip_table
  data/uniequip.json      uniequip_table (generic)
"""

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TABLES_DIR = os.path.join(SCRIPT_DIR, "..", "..", "data", "tables")
OUT_DIR = os.path.join(SCRIPT_DIR, "data")
sys.path.insert(0, os.path.join(SCRIPT_DIR, "..", "enemy"))

from extract_enemy_data import FB, i2f, parse_blackboard  # noqa: E402

CHARACTER_TB = os.path.join(TABLES_DIR, "character_table9fc534.bin")
SKILL_TB = os.path.join(TABLES_DIR, "skill_tableafb859.bin")
BATTLE_EQUIP_TB = os.path.join(TABLES_DIR, "battle_equip_table91e6b6.bin")
UNIEQUIP_TB = os.path.join(TABLES_DIR, "uniequip_table8b1bb5.bin")

PROFESSION_NAMES = {
    0: "NONE", 1: "WARRIOR", 2: "SNIPER", 4: "TANK", 8: "MEDIC",
    16: "SUPPORT", 32: "CASTER", 64: "SPECIAL", 128: "TOKEN",
    256: "TRAP", 512: "PIONEER",
}
RARITY_NAMES = {
    0: "TIER_1", 1: "TIER_2", 2: "TIER_3", 3: "TIER_4",
    4: "TIER_5", 5: "TIER_6",
}


def read_str(fb, fpos):
    t = fb.target_of(fpos)
    return fb.read_string(t) if fb.is_string(t) else None


def read_i32(fb, fpos):
    return fb.i32(fpos)


def read_bool(fb, fpos):
    b = fb.d[fpos] if fpos < fb.size else 0
    return bool(b & 1)


def read_f32(fb, fpos):
    return i2f(fb.i32(fpos))


def read_vec(fb, fpos, elem_parser=None, cap=5000):
    t = fb.target_of(fpos)
    if not fb.is_vector(t):
        return None
    out = []
    for slot in fb.vector(t)[:cap]:
        epos = slot + fb.i32(slot)
        if elem_parser is not None:
            out.append(elem_parser(fb, epos))
        else:
            v = fb.parse_value(slot)
            if isinstance(v, dict) and 1 in v and isinstance(v.get(0), int):
                v = v[1]
            out.append(v)
    return out


def read_table(fb, fpos):
    t = fb.target_of(fpos)
    return fb.parse_table(t) if fb.is_table(t) else None


def table_pos(fb, fpos):
    t = fb.target_of(fpos)
    return t if fb.is_table(t) else None


def vector_pos(fb, fpos):
    t = fb.target_of(fpos)
    return t if fb.is_vector(t) else None


def parse_unlock_condition(fb, pos):
    f = fb.table_fields(pos)
    out = {}
    if len(f) > 0 and f[0] is not None:
        out['phase'] = fb.i32(f[0])
    if len(f) > 1 and f[1] is not None:
        out['level'] = fb.i32(f[1])
    return out


def parse_item_bundle(fb, pos):
    f = fb.table_fields(pos)
    out = {}
    if len(f) > 0 and f[0] is not None:
        out['id'] = read_str(fb, f[0])
    if len(f) > 1 and f[1] is not None:
        out['count'] = fb.i32(f[1])
    return out


CHAR_ATTR_NAMES = [
    'maxHp', 'atk', 'def', 'magicResistance', 'cost', 'blockCnt',
    'moveSpeed', 'attackSpeed', 'baseAttackTime', 'respawnTime',
    'hpRecoveryPerSec', 'spRecoveryPerSec', 'maxDeployCount',
    'maxDeckStackCnt', 'tauntLevel', 'massLevel', 'baseForceLevel',
    'epDamageResistance', 'epResistance', 'damageHitratePhysical',
    'damageHitrateMagical', 'abilityRangeForwardExtend', 'defPenetrate',
    'magicResistPenetrate', 'hpRecoveryPerSecByMaxHpRatio',
    'defPenetrateFixed', 'oneMinusStatusResistance',
    'magicResistPenetrateFixed', 'maxEp', 'epRecoveryPerSec',
    'spRecoverRatio', 'epBreakRecoverSpeed', 'slowDown',
]
CHAR_ATTR_FLOAT = {
    'magicResistance', 'moveSpeed', 'attackSpeed', 'baseAttackTime',
    'hpRecoveryPerSec', 'spRecoveryPerSec', 'epDamageResistance',
    'epResistance', 'damageHitratePhysical', 'damageHitrateMagical',
    'abilityRangeForwardExtend', 'defPenetrate', 'magicResistPenetrate',
    'hpRecoveryPerSecByMaxHpRatio', 'defPenetrateFixed',
    'oneMinusStatusResistance', 'magicResistPenetrateFixed',
    'epRecoveryPerSec', 'spRecoverRatio', 'epBreakRecoverSpeed', 'slowDown',
}


def parse_char_attributes(fb, pos):
    f = fb.table_fields(pos)
    out = {}
    for i, nm in enumerate(CHAR_ATTR_NAMES):
        if i >= len(f) or f[i] is None:
            out[nm] = None
            continue
        if nm in CHAR_ATTR_FLOAT:
            out[nm] = i2f(fb.i32(f[i]))
        else:
            out[nm] = fb.i32(f[i])
    return out


def parse_keyframe(fb, pos):
    """KeyFrame{level, data} (dump.cs:166401)."""
    f = fb.table_fields(pos)
    out = {'level': fb.i32(f[0]) if len(f) > 0 and f[0] is not None else None}
    if len(f) > 1 and f[1] is not None:
        t = fb.target_of(f[1])
        if fb.is_table(t):
            out['data'] = parse_char_attributes(fb, t)
        else:
            out['data'] = fb.parse_value(f[1])
    return out


def parse_key_frames(fb, pos):
    """KeyFrames<T> = List<KeyFrame> (dump.cs:166421); serialized directly
    as a vector of KeyFrame tables (verified in phase attributesKeyFrames)."""
    if fb.is_vector(pos):
        return [parse_keyframe(fb, s + fb.i32(s)) for s in fb.vector(pos)]
    if fb.is_table(pos):
        f = fb.table_fields(pos)
        if len(f) > 0 and f[0] is not None:
            t = fb.target_of(f[0])
            if fb.is_vector(t):
                return [parse_keyframe(fb, s + fb.i32(s)) for s in fb.vector(t)]
    return None


def parse_phase(fb, pos):
    """PhaseData (dump.cs:165027): characterPrefabKey, rangeId, maxLevel,
    attributesKeyFrames, evolveCost."""
    f = fb.table_fields(pos)
    out = {}
    if len(f) > 0 and f[0] is not None:
        out['characterPrefabKey'] = read_str(fb, f[0])
    if len(f) > 1 and f[1] is not None:
        out['rangeId'] = read_str(fb, f[1])
    if len(f) > 2 and f[2] is not None:
        out['maxLevel'] = fb.i32(f[2])
    if len(f) > 3 and f[3] is not None:
        t = fb.target_of(f[3])
        out['attributesKeyFrames'] = parse_key_frames(fb, t)
    if len(f) > 4 and f[4] is not None:
        out['evolveCost'] = read_vec(fb, f[4], parse_item_bundle)
    return out


def parse_main_skill(fb, pos):
    """MainSkill (dump.cs:165059): skillId, overridePrefabKey,
    overrideTokenKey, specializeLevelUpData, initialUnlockCond."""
    f = fb.table_fields(pos)
    out = {}
    if len(f) > 0 and f[0] is not None:
        out['skillId'] = read_str(fb, f[0])
    if len(f) > 1 and f[1] is not None:
        out['overridePrefabKey'] = read_str(fb, f[1])
    if len(f) > 2 and f[2] is not None:
        out['overrideTokenKey'] = read_str(fb, f[2])
    if len(f) > 3 and f[3] is not None:
        out['specializeLevelUpData'] = read_vec(
            fb, f[3],
            lambda fb_, p_: {
                'unlockCond': parse_unlock_condition(fb_, p_),
                'levelUpCost': read_vec(fb_, p_ + 0, parse_item_bundle),
            } if False else _parse_specialize(fb_, p_))
    if len(f) > 4 and f[4] is not None:
        t = table_pos(fb, f[4])
        if t:
            out['initialUnlockCond'] = parse_unlock_condition(fb, t)
    return out


def _parse_specialize(fb, pos):
    """SpecializeLevelData (dump.cs:165044): unlockCond, lvlUpTime,
    levelUpCost."""
    f = fb.table_fields(pos)
    out = {}
    if len(f) > 0 and f[0] is not None:
        t = table_pos(fb, f[0])
        if t:
            out['unlockCond'] = parse_unlock_condition(fb, t)
    if len(f) > 1 and f[1] is not None:
        out['lvlUpTime'] = fb.i32(f[1])
    if len(f) > 2 and f[2] is not None:
        out['levelUpCost'] = read_vec(fb, f[2], parse_item_bundle)
    return out


def parse_talent(fb, pos):
    """TalentData (dump.cs:191011): unlockCondition, requiredPotentialRank,
    prefabKey, name, description, rangeId, blackboard, tokenKey,
    isHideTalent."""
    f = fb.table_fields(pos)
    out = {}
    if len(f) > 0 and f[0] is not None:
        t = table_pos(fb, f[0])
        if t:
            out['unlockCondition'] = parse_unlock_condition(fb, t)
    if len(f) > 1 and f[1] is not None:
        out['requiredPotentialRank'] = fb.i32(f[1])
    if len(f) > 2 and f[2] is not None:
        out['prefabKey'] = read_str(fb, f[2])
    if len(f) > 3 and f[3] is not None:
        out['name'] = read_str(fb, f[3])
    if len(f) > 4 and f[4] is not None:
        out['description'] = read_str(fb, f[4])
    if len(f) > 5 and f[5] is not None:
        out['rangeId'] = read_str(fb, f[5])
    if len(f) > 6 and f[6] is not None:
        t = vector_pos(fb, f[6])
        out['blackboard'] = parse_blackboard(fb, t) if t else None
    if len(f) > 7 and f[7] is not None:
        out['tokenKey'] = read_str(fb, f[7])
    if len(f) > 8 and f[8] is not None:
        out['isHideTalent'] = read_bool(fb, f[8])
    return out


def parse_trait(fb, pos):
    """TraitData (dump.cs:164936): unlockCondition, requiredPotentialRank,
    blackboard, overrideDescripton, prefabKey, rangeId."""
    f = fb.table_fields(pos)
    out = {}
    if len(f) > 0 and f[0] is not None:
        t = table_pos(fb, f[0])
        if t:
            out['unlockCondition'] = parse_unlock_condition(fb, t)
    if len(f) > 1 and f[1] is not None:
        out['requiredPotentialRank'] = fb.i32(f[1])
    if len(f) > 2 and f[2] is not None:
        t = vector_pos(fb, f[2])
        out['blackboard'] = parse_blackboard(fb, t) if t else None
    if len(f) > 3 and f[3] is not None:
        out['overrideDescripton'] = read_str(fb, f[3])
    if len(f) > 4 and f[4] is not None:
        out['prefabKey'] = read_str(fb, f[4])
    if len(f) > 5 and f[5] is not None:
        out['rangeId'] = read_str(fb, f[5])
    return out


def parse_potential_rank(fb, pos):
    """PotentialRank (dump.cs:165090): type, description, buff,
    equivalentCost."""
    f = fb.table_fields(pos)
    out = {}
    if len(f) > 0 and f[0] is not None:
        out['type'] = fb.i32(f[0])
    if len(f) > 1 and f[1] is not None:
        out['description'] = read_str(fb, f[1])
    if len(f) > 2 and f[2] is not None:
        t = table_pos(fb, f[2])
        out['buff'] = fb.parse_table(t) if t else None
    if len(f) > 3 and f[3] is not None:
        out['equivalentCost'] = read_vec(fb, f[3], parse_item_bundle)
    return out


def parse_character(fb, pos):
    f = fb.table_fields(pos)
    out = {}
    n = len(f)
    def s(i):
        return read_str(fb, f[i]) if i < n and f[i] is not None else None
    def v(i, parser=None):
        if i >= n or f[i] is None:
            return None
        if parser:
            return read_vec(fb, f[i], parser)
        return read_vec(fb, f[i])
    def t(i):
        if i >= n or f[i] is None:
            return None
        p = table_pos(fb, f[i])
        return fb.parse_table(p) if p else None
    out['name'] = s(0)
    out['description'] = s(1)
    out['sortIndex'] = read_i32(fb, f[2]) if n > 2 and f[2] is not None else None
    out['spTargetType'] = read_i32(fb, f[3]) if n > 3 and f[3] is not None else None
    out['spTargetId'] = s(4)
    out['canUseGeneralPotentialItem'] = read_bool(fb, f[5]) if n > 5 and f[5] is not None else None
    out['canUseActivityPotentialItem'] = read_bool(fb, f[6]) if n > 6 and f[6] is not None else None
    out['potentialItemId'] = s(7)
    out['activityPotentialItemId'] = s(8)
    out['classicPotentialItemId'] = s(9)
    out['nationId'] = s(10)
    out['groupId'] = s(11)
    out['teamId'] = s(12)
    out['mainPower'] = t(13)
    out['subPower'] = v(14)
    out['displayNumber'] = s(15)
    out['appellation'] = s(16)
    out['position'] = read_i32(fb, f[17]) if n > 17 and f[17] is not None else None
    out['tagList'] = v(18)
    out['itemUsage'] = s(19)
    out['itemDesc'] = s(20)
    out['itemObtainApproach'] = s(21)
    out['isNotObtainable'] = read_bool(fb, f[22]) if n > 22 and f[22] is not None else None
    out['isSpChar'] = read_bool(fb, f[23]) if n > 23 and f[23] is not None else None
    out['maxPotentialLevel'] = read_i32(fb, f[24]) if n > 24 and f[24] is not None else None
    out['rarity'] = read_i32(fb, f[25]) if n > 25 and f[25] is not None else None
    out['profession'] = read_i32(fb, f[26]) if n > 26 and f[26] is not None else None
    out['subProfessionId'] = s(27)
    if n > 28 and f[28] is not None:
        p = table_pos(fb, f[28])
        if p:
            tf = fb.table_fields(p)
            cands = None
            if len(tf) > 0 and tf[0] is not None:
                cands = read_vec(fb, tf[0], parse_trait)
            out['trait'] = {'candidates': cands}
    out['phases'] = v(29, parse_phase)
    out['skills'] = v(30, parse_main_skill)
    if n > 31 and f[31] is not None:
        out['displayTokenDict'] = read_vec(fb, f[31])
    if n > 32 and f[32] is not None:
        out['talents'] = read_vec(fb, f[32], lambda fb_, p_: _parse_talent_bundle(fb_, p_))
    out['potentialRanks'] = v(33, parse_potential_rank)
    if n > 34 and f[34] is not None:
        p = table_pos(fb, f[34])
        out['favorKeyFrames'] = parse_key_frames(fb, p) if p else None
    if n > 35 and f[35] is not None:
        out['allSkillLvlup'] = read_vec(fb, f[35], _parse_skill_level_cost)
    return out


def _parse_talent_bundle(fb, pos):
    """TalentDataBundle{candidates} (dump.cs:164864)."""
    f = fb.table_fields(pos)
    if len(f) > 0 and f[0] is not None:
        return {'candidates': read_vec(fb, f[0], parse_talent)}
    return {}


def _parse_skill_level_cost(fb, pos):
    """SkillLevelCost (dump.cs:165120): unlockCond, lvlUpCost."""
    f = fb.table_fields(pos)
    out = {}
    if len(f) > 0 and f[0] is not None:
        p = table_pos(fb, f[0])
        if p:
            out['unlockCond'] = parse_unlock_condition(fb, p)
    if len(f) > 1 and f[1] is not None:
        out['lvlUpCost'] = read_vec(fb, f[1], parse_item_bundle)
    return out


def parse_character_table(fb):
    root_fields = fb.table_fields(fb.root)
    vec = root_fields[0] + fb.i32(root_fields[0])
    entries = fb.read_dict(vec)
    out = {}
    for key, vpos in entries:
        try:
            t = vpos + fb.i32(vpos)
            if fb.is_table(t):
                out[key] = parse_character(fb, t)
        except Exception:
            continue
    return out


def parse_sp_data(fb, pos):
    """SpData (dump.cs:188231): spType, levelUpCost, maxChargeTime, spCost,
    initSp, increment."""
    f = fb.table_fields(pos)
    out = {}
    if len(f) > 0 and f[0] is not None:
        out['spType'] = fb.i32(f[0])
    if len(f) > 1 and f[1] is not None:
        out['levelUpCost'] = read_vec(fb, f[1], parse_item_bundle)
    if len(f) > 2 and f[2] is not None:
        out['maxChargeTime'] = fb.i32(f[2])
    if len(f) > 3 and f[3] is not None:
        out['spCost'] = fb.i32(f[3])
    if len(f) > 4 and f[4] is not None:
        out['initSp'] = fb.i32(f[4])
    if len(f) > 5 and f[5] is not None:
        out['increment'] = i2f(fb.i32(f[5]))
    return out


def parse_skill_level(fb, pos):
    """SkillDataBundle.LevelData (dump.cs:188379): name, rangeId, description,
    skillType, durationType, spData, prefabId, duration, blackboard."""
    f = fb.table_fields(pos)
    out = {}
    n = len(f)
    if n > 0 and f[0] is not None:
        out['name'] = read_str(fb, f[0])
    if n > 1 and f[1] is not None:
        out['rangeId'] = read_str(fb, f[1])
    if n > 2 and f[2] is not None:
        out['description'] = read_str(fb, f[2])
    if n > 3 and f[3] is not None:
        out['skillType'] = fb.i32(f[3])
    if n > 4 and f[4] is not None:
        out['durationType'] = fb.i32(f[4])
    if n > 5 and f[5] is not None:
        p = table_pos(fb, f[5])
        out['spData'] = parse_sp_data(fb, p) if p else None
    if n > 6 and f[6] is not None:
        out['prefabId'] = read_str(fb, f[6])
    if n > 7 and f[7] is not None:
        out['duration'] = i2f(fb.i32(f[7]))
    if n > 8 and f[8] is not None:
        t = vector_pos(fb, f[8])
        out['blackboard'] = parse_blackboard(fb, t) if t else None
    return out


def parse_skill_bundle(fb, pos):
    f = fb.table_fields(pos)
    out = {}
    n = len(f)
    if n > 0 and f[0] is not None:
        out['skillId'] = read_str(fb, f[0])
    if n > 1 and f[1] is not None:
        out['iconId'] = read_str(fb, f[1])
    if n > 2 and f[2] is not None:
        out['hidden'] = read_bool(fb, f[2])
    if n > 3 and f[3] is not None:
        out['levels'] = read_vec(fb, f[3], parse_skill_level)
    return out


def parse_skill_table(fb):
    root_fields = fb.table_fields(fb.root)
    vec = root_fields[0] + fb.i32(root_fields[0])
    entries = fb.read_dict(vec)
    out = {}
    for key, vpos in entries:
        try:
            t = vpos + fb.i32(vpos)
            if fb.is_table(t):
                out[key] = parse_skill_bundle(fb, t)
        except Exception:
            continue
    return out


def classify_devices(chars):
    """Neutral devices/tokens: profession TOKEN(128)/TRAP(256) or
    isNotObtainable/isSpChar markers or name patterns."""
    devices = {}
    others = {}
    for cid, c in chars.items():
        prof = c.get('profession')
        if prof in (128, 256):
            devices[cid] = c
        elif c.get('isNotObtainable') or c.get('isSpChar'):
            others[cid] = c
    return devices, others


def parse_battle_equip(fb):
    root_fields = fb.table_fields(fb.root)
    vec = root_fields[0] + fb.i32(root_fields[0])
    entries = fb.read_dict(vec)
    out = {}
    for key, vpos in entries:
        try:
            t = vpos + fb.i32(vpos)
            if fb.is_table(t):
                out[key] = fb.parse_table(t)
        except Exception:
            continue
    return out


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print('== character_table ==', flush=True)
    fb = FB(CHARACTER_TB)
    chars = parse_character_table(fb)
    path = os.path.join(OUT_DIR, 'characters.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(chars, f, ensure_ascii=False)
    print(f'{len(chars)} characters -> {path}', flush=True)
    a = chars.get('char_002_amiya', {})
    print('amiya sample:', json.dumps(
        {k: a.get(k) for k in ('name', 'position', 'rarity', 'profession',
                               'subProfessionId', 'maxPotentialLevel',
                               'phases', 'skills', 'talents',
                               'potentialRanks')}, ensure_ascii=False)[:600],
          flush=True)

    devices, others = classify_devices(chars)
    path2 = os.path.join(OUT_DIR, 'devices.json')
    with open(path2, 'w', encoding='utf-8') as f:
        json.dump({'token_trap': devices, 'special_unobtainable': others},
                  f, ensure_ascii=False)
    print(f'token/trap devices: {len(devices)}, special others: {len(others)}'
          f' -> {path2}', flush=True)
    print('  device samples:', list(devices)[:15], flush=True)

    print('== skill_table ==', flush=True)
    fb2 = FB(SKILL_TB)
    skills = parse_skill_table(fb2)
    path3 = os.path.join(OUT_DIR, 'skills.json')
    with open(path3, 'w', encoding='utf-8') as f:
        json.dump(skills, f, ensure_ascii=False)
    print(f'{len(skills)} skills -> {path3}', flush=True)
    sk = skills.get('skchr_amiya2_1', {}) or skills.get('skchr_amiya_1', {})
    print('skchr_amiya2_1 sample:', json.dumps(sk, ensure_ascii=False)[:500],
          flush=True)

    print('== battle_equip ==', flush=True)
    fb3 = FB(BATTLE_EQUIP_TB)
    be = parse_battle_equip(fb3)
    path4 = os.path.join(OUT_DIR, 'battle_equip.json')
    with open(path4, 'w', encoding='utf-8') as f:
        json.dump(be, f, ensure_ascii=False)
    print(f'{len(be)} equip packs -> {path4}', flush=True)

    print('== uniequip ==', flush=True)
    import extract_enemy_data as E
    _saved_depth = E.MAX_DEPTH
    E.MAX_DEPTH = 3   # compact: keep top-level fields only (uniequip is huge)
    try:
        fb4 = FB(UNIEQUIP_TB)
        ue = parse_battle_equip(fb4)
    finally:
        E.MAX_DEPTH = _saved_depth
    path5 = os.path.join(OUT_DIR, 'uniequip.json')
    with open(path5, 'w', encoding='utf-8') as f:
        json.dump(ue, f, ensure_ascii=False)
    print(f'{len(ue)} uniequip entries -> {path5}', flush=True)


if __name__ == '__main__':
    main()
