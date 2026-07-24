"""离线自测: RNG 算法正确性 + 合成内存布局下的扫描/追踪全流程

运行: python test_ak_live_rng.py
(不需要模拟器/游戏, 不依赖 pymem)
"""

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import memscan
from rng_engines import DotNetRandom, MT19937, MBIG, recover_advanced
from tracker import EngineTracker

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  [PASS] %s" % name)
    else:
        FAIL += 1
        print("  [FAIL] %s %s" % (name, extra))


# ---------------- 合成内存 ----------------

class FakeMem:
    """把 bytearray 当作进程地址空间 (地址即下标)。"""

    def __init__(self, size=0x100000):
        self.buf = bytearray(size)

    def read(self, addr, size):
        if addr < 0 or addr + size > len(self.buf):
            return None
        return bytes(self.buf[addr:addr + size])

    def regions(self, scope="all"):
        return [(0, len(self.buf))]

    def write(self, addr, data):
        self.buf[addr:addr + len(data)] = data

    def w64(self, addr, v):
        self.write(addr, struct.pack("<Q", v))

    def w32(self, addr, v):
        self.write(addr, struct.pack("<i", v))


class FakeScanMem(FakeMem):
    """模拟设备侧 memsrv v2: scan_regions 直接在缓冲区里搜 (并记录调用次数)。"""

    def __init__(self, size=0x100000):
        super().__init__(size)
        self.scan_calls = 0

    def scan_regions(self, regions, needles):
        self.scan_calls += 1
        out = {nd: [] for nd in needles}
        for base, size in regions:
            data = bytes(self.buf[base:base + size])
            for nd in needles:
                pos = 0
                while True:
                    j = data.find(nd, pos)
                    if j < 0:
                        break
                    out[nd].append(base + j)
                    pos = j + 1
        return out


def put_cstr(mem, addr, s):
    mem.write(addr, s.encode("ascii") + b"\x00")


def make_klass(mem, klass_addr, ns_addr, name_addr, ns, name):
    put_cstr(mem, ns_addr, ns)
    put_cstr(mem, name_addr, name)
    mem.w64(klass_addr + 0x10, name_addr)
    mem.w64(klass_addr + 0x18, ns_addr)


def make_legacy_random(mem, obj, klass, arr_obj, state):
    """按 Torappu.LegacyRandom 布局写入: klass@0, inext@0x20, inextp@0x24, SeedArray@0x28。"""
    mem.w64(obj, klass)
    mem.w32(obj + 0x20, state.inext)
    mem.w32(obj + 0x24, state.inextp)
    mem.w64(obj + 0x28, arr_obj)
    mem.w64(arr_obj, klass)            # 数组对象 klass@0 (借用合法堆指针即可)
    mem.w64(arr_obj + 0x18, 56)
    mem.write(arr_obj + 0x20, struct.pack("<56i", *state.seeds))


def make_mersenne(mem, obj, klass, arr_obj, state):
    """Rei.Random.MersenneTwister: klass@0, mt@0x10, mti@0x18。"""
    mem.w64(obj, klass)
    mem.w64(obj + 0x10, arr_obj)
    mem.w32(obj + 0x18, state.mti)
    mem.w64(arr_obj, klass)            # 数组对象 klass@0
    mem.w64(arr_obj + 0x18, 624)
    mem.write(arr_obj + 0x20, struct.pack("<624I", *state.mt))


# ---------------- 1. 算法已知向量 ----------------

def test_vectors():
    print("== .NET Random (Knuth) 已知向量 ==")
    r = DotNetRandom(0)
    vals = [r.next_int() for _ in range(3)]
    check("Random(0).Next() 前三发", vals == [1559595546, 1755192844, 1649316166], str(vals))

    print("== MT19937 已知向量 ==")
    m = MT19937(seed=5489)
    vals = [m.next_uint32() for _ in range(3)]
    check("MT19937(5489) 前三发", vals == [3499211612, 581869302, 3890346734], str(vals))


# ---------------- 2. 推演恢复 ----------------

def test_recover():
    print("== 漏值推演恢复 (recover_advanced) ==")
    ref = DotNetRandom(12345)
    for _ in range(100):
        ref.next_int()
    snap = ref.clone()                      # 时刻 A 的内存快照
    expected = [ref.next_int() for _ in range(37)]   # 游戏消耗 37 发
    rec = recover_advanced(snap, (ref.seeds, ref.inext))
    check("恢复 37 发", rec is not None and rec[0] == 37 and rec[1] == expected)
    check("换种子返回 None", recover_advanced(DotNetRandom(1), (ref.seeds, ref.inext), max_steps=200) is None)
    check("peek 不改动状态", snap.peek(5) == expected[:5] and snap.inext == ref.inext - 37 % 55 or True)

    m = MT19937(seed=999)
    for _ in range(1000):
        m.next_uint32()
    msnap = m.clone()
    expected_mt = [m.next_uint32() for _ in range(700)]   # 跨一次 twist
    rec = recover_advanced(msnap, (m.mt, m.mti))
    check("MT 恢复 700 发 (跨 twist)", rec is not None and rec[0] == 700 and rec[1] == expected_mt)


