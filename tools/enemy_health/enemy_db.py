# -*- coding: utf-8 -*-
"""敌人图鉴数据库解析 (enemy_handbook_table)

从 data/tables/enemy_handbook_table*.bin 中解析:
    敌人ID (enemy_xxx) -> 中文名 / 图鉴编号 / 描述

表为 FlatBuffers 变体, 这里用启发式扫描:
  条目布局(实测): [len][名称][..][len][编号ASCII][len][enemy_id][对齐][len][描述]
"""

import os
import re
import struct
import glob

ID_RE = re.compile(rb'enemy_[0-9a-zA-Z_]+')
CJK_RE = re.compile(r'[一-鿿]')


def _u32(b, p):
    return struct.unpack_from('<I', b, p)[0]


def _is_cjk_str(s):
    return bool(CJK_RE.search(s))


def _try_utf8(raw):
    try:
        s = raw.decode('utf-8')
    except Exception:
        return None
    if any(ord(c) < 0x20 for c in s):
        return None
    return s


def parse_handbook(path):
    """解析 enemy_handbook_table bin -> {enemy_id: {'name','code','desc'}}"""
    data = open(path, 'rb').read()
    db = {}
    for m in ID_RE.finditer(data):
        eid_b = m.group(0)
        i = m.start()
        # 长度前缀校验 (排除嵌在更长字符串里的匹配)
        if i < 4 or _u32(data, i - 4) != len(eid_b):
            continue
        eid = eid_b.decode('ascii')

        # ---- 向前找名称 (96 字节窗口内最长 CJK 长度前缀串) ----
        name, code = None, None
        best = None  # (length, name, end_pos)
        lo = max(0, i - 4 - 96)
        for p in range(lo, i - 4):
            ln = _u32(data, p)
            if ln < 3 or ln > 60 or p + 4 + ln > i - 4:
                continue
            s = _try_utf8(data[p + 4:p + 4 + ln])
            if s and _is_cjk_str(s):
                if best is None or ln > best[0]:
                    best = (ln, s, p + 4 + ln)
        if best:
            name = best[1]
            # 名称与 id 之间找图鉴编号 (短 ASCII 长度前缀串, 如 "B2")
            for p in range(best[2], i - 4):
                ln = _u32(data, p)
                if 1 <= ln <= 4 and p + 4 + ln <= i - 4:
                    s = _try_utf8(data[p + 4:p + 4 + ln])
                    if s and re.fullmatch(r'[A-Z0-9]+', s):
                        code = s
                        break

        # ---- 向后找描述 ----
        desc = None
        p = i + len(eid_b)
        while p < len(data) and data[p] == 0:  # 对齐填充
            p += 1
        if p + 4 <= len(data):
            ln = _u32(data, p)
            if 8 <= ln <= 600 and p + 4 + ln <= len(data):
                s = _try_utf8(data[p + 4:p + 4 + ln])
                if s and _is_cjk_str(s):
                    desc = s

        # ---- 去重: 优先保留信息全的 ----
        old = db.get(eid)
        score = (1 if name else 0) + (1 if desc else 0)
        if old is None or score > old[0]:
            db[eid] = (score, name, code, desc)

    return {eid: {'name': n, 'code': c, 'desc': d}
            for eid, (s, n, c, d) in db.items() if n}


def find_handbook_bin(tables_dir=None):
    if tables_dir is None:
        here = os.path.dirname(os.path.abspath(__file__))
        tables_dir = os.path.join(here, '..', '..', 'data', 'tables')
    for pat in ('enemy_handbook_table*.bin',):
        files = glob.glob(os.path.join(tables_dir, pat))
        if files:
            return files[0]
    return None


_db_cache = None


def load_enemy_db(tables_dir=None):
    """加载敌人数据库 (带缓存); 失败返回 {}"""
    global _db_cache
    if _db_cache is not None:
        return _db_cache
    path = find_handbook_bin(tables_dir)
    if not path:
        _db_cache = {}
        return _db_cache
    try:
        _db_cache = parse_handbook(path)
    except Exception:
        _db_cache = {}
    return _db_cache


if __name__ == '__main__':
    db = load_enemy_db()
    print(f"共 {len(db)} 个敌人")
    for eid in ('enemy_1007_slime_2', 'enemy_1002_nsabr_1', 'enemy_1500_skulsr'):
        info = db.get(eid)
        if info:
            print(f"{eid}: {info['name']} [{info['code']}] {str(info['desc'])[:50]}")
        else:
            print(f"{eid}: (未找到)")
