#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""提取我方/敌方每个动作（普攻/技能）的生效帧数据 → data/tables/effect_frames.json

数据链路（全部本地解包资产）：
  敌方技能表   ark_parser/enemy/data/enemy_database.json   enemyId → skills[prefabKey]
  技能 prefab  data/battle/enm_pfb_*.ab_unpacked           prefabKey → Ability._animKey/_preDelay/_projectileKey
  敌人普攻     data/battle/enm_pfb_*.ab_unpacked           enemy prefab → _modes → _attack Ability
  敌人动画     data/refs/arts/enm_art_*.ab_unpacked        enemy_xxx.skel (Spine 3.8 二进制) → 动画事件时间
  我方技能表   ark_parser/character/data/characters.json + skills.json
  我方 prefab  data/charpack/*.ab_unpacked                 char prefab → _modes(Default/S2/S3) → _attack Ability
  我方动画     data/chararts/*.ab_unpacked                 char_xxx.skel（默认皮）→ 动画事件时间
  弹道速度     data/battle/prefabs/[uc]projectiles.ab_unpacked  projectileKey → 移动组件 _speed (格/秒)

生效帧定义：动画 EventTimeline 上的事件时间（OnAttack=伤害/弹道发射/效果触发时刻），
秒 × 30 = 帧数（游戏 30 tick/s）。弹道命中帧 = 发射帧 + 距离 × (30 / speed)。

依赖：UnityPy（系统 Python 已装）；spine_asset 库在 unpack_work/spine_asset_lib。
用法：python ark_parser/extract_effect_frames.py [--out data/tables/effect_frames.json]
"""

import argparse
import glob
import json
import os
import struct
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, os.path.join(ROOT, "unpack_work", "spine_asset_lib"))


def _unitypy():
    """UnityPy 只在提取主流程用到；延迟导入让 normalize_enemy_database 等
    纯数据函数（及其测试）能在无 UnityPy 的环境（如 .venv）中运行。"""
    import UnityPy
    return UnityPy

TICK = 30.0  # 游戏逻辑帧率

ENM_PFB_DIR = os.path.join(ROOT, "data", "battle")
ENM_ART_DIR = os.path.join(ROOT, "data", "refs", "arts")
CHARPACK_DIR = os.path.join(ROOT, "data", "charpack")
CHARARTS_DIR = os.path.join(ROOT, "data", "chararts")
PROJECTILES_DIR = os.path.join(ROOT, "data", "battle", "prefabs",
                               "[uc]projectiles.ab_unpacked")
ENEMY_DB_JSON = os.path.join(SCRIPT_DIR, "enemy", "data", "enemy_database.json")
CHARACTERS_JSON = os.path.join(SCRIPT_DIR, "character", "data", "characters.json")
SKILLS_JSON = os.path.join(SCRIPT_DIR, "character", "data", "skills.json")
DEFAULT_OUT = os.path.join(ROOT, "data", "tables", "effect_frames.json")


# ---------------------------------------------------------------- spine 解析

def _read_textasset_bytes(obj):
    """TextAsset 原始字节（UnityPy 把 m_Script 当 str 会毁二进制，手动解析）。"""
    buf = obj.get_raw_data()
    pos = 0
    nlen = struct.unpack_from("<i", buf, pos)[0]
    pos += 4 + nlen
    pos = (pos + 3) & ~3
    slen = struct.unpack_from("<i", buf, pos)[0]
    pos += 4
    return buf[pos:pos + slen]


def parse_skel_events(raw):
    """Spine 3.8 二进制 → {动画名: {d: 时长秒, ev: [{n, t, f}]}}，只保留带事件的动画。"""
    from spine_asset.v38.SkeletonBinary import SkeletonBinary
    try:
        data = SkeletonBinary().read_skeleton_data(raw)
    except Exception:
        return None
    anims = {}
    for a in data.animations:
        events = []
        for t in a.timelines:
            if type(t).__name__ != "EventTimeline":
                continue
            for i, fr in enumerate(t.frames):
                ev = t.events[i]
                name = ev.data.name if hasattr(ev, "data") else "?"
                events.append({"n": name, "t": round(fr, 4),
                               "f": round(fr * TICK, 1)})
        if events:
            events.sort(key=lambda e: e["t"])
            anims[a.name] = {"d": round(a.duration, 4),
                             "df": round(a.duration * TICK, 1),
                             "ev": events}
    return anims


def iter_cabs(pkg_dir):
    for f in sorted(os.listdir(pkg_dir)):
        if f.startswith("CAB-") and not f.endswith(".resS"):
            yield os.path.join(pkg_dir, f)


def scan_skels(packages, want_name=None):
    """扫描一组 ab_unpacked 目录，提取全部 .skel 的动画事件。
    want_name(skel 名 → True/False) 可过滤。返回 {skel名(无后缀): anims}。"""
    out = {}
    for pkg in packages:
        for cab in iter_cabs(pkg):
            try:
                env = _unitypy().load(cab)
            except Exception:
                continue
            for obj in env.objects:
                if obj.type.name != "TextAsset":
                    continue
                try:
                    name = obj.read().m_Name
                except Exception:
                    continue
                if not name.endswith(".skel"):
                    continue
                base = name[:-5]
                if want_name and not want_name(base):
                    continue
                if base in out:
                    continue
                try:
                    anims = parse_skel_events(_read_textasset_bytes(obj))
                except Exception:
                    continue
                if anims:
                    out[base] = anims
    return out


# ---------------------------------------------------------------- CAB 组件下钻

class CabContext:
    """单个 CAB 的 GameObject/MonoBehaviour 索引，支持 PPtr(m_FileID=0) 下钻。"""

    def __init__(self, path):
        self.env = _unitypy().load(path)
        self.go_names = {}
        self.monos = {}           # path_id -> typetree dict
        self.go_of_mono = {}      # mono path_id -> GO path_id
        self.monos_on_go = {}     # GO path_id -> [mono path_id]
        for obj in self.env.objects:
            t = obj.type.name
            if t == "GameObject":
                try:
                    self.go_names[obj.path_id] = obj.read().m_Name
                except Exception:
                    pass
        for obj in self.env.objects:
            if obj.type.name != "MonoBehaviour":
                continue
            try:
                tt = obj.read_typetree()
            except Exception:
                continue
            self.monos[obj.path_id] = tt
            go = tt.get("m_GameObject", {}).get("m_PathID", 0)
            self.go_of_mono[obj.path_id] = go
            self.monos_on_go.setdefault(go, []).append(obj.path_id)

    def go_name(self, go_pid):
        return self.go_names.get(go_pid, "?")

    def mono(self, pid):
        return self.monos.get(pid)

    def deref(self, pptr):
        if not isinstance(pptr, dict) or pptr.get("m_FileID") not in (0, None):
            return None
        return self.monos.get(pptr.get("m_PathID"))


ABILITY_KEYS = ("_animKey", "_endAnimKey", "_preDelay", "_projectileKey",
                "_waitForAttackEvent", "_maxAnimScale")


def _dedup_abilities(abs_):
    """去掉字段完全相同的重复变体（同一 prefab 在多个 CAB 重复出现）。"""
    seen, out = set(), []
    for ab in abs_:
        key = json.dumps({k: v for k, v in ab.items() if k != "go"},
                         sort_keys=True, ensure_ascii=False)
        if key not in seen:
            seen.add(key)
            out.append(ab)
    return out


def ability_info(fields):
    out = {}
    for k in ABILITY_KEYS:
        if k in fields:
            v = fields[k]
            if isinstance(v, str) and not v:
                continue            # 空字符串视为未配置 (animKey 等)
            if isinstance(v, float):
                v = round(v, 4)
            out[k[1:]] = v          # 去掉下划线前缀: animKey/endAnimKey/preDelay/...
    return out


def resolve_mode_attack(ctx, mode_tt):
    """mode._attack → 参数字典；复合 Ability(_abilities) 逐个子 Ability 合并，
    并附带同 GO 动画组件的 _oneshotAnim/_beginAnim。"""
    atk = ctx.deref(mode_tt.get("_attack") or {})
    if not atk:
        return {}
    subs = atk.get("_abilities")
    if isinstance(subs, list) and subs:
        info = {}
        for sp in subs:
            sub = ctx.deref(sp)
            if not sub:
                continue
            for k, v in ability_info(sub).items():
                if k not in info:
                    info[k] = v
        info["composite"] = 1
    else:
        info = ability_info(atk)
    atk_pid = _find_pid(ctx.monos, atk)
    atk_go = ctx.go_of_mono.get(atk_pid, 0)
    for sib in ctx.monos_on_go.get(atk_go, []):
        st = ctx.monos[sib]
        if "_oneshotAnim" in st:
            if st.get("_oneshotAnim"):
                info["oneshotAnim"] = st["_oneshotAnim"]
            if st.get("_beginAnim"):
                info["beginAnim"] = st["_beginAnim"]
    return info


def scan_prefab_abilities(packages, name_filter):
    """在 enm_pfb/charpack 包里找：_modes 持有者(实体 prefab) 与技能 prefab 的 Ability。

    返回 (entity_modes, skill_abilities)：
      entity_modes: {实体名: [{mode, attack:{animKey,preDelay,projectileKey,...}}]}
      skill_abilities: {prefabKey: [{go, animKey, preDelay, projectileKey, ...}]}
    name_filter(GO 名) 为 None 时全部收。
    """
    entity_modes = {}
    skill_abilities = {}
    for pkg in packages:
        for cab in iter_cabs(pkg):
            try:
                ctx = CabContext(cab)
            except Exception:
                continue
            for pid, tt in ctx.monos.items():
                # 实体 prefab 根组件: _modes
                modes = tt.get("_modes")
                if isinstance(modes, list) and modes:
                    go = ctx.go_name(ctx.go_of_mono.get(pid, 0))
                    if name_filter and not name_filter(go):
                        continue
                    entries = []
                    for pptr in modes:
                        mode_tt = ctx.deref(pptr)
                        if not mode_tt:
                            continue
                        mode_go = ctx.go_name(
                            ctx.go_of_mono.get(
                                _find_pid(ctx.monos, mode_tt), 0))
                        info = resolve_mode_attack(ctx, mode_tt)
                        entries.append({"mode": mode_go, "attack": info})
                    if entries:
                        entity_modes[go] = entries
                # 技能 prefab: 带 _animKey 的 Ability
                if "_animKey" in tt and ("_selector" in tt or "_metadata" in tt):
                    go = ctx.go_name(ctx.go_of_mono.get(pid, 0))
                    root = _root_go_name(ctx, ctx.go_of_mono.get(pid, 0))
                    if name_filter and not (name_filter(go) or name_filter(root)):
                        continue
                    info = ability_info(tt)
                    info["go"] = go
                    skill_abilities.setdefault(root, []).append(info)
    return entity_modes, skill_abilities


def _find_pid(monos, tt):
    for pid, x in monos.items():
        if x is tt:
            return pid
    return 0


def _root_go_name(ctx, go_pid, _depth=0):
    """通过 Transform 父链近似求根 GO 名（技能 prefab 根）。"""
    # MonoBehaviour 的 m_GameObject 只给直接 GO；Transform 父链需要 Transform 表，
    # 这里退化为: enm_pfb 中技能 prefab 的 Ability 常挂在以技能命名的根 GO 的子节点。
    # 用 GO 自身名 + 已知技能名匹配, 调用方以 root 名兜底。
    return ctx.go_names.get(go_pid, "?")


# ---------------------------------------------------------------- 弹道速度

def scan_projectile_moves():
    """[uc]projectiles.ab → {GO名: {'speed': 格/秒} 或 {'flyTime': 秒}}。

    弹道移动组件两种形态：
    - 速度型：_speed + _moveType（如 projectile_faust，恒定 格/秒）
    - 定时型：_time + _forceReachedWhenTimeup（如 projectile_amiya_logic，
      固定飞行时间到达）。移动组件可能挂在 projectileKey 的
      _logic/_graphic 子 GO 上，调用方需回退查找。
    """
    moves = {}
    for cab in iter_cabs(PROJECTILES_DIR):
        try:
            ctx = CabContext(cab)
        except Exception:
            continue
        for pid, tt in ctx.monos.items():
            go = ctx.go_name(ctx.go_of_mono.get(pid, 0))
            if not go:
                continue
            if "_speed" in tt and "_moveType" in tt:
                sp = tt.get("_speed")
                if isinstance(sp, (int, float)):
                    moves.setdefault(go, {})["speed"] = round(float(sp), 4)
            elif "_time" in tt and "_rotateToTarget" in tt:
                t = tt.get("_time")
                if isinstance(t, (int, float)) and t > 0:
                    moves.setdefault(go, {})["flyTime"] = round(float(t), 4)
    return moves


def resolve_projectile_move(moves, key):
    """按 projectileKey 解析移动参数（root → _logic → _graphic 回退）。"""
    if not key:
        return None
    for name in (key, key + "_logic", key + "_graphic"):
        mv = moves.get(name)
        if mv:
            return mv
    return None


def _apply_move(row, proj_moves):
    """把弹道移动参数写入动作行（speed 格/秒 或 flyTime 秒）。"""
    mv = resolve_projectile_move(proj_moves, row.get("projectileKey"))
    if mv:
        if "speed" in mv:
            row["projectileSpeed"] = mv["speed"]
        if "flyTime" in mv:
            row["projectileFlyTime"] = mv["flyTime"]


def normalize_enemy_database(payload):
    """兼容本仓库解析器与 OpenArknightsFBS 导出的两种敌人表结构。"""
    if not isinstance(payload, dict):
        raise ValueError("enemy_database 根节点必须是对象")
    rows = payload.get("enemies")
    if not isinstance(rows, list):
        return payload
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        enemy_id = row.get("Key") or row.get("key")
        levels = row.get("Value") or row.get("value") or []
        if not enemy_id or not isinstance(levels, list):
            continue
        normalized = []
        for level in levels:
            if not isinstance(level, dict):
                continue
            if isinstance(level.get("data"), dict):
                normalized.append(level)
                continue
            enemy_data = level.get("enemyData")
            if isinstance(enemy_data, dict):
                normalized.append({"level": level.get("level"), "data": enemy_data})
        result[str(enemy_id)] = normalized
    return result


def load_enemy_database(path):
    with open(path, encoding="utf-8") as stream:
        return normalize_enemy_database(json.load(stream))


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    print("[1/6] 弹道移动参数 ...")
    proj_moves = scan_projectile_moves()
    print(f"  弹道 {len(proj_moves)} 个")

    print("[2/6] 敌人 spine 动画事件 (enm_art) ...")
    enm_packs = sorted(glob.glob(os.path.join(ENM_ART_DIR, "enm_art_*.ab_unpacked")))
    enemy_anims = scan_skels(enm_packs)
    print(f"  敌人 skel {len(enemy_anims)} 个")

    print("[3/6] 我方 spine 动画事件 (chararts 默认皮) ...")
    char_packs = sorted(glob.glob(os.path.join(CHARARTS_DIR, "*.ab_unpacked")))
    char_anims = scan_skels(
        char_packs,
        want_name=lambda b: "_" in b and not b.startswith("build_")
        and "#" not in b and b.count("_") >= 2)
    print(f"  我方 skel {len(char_anims)} 个")

    print("[4/6] 敌人 prefab 普攻/技能 Ability (enm_pfb) ...")
    enm_pfb_packs = sorted(glob.glob(os.path.join(ENM_PFB_DIR, "enm_pfb_*.ab_unpacked")))
    enemy_modes, enemy_skill_ab = scan_prefab_abilities(enm_pfb_packs, None)
    print(f"  敌人实体 {len(enemy_modes)} 个, 技能 prefab {len(enemy_skill_ab)} 个")

    print("[5/6] 我方 prefab modes (charpack) ...")
    char_pfb_packs = sorted(glob.glob(os.path.join(CHARPACK_DIR, "*.ab_unpacked")))
    char_modes, _ = scan_prefab_abilities(char_pfb_packs, None)
    print(f"  我方实体 {len(char_modes)} 个")

    print("[6/6] 合并输出 ...")
    enemy_db = load_enemy_database(ENEMY_DB_JSON)
    enemies = {}
    for eid, levels in enemy_db.items():
        base = levels[0].get("data", {}) if levels else {}
        skills = base.get("skills") or []
        entry = {}
        anims = enemy_anims.get(eid)
        if anims:
            entry["anims"] = anims
        modes = enemy_modes.get(eid)
        if modes:
            atk = modes[0].get("attack") or {}
            # 敌人普攻动画命名约定为 Attack* (AttackAbility 不一定序列化 _animKey)
            atk.setdefault("animKey", "Attack")
            _apply_move(atk, proj_moves)
            entry["attack"] = atk
        sk_list = []
        code = eid.split("_")[-1] if "_" in eid else eid
        for sk in skills:
            pkey = sk.get("prefabKey")
            if not pkey:
                continue
            row = {"prefabKey": pkey,
                   "cooldown": sk.get("cooldown"),
                   "initCooldown": sk.get("initCooldown")}
            abs_ = _dedup_abilities(enemy_skill_ab.get(pkey) or [])
            if abs_:
                # 多变体技能 prefab（如 CriticalHit 被 faust/flsnip 共用）:
                # 优先选字段里含本敌人代号的变体, 否则取第一个
                pick = abs_[0]
                for ab in abs_:
                    if code and code in json.dumps(ab, ensure_ascii=False):
                        pick = ab
                        break
                ab = dict(pick)
                ab.pop("go", None)
                _apply_move(ab, proj_moves)
                row.update(ab)
            sk_list.append(row)
        if sk_list:
            entry["skills"] = sk_list
        if entry:
            enemies[eid] = entry

    characters = {}
    chars_db = json.load(open(CHARACTERS_JSON, encoding="utf-8"))
    skills_db = json.load(open(SKILLS_JSON, encoding="utf-8"))
    for cid, cdata in chars_db.items():
        entry = {}
        anims = char_anims.get(cid)
        if anims:
            entry["anims"] = anims
        modes = char_modes.get(cid)
        if modes:
            ms = []
            for m in modes:
                atk = dict(m.get("attack") or {})
                _apply_move(atk, proj_moves)
                ms.append({"mode": m["mode"], "attack": atk})
            entry["modes"] = ms
        sk_list = []
        for sk in cdata.get("skills") or []:
            sid = sk.get("skillId")
            if not sid:
                continue
            name = None
            sd = skills_db.get(sid)
            if sd and sd.get("levels"):
                name = sd["levels"][0].get("name")
            sk_list.append({"skillId": sid, "name": name})
        if sk_list:
            entry["skills"] = sk_list
        if entry:
            characters[cid] = entry

    result = {
        "meta": {"generatedBy": "ark_parser/extract_effect_frames.py",
                 "tick": TICK,
                 "note": "t=秒 f=帧(30/s); 速度型弹道命中帧=发射帧+距离×(30/speed); 定时型弹道命中帧=发射帧+flyTime×30"},
        "enemies": enemies,
        "characters": characters,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
    size = os.path.getsize(args.out)
    print(f"敌人 {len(enemies)} 个, 干员 {len(characters)} 个 -> {args.out} "
          f"({size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()