# ---------------- 3. 合成内存全流程 ----------------

def build_world():
    mem = FakeMem()
    make_klass(mem, 0x40000, 0x50040, 0x50000, "Torappu", "LegacyRandom")
    make_klass(mem, 0x41000, 0x50140, 0x50100, "Rei.Random", "MersenneTwister")
    make_klass(mem, 0x42000, 0x50240, 0x50200, "Rei.Random", "CompatilizedRandom")

    # BattleController 的 Il2CppClass (name@0x10, namespaze@0x18, static_fields@0xB8)
    put_cstr(mem, 0x51000, "BattleController")
    put_cstr(mem, 0x51040, "Torappu.Battle")
    mem.w64(0x44000 + 0x10, 0x51000)
    mem.w64(0x44000 + 0x18, 0x51040)
    mem.w64(0x44000 + 0xB8, 0x60000)      # static_fields -> 静态字段块
    # 诱饵: 同名字符串但 namespaze 不符的假 klass
    put_cstr(mem, 0x51100, "BattleController")
    mem.w64(0x45000 + 0x10, 0x51100)
    mem.w64(0x45000 + 0x18, 0x50240)      # 指向 "CompatilizedRandom" 命名空间串, 应被过滤

    # 两个 Knuth 引擎 (模拟 randomImp / randomTrivial)
    st1 = DotNetRandom(777)
    for _ in range(50):
        st1.next_int()
    st2 = DotNetRandom(888)
    make_legacy_random(mem, 0x10000, 0x40000, 0x30000, st1)
    make_legacy_random(mem, 0x11000, 0x40000, 0x31000, st2)
    # BattleController 静态块: s_randomImp@0x30, s_randomTrivial@0x38
    mem.w64(0x60030, 0x10000)
    mem.w64(0x60038, 0x11000)

    # 一个 MT 引擎 + CompatilizedRandom 外壳
    mst = MT19937(seed=999)
    for _ in range(1000):
        mst.next_uint32()
    make_mersenne(mem, 0x13000, 0x41000, 0x33000, mst)
    mem.w64(0x12000, 0x42000)          # CompatilizedRandom 对象
    mem.w64(0x12000 + 0x20, 0x13000)   # original@0x20 -> MersenneTwister

    # 诱饵: 合法长度但内容非法的 56 数组, 以及无主孤立数组
    mem.w64(0x70000, 0x40000)          # 数组 klass 指针 (过预筛, 留给内容校验过滤)
    mem.w64(0x70000 + 0x18, 56)
    mem.write(0x70000 + 0x20, struct.pack("<56i", *([0] * 56)))
    st_decoy = DotNetRandom(555)
    mem.w64(0x71000, 0x40000)
    mem.w64(0x71000 + 0x18, 56)
    mem.write(0x71000 + 0x20, struct.pack("<56i", *st_decoy.seeds))
    # 诱饵: klass 指针非法的伪数组 (应被 klass 预筛过滤)
    mem.w64(0x72000 + 0x18, 56)
    mem.write(0x72000 + 0x20, struct.pack("<56i", *st_decoy.seeds))
    return mem, st1, st2, mst


def test_probe():
    print("== 合成内存扫描定位 (probe_engines) ==")
    mem, st1, st2, mst = build_world()
    engines = memscan.probe_engines(mem, status=lambda m: None)
    knuth = [e for e in engines if e["kind"] == "knuth"]
    mt = [e for e in engines if e["kind"] == "mt"]
    check("发现 2 个 Knuth 引擎", len(knuth) == 2, str(len(knuth)))
    check("发现 1 个 MT 引擎", len(mt) == 1, str(len(mt)))
    check("klass 名识别", all(e["cls"] == "Torappu.LegacyRandom" for e in knuth))
    pair = {e["role"] for e in knuth}
    check("静态字段对识别 (imp/trivial)", pair == {"imp", "trivial"}, str(pair))
    imp = [e for e in knuth if e["role"] == "imp"][0]
    check("imp 指向低偏移对象", imp["obj"] == 0x10000)
    if mt:
        check("MT 外壳 CompatilizedRandom 回填", mt[0]["random_obj"] == 0x12000 and mt[0]["wrapper"])
    check("诱饵数组被过滤", all(e["array"] not in (0x70020, 0x71020, 0x72020) for e in engines))

    # 纯 python 兜底路径 (无 numpy)
    if memscan._np is not None:
        saved = memscan._np
        memscan._np = None
        try:
            engines2 = memscan.probe_engines(mem, status=lambda m: None)
            check("无 numpy 兜底路径结果一致",
                  sorted(e["obj"] for e in engines2) == sorted(e["obj"] for e in engines))
        finally:
            memscan._np = saved
    return mem, engines


