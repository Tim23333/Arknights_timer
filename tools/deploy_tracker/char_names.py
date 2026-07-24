"""干员 ID -> 中文名映射

ark_parser/characters.json 的 name 字段大面积错位不可用, 这里直接从
data/tables/character_table*.bin 单遍扫描构建 {charId: 中文名}:

  character_table 是 FlatBuffers 字典 (key=charId 字符串, value=CharacterData 表)。
  CharacterData 采用标准 FlatBuffers 布局 (vtable 在表之前, soffset>0),
  field 0 即中文名 (现网实测: char_002_amiya->"阿米娅", char_1051_headb2->"怒潮凛冬")。

结果缓存到 ark_parser/char_names.json (按 bin 文件 mtime 失效重建)。
游戏版本更新后 extract_tables.py 会产出新 bin, 缓存自动重建。
"""

import glob
import json
import os
import re
import struct

_CHAR_ID_RE = re.compile(r"^char_\d+_\w+$")
_CACHE_NAME = "char_names.json"

# CharacterData 表扫描参数 (实测 vtable 36 字段以内)
_MAX_NF = 48


def _read_string(data, pos):
    if pos < 0 or pos + 4 > len(data):
        return None
    strlen = struct.unpack_from("<I", data, pos)[0]
    if strlen == 0 or strlen > 64 or pos + 4 + strlen > len(data):
        return None
    try:
        s = data[pos + 4:pos + 4 + strlen].decode("utf-8")
    except UnicodeDecodeError:
        return None
    return s if s.isprintable() else None


def _field0_name(data, tbl_pos):
    """读取 CharacterData 表 field 0 (中文名)。
    vtable 可能在表之前 (soff>0) 或之后 (soff<0, 自定义变体), vtp = tbl_pos - soff 通吃。"""
    if tbl_pos < 0 or tbl_pos + 4 > len(data):
        return None
    soff = struct.unpack_from("<i", data, tbl_pos)[0]
    if soff == 0:
        return None
    vtp = tbl_pos - soff
    if vtp < 0 or vtp + 8 > len(data):
        return None
    vts = struct.unpack_from("<H", data, vtp)[0]
    if vts < 8 or vts > 4 + _MAX_NF * 2 or vts % 2:
        return None
    obs = struct.unpack_from("<H", data, vtp + 2)[0]
    fo0 = struct.unpack_from("<H", data, vtp + 4)[0]
    if fo0 == 0 or fo0 >= obs + 64:
        return None
    p = tbl_pos + fo0
    if p + 4 > len(data):
        return None
    return _read_string(data, p + struct.unpack_from("<i", data, p)[0])


def build_char_names(bin_path):
    """单遍扫描 character_table bin, 返回 {charId: 中文名}。"""
    with open(bin_path, "rb") as f:
        data = f.read()
    size = len(data)
    names = {}
    # FlatBuffers 字典条目: 2 字段表 (key, value), vtable 在条目之后 (自定义变体,
    # soffset<0)。与 ark_parser/deep_parse.py find_entry 同一判别式。
    for pos in range(4000, size - 8, 4):
        soff = struct.unpack_from("<i", data, pos)[0]
        if soff >= 0 or soff < -size:
            continue
        vtp = pos - soff
        if vtp < 0 or vtp + 12 > size:
            continue
        vts = struct.unpack_from("<H", data, vtp)[0]
        if vts < 8 or vts > 200 or vts % 2:
            continue
        nf = (vts - 4) // 2
        if nf < 2:
            continue
        fo0 = struct.unpack_from("<H", data, vtp + 4)[0]
        fo1 = struct.unpack_from("<H", data, vtp + 6)[0]
        if fo0 == 0 or fo1 == 0:
            continue
        fp0 = pos + fo0
        if fp0 + 4 > size:
            continue
        key = _read_string(data, fp0 + struct.unpack_from("<i", data, fp0)[0])
        if not key or not _CHAR_ID_RE.match(key):
            continue
        fp1 = pos + fo1
        if fp1 + 4 > size:
            continue
        name = _field0_name(data, fp1 + struct.unpack_from("<i", data, fp1)[0])
        if name:
            names[key] = name
    return names


def _find_bin(project_root):
    pats = os.path.join(project_root, "data", "tables", "character_table*.bin")
    files = glob.glob(pats)
    return max(files, key=os.path.getmtime) if files else None


def load_char_names(project_root):
    """加载 {charId: 中文名}; 优先缓存, 失效则从 bin 重建, 兜底 characters.json。"""
    cache_path = os.path.join(project_root, "ark_parser", _CACHE_NAME)
    bin_path = _find_bin(project_root)

    if os.path.exists(cache_path):
        try:
            if bin_path is None or os.path.getmtime(cache_path) >= os.path.getmtime(bin_path):
                with open(cache_path, encoding="utf-8") as f:
                    names = json.load(f)
                if names:
                    return names
        except (OSError, json.JSONDecodeError):
            pass

    if bin_path is not None:
        try:
            names = build_char_names(bin_path)
        except OSError:
            names = {}
        if names:
            try:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(names, f, ensure_ascii=False, indent=1)
            except OSError:
                pass
            return names

    # 兜底: characters.json 中仍是字符串的 name
    names = {}
    try:
        with open(os.path.join(project_root, "ark_parser", "characters.json"),
                  encoding="utf-8") as f:
            for cid, v in json.load(f).items():
                name = v.get("name")
                if isinstance(name, str) and name:
                    names[cid] = name
    except (OSError, json.JSONDecodeError):
        pass
    return names


if __name__ == "__main__":
    import sys
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    names = load_char_names(root)
    print(f"{len(names)} chars", file=sys.stderr)
    for cid in ("char_002_amiya", "char_1051_headb2", "char_1045_svash2"):
        print(cid, "->", names.get(cid))
