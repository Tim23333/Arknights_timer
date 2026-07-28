"""模拟器内存扫描: 定位游戏内的 RNG 引擎对象 (可被 FakeMem 注入以离线测试)

定位链路 (全程不依赖固定地址, 抗版本漂移):

  1. 全堆扫描 int64 长度字段 == 56 且首元素为 0 的 Knuth SeedArray
     (seeds[0]==0, 全部落在 [0, MBIG), 恰好 1 个 0 —— .NET Random 下标 0 恒为 0)
  2. 全堆扫描 int64 长度字段 == 624 的 MT19937 mt 数组
  3. 反向扫描指向数组头的指针, 命中处减去候选字段偏移得到持有对象:
       hit-0x28 klass=LegacyRandom     -> Torappu/Spine Knuth (inext@0x20)
       hit-0x18 klass=Random           -> mscorlib System.Random (inext@0x10)
       hit-0x10 klass=MersenneTwister  -> Rei.Random MT (mti@0x18)
       hit-0x18 klass=TSRandom         -> TrueSync MT (mti@0x20)
     klass 名通过 IL2CPP klass->name 链读取 (模拟器内存中指针可直接追踪,
     与 tools/deploy_tracker 相同的现网验证结论)
  4. MT 引擎再反查 CompatilizedRandom(original@0x20) 外壳
  5. 扫描指向各 Random 对象的指针, 命中地址相差 8 的两者即静态字段对
     (BattleController s_randomImp@0x30 / s_randomTrivial@0x38 布局,
      低偏移者为 imp)

读取协议: reader 需实现 read(addr, size) + regions(scope);
  若额外实现 scan_regions(regions, needles) -> {needle: [addr...]} (adb 后端
  的设备侧 memsrv v2, 见 tools/enemy_health/memsrv.c), 三遍扫描全部下沉到
  设备执行 (3.7GB rw 全扫 ~12s, 对比 adb forward 直读 ~4min);
  未实现时 (pymem / FakeMem / memsrv v1) 自动回退逐块 python 扫描。

实测落点 (MuMu + 官服包): 类名/命名空间 C 字符串与 Il2CppClass 均位于
  大号匿名 rw 映射 (libil2cpp.so 只读段里没有, 全局 metadata magic
  0xFAB11BAF 也搜不到 —— metadata 被 Arknights 加密加载后在堆中重建);
  GC 堆里另有字符串拷贝但 klass 只引用 metadata 区的原件, 故静态链
  直接全 rw 单遍扫描 (设备侧 ~13s), 不做分区裁剪。
"""

import struct
import time

try:
    import numpy as _np
except ImportError:
    _np = None

MBIG = 2147483647

SCAN_CHUNK = 16 * 1024 * 1024
ARRAY_LEN_OFF = 0x18          # IL2CPP 数组对象: 长度字段偏移
ARRAY_ELEM_OFF = 0x20         #                 元素起始偏移

EMULATOR_PROCESSES = [
    "MuMuVMMHeadless.exe", "NemuHeadless.exe", "Ld9BoxHeadless.exe",
    "LdBoxHeadless.exe", "dnplayer.exe", "NoxVMMHeadless.exe",
    "HD-Player.exe", "MEmuHeadless.exe",
]

# 指针命中处相对持有对象起始的候选字段偏移 -> (引擎种类, klass 名, 游标字段偏移)
OWNER_LAYOUTS = [
    (0x28, "LegacyRandom", "knuth", 0x20),
    (0x18, "Random", "knuth", 0x10),
    (0x10, "MersenneTwister", "mt", 0x18),
    (0x18, "TSRandom", "mt", 0x20),
]


def _is_heap_ptr(v):
    return 0x10000 <= v < 0x0000800000000000