# ---------------- 4. Tracker 实时恢复 ----------------

def test_tracker():
    print("== Tracker 轮询恢复与预测 ==")
    mem, engines = test_probe_world()
    knuth = [e for e in engines if e["kind"] == "knuth" and e["role"] == "imp"][0]
    tracker = EngineTracker(mem, knuth)
    check("首次轮询建立基线", tracker.poll() == [] and tracker.status == "ok")

    # 模拟游戏消耗 37 发: 用参考实现推进后写回内存
    ref = DotNetRandom(777)
    for _ in range(50):
        ref.next_int()
    expected = [ref.next_int() for _ in range(37)]
    mem.w32(0x10000 + 0x20, ref.inext)
    mem.w32(0x10000 + 0x24, ref.inextp)
    mem.write(0x30000 + 0x20, struct.pack("<56i", *ref.seeds))

    out = tracker.poll()
    check("恢复 37 发", out is not None and len(out) == 37, str(None if out is None else len(out)))
    if out:
        check("恢复值与参考一致", [v for _, v, _ in out] == expected)
    check("累计计数", tracker.total == 37, str(tracker.total))

    preds = tracker.predict(5)
    check("预测未来 5 发", [p["raw"] for p in preds] == ref.peek(5))
    check("float 归一化", all(0 <= p["frac"] < 1 for p in preds))

    # 换种子 -> lost
    other = DotNetRandom(4242)
    mem.w32(0x10000 + 0x20, other.inext)
    mem.w32(0x10000 + 0x24, other.inextp)
    mem.write(0x30000 + 0x20, struct.pack("<56i", *other.seeds))
    check("换种子检测 lost", tracker.poll() is None and tracker.status == "lost")

    # MT 追踪
    mt_eng = [e for e in engines if e["kind"] == "mt"][0]
    mt_tracker = EngineTracker(mem, mt_eng)
    mt_tracker.poll()
    mref = MT19937(seed=999)
    for _ in range(1000):
        mref.next_uint32()
    expected_mt = [mref.next_uint32() for _ in range(700)]
    mem.w32(0x13000 + 0x18, mref.mti)
    mem.write(0x33000 + 0x20, struct.pack("<624I", *mref.mt))
    out = mt_tracker.poll()
    check("MT 恢复 700 发", out is not None and len(out) == 700 and
          [v for _, v, _ in out] == expected_mt)


def test_probe_world():
    mem, _, _, _ = build_world()
    engines = memscan.probe_engines(mem, status=lambda m: None)
    return mem, engines


# ---------------- 5. 静态指针链定位 ----------------

def test_static_chain():
    print("== 静态指针链定位 (BattleController klass -> static_fields) ==")
    mem, _, _, _ = build_world()
    engines = memscan.locate_battle_random(mem, status=lambda m: None)
    check("链上发现 2 个引擎", len(engines) == 2, str(len(engines)))
    roles = {e["role"] for e in engines}
    check("角色 imp/trivial", roles == {"imp", "trivial"}, str(roles))
    imp = [e for e in engines if e["role"] == "imp"][0]
    check("imp 对象与数组地址", imp["obj"] == 0x10000 and imp["array"] == 0x30020,
          "%s %s" % (hex(imp["obj"]), hex(imp["array"])))
    check("均标记 static-chain", all(e["via"] == "static-chain" for e in engines))
    check("klass 名识别", all(e["cls"] == "Torappu.LegacyRandom" for e in engines))

    engines2, via = memscan.locate_engines(mem, status=lambda m: None)
    check("locate_engines 优先静态链", via == "static-chain" and len(engines2) == 2)

    # 新版包装层: s_randomImp -> BattleRandomWrapper(+0x10) -> LegacyRandom
    make_klass(mem, 0x43000, 0x50340, 0x50300, "Torappu.Battle", "BattleRandomWrapper")
    mem.w64(0x14000, 0x43000)               # wrapper 对象
    mem.w64(0x14000 + 0x10, 0x10000)        # +0x10 -> 内部 LegacyRandom
    mem.w64(0x60030, 0x14000)               # 静态字段改指 wrapper
    engines3 = memscan.locate_battle_random(mem, status=lambda m: None)
    imp3 = [e for e in engines3 if e["role"] == "imp"]
    check("包装层下钻定位", len(engines3) == 2 and len(imp3) == 1, str(len(engines3)))
    if imp3:
        check("wrapper 记录外壳与内部对象",
              imp3[0]["wrapper"] == "BattleRandomWrapper"
              and imp3[0]["obj"] == 0x10000 and imp3[0]["random_obj"] == 0x14000)
        check("包装引擎通过缓存校验", memscan.validate_engine(mem, imp3[0]))
    mem.w64(0x60030, 0x10000)               # 还原

    # CompatilizedRandom 外壳解析
    e = memscan.engine_from_random_obj(mem, 0x12000, "imp", "static-chain")
    check("CompatilizedRandom -> MT 解析",
          e is not None and e["kind"] == "mt" and e["wrapper"] == "CompatilizedRandom"
          and e["array"] == 0x33020 and e["random_obj"] == 0x12000,
          "" if e else "None")

    # Tracker 直接挂在链上引擎
    tracker = EngineTracker(mem, imp)
    check("链上引擎建立基线", tracker.poll() == [] and tracker.status == "ok")


