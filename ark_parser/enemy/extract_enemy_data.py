#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract Arknights enemy-side data tables to JSON (research artifact).

Reads the Arknights custom FlatBuffers variant:
  [u32 name_len][name bytes][pad to 4][128B obfuscation][...]
  root uoffset -> root table; table: i32 soffset -> vtable;
  vtable: u16 vts, u16 objsz, u16 field_offset[] (0 = absent);
  string: u32 len + utf8 + NUL; vector: u32 count + slots;
  dict entries are 2-field tables (field0=key string, field1=value).

Undefinable<T> in this data is a 2-field wrapper table:
  field0 = hasValue (1 byte bool, unaligned -> do not read as i32)
  field1 = value (inline scalar or offset to string/table/vector)
An empty/1-field wrapper means the value is not set.

Outputs (relative to this file):
  data/enemy_database.json        all enemies (id -> levels -> data)
  data/enemy_handbook.json        handbook entries (generic parse)
  data/stage_enemy_usage.json     per-stage level data: waves/enemies/routes
  data/enemy_stats.json           summary stats (tags/behaviors/prefabKeys/bb keys)

Usage:
    python extract_enemy_data.py
"""

import collections
import json
import os
import struct
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TABLES_DIR = os.path.join(SCRIPT_DIR, "..", "..", "data", "tables")
OUT_DIR = os.path.join(SCRIPT_DIR, "data")

ENEMY_DB = os.path.join(TABLES_DIR, "enemy_databasea5b667.bin")
ENEMY_HB = os.path.join(TABLES_DIR, "enemy_handbook_table493349.bin")
STAGE_TB = os.path.join(TABLES_DIR, "stage_table9f5b77.bin")

MAX_DEPTH = 10


def i2f(val):
    """Reinterpret int32/uint32 as IEEE754 float (blackboard display rule)."""
    if isinstance(val, int) and -(2 ** 31) <= val < 2 ** 32:
        val &= 0xFFFFFFFF
        f = struct.unpack('<f', struct.pack('<I', val))[0]
        return round(f, 4)
    return val


class FB:
    def __init__(self, path):
        self.path = path
        self.d = open(path, 'rb').read()
        self.size = len(self.d)
        name_len = self.u32(0)
        self.name = self.d[4:4 + name_len].decode('ascii', 'replace')
        self.start = ((4 + name_len + 3) & ~3) + 132
        root_off = self.u32(self.start)
        self.root = self.start + root_off

    def u16(self, p):
        return struct.unpack_from('<H', self.d, p)[0]

    def u32(self, p):
        return struct.unpack_from('<I', self.d, p)[0]

    def i32(self, p):
        return struct.unpack_from('<i', self.d, p)[0]

    def f32(self, p):
        return struct.unpack_from('<f', self.d, p)[0]

    def table_fields(self, tpos):
        soff = self.i32(tpos)
        vpos = tpos - soff
        if not (0 <= vpos < self.size - 4):
            raise ValueError(f'bad vtable pos {vpos:#x} for table {tpos:#x}')
        vts = self.u16(vpos)
        objsz = self.u16(vpos + 2)
        if vts < 4 or vts > 1024 or vts % 2 or objsz < 4 or objsz > 16384:
            raise ValueError(f'bad vtable header at {vpos:#x}: vts={vts} obj={objsz}')
        if vpos + vts > self.size:
            raise ValueError(f'vtable overruns file at {vpos:#x}')
        fields = []
        for i in range((vts - 4) // 2):
            fo = self.u16(vpos + 4 + 2 * i)
            if fo == 0 or fo >= objsz or tpos + fo >= self.size:
                fields.append(None)
            else:
                fields.append(tpos + fo)
        return fields

    def is_table(self, p):
        try:
            self.table_fields(p)
            return True
        except ValueError:
            return False

    def is_string(self, p):
        if p < 0 or p + 4 > self.size:
            return False
        slen = self.u32(p)
        if slen < 1 or slen > 65536 or p + 4 + slen >= self.size:
            return False
        if self.d[p + 4 + slen] != 0:
            return False
        try:
            s = self.d[p + 4:p + 4 + slen].decode('utf-8')
        except UnicodeDecodeError:
            return False
        for ch in s:
            o = ord(ch)
            if o < 0x20 and ch not in '\n\t':
                return False
        return True

    def read_string(self, p):
        slen = self.u32(p)
        return self.d[p + 4:p + 4 + slen].decode('utf-8', 'replace')

    def vector(self, pos):
        cnt = self.u32(pos)
        out = []
        for i in range(cnt):
            out.append(pos + 4 + 4 * i)
        return out

    def is_vector(self, p):
        if p < 0 or p + 4 > self.size:
            return False
        cnt = self.u32(p)
        return 1 <= cnt <= 200000 and p + 4 + 4 * cnt <= self.size

    # ---- generic value parser ----
    def parse_value(self, pos, depth=0):
        rel = self.i32(pos)
        target = pos + rel
        if rel != 0 and 4 <= target < self.size - 4 and depth < MAX_DEPTH:
            if self.is_string(target):
                return self.read_string(target)
            if self.is_table(target):
                return self.parse_table(target, depth + 1)
            vec = self.try_vector(target, depth)
            if vec is not None:
                return vec
        return rel

    def try_vector(self, p, depth):
        if not self.is_vector(p):
            return None
        cnt = self.u32(p)
        if cnt > 3000:
            return None
        first = p + 4
        rel0 = self.i32(first)
        t0 = first + rel0
        if rel0 != 0 and 4 <= t0 < self.size - 4:
            if self.is_string(t0) or self.is_table(t0):
                return [self.parse_value(p + 4 + 4 * i, depth + 1) for i in range(cnt)]
        vals = [self.i32(p + 4 + 4 * i) for i in range(cnt)]
        if all(-100000 <= v <= 100000 for v in vals):
            return vals
        return None

    def parse_table(self, tpos, depth=0):
        fields = self.table_fields(tpos)
        vpos = tpos - self.i32(tpos)
        vts = self.u16(vpos)
        objsz = self.u16(vpos + 2)
        present = [i for i, fp in enumerate(fields) if fp is not None]
        if vts == 8 and objsz == 12 and len(present) == 2:
            # Undefinable<T> wrapper: field0 = hasValue (1-byte bool),
            # field1 = value (inline scalar or offset).
            out = {}
            for idx in present:
                if idx == 0:
                    out[0] = self.d[fields[0]] if fields[0] < self.size else 0
                else:
                    out[1] = self.parse_value(fields[1], depth)
            return out
        # overlapping slots: one is a 1-byte bool flag, never follow its offset
        skip_bool = set()
        for i in range(len(fields)):
            if fields[i] is None:
                continue
            for j in range(i + 1, len(fields)):
                if fields[j] is None:
                    continue
                if abs(fields[i] - fields[j]) < 4:
                    bi = self.d[fields[i]] if fields[i] < self.size else 255
                    bj = self.d[fields[j]] if fields[j] < self.size else 255
                    if bi in (0, 1) and bj not in (0, 1):
                        skip_bool.add(i)
                    elif bj in (0, 1) and bi not in (0, 1):
                        skip_bool.add(j)
        out = {}
        for idx, fpos in enumerate(fields):
            if fpos is None:
                continue
            if idx in skip_bool:
                out[idx] = self.d[fpos] if fpos < self.size else 0
            else:
                out[idx] = self.parse_value(fpos, depth)
        return out

    # ---- structure probes ----
    def target_of(self, fpos):
        rel = self.i32(fpos)
        return fpos + rel

    def read_dict(self, vec_pos):
        """Read vector of {key, value} entry tables -> list of (key, value_pos)."""
        cnt = self.u32(vec_pos)
        entries = []
        for i in range(cnt):
            slot = vec_pos + 4 + 4 * i
            epos = slot + self.i32(slot)
            fields = self.table_fields(epos)
            if len(fields) < 2 or fields[0] is None or fields[1] is None:
                raise ValueError(f'entry {i} at {epos:#x} malformed')
            key = self.read_string(fields[0] + self.i32(fields[0]))
            entries.append((key, fields[1]))
        return entries


ENEMY_ATTR_NAMES = [
    'maxHp', 'atk', 'def', 'magicResistance', 'cost', 'blockCnt',
    'moveSpeed', 'attackSpeed', 'baseAttackTime', 'respawnTime',
    'hpRecoveryPerSec', 'spRecoveryPerSec', 'maxDeployCount', 'massLevel',
    'baseForceLevel', 'tauntLevel', 'epDamageResistance', 'epResistance',
    'damageHitratePhysical', 'damageHitrateMagical', 'epBreakRecoverSpeed',
    'stunImmune', 'silenceImmune', 'sleepImmune', 'frozenImmune',
    'levitateImmune', 'disarmedCombatImmune', 'fearedImmune', 'palsyImmune',
    'attractImmune', 'teleportImmune', 'groundBoundImmune',
]
ENEMY_ATTR_FLOAT = {
    'magicResistance', 'moveSpeed', 'attackSpeed', 'baseAttackTime',
    'hpRecoveryPerSec', 'spRecoveryPerSec', 'epDamageResistance',
    'epResistance', 'damageHitratePhysical', 'damageHitrateMagical',
    'epBreakRecoverSpeed',
}
ENEMY_ATTR_BOOL = {
    'stunImmune', 'silenceImmune', 'sleepImmune', 'frozenImmune',
    'levitateImmune', 'disarmedCombatImmune', 'fearedImmune', 'palsyImmune',
    'attractImmune', 'teleportImmune', 'groundBoundImmune',
}

ENEMY_DATA_NAMES = [
    'name', 'description', 'prefabKey', 'attributes', 'applyWay', 'motion',
    'enemyTags', 'lifePointReduce', 'levelType', 'rangeRadius',
    'numOfExtraDrops', 'viewRadius', 'notCountInTotal', 'talentBlackboard',
    'skills', 'spData',
]


def unwrap_undef(fb, fpos, float_field=False, scalar=False):
    """Parse an Undefinable<T> wrapper stored at field position fpos.

    scalar=True: the wrapped value is an inline int/float/bool -> read the
    value slot as raw i32 (an inline scalar can coincidentally look like a
    valid offset, so we must NOT follow the offset heuristic).
    """
    rel = fb.i32(fpos)
    target = fpos + rel
    if rel == 0 or not (4 <= target < fb.size - 4):
        return fb.i32(fpos)
    if fb.is_string(target):
        return fb.read_string(target)
    if fb.is_table(target):
        fields = fb.table_fields(target)
        if len(fields) >= 2 and fields[1] is not None:
            if scalar:
                v = fb.i32(fields[1])
                return i2f(v) if float_field else v
            v = fb.parse_value(fields[1])
            if float_field and isinstance(v, int):
                return i2f(v)
            return v
        return None  # undefined
    if fb.is_vector(target):
        v = fb.parse_value(fpos)
        return v
    return fb.i32(fpos)


def parse_blackboard(fb, pos):
    """Blackboard = vector of DataPair tables {0:key, 1:value(float), 2:valueStr?}."""
    if not fb.is_vector(pos):
        return []
    slots = fb.vector(pos)
    out = []
    for slot in slots:
        epos = slot + fb.i32(slot)
        if not fb.is_table(epos):
            continue
        f = fb.table_fields(epos)
        rec = {}
        if len(f) > 0 and f[0] is not None and fb.is_string(fb.target_of(f[0])):
            rec['key'] = fb.read_string(fb.target_of(f[0]))
        if len(f) > 1 and f[1] is not None:
            raw = fb.i32(f[1])
            rec['value'] = i2f(raw)
            rec['value_raw'] = raw
        if len(f) > 2 and f[2] is not None:
            t = fb.target_of(f[2])
            if fb.is_string(t):
                rec['valueStr'] = fb.read_string(t)
        out.append(rec)
    return out


def parse_eskill(fb, pos):
    """ESkillData: 0 prefabKey str, 1 priority int, 2 cooldown f, 3 initCooldown f,
    4 spCost int, 5 blackboard."""
    f = fb.table_fields(pos)
    out = {}
    def get(i, as_float=False):
        if i >= len(f) or f[i] is None:
            return None
        v = fb.parse_value(f[i])
        if as_float and isinstance(v, int):
            return i2f(v)
        return v
    out['prefabKey'] = get(0)
    out['priority'] = get(1)
    out['cooldown'] = get(2, True)
    out['initCooldown'] = get(3, True)
    out['spCost'] = get(4)
    bb = None
    if 5 < len(f) and f[5] is not None:
        t = fb.target_of(f[5])
        if fb.is_vector(t):
            bb = parse_blackboard(fb, t)
    out['blackboard'] = bb
    return out


def parse_espdata(fb, pos):
    f = fb.table_fields(pos)
    out = {}
    def get(i, as_float=False):
        if i >= len(f) or f[i] is None:
            return None
        v = fb.i32(f[i])
        if as_float:
            return i2f(v)
        return v
    out['spType'] = get(0)
    out['maxSp'] = get(1)
    out['initSp'] = get(2)
    out['increment'] = get(3, True)
    return out


def parse_enemy_attributes(fb, pos):
    f = fb.table_fields(pos)
    out = {}
    for i, name in enumerate(ENEMY_ATTR_NAMES):
        if i >= len(f) or f[i] is None:
            out[name] = None
            continue
        v = unwrap_undef(fb, f[i], float_field=(name in ENEMY_ATTR_FLOAT),
                          scalar=True)
        if name in ENEMY_ATTR_BOOL:
            v = bool(v) if v is not None else None
        out[name] = v
    return out


def parse_enemy_data(fb, pos):
    f = fb.table_fields(pos)
    out = {}
    n = len(f)
    def undef_field(i, as_float=False, scalar=False):
        if i >= n or f[i] is None:
            return None
        return unwrap_undef(fb, f[i], float_field=as_float, scalar=scalar)
    out['name'] = undef_field(0)
    out['description'] = undef_field(1)
    out['prefabKey'] = undef_field(2)
    if 3 < n and f[3] is not None:
        t = fb.target_of(f[3])
        out['attributes'] = parse_enemy_attributes(fb, t) if fb.is_table(t) else None
    else:
        out['attributes'] = None
    out['applyWay'] = undef_field(4, scalar=True)
    out['motion'] = undef_field(5, scalar=True)
    out['enemyTags'] = undef_field(6)
    out['lifePointReduce'] = undef_field(7, scalar=True)
    out['levelType'] = undef_field(8, scalar=True)
    out['rangeRadius'] = undef_field(9, True, scalar=True)
    out['numOfExtraDrops'] = undef_field(10, scalar=True)
    out['viewRadius'] = undef_field(11, True, scalar=True)
    out['notCountInTotal'] = undef_field(12, scalar=True)
    if 13 < n and f[13] is not None:
        t = fb.target_of(f[13])
        out['talentBlackboard'] = parse_blackboard(fb, t) if fb.is_vector(t) else None
    else:
        out['talentBlackboard'] = None
    if 14 < n and f[14] is not None:
        t = fb.target_of(f[14])
        if fb.is_vector(t):
            skills = []
            for slot in fb.vector(t):
                spos = slot + fb.i32(slot)
                if fb.is_table(spos):
                    skills.append(parse_eskill(fb, spos))
            out['skills'] = skills
        else:
            out['skills'] = None
    else:
        out['skills'] = None
    if 15 < n and f[15] is not None:
        t = fb.target_of(f[15])
        out['spData'] = parse_espdata(fb, t) if fb.is_table(t) else None
    else:
        out['spData'] = None
    return out


def parse_enemy_database(fb):
    """Root: dict entry value = vector of EnemyLevel{0:level,1:enemyData}."""
    root_fields = fb.table_fields(fb.root)
    vec = root_fields[0] + fb.i32(root_fields[0])
    entries = fb.read_dict(vec)
    db = {}
    for key, vpos in entries:
        vv = vpos + fb.i32(vpos)
        if not fb.is_vector(vv):
            continue
        levels = []
        for slot in fb.vector(vv):
            lpos = slot + fb.i32(slot)
            if not fb.is_table(lpos):
                continue
            f = fb.table_fields(lpos)
            lv = None
            if len(f) > 0 and f[0] is not None:
                lv = fb.i32(f[0])
            ed = None
            if len(f) > 1 and f[1] is not None:
                t = fb.target_of(f[1])
                if fb.is_table(t):
                    ed = parse_enemy_data(fb, t)
            levels.append({'level': lv, 'data': ed})
        db[key] = levels
    return db


def parse_handbook(fb):
    """EnemyHandbookDB: root table has several dicts; field 1 = enemies
    (id -> EnemyHandbookInfo). Values are generic-parsed for now."""
    root_fields = fb.table_fields(fb.root)
    vec = root_fields[1] + fb.i32(root_fields[1])
    entries = fb.read_dict(vec)
    out = {}
    for key, vpos in entries:
        out[key] = fb.parse_value(vpos)
    return out


LEVEL_NAMES = [
    'options', 'levelId', 'mapId', 'bgmEvent', 'environmentSe', 'mapData',
    'tilesDisallowToLocate', 'runes', 'optionalRunes', 'globalBuffs', 'routes',
    'extraRoutes', 'enemies', 'enemyDbRefs', 'waves', 'branches', 'predefines',
    'hardPredefines', 'excludeCharIdList', 'randomSeed', 'operaConfig',
    'cameraPlugin', 'runtimeData',
]


def parse_action(fb, pos):
    f = fb.table_fields(pos)
    names = ['actionType', 'managedByScheduler', 'key', 'count', 'preDelay',
             'interval', 'useExtraRoute', 'routeIndex', 'blockFragment',
             'autoPreviewRoute', 'autoDisplayEnemyInfo',
             'isUnharmfulAndAlwaysCountAsKilled', 'hiddenGroup',
             'randomSpawnGroupKey', 'randomSpawnGroupPackKey', 'randomType',
             'refreshType', 'weight', 'dontBlockWave', 'forceBlockWaveInBranch',
             'isValid', 'notCountInTotal', 'extraMeta', 'actionId']
    out = {}
    for i, nm in enumerate(names):
        if i >= len(f) or f[i] is None:
            continue
        v = fb.parse_value(f[i])
        if isinstance(v, int):
            if nm in ('preDelay', 'interval'):
                v = i2f(v)
        out[nm] = v
    return out


def parse_fragment(fb, pos):
    f = fb.table_fields(pos)
    out = {}
    if len(f) > 0 and f[0] is not None:
        out['preDelay'] = i2f(fb.i32(f[0]))
    if len(f) > 1 and f[1] is not None:
        t = fb.target_of(f[1])
        if fb.is_vector(t):
            acts = []
            for slot in fb.vector(t):
                apos = slot + fb.i32(slot)
                if fb.is_table(apos):
                    acts.append(parse_action(fb, apos))
            out['actions'] = acts
    return out


def parse_wave(fb, pos):
    f = fb.table_fields(pos)
    out = {}
    if len(f) > 0 and f[0] is not None:
        out['preDelay'] = i2f(fb.i32(f[0]))
    if len(f) > 1 and f[1] is not None:
        out['postDelay'] = i2f(fb.i32(f[1]))
    if len(f) > 2 and f[2] is not None:
        out['maxTimeWaitingForNextWave'] = i2f(fb.i32(f[2]))
    if len(f) > 3 and f[3] is not None:
        t = fb.target_of(f[3])
        if fb.is_vector(t):
            frags = []
            for slot in fb.vector(t):
                fpos = slot + fb.i32(slot)
                if fb.is_table(fpos):
                    frags.append(parse_fragment(fb, fpos))
            out['fragments'] = frags
    if len(f) > 4 and f[4] is not None:
        t = fb.target_of(f[4])
        if fb.is_string(t):
            out['advancedWaveTag'] = fb.read_string(t)
    return out


def parse_route(fb, pos):
    """RouteData: keep compact summary (motionMode, start/end, checkpoint count)."""
    f = fb.table_fields(pos)
    out = {}
    names = ['motionMode', 'startPosition', 'endPosition', 'spawnRandomRange',
             'spawnOffset', 'checkpoints', 'allowDiagonalMove',
             'visitEveryTileCenter', 'visitEveryNodeCenter',
             'visitEveryCheckPoint']
    for i, nm in enumerate(names):
        if i >= len(f) or f[i] is None:
            continue
        v = fb.parse_value(f[i])
        if isinstance(v, int) and nm in ('motionMode',):
            v = i2f(v)
        out[nm] = v
    if 'checkpoints' in out and isinstance(out['checkpoints'], list):
        out['checkpointCount'] = len(out['checkpoints'])
    return out


def parse_level(fb, pos):
    f = fb.table_fields(pos)
    out = {}
    def vec_of_strings(i):
        if i >= len(f) or f[i] is None:
            return None
        t = fb.target_of(f[i])
        if not fb.is_vector(t):
            return None
        res = []
        for slot in fb.vector(t):
            v = fb.parse_value(slot)
            if isinstance(v, dict) and 1 in v:
                v = v[1]
            res.append(v)
        return res
    out['levelId'] = None
    if 1 < len(f) and f[1] is not None:
        t = fb.target_of(f[1])
        if fb.is_string(t):
            out['levelId'] = fb.read_string(t)
    out['mapId'] = None
    if 2 < len(f) and f[2] is not None:
        t = fb.target_of(f[2])
        if fb.is_string(t):
            out['mapId'] = fb.read_string(t)
    if 0 < len(f) and f[0] is not None:
        t = fb.target_of(f[0])
        if fb.is_table(t):
            out['options'] = fb.parse_table(t)
    if 7 < len(f) and f[7] is not None:
        t = fb.target_of(f[7])
        if fb.is_vector(t):
            runes = []
            for slot in fb.vector(t):
                rpos = slot + fb.i32(slot)
                if fb.is_table(rpos):
                    rf = fb.table_fields(rpos)
                    r = {}
                    if len(rf) > 0 and rf[0] is not None and fb.is_string(fb.target_of(rf[0])):
                        r['key'] = fb.read_string(fb.target_of(rf[0]))
                    if len(rf) > 2 and rf[2] is not None:
                        t2 = fb.target_of(rf[2])
                        if fb.is_vector(t2):
                            r['blackboard'] = parse_blackboard(fb, t2)
                    runes.append(r)
            out['runes'] = runes
    if 10 < len(f) and f[10] is not None:
        t = fb.target_of(f[10])
        if fb.is_vector(t):
            routes = []
            for slot in fb.vector(t):
                rpos = slot + fb.i32(slot)
                if fb.is_table(rpos):
                    routes.append(parse_route(fb, rpos))
            out['routes'] = routes
    if 12 < len(f) and f[12] is not None:
        t = fb.target_of(f[12])
        if fb.is_vector(t):
            enemies = []
            for slot in fb.vector(t):
                epos = slot + fb.i32(slot)
                if fb.is_table(epos):
                    enemies.append(fb.parse_table(epos))
            out['enemies'] = enemies
    if 13 < len(f) and f[13] is not None:
        t = fb.target_of(f[13])
        if fb.is_vector(t):
            refs = []
            for slot in fb.vector(t):
                epos = slot + fb.i32(slot)
                if fb.is_table(epos):
                    refs.append(fb.parse_table(epos))
            out['enemyDbRefs'] = refs
    if 14 < len(f) and f[14] is not None:
        t = fb.target_of(f[14])
        if fb.is_vector(t):
            waves = []
            for slot in fb.vector(t):
                wpos = slot + fb.i32(slot)
                if fb.is_table(wpos):
                    waves.append(parse_wave(fb, wpos))
            out['waves'] = waves
    return out


STAGE_NAMES = [
    'stageType', 'difficulty', 'performanceStageFlag', 'diffGroup',
    'unlockCondition', 'stageId', 'levelId', 'zoneId', 'code', 'name',
    'description', 'hardStagedId', 'sixStarStageId', 'dangerLevel',
    'dangerPoint', 'loadingPicId', 'battleFinishLoadingPicId', 'canPractice',
    'canBattleReplay', 'apCost', 'apFailReturn', 'maxSlot', 'etItemId',
    'etCost', 'etFailReturn', 'etButtonStyle', 'apProtectTimes',
    'diamondOnceDrop', 'practiceTicketCost', 'dailyStageDifficulty',
    'expGain', 'goldGain', 'loseExpGain', 'loseGoldGain', 'passFavor',
    'completeFavor', 'slProgress', 'displayMainItem', 'hilightMark',
    'bossMark', 'isPredefined', 'isHardPredefined', 'isSkillSelectablePredefined',
    'isStoryOnly', 'appearanceStyle', 'stageDropInfo', 'canUseCharm',
    'canUseTech', 'canUseTrapTool', 'canUseBattlePerformance',
    'canUseFirework', 'canMultipleBattle', 'startButtonOverrideId',
    'isStagePatch', 'mainStageId', 'extraCondition', 'extraInfo',
    'sixStarBaseDesc', 'sixStarDisplayRewardList', 'advancedRuneIdList1',
    'advancedRuneIdList2', 'useSpecialSizeMapPreview',
]


STAGE_STR_FIELDS = {
    'stageId', 'levelId', 'zoneId', 'code', 'name', 'description',
    'hardStagedId', 'sixStarStageId', 'dangerLevel', 'loadingPicId',
    'battleFinishLoadingPicId', 'etItemId', 'etButtonStyle',
    'displayMainItem', 'startButtonOverrideId', 'mainStageId',
    'sixStarBaseDesc',
}
STAGE_FLOAT_FIELDS = {'dangerPoint'}
STAGE_VEC_FIELDS = {
    'unlockCondition', 'sixStarDisplayRewardList', 'advancedRuneIdList1',
    'advancedRuneIdList2', 'extraCondition', 'extraInfo',
}


def parse_stages(fb):
    """stage_table: root field0 = dict stageId -> StageData (61 fields).
    LevelData (waves/routes/enemies) lives in separate encrypted level
    TextAssets (level_main_*, level_act*_*, ...) - see levels_index.json."""
    root_fields = fb.table_fields(fb.root)
    vec = root_fields[0] + fb.i32(root_fields[0])
    entries = fb.read_dict(vec)
    out = {}
    for key, vpos in entries:
        try:
            t = vpos + fb.i32(vpos)
            if not fb.is_table(t):
                continue
            f = fb.table_fields(t)
            rec = {}
            for i, nm in enumerate(STAGE_NAMES):
                if i >= len(f) or f[i] is None:
                    continue
                if nm in STAGE_STR_FIELDS:
                    t2 = fb.target_of(f[i])
                    if fb.is_string(t2):
                        rec[nm] = fb.read_string(t2)
                elif nm in STAGE_FLOAT_FIELDS:
                    rec[nm] = i2f(fb.i32(f[i]))
                elif nm in STAGE_VEC_FIELDS:
                    t2 = fb.target_of(f[i])
                    if fb.is_vector(t2):
                        slots = fb.vector(t2)
                        elems = []
                        for s in slots[:500]:
                            v = fb.parse_value(s)
                            if isinstance(v, dict) and 1 in v and                                     isinstance(v.get(0), int):
                                v = v[1]
                            elems.append(v)
                        rec[nm] = elems
                else:
                    rec[nm] = fb.i32(f[i])
            out[key] = rec
        except Exception:
            continue
    return out


def stats_of(db):
    tags = collections.Counter()
    behaviors = collections.Counter()
    prefab_keys = collections.Counter()
    bb_keys = collections.Counter()
    motions = collections.Counter()
    level_types = collections.Counter()
    sp_types = collections.Counter()
    levels_per_enemy = collections.Counter()
    total = 0
    for eid, levels in db.items():
        total += 1
        levels_per_enemy[len(levels)] += 1
        for lv in levels:
            d = lv.get('data') or {}
            et = d.get('enemyTags')
            if isinstance(et, list):
                for tag in et:
                    if isinstance(tag, str):
                        tags[tag] += 1
            elif isinstance(et, str):
                tags[et] += 1
            motions[d.get('motion')] += 1
            level_types[d.get('levelType')] += 1
            sd = d.get('spData') or {}
            st = sd.get('spType')
            if st is not None:
                sp_types[st] += 1
            for sk in (d.get('skills') or []):
                pk = sk.get('prefabKey')
                if pk:
                    prefab_keys[pk] += 1
                for p in (sk.get('blackboard') or []):
                    k = p.get('key')
                    if k:
                        bb_keys[k] += 1
            for p in (d.get('talentBlackboard') or []):
                k = p.get('key')
                if k:
                    bb_keys['talent:' + k] += 1
    return {
        'enemy_count': total,
        'levels_per_enemy': dict(levels_per_enemy),
        'tags': dict(tags.most_common()),
        'motion': dict(motions),
        'levelType': dict(level_types),
        'spType': dict(sp_types),
        'skill_prefab_keys': dict(prefab_keys.most_common()),
        'blackboard_keys': dict(bb_keys.most_common()),
    }


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print('== enemy_database ==')
    fb = FB(ENEMY_DB)
    db = parse_enemy_database(fb)
    path = os.path.join(OUT_DIR, 'enemy_database.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False)
    print(f'{len(db)} enemies -> {path}')
    sample = db.get('enemy_10001_trslim')
    if sample:
        print('sample enemy_10001_trslim:', json.dumps(sample[0], ensure_ascii=False)[:400])

    print('== enemy_handbook ==')
    fb2 = FB(ENEMY_HB)
    hb = parse_handbook(fb2)
    path2 = os.path.join(OUT_DIR, 'enemy_handbook.json')
    with open(path2, 'w', encoding='utf-8') as f:
        json.dump(hb, f, ensure_ascii=False)
    print(f'{len(hb)} handbook entries -> {path2}')
    first_key = next(iter(hb))
    print('sample key:', first_key, '->', json.dumps(hb[first_key], ensure_ascii=False)[:300])

    print('== stage_table ==')
    fb3 = FB(STAGE_TB)
    stages = parse_stages(fb3)
    path3 = os.path.join(OUT_DIR, 'stage_enemy_usage.json')
    with open(path3, 'w', encoding='utf-8') as f:
        json.dump(stages, f, ensure_ascii=False)
    print(f'{len(stages)} stages -> {path3}')
    for k in ('main_01-01', 'main_13-01', 'act10side_01'):
        if k in stages:
            s = stages[k]
            print('sample', k, {kk: s.get(kk) for kk in
                                ('stageId', 'levelId', 'code', 'name', 'difficulty',
                                 'stageType', 'bossMark')}, flush=True)

    print('== stats ==')
    st = stats_of(db)
    path4 = os.path.join(OUT_DIR, 'enemy_stats.json')
    with open(path4, 'w', encoding='utf-8') as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in st.items() if k != 'skill_prefab_keys'},
                     ensure_ascii=False, indent=1)[:1500])
    print('top 20 skill prefabKeys:')
    for k, v in list(st['skill_prefab_keys'].items())[:20]:
        print('  ', k, v)


if __name__ == '__main__':
    main()