class PymemReader:
    """pymem 进程读取器 (read 失败返回 None, 区域按 16MB 切块)。"""

    def __init__(self, pm):
        self.pm = pm
        self.handle = pm.process_handle

    def read(self, addr, size):
        import pymem.exception
        import pymem.memory
        try:
            return pymem.memory.read_bytes(self.handle, addr, size)
        except (pymem.exception.MemoryReadError, pymem.exception.WinAPIError, OverflowError):
            return None

    def regions(self, scope="all"):
        import pymem.memory
        chunks = []
        curr = 0
        while True:
            try:
                mbi = pymem.memory.virtual_query(self.handle, curr)
                curr += mbi.RegionSize
                if mbi.State == 0x1000 and (mbi.Protect & 0x66) and mbi.RegionSize >= 4096:
                    base, size = mbi.BaseAddress, mbi.RegionSize
                    off = 0
                    while off < size:
                        n = min(size - off, SCAN_CHUNK)
                        chunks.append((base + off, n))
                        off += n
            except Exception:
                break
        return chunks


def read_u64(reader, addr):
    d = reader.read(addr, 8)
    return struct.unpack("<Q", d)[0] if d else 0


def read_c_string(reader, ptr, limit=64):
    if not _is_heap_ptr(ptr):
        return None
    d = reader.read(ptr, limit)
    if not d:
        return None
    end = d.find(b"\x00")
    if end <= 0:
        return None
    try:
        return d[:end].decode("ascii", errors="strict")
    except UnicodeDecodeError:
        return None


def read_klass(reader, obj_addr):
    """IL2CPP 对象 -> (命名空间, 类名); 失败返回 None。"""
    if not _is_heap_ptr(obj_addr):
        return None
    klass = read_u64(reader, obj_addr)
    if not _is_heap_ptr(klass):
        return None
    name = read_c_string(reader, read_u64(reader, klass + 0x10))
    if not name:
        return None
    ns = read_c_string(reader, read_u64(reader, klass + 0x18)) or ""
    return ns, name


# ---------------- 设备侧 / python 扫描统一入口 ----------------

def _scan_needles(reader, scope, needles, status=lambda m: None, label="扫描"):
    """优先走 reader.scan_regions (adb 设备侧 memsrv v2); 不可用返回 None。

    返回 {needle: [命中地址...]}。命中不做对齐过滤, 由调用方按需筛选
    (memsrv 对全 8 字节针只回报对齐命中, 与客户端校验一致)。"""
    fn = getattr(reader, "scan_regions", None)
    if fn is None:
        return None
    regions = reader.regions(scope)
    total = sum(s for _, s in regions)
    t0 = time.time()
    res = fn(regions, needles)
    if res is None:
        err = getattr(reader, "last_scan_error", None)
        if err:
            status("  %s: 设备侧扫描异常, 回退逐块扫描 (%s)" % (label, err))
        return None
    status("  %s: 设备侧扫描 %.0f MB 用时 %.1fs" %
           (label, total / 1048576, time.time() - t0))
    return res


def _find_all(data, needle, align8):
    """python 兜底: data 内全部命中偏移 (align8 时只保留 8 对齐)。"""
    out = []
    pos = 0
    while True:
        j = data.find(needle, pos)
        if j < 0:
            break
        if not align8 or j % 8 == 0:
            out.append(j)
        pos = j + 1
    return out


# ---------------- 数组扫描 ----------------

def _valid_knuth_seeds(seeds):
    if seeds[0] != 0:
        return False
    zeros = 0
    first = seeds[1]
    all_same = True
    for s in seeds:
        if s < 0 or s >= MBIG:
            return False
        if s == 0:
            zeros += 1
        if s != first:
            all_same = False
    return zeros == 1 and not all_same


def _valid_mt_block(mt):
    if all(v == 0 for v in mt[:32]):
        return False
    return len(set(mt[:64])) > 8