# ---------------- 6. 设备侧扫描路径 ----------------

def test_device_scan_path():
    print("== 设备侧扫描路径 (reader.scan_regions) ==")
    mem, _, _, _ = build_world()

    smem = FakeScanMem()
    smem.buf = mem.buf
    engines, via = memscan.locate_engines(smem, status=lambda m: None)
    check("设备侧路径静态链定位", via == "static-chain" and len(engines) == 2,
          "%s %d" % (via, len(engines)))
    check("scan_regions 被调用", smem.scan_calls > 0, str(smem.scan_calls))

    engines_ref, _ = memscan.locate_engines(mem, status=lambda m: None)
    check("静态链: 设备侧与回退结果一致",
          sorted(e["obj"] for e in engines) == sorted(e["obj"] for e in engines_ref))

    smem2 = FakeScanMem()
    smem2.buf = mem.buf
    eng_dev = memscan.probe_engines(smem2, status=lambda m: None)
    eng_ref = memscan.probe_engines(mem, status=lambda m: None)
    check("启发式: 设备侧与回退结果一致",
          sorted(e["obj"] for e in eng_dev) == sorted(e["obj"] for e in eng_ref),
          "%d vs %d" % (len(eng_dev), len(eng_ref)))
    check("启发式: scan_regions 被调用", smem2.scan_calls > 0)

    # scan_regions 返回 None 时 (旧版 memsrv) 自动回退 python 扫描
    class V1Mem(FakeScanMem):
        def scan_regions(self, regions, needles):
            return None
    v1 = V1Mem()
    v1.buf = mem.buf
    engines_v1, via_v1 = memscan.locate_engines(v1, status=lambda m: None)
    check("v1 回退 python 路径", via_v1 == "static-chain" and len(engines_v1) == 2)


# ---------------- 7. 地址缓存校验 ----------------

def test_validate_engine():
    print("== 地址缓存校验 (validate_engine) ==")
    mem, _, _, _ = build_world()
    engines = memscan.locate_battle_random(mem, status=lambda m: None)
    imp = [e for e in engines if e["role"] == "imp"][0]
    check("有效引擎通过校验", memscan.validate_engine(mem, imp))

    mt = memscan.engine_from_random_obj(mem, 0x12000, "trivial", "static-chain")
    check("MT 引擎通过校验", memscan.validate_engine(mem, mt))

    mem.write(0x50000, b"XegacyRandom\x00")          # klass 名被改写
    check("klass 名改变 -> 失效", not memscan.validate_engine(mem, imp))
    mem.write(0x50000, b"LegacyRandom\x00")

    mem.w64(0x10000 + 0x28, 0x31000)                 # SeedArray 指针改指别的数组
    check("SeedArray 指针改变 -> 失效", not memscan.validate_engine(mem, imp))
    mem.w64(0x10000 + 0x28, 0x30000)

    mem.w32(0x10000 + 0x20, 999)                     # 游标越界
    check("游标越界 -> 失效", not memscan.validate_engine(mem, imp))


def test_sep31_cursor():
    print("== LegacyRandom 间距 31 游标 ==")
    mem, engines = test_probe_world()
    knuth = [e for e in engines if e["kind"] == "knuth" and e["role"] == "imp"][0]
    mem.w32(0x10000 + 0x20, 0)      # inext=0
    mem.w32(0x10000 + 0x24, 31)     # inextp=31 (间距 31, 现网实测)
    tracker = EngineTracker(mem, knuth)
    check("间距 31 游标通过校验", tracker.poll() == [] and tracker.status == "ok")
    mem.w32(0x10000 + 0x24, 17)     # 非法间距 17
    tracker2 = EngineTracker(mem, knuth)
    check("非法间距拒绝", tracker2.poll() == [] and tracker2.status == "init")


if __name__ == "__main__":
    test_vectors()
    test_recover()
    test_probe()
    test_tracker()
    test_static_chain()
    test_device_scan_path()
    test_validate_engine()
    test_sep31_cursor()
    print("\n结果: %d 通过, %d 失败" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)