def find_arrays(reader, length, validator, status=lambda m: None, scope="gc",
                first_elem=None):
    """扫描区域, 返回元素区起始地址 (数组对象 +0x20) 列表。

    needle = 长度字段(8B) [+ 首元素(4B)]: 首元素已知时带上可大幅降噪
    (裸 u64==56 在堆中极其常见, 设备侧单针命中上限 65536 会被打爆)。
    命中后的校验全部走 read_many 批量读 (逐命中单读在 adb 通道上是
    毫秒级往返, 几千候选会拖到几分钟)。"""
    if first_elem is not None:
        needle = struct.pack("<q", length) + struct.pack("<i", first_elem)
    else:
        needle = struct.pack("<q", length)
    elem_bytes = length * 4

    hits = _scan_needles(reader, scope, [needle], status,
                         label="数组(len=%d)" % length)
    if hits is not None:                     # 设备侧路径
        cands = [a for a in hits[needle] if a % 8 == 0]
        return _validate_array_cands(reader, cands, length, validator)

    cands = []
    regions = reader.regions(scope)          # python 回退 (pymem / FakeMem)
    for i, (base, size) in enumerate(regions):
        data = reader.read(base, size)
        if not data:
            continue
        if _np is not None and first_elem is None and len(data) >= 8:
            u8 = _np.frombuffer(data[: len(data) // 8 * 8], dtype="<u8")
            idxs = _np.nonzero(u8 == length)[0]
            positions = [int(i) * 8 for i in idxs]
        else:
            positions = _find_all(data, needle, align8=True)
        for p in positions:
            if p + 8 + elem_bytes <= len(data):
                cands.append(base + p)
        if status and (i + 1) % 64 == 0:
            status("  扫描数组(len=%d) %d%%" % (length, int((i + 1) / len(regions) * 100)))
    return _validate_array_cands(reader, cands, length, validator)


def _validate_array_cands(reader, cands, length, validator):
    """数组候选批量校验: 先查数组对象 klass 指针 (必须是堆指针, 随机数据块
    在 obj+0 处极少合法), 再批量读回元素内容过 validator。
    返回元素区起始地址 (候选命中点 +8) 列表。"""
    elem_bytes = length * 4
    read_many = getattr(reader, "read_many", None)
    if read_many is None:
        def read_many(reqs):
            return [reader.read(a, s) for a, s in reqs]
    cands = sorted(set(cands))
    # 1. klass 指针预筛 (klass 在 arr_obj+0 = 命中点-0x18)
    surv = []
    for i in range(0, len(cands), 512):
        batch = cands[i:i + 512]
        for p, d in zip(batch, read_many([(p - 0x18, 8) for p in batch])):
            if d and _is_heap_ptr(struct.unpack("<Q", d)[0]):
                surv.append(p)
    # 2. 元素内容校验
    results = []
    for i in range(0, len(surv), 256):
        batch = surv[i:i + 256]
        for p, d in zip(batch, read_many([(p + 8, elem_bytes) for p in batch])):
            if not d or len(d) < elem_bytes:
                continue
            vals = struct.unpack("<%di" % length, d)
            if validator(vals):
                results.append(p + 8)
    return results


def find_ptr_hits(reader, targets, status=lambda m: None, scope="rw"):
    """单遍扫描, 返回 {目标值: [命中地址...]} (targets 为地址值集合, 仅对齐命中)。"""
    targets = set(targets)
    out = {t: [] for t in targets}
    if not targets:
        return out
    needles = {struct.pack("<Q", t): t for t in targets}

    hits = _scan_needles(reader, scope, list(needles), status, label="指针回扫")
    if hits is not None:
        for nd, t in needles.items():
            out[t] = sorted(a for a in hits.get(nd, []) if a % 8 == 0)
        return out

    regions = reader.regions(scope)
    if _np is not None:
        vals = _np.array(sorted(targets), dtype="<u8")
    for i, (base, size) in enumerate(regions):
        data = reader.read(base, size)
        if not data:
            continue
        if _np is not None:
            u8 = _np.frombuffer(data[: len(data) // 8 * 8], dtype="<u8")
            hit_idx = _np.nonzero(_np.isin(u8, vals))[0]
            for k in hit_idx:
                v = int(u8[k])
                out[v].append(base + int(k) * 8)
        else:
            for t in targets:
                nd = struct.pack("<Q", t)
                for j in _find_all(data, nd, align8=True):
                    out[t].append(base + j)
        if status and (i + 1) % 64 == 0:
            status("  指针回扫 %d%%" % int((i + 1) / len(regions) * 100))
    return out


# ---------------- 引擎识别 ----------------

def probe_engines(reader, status=lambda m: None):
    """完整定位流程, 返回引擎记录列表 (按发现顺序)。"""
    status("第 1 遍: 扫描 Knuth SeedArray (len=56) ...")
    knuth_arrays = find_arrays(reader, 56, _valid_knuth_seeds, status, first_elem=0)
    status("  Knuth 数组候选 %d 个" % len(knuth_arrays))

    status("第 2 遍: 扫描 MT19937 mt 数组 (len=624) ...")
    mt_arrays = find_arrays(reader, 624, _valid_mt_block, status)
    status("  MT 数组候选 %d 个" % len(mt_arrays))

    all_arrays = knuth_arrays + mt_arrays
    if not all_arrays:
        return []

    status("第 3 遍: 反查数组持有者 (klass 校验) ...")
    hits = find_ptr_hits(reader, (a - ARRAY_ELEM_OFF for a in all_arrays), status)

    engines = []
    seen_obj = set()
    klass_cache = {}

    def klass_of(obj):
        if obj not in klass_cache:
            klass_cache[obj] = read_klass(reader, obj)
        return klass_cache[obj]

    for elem_addr in all_arrays:
        arr_obj = elem_addr - ARRAY_ELEM_OFF
        for hit in hits.get(arr_obj, []):
            for off, cls_name, kind, cursor_off in OWNER_LAYOUTS:
                obj = hit - off
                if obj in seen_obj:
                    continue
                kc = klass_of(obj)
                if not kc or kc[1] != cls_name:
                    continue
                seen_obj.add(obj)
                engines.append({
                    "kind": kind,
                    "cls": "%s.%s" % (kc[0], kc[1]) if kc[0] else kc[1],
                    "obj": obj,
                    "array": elem_addr,
                    "cursor_addr": obj + cursor_off,
                    "random_obj": obj,     # CompatilizedRandom 外壳稍后回填
                    "wrapper": "",
                    "label": "",
                    "paired": False,
                    "role": "",
                })
                break
    status("  klass 校验后引擎 %d 个" % len(engines))

    # MT 引擎反查 CompatilizedRandom 外壳 (original@0x20)
    mt_objs = [e["obj"] for e in engines if e["kind"] == "mt"]
    if mt_objs:
        whits = find_ptr_hits(reader, mt_objs)
        for e in engines:
            if e["kind"] != "mt":
                continue
            for hit in whits.get(e["obj"], []):
                wrapper = hit - 0x20
                kc = klass_of(wrapper)
                if kc and kc[1] == "CompatilizedRandom":
                    e["random_obj"] = wrapper
                    e["wrapper"] = "CompatilizedRandom"
                    break

    # 静态字段对检测: 指向 random_obj 的指针命中地址相差 8
    status("第 4 遍: 检测静态字段对 (randomImp/randomTrivial) ...")
    phits = find_ptr_hits(reader, [e["random_obj"] for e in engines])
    ref_addrs = {}
    for e in engines:
        ref_addrs[e["random_obj"]] = phits.get(e["random_obj"], [])
    for i, a in enumerate(engines):
        for b in engines[i + 1:]:
            for ha in ref_addrs.get(a["random_obj"], []):
                for hb in ref_addrs.get(b["random_obj"], []):
                    if hb - ha == 8:
                        a["paired"] = b["paired"] = True
                        a["role"] = "imp"
                        b["role"] = "trivial"
                        a["pair_hit"] = ha
                        b["pair_hit"] = hb
    for idx, e in enumerate(engines):
        role = {"imp": "关键随机 (randomImp)", "trivial": "表现随机 (randomTrivial)"}.get(e["role"], "")
        bits = [e["cls"]]
        if e["wrapper"]:
            bits.append("经 %s 包装" % e["wrapper"])
        if role:
            bits.append(role)
        e["label"] = " / ".join(bits)
        e["id"] = idx
    return engines


# ---------------- 静态指针链定位 (主路径) ----------------
#
# 游戏自身就持有指向 RNG 的指针链, 无需任何猜测:
#
#   "BattleController" 字符串 (堆中重建的 metadata, 见模块 docstring)
#     <- 被 Il2CppClass.name (+0x10) 引用, namespaze (+0x18) == "Torappu.Battle"
#   Il2CppClass.static_fields (+0xB8, 布局见 Ark_data/il2cpp.h:99-106)
#     +0x30 -> s_randomImp    (现网: BattleRandomWrapper 外壳)
#     +0x38 -> s_randomTrivial
#   BattleRandomWrapper (+0x10) -> 内部 Random 对象 (新版包装层,
#     dump.cs 旧版静态字段直接声明 Random; 现网实测为外壳, 见 AGENTS.md)
#   Random 对象 (klass 名判定具体实现):
#     LegacyRandom  -> SeedArray@0x28, inext@0x20, inextp@0x24   (Knuth)
#     Random(mscorlib) -> _seedArray@0x18, _inext@0x10           (Knuth)
#     CompatilizedRandom -> original@0x20 -> MersenneTwister(mt@0x10, mti@0x18)
#
# 已联网证实战斗 RNG 即 System.Random (mono mscorlib, Knuth 减法门),
# 判定方式为 NextDouble() < 阈值 (prts.wiki 代理学 + 贴吧逆向帖)。

KLASS_NAME = 0x10
KLASS_NAMESPAZE = 0x18
KLASS_STATIC_FIELDS = 0xB8
BC_STATIC_IMP = 0x30
BC_STATIC_TRIVIAL = 0x38

# Random 对象 klass 名 -> (kind, 游标偏移, 状态数组字段偏移)
RANDOM_OBJ_LAYOUTS = {
    "LegacyRandom": ("knuth", 0x20, 0x28),
    "Random": ("knuth", 0x10, 0x18),
}
# 透明包装 klass 名 -> 内部 Random 对象字段偏移 (新版战斗随机外层,
# dump.cs 旧版无此类: s_randomImp 声明为 Random, 现网实际指向包装)
WRAPPER_LAYOUTS = {
    "BattleRandomWrapper": 0x10,
}
INNER_MT_LAYOUTS = {
    "MersenneTwister": (0x18, 0x10),
    "TSRandom": (0x20, 0x18),
}


def find_cstring_hits(reader, needle, status=lambda m: None, scope="gc"):
    """全堆搜索 C 字符串, 返回起始地址列表 (要求前一字节为 \\0, 保证完整匹配)。

    默认 scope='gc': 实测类名/命名空间字符串位于大号匿名 rw 映射
    (libil2cpp.so 只读段里没有), 该分区与 GC 堆特征相同, 见模块 docstring。"""
    label = "字符串 \"%s\"" % needle[:24].decode("ascii", "replace")
    hits = _scan_needles(reader, scope, [needle], status, label=label)
    if hits is not None:                     # 设备侧路径: 逐命中补前字节校验
        results = []
        for addr in hits[needle]:
            prev = reader.read(addr - 1, 1)
            if prev and prev != b"\x00":
                continue
            results.append(addr)
        status("  %s 命中 %d 处" % (label, len(results)))
        return results

    results = []
    regions = reader.regions(scope)
    for base, size in regions:
        data = reader.read(base, size)
        if not data:
            continue
        pos = 0
        while True:
            j = data.find(needle, pos)
            if j < 0:
                break
            addr = base + j
            pos = j + 1
            if j > 0:
                if data[j - 1] != 0:
                    continue
            else:
                prev = reader.read(addr - 1, 1)
                if prev and prev != b"\x00":
                    continue
            results.append(addr)
    status("  %s 命中 %d 处" % (label, len(results)))
    return results


def _mk_engine(engine_id, kind, cls, obj, array, cursor_addr, role, via, wrapper=""):
    role_name = {"imp": "关键随机 (randomImp)", "trivial": "表现随机 (randomTrivial)"}.get(role, "")
    bits = [cls]
    if wrapper:
        bits.append("经 %s 包装" % wrapper)
    if role_name:
        bits.append(role_name)
    return {
        "id": engine_id,
        "kind": kind,
        "cls": cls,
        "obj": obj,
        "array": array,
        "cursor_addr": cursor_addr,
        "random_obj": obj,
        "wrapper": wrapper,
        "label": " / ".join(bits),
        "paired": role in ("imp", "trivial"),
        "role": role,
        "via": via,
    }


def resolve_engine_obj(reader, slot_addr):
    """解析静态槽地址 -> 内部 Random 对象地址 (经 BattleRandomWrapper 下钻)。

    槽空/对象非法返回 None。用于新一局检测: 重新开战后静态槽会指向新建的
    wrapper+引擎对象, 而旧对象内存可能原样残留 (轮询观测不到变化, 不会 lost),
    必须比对静态槽当前指向才能发现。"""
    obj = read_u64(reader, slot_addr)
    if not _is_heap_ptr(obj):
        return None
    kc = read_klass(reader, obj)
    if not kc:
        return None
    if kc[1] in WRAPPER_LAYOUTS:
        inner = read_u64(reader, obj + WRAPPER_LAYOUTS[kc[1]])
        return inner if _is_heap_ptr(inner) else None
    return obj


def engine_from_random_obj(reader, obj, role, via, engine_id=0, _depth=0):
    """把一个 System.Random 引用解析成引擎记录 (自动识别具体实现类/包装)。"""
    if not _is_heap_ptr(obj):
        return None
    kc = read_klass(reader, obj)
    if not kc:
        return None
    ns, name = kc
    cls = ("%s.%s" % (ns, name)) if ns else name
    if name in WRAPPER_LAYOUTS and _depth < 2:
        # 透明包装 (BattleRandomWrapper): 下钻内部 Random, 外壳记为 wrapper,
        # random_obj 保持静态字段直接持有的对象 (静态字段对检测用)
        inner = read_u64(reader, obj + WRAPPER_LAYOUTS[name])
        e = engine_from_random_obj(reader, inner, role, via, engine_id, _depth + 1)
        if e:
            e["wrapper"] = e["wrapper"] or name
            e["random_obj"] = obj
            bits = [e["cls"], "经 %s 包装" % name]
            role_name = {"imp": "关键随机 (randomImp)",
                         "trivial": "表现随机 (randomTrivial)"}.get(role)
            if role_name:
                bits.append(role_name)
            e["label"] = " / ".join(bits)
        return e
    if name in RANDOM_OBJ_LAYOUTS:
        kind, cursor_off, seed_off = RANDOM_OBJ_LAYOUTS[name]
        array_obj = read_u64(reader, obj + seed_off)
        if not _is_heap_ptr(array_obj):
            return None
        return _mk_engine(engine_id, kind, cls, obj, array_obj + ARRAY_ELEM_OFF,
                          obj + cursor_off, role, via)
    if name == "CompatilizedRandom":
        inner = read_u64(reader, obj + 0x20)
        ikc = read_klass(reader, inner)
        if not ikc or ikc[1] not in INNER_MT_LAYOUTS:
            return None
        cursor_off, mt_off = INNER_MT_LAYOUTS[ikc[1]]
        array_obj = read_u64(reader, inner + mt_off)
        if not _is_heap_ptr(array_obj):
            return None
        inner_cls = ("%s.%s" % ikc) if ikc[0] else ikc[1]
        e = _mk_engine(engine_id, "mt", inner_cls, inner, array_obj + ARRAY_ELEM_OFF,
                       inner + cursor_off, role, via, wrapper="CompatilizedRandom")
        e["random_obj"] = obj
        return e
    return None


def locate_battle_random(reader, status=lambda m: None):
    """经 BattleController 静态指针链精确定位 randomImp/randomTrivial。

    返回 (引擎列表, 定位方式 'static-chain'); 失败返回 ([] ,'static-chain')。
    战斗未开始时静态字段为 null, 同样返回空。
    """
    status("静态链: 搜索 BattleController klass ...")
    # 实测类名字符串与 Il2CppClass 都在堆中重建的 metadata 区 (非 GC 大匿名
    # 映射也可能只有拷贝), gc 分区只能扫到拷贝串 —— 直接全 rw 单遍扫
    strings = find_cstring_hits(reader, b"BattleController\x00", status, scope="rw")
    if not strings:
        return []
    hits = find_ptr_hits(reader, strings, status, scope="rw")

    engines = []
    seen_obj = set()
    for s, addrs in hits.items():
        for a in addrs:
            klass = a - KLASS_NAME
            ns = read_c_string(reader, read_u64(reader, klass + KLASS_NAMESPAZE))
            if ns != "Torappu.Battle":
                continue
            static_fields = read_u64(reader, klass + KLASS_STATIC_FIELDS)
            if not _is_heap_ptr(static_fields):
                continue
            status("静态链: BattleController klass=%s static_fields=%s" %
                   (hex(klass), hex(static_fields)))
            for role, off in (("imp", BC_STATIC_IMP), ("trivial", BC_STATIC_TRIVIAL)):
                obj = read_u64(reader, static_fields + off)
                if obj == 0 or obj in seen_obj:
                    continue
                e = engine_from_random_obj(reader, obj, role, "static-chain",
                                           engine_id=len(engines))
                if e:
                    e["watch_addr"] = static_fields + off   # 静态槽, 新一局检测用
                    seen_obj.add(obj)
                    engines.append(e)
                    status("静态链: s_random%s -> %s obj=%s array=%s" %
                           (role, e["cls"], hex(e["obj"]), hex(e["array"])))
    return engines


def locate_engines(reader, status=lambda m: None):
    """主入口: 优先静态指针链精确定位, 失败回退启发式全盘扫描。"""
    engines = locate_battle_random(reader, status)
    if engines:
        return engines, "static-chain"
    status("静态链未定位 (可能尚未开战), 回退启发式全盘扫描 ...")
    engines = probe_engines(reader, status)
    for e in engines:
        e["via"] = "heuristic"
    return engines, "heuristic"


# ---------------- 地址缓存校验 ----------------

def validate_engine(reader, e):
    """校验缓存的引擎地址在当前进程仍然有效 (游戏未重启时地址可复用)。

    三重校验: klass 名不变 / 对象状态字段仍指向缓存的数组 / 数组长度与
    游标值合法。任一项失败即视为缓存失效 (游戏重启或对象已回收)。"""
    try:
        kc = read_klass(reader, e["obj"])
        if not kc:
            return False
        ns, name = kc
        cls = ("%s.%s" % (ns, name)) if ns else name
        if cls != e["cls"]:
            return False
        if e["kind"] == "knuth":
            _, cursor_off, seed_off = RANDOM_OBJ_LAYOUTS[name]
            length = 56
        else:
            cursor_off, seed_off = INNER_MT_LAYOUTS[name]
            length = 624
        arr_obj = read_u64(reader, e["obj"] + seed_off)
        if arr_obj != e["array"] - ARRAY_ELEM_OFF:
            return False
        if read_u64(reader, arr_obj + ARRAY_LEN_OFF) != length:
            return False
        cursor = read_u64(reader, e["cursor_addr"]) & 0xFFFFFFFF
        return cursor < length
    except Exception:
        return False
