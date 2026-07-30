# -*- coding: utf-8 -*-
"""敌人读取器 (正式版, 2026-07-22 全偏移实测重写)

工作原理:
  bootstrap (一次性, 结果缓存磁盘):
    1. 扫 GC 堆找 "enemy_" UTF-16 字符串对象集合 S 和 HP 签名位置 P
       (FP Q32.32: 整数血量 -> 低32位=0, 高32位=HP)
    2. 扫指向 S 的指针位置集合 R; 候选实体 B=P-0x40, 若 B+0x100..0x1A8
       内有位置 ∈ R 且 klass 名 == 'Enemy' -> 场上敌人
    3. 扫指向敌人的指针 -> items 数组 -> List<Enemy> (m_managedWaveEnemies)
    4. 扫指向 List 的指针 (全堆唯一) -> Scheduler; 经 SchedulerDriver(+0xF0)
       的 +0x10 找到 BattleController
  poll (每次 ~2-3 秒):
    List -> items -> 逐敌人读 0x200 块 + Attributes -> HP/攻击/防御/法抗/移速/攻速
    BattleController -> 状态/倍速/战斗时间
"""

import os
import sys
import time
import pickle
import struct
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor

try:
    import numpy as np
except ImportError:
    np = None

from .memcore import MemCore, TcpChannel
from . import game_structs as gs
from .enemy_db import load_enemy_db

NEEDLE_ENEMY = 'enemy_'.encode('utf-16-le')   # UTF-16LE "enemy_"
HP_MIN, HP_MAX = 50, 1_000_000                # HP 签名高32位范围
SCAN_CAP = 32 * 1024 * 1024                   # 每块 32MB

if getattr(sys, 'frozen', False):
    # 打包模式: _MEIPASS 是每次启动重建的临时目录, 缓存放 exe 旁以便跨启动复用
    CACHE_FILE = os.path.join(os.path.dirname(sys.executable), 'enemy_cache.pkl')
else:
    CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'enemy_cache.pkl')


def _u64(b, o):
    return struct.unpack_from('<Q', b, o)[0]


def _i32(b, o):
    return struct.unpack_from('<i', b, o)[0]


def _f32x2(b, o):
    return struct.unpack_from('<2f', b, o)


class _HeapSnapshot:
    """首次扫描的堆快照: 第 1 遍扫描边扫边落盘, 后续各遍从本地磁盘读。

    adb 隧道聚合带宽 ~20MB/s 且 4 路并发即饱和, 5 遍全量扫描 = 传 5 份堆;
    快照把传输压到 1 份 (耗时 ~堆大小/带宽), 其余 4 遍本地读盘 (GB/s 级)。
    IL2CPP Boehm GC 不移动对象, 扫描窗口 (~1 分钟) 内长寿命对象地址稳定,
    快照自洽。临时文件用完即删。"""

    def __init__(self):
        fd, self.path = tempfile.mkstemp(prefix='ak_heap_', suffix='.bin')
        self.fd = fd
        self.size = 0
        self.ranges = []          # (base, file_off, size), 写入顺序
        self._lock = threading.Lock()

    def write(self, base: int, data: bytes):
        with self._lock:
            off = self.size
            view = memoryview(data)
            while view:
                n = os.write(self.fd, view)
                view = view[n:]
            self.size += len(data)
            self.ranges.append((base, off, len(data)))

    def iter_chunks(self):
        """按基址升序产出 (base, bytes)"""
        with open(self.path, 'rb', buffering=1024 * 1024) as f:
            for base, off, size in sorted(self.ranges):
                f.seek(off)
                yield base, f.read(size)

    def discard(self):
        try:
            os.close(self.fd)
        except OSError:
            pass
        try:
            os.remove(self.path)
        except OSError:
            pass


class EnemyInfo:
    __slots__ = ('addr', 'eid', 'name', 'code', 'hp', 'max_hp', 'atk', 'def_', 'res',
                 'mspd', 'aspd', 'direction', 'finish', 'alive', 'id_ptr', 'attr_ptr',
                 'pos_x', 'pos_y', 'blk_x', 'blk_y', 'spawn_row', 'spawn_col', 'skills',
                 'state_ptr', 'state_id', 'ep_ptr', 'ep_controller_ptr',
                 'shield_controller_ptr', 'es', 'shield',
                 'ep_remaining', 'ep_break_recovery', 'buff_container_ptr',
                 'attributes', 'raw_attributes', 'abnormal_flags', 'abnormal_immunes',
                 'abnormal_antis', 'abnormal_combos', 'abnormal_combo_immunes',
                 'buffs', 'global_buffs')

    def __init__(self, addr):
        self.addr = addr
        self.eid = ''
        self.name = ''
        self.code = ''
        self.hp = 0.0
        self.max_hp = 0.0
        self.atk = 0.0
        self.def_ = 0.0
        self.res = 0.0
        self.mspd = 0.0
        self.aspd = 0.0
        self.direction = 0
        self.finish = 0
        self.alive = True
        self.id_ptr = 0
        self.attr_ptr = 0
        self.pos_x = 0.0
        self.pos_y = 0.0
        self.blk_x = 0.0
        self.blk_y = 0.0
        self.spawn_row = 0
        self.spawn_col = 0
        self.skills = []          # [(prefabKey, remaining, period), ...]
        self.state_ptr = 0
        self.state_id = gs.EnemyState.DEFAULT
        self.ep_ptr = 0
        self.ep_controller_ptr = 0
        self.shield_controller_ptr = 0
        self.es = 0.0
        self.shield = 0.0
        self.ep_remaining = {}    # ElementType -> 剩余损伤容量
        self.ep_break_recovery = False
        self.buff_container_ptr = 0
        self.attributes = {}      # AttributeType -> 最终值 (cachedData)
        self.raw_attributes = {}  # AttributeType -> 原始值 (rawData), 详情读取
        self.abnormal_flags = [0] * gs.AbnormalFlag.E_NUM
        self.abnormal_immunes = [0] * gs.AbnormalFlag.E_NUM
        self.abnormal_antis = [0] * gs.AbnormalFlag.E_NUM
        self.abnormal_combos = [0] * gs.AbnormalCombo.E_NUM
        self.abnormal_combo_immunes = [0] * gs.AbnormalCombo.E_NUM
        self.buffs = []
        self.global_buffs = []

    def attribute(self, index, default=0.0):
        return self.attributes.get(index, default)

    @property
    def status_resistance(self):
        """游戏保存的是 1 - 状态抗性；界面对外展示实际状态抗性。"""
        return 1.0 - self.attribute(gs.AttributeType.ONE_MINUS_STATUS_RESISTANCE, 1.0)

    def active_status_names(self):
        names = [gs.ABNORMAL_FLAG_CN_NAMES.get(i, str(i))
                 for i, count in enumerate(self.abnormal_flags) if count > 0]
        names.extend(gs.ABNORMAL_COMBO_CN_NAMES.get(i, str(i))
                     for i, count in enumerate(self.abnormal_combos) if count > 0)
        # 状态机是另一条独立数据链。有些极短状态先切状态机、后更新计数，合并显示。
        state_status = {
            gs.EnemyState.STUN: '眩晕', gs.EnemyState.FROZEN: '冻结',
            gs.EnemyState.LEVITATE: '浮空', gs.EnemyState.PALSY: '麻痹',
            gs.EnemyState.UNBALANCE: '失衡',
        }.get(self.state_id)
        if state_status and state_status not in names:
            names.append(state_status)
        return names

    def status_text(self):
        names = self.active_status_names()
        return '、'.join(names) if names else '正常'

    def element_damage(self, element_type):
        maximum = max(0.0, self.attribute(gs.AttributeType.MAX_EP, 0.0))
        remaining = max(0.0, self.ep_remaining.get(element_type, maximum))
        damage = max(0.0, maximum - remaining)
        return damage, remaining, maximum


class EnemyReader:
    def __init__(self, adb_path=None, package='com.hypergryph.arknights',
                 cache_file=CACHE_FILE, with_bc=True, log=print, workers=8, mc=None):
        self.mc = mc if mc is not None else MemCore(adb_path, package)
        self.cache_file = cache_file
        self.with_bc = with_bc
        self.log = log
        self.workers = workers          # 扫描并发 adb 流数
        self.progress = None            # 可选回调 progress(pct:int, desc:str)
        # 发现的地址
        self.enemy_addrs = []
        self.items_addr = 0
        self.list_addr = 0
        self.sched_addr = 0
        self.bc_addr = 0
        # 轮询缓存
        self._names = {}          # enemy addr -> (eid, name, code)
        self._attr_cache = {}     # enemy addr -> cachedData 数组地址
        self._db = None
        self._stale_cnt = 0
        self._last_bootstrap = 0.0
        self._merge_lock = threading.Lock()  # 并行扫描合并锁
        # 准实时轮询 (常驻 TCP 通道)
        self._chan = None             # TcpChannel, 惰性打开
        self._fast_tick = 0
        self._attr_snapshot = {}      # enemy addr -> {AttributeType: 最终属性值}
        self._runtime_snapshot = {}   # enemy addr -> 状态/损伤条/异常计数
        self._runtime_ptrs = {}       # enemy addr -> 运行时详情指针缓存
        self._f_items = 0             # 上一帧 items 数组地址 (投机读用)
        self._f_cnt = 0               # 上一帧敌人数量
        self._f_ptrs = []             # 上一帧敌人指针列表
        self._f_version = -1          # 上一帧 List._version (变化即重读 items)
        self._bc_snap = None          # BC 块缓存 (state, speed, time_scale, play_time)
        self._attr_ptrs = {}          # enemy addr -> Attributes* (属性轮换读取用)
        self._chan_fail = 0           # 通道连续异常计数 (日志节流)
        self._chan_dead_ts = 0.0      # 通道上次失败时间 (冷却期内直接走慢速)
        self._skill_lp = {}           # enemy addr -> m_skills List* (主块内提取)
        self._skill_names = {}        # skill addr -> prefabKey (技能静态名缓存)
        self._skill_cd = {}           # enemy addr -> [(key, remaining, period), ...]

    # ================= 连接 =================

    def connect(self):
        pid = self.mc.connect()
        self.log(f"[连接] 游戏 PID = {pid}")
        return pid

    # ================= 底层扫描 =================

    def _scan_pass(self, on_chunk, desc, sink=None):
        """对 GC 堆做一次扫描, on_chunk(base, bytes) 回调。
        多路 adb 并行读取 (有界并发, 在飞块数=workers, 内存可控);
        on_chunk 在锁内串行执行, 回调写法与顺序版一致。
        sink 非空时把成功读取的块同时写入 _HeapSnapshot。"""
        targets = self.mc.scan_targets()
        total = sum(e - s for s, e in targets)
        segs = []
        for s, e in targets:
            a = s
            while a < e:
                segs.append((a, min(a + SCAN_CAP, e)))
                a += SCAN_CAP
        done = [0]
        miss = [0]
        t0 = time.time()
        lock = threading.Lock()
        sem = threading.Semaphore(self.workers)   # 有界提交: 在飞任务 ≤ workers

        def job(a, b):
            try:
                try:
                    d = self.mc.read(a, b - a, timeout=30)
                except Exception:
                    d = None   # dd 偶发卡死/超时: 跳过该块, 不让整遍扫描崩
                if d is None:
                    with lock:
                        miss[0] += b - a
                else:
                    if sink is not None:
                        sink.write(a, d)
                    on_chunk(a, d)   # 无锁调用; 各回调用 _merge_lock 自行合并
                with lock:
                    done[0] += b - a
                    el = time.time() - t0
                    pct = done[0] * 100 // total
                    msg = (f"[扫描] {desc} {pct}% ({done[0]/1e6:.0f}/{total/1e6:.0f} MB, "
                           f"{done[0]/1e6/(el+0.01):.0f} MB/s)")
                    print(f"\r{msg}   ", end='', flush=True)
                    if self.progress:
                        self.progress(pct, desc)
            finally:
                sem.release()

        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            futs = []
            for a, b in segs:
                sem.acquire()
                futs.append(ex.submit(job, a, b))
            for f in futs:
                f.result()
        print()
        if miss[0]:
            self.log(f"[扫描] 警告: {miss[0]/1e6:.1f} MB 读取失败被跳过 ({desc})")

    def _scan_pass_local(self, snap, on_chunk, desc):
        """从堆快照重放一次扫描 (零 adb, 磁盘 GB/s 级)"""
        t0 = time.time()
        for base, d in snap.iter_chunks():
            on_chunk(base, d)
        self.log(f"[扫描] {desc} (快照) {time.time()-t0:.1f}s")
        if self.progress:
            self.progress(100, desc)

    def _pass(self, snap, on_chunk, desc):
        """有快照走本地, 否则走网络扫描"""
        if snap is not None:
            self._scan_pass_local(snap, on_chunk, desc)
        else:
            self._scan_pass(on_chunk, desc)

    # ---------------- bootstrap 各阶段 ----------------

    def _find_strings_and_hp(self, snap=None):
        """第 1 遍: enemy_ 字符串对象集合 S + HP 签名位置 P
        (同时把全部扫描块写入快照 snap, 供后续各遍本地复用)"""
        S, P = set(), []
        hp_min, hp_max = HP_MIN, HP_MAX

        def on_chunk(base, d):
            pos = 0
            while True:
                i = d.find(NEEDLE_ENEMY, pos)
                if i < 0:
                    break
                pos = i + 2
                obj = base + i - gs.Il2CppString.CHARS
                if i < gs.Il2CppString.CHARS:
                    continue
                ln = _i32(d, i - gs.Il2CppString.CHARS + gs.Il2CppString.LENGTH)
                if 8 <= ln <= 80:
                    S.add(obj)
            if np is not None:
                q = np.frombuffer(d, dtype='<u8')
                mask = ((q & 0xFFFFFFFF) == 0) & (q >> 32 >= hp_min) & (q >> 32 <= hp_max)
                idx = np.nonzero(mask)[0]
                P.extend((base + int(i) * 8 for i in idx))
            else:
                for off in range(0, len(d) - 8, 8):
                    v = _u64(d, off)
                    if (v & 0xFFFFFFFF) == 0 and hp_min <= v >> 32 <= hp_max:
                        P.append(base + off)

        self._scan_pass(on_chunk, "enemy字符串+HP签名", sink=snap)
        self.log(f"[扫描] 字符串 {len(S)} 个, HP签名 {len(P)} 处")
        return S, P

    def _find_refs(self, S, snap=None):
        """第 2 遍: 指向 S 的指针位置集合 R"""
        R = set()
        if np is not None:
            s_arr = np.array(sorted(S), dtype='<u8')

            def on_chunk(base, d):
                q = np.frombuffer(d, dtype='<u8')
                idx = np.nonzero(np.isin(q, s_arr))[0]
                R.update(base + int(i) * 8 for i in idx)
        else:
            def on_chunk(base, d):
                for off in range(0, len(d) - 8, 8):
                    if _u64(d, off) in S:
                        R.add(base + off)

        self._pass(snap, on_chunk, "字符串引用")
        self.log(f"[扫描] 引用 {len(R)} 处")
        return R

    def _filter_enemies(self, P, R):
        """候选实体 -> klass 名过滤 -> 场上敌人"""
        survivors = []
        for p in P:
            B = p - gs.EntityFields.M_HP
            for x in range(0x100, 0x1A9, 8):
                if B + x in R:
                    survivors.append(B)
                    break
        self.log(f"[扫描] 候选实体 {len(survivors)} 个, 验证 klass ...")
        out = []
        for B in survivors:
            if self.mc.read_klass_name(B) == 'Enemy':
                out.append(B)
                self.log(f"  敌人 @ {hex(B)}")
        return out

    def _find_items_array(self, enemies, snap=None):
        """第 3 遍: 指向敌人的指针 -> items 数组候选 (块内局部解析, 无额外 adb)。
        返回按匹配分降序的候选地址列表 (可能有重复引用的干扰数组, 由第 4 遍验证)。"""
        eset = set(enemies)
        s_arr = np.array(sorted(eset), dtype='<u8') if np is not None else None
        cand = {}  # 数组基址 -> 匹配数

        def on_chunk(base, d):
            if np is not None:
                q = np.frombuffer(d, dtype='<u8')
                hit_idx = np.nonzero(np.isin(q, s_arr))[0]
            else:
                hit_idx = [o // 8 for o in range(0, len(d) - 8, 8) if _u64(d, o) in eset]
            n = len(d) // 8
            for j in hit_idx:
                j = int(j)
                for slot in range(16):
                    a0 = j - slot - gs.Il2CppArray.ITEMS // 8   # 数组基址(qword索引)
                    if a0 < 0:
                        continue
                    cap = _i32(d, a0 * 8 + gs.Il2CppArray.MAX_LENGTH)
                    # cap 只作粗过滤: 扫描发现的敌人数常偏离真实列表长度
                    # (退场对象未回收/非整数血量漏检/扫描期间刷怪),
                    # 精确性交给匹配分排序与第 5 遍 Scheduler 反查
                    if not (1 <= cap <= 300):
                        continue
                    klass = _u64(d, a0 * 8)
                    # klass 指针合理性: 48 位用户态高地址段 (1TB-256TB)。
                    # 不能按具体设备 ASLR 写死范围 (曾写死 0x70-0x72,
                    # 换机后堆映射到 0x74 段导致全部误杀)
                    if not (0x10000000000 <= klass < 0x1000000000000):
                        continue
                    body0 = a0 + gs.Il2CppArray.ITEMS // 8
                    if body0 + cap > n:
                        continue
                    score = 0
                    for k in range(cap):
                        if _u64(d, body0 * 8 + k * 8) in eset:
                            score += 1
                    A = base + a0 * 8
                    with self._merge_lock:
                        if score > cand.get(A, 0):
                            cand[A] = score

        self._pass(snap, on_chunk, "敌人指针")
        if not cand:
            return []
        cands = sorted(((s, a) for a, s in cand.items() if s >= 1), reverse=True)
        self.log(f"[扫描] items 候选 {len(cands)} 个, 最高匹配 {cands[0][0]}/{len(enemies)}")
        return [a for s, a in cands[:32]]

    def _find_list(self, items_cands, expect_cnt, snap=None):
        """第 4 遍: 单遍扫描同时找多个 items 候选的引用 -> List<Enemy> 候选。
        返回 (exact, near): exact=[(L, items), ...] 为 count==expect_cnt 的
        候选 (按 items 匹配分降序), near=[(L, items), ...] 为 count 合理但
        不等于 expect_cnt 的近似候选 (扫描发现的敌人数常因退场未回收/
        漏检/刷怪偏离真实列表长度)。哪个是真 m_managedWaveEnemies
        由第 5 遍 Scheduler 反查判定。"""
        narr = np.array(sorted(items_cands), dtype='<u8') if np is not None else None
        needle_map = {a: struct.pack('<Q', a) for a in items_cands}
        hits = []  # (items_addr, hit_pos)

        def on_chunk(base, d):
            if np is not None:
                q = np.frombuffer(d, dtype='<u8')
                for i in np.nonzero(np.isin(q, narr))[0]:
                    hits.append((int(q[int(i)]), base + int(i) * 8))
            else:
                for a, nd in needle_map.items():
                    pos = 0
                    while True:
                        i = d.find(nd, pos)
                        if i < 0:
                            break
                        hits.append((a, base + i))
                        pos = i + 8

        self._pass(snap, on_chunk, "List指针")
        self.log(f"[扫描] List 引用命中 {len(hits)} 处")
        exact, near = [], []
        seen = set()
        for items in items_cands:   # 已按匹配分降序
            for v, h in hits:
                if v != items:
                    continue
                L = h - gs.ListInternal.ITEMS
                if L in seen:
                    continue
                d = self.mc.read(L, 0x20)
                if not d or _u64(d, gs.ListInternal.ITEMS) != items:
                    continue
                cnt = _i32(d, gs.ListInternal.SIZE)
                if not (0 < cnt <= 300):
                    continue
                seen.add(L)
                if cnt == expect_cnt:
                    exact.append((L, items))
                else:
                    near.append((L, items))
        self.log(f"[扫描] List 候选 {len(exact)} 个 (+近似 {len(near)} 个)")
        return exact, near

    def _find_scheduler_bc(self, list_addrs, snap=None):
        """第 5 遍: 单遍扫描指向任一 List 候选的指针 -> Scheduler -> SchedulerDriver
        -> BattleController。返回 (list_addr, sched_addr, bc_addr);
        哪个候选被真 Scheduler 持有, 哪个才是真 m_managedWaveEnemies。
        全部未命中返回 (0, 0, 0)。"""
        narr = np.array(sorted(list_addrs), dtype='<u8') if np is not None else None
        needle_map = {a: struct.pack('<Q', a) for a in list_addrs}
        hits = []  # (list_addr, hit_pos)

        def on_chunk(base, d):
            if np is not None:
                q = np.frombuffer(d, dtype='<u8')
                for i in np.nonzero(np.isin(q, narr))[0]:
                    hits.append((int(q[int(i)]), base + int(i) * 8))
            else:
                for a, nd in needle_map.items():
                    pos = 0
                    while True:
                        i = d.find(nd, pos)
                        if i < 0:
                            break
                        hits.append((a, base + i))
                        pos = i + 8

        self._pass(snap, on_chunk, "Scheduler指针")
        self.log(f"[扫描] 命中 {len(hits)} 处")
        for L, h in hits:
            X = h - gs.SchedulerFields.M_MANAGED_WAVE_ENEMIES
            d = self.mc.read(X, 0x200)
            if not d:
                continue
            for off in range(0x10, 0x1F8, 8):
                v = _u64(d, off)
                if not self.mc.is_ptr(v):
                    continue
                if self.mc.read_klass_name(v) == 'SchedulerDriver':
                    bc = self.mc.read_ptr(v + gs.SchedulerDriverFields.BATTLE_CONTROLLER)
                    if bc and self.mc.read_klass_name(bc) == 'BattleController':
                        self.log(f"[扫描] List<Enemy> @ {hex(L)} (Scheduler 确认), "
                                 f"BattleController @ {hex(bc)}")
                        return L, X, bc
        return 0, 0, 0

    # ================= bootstrap =================

    def _validate_chain(self):
        """验证缓存的地址链是否仍然有效。
        注意: 只锚定 List 地址; items 数组会随列表扩容重新分配, 不作相等校验。"""
        try:
            d = self.mc.read(self.list_addr, 0x20)
            if not d:
                return False
            items, cnt = _u64(d, gs.ListInternal.ITEMS), _i32(d, gs.ListInternal.SIZE)
            if not (0 <= cnt <= 300) or (cnt > 0 and not self.mc.is_ptr(items)):
                return False
            if cnt > 0:
                arr = self.mc.read(items + gs.Il2CppArray.ITEMS, 8)
                if not arr:
                    return False
                e0 = _u64(arr, 0)
                if e0 and self.mc.read_klass_name(e0) != 'Enemy':
                    return False
            self.items_addr = items  # 刷新为当前 items 数组
            if self.with_bc and self.bc_addr:
                if self.mc.read_klass_name(self.bc_addr) != 'BattleController':
                    return False
            return True
        except Exception:
            return False

    def bootstrap(self, force=False):
        """发现地址链 (优先用缓存)"""
        if not force and os.path.isfile(self.cache_file):
            try:
                c = pickle.load(open(self.cache_file, 'rb'))
                if c.get('ver') == 2 and c.get('pid') == self.mc.pid:
                    self.enemy_addrs = c['enemies']
                    self.items_addr = c['items']
                    self.list_addr = c['list']
                    self.sched_addr = c.get('sched', 0)
                    self.bc_addr = c.get('bc', 0)
                    if self._validate_chain():
                        self.log(f"[缓存] 地址链有效 (敌人 {len(self.enemy_addrs)} 个, "
                                 f"List @ {hex(self.list_addr)})")
                        self._last_bootstrap = time.time()
                        self._prefill()
                        return True
            except Exception as e:
                self.log(f"[缓存] 无效: {e}")
            self.log("[缓存] 已失效, 重新扫描 ...")

        t0 = time.time()
        snap = None
        try:
            snap = _HeapSnapshot()   # 1 遍传输 + 4 遍本地复用; 失败回退 5 遍网络扫
        except OSError as e:
            self.log(f"[扫描] 快照不可用 ({e}), 回退多遍网络扫描")
        try:
            S, P = self._find_strings_and_hp(snap=snap)
            R = self._find_refs(S, snap=snap)
            self.enemy_addrs = self._filter_enemies(P, R)
            if not self.enemy_addrs:
                self.log("[扫描] 未发现敌人 (关卡未开始或已全部退场?)")
                return False
            items_cands = self._find_items_array(self.enemy_addrs, snap=snap)
            if not items_cands:
                self.log("[扫描] 未找到 items 数组")
                return False
            exact, near = self._find_list(items_cands, len(self.enemy_addrs), snap=snap)
            if not exact and not near:
                self.log("[扫描] 未找到 List<Enemy> (可在敌人刚出场满血时重扫)")
                return False
            self.sched_addr = self.bc_addr = 0
            self.list_addr = 0
            if self.with_bc:
                cands = [L for L, _ in exact] + [L for L, _ in near]
                L, self.sched_addr, self.bc_addr = self._find_scheduler_bc(cands, snap=snap)
                if L:
                    self.list_addr = L   # 被真 Scheduler 持有的才是活列表
                else:
                    self.log("[扫描] 未找到 BattleController (继续, 仅无战斗状态信息)")
            if not self.list_addr:
                self.list_addr = exact[0][0] if exact else near[0][0]
                self.log(f"[扫描] List<Enemy> @ {hex(self.list_addr)} (取首候选)")
            d = self.mc.read(self.list_addr, 0x20)
            self.items_addr = _u64(d, gs.ListInternal.ITEMS) if d else 0
        finally:
            if snap is not None:
                snap.discard()

        pickle.dump({'ver': 2, 'pid': self.mc.pid, 'enemies': self.enemy_addrs,
                     'items': self.items_addr, 'list': self.list_addr,
                     'sched': self.sched_addr, 'bc': self.bc_addr},
                    open(self.cache_file, 'wb'))
        self._last_bootstrap = time.time()
        self._prefill()
        self.log(f"[完成] 扫描耗时 {time.time()-t0:.0f} 秒, 已缓存")
        return True

    def _prefill(self):
        """预热名称/属性缓存, 让 poll_fast 首帧即全速"""
        for ep in self.enemy_addrs:
            full = self._read_enemy(ep, with_runtime=False)
            self._attr_snapshot[ep] = dict(full.attributes)

    # ================= 轮询 =================

    def _fill_attrs(self, ep, blk, info):
        """填充属性 (cachedData 数组地址有缓存, 失效时走完整链重解析)"""
        cd = None
        cdp = self._attr_cache.get(ep, 0)
        if cdp:
            cd = self.mc.read(cdp, 0x20 + gs.AttributeType.E_NUM * gs.OBSCURED_FP_SIZE)
            if not cd or not (0 < _i32(cd, gs.Il2CppArray.MAX_LENGTH) <= 64):
                self._attr_cache.pop(ep, None)
                cd = None
        if cd is None:
            attrp = _u64(blk, gs.EntityFields.M_ATTRIBUTES)
            ab = self.mc.read(attrp, 0x60) if self.mc.is_ptr(attrp) else None
            cdp2 = _u64(ab, gs.AttributesFields.M_CACHED_DATA) if ab else 0
            if cdp2 and self.mc.is_ptr(cdp2):
                cd2 = self.mc.read(
                    cdp2, 0x20 + gs.AttributeType.E_NUM * gs.OBSCURED_FP_SIZE)
                if cd2 and 0 < _i32(cd2, gs.Il2CppArray.MAX_LENGTH) <= 64:
                    self._attr_cache[ep] = cdp2
                    cd = cd2
        if cd:
            self._apply_cached_data(cd, info)
        return info

    @staticmethod
    def _apply_cached_data(cd, info):
        base = gs.Il2CppArray.ITEMS
        count = min(_i32(cd, gs.Il2CppArray.MAX_LENGTH), gs.AttributeType.E_NUM)
        attrs = {}
        for idx in range(max(0, count)):
            o = base + idx * gs.OBSCURED_FP_SIZE
            if o + 16 > len(cd):
                break
            attrs[idx] = gs.obscured_fp_to_float(_u64(cd, o), _u64(cd, o + 8))
        info.attributes = attrs
        info.max_hp = attrs.get(gs.AttributeType.MAX_HP, 0.0)
        info.atk = attrs.get(gs.AttributeType.ATK, 0.0)
        info.def_ = attrs.get(gs.AttributeType.DEF, 0.0)
        info.res = attrs.get(gs.AttributeType.MAGIC_RESISTANCE, 0.0)
        info.mspd = attrs.get(gs.AttributeType.MOVE_SPEED, 0.0)
        info.aspd = attrs.get(gs.AttributeType.ATTACK_SPEED, 0.0)

    @staticmethod
    def _apply_raw_data(raw, info):
        base = gs.Il2CppArray.ITEMS
        count = min(_i32(raw, gs.Il2CppArray.MAX_LENGTH), gs.AttributeType.E_NUM)
        values = {}
        for idx in range(max(0, count)):
            o = base + idx * gs.OBSCURED_FP_SIZE
            if o + 16 > len(raw):
                break
            values[idx] = gs.obscured_fp_to_float(_u64(raw, o), _u64(raw, o + 8))
        info.raw_attributes = values

    def _fill_skills(self, ep, blk, info):
        """慢速路径技能 CD 解析: m_skills List -> EnemySkill -> PeriodicTimer
        (period=总CD, remaining=剩余CD) + ESkillData.prefabKey (技能名缓存)"""
        out = []
        lp = _u64(blk, gs.EnemyFields.M_SKILLS) if len(blk) >= gs.EnemyFields.READ_SIZE else 0
        if self.mc.is_ptr(lp):
            self._skill_lp[ep] = lp
            hd = self.mc.read(lp, 0x20)
            items = _u64(hd, gs.ListInternal.ITEMS) if hd else 0
            n = _i32(hd, gs.ListInternal.SIZE) if hd else 0
            if 0 < n <= 8 and self.mc.is_ptr(items):
                arr = self.mc.read(items + gs.Il2CppArray.ITEMS, n * 8)
                for j in range(n if arr else 0):
                    s = _u64(arr, j * 8)
                    if not self.mc.is_ptr(s):
                        continue
                    sb = self.mc.read(s, 0x90)
                    if not sb:
                        continue
                    t = _u64(sb, gs.EnemySkillFields.M_COOLDOWN_TIMER)
                    td = self.mc.read(t, 0x20) if self.mc.is_ptr(t) else None
                    if not td:
                        continue
                    period = gs.fp_to_float(_u64(td, gs.PeriodicTimerFields.M_PERIOD_TIME))
                    remain = gs.fp_to_float(_u64(td, gs.PeriodicTimerFields.M_REMAINING_TIME))
                    if not (0 <= period <= 3600):
                        continue
                    key = self._skill_names.get(s)
                    if key is None:
                        dp = _u64(sb, gs.EnemySkillFields.DATA)
                        dd = self.mc.read(dp, 0x28) if self.mc.is_ptr(dp) else None
                        pk = _u64(dd, gs.ESkillDataFields.PREFAB_KEY) if dd else 0
                        key = (self.mc.read_ustring(pk) if self.mc.is_ptr(pk) else None) or '?'
                        self._skill_names[s] = key
                    out.append((key, remain, period))
        info.skills = out
        self._skill_cd[ep] = out
        return info

    def _fill_name(self, ep, blk, info):
        """填充名称 (只读一次, 之后走缓存)"""
        if ep not in self._names:
            eid = self.mc.read_ustring(_u64(blk, gs.EntityFields.ID)) or ''
            if self._db is None:
                self._db = load_enemy_db()
            ent = self._db.get(eid, {})
            self._names[ep] = (eid, ent.get('name') or eid, ent.get('code') or '')
        info.eid, info.name, info.code = self._names[ep]
        return info

    @staticmethod
    def _parse_enemy_block(ep, blk):
        """解析 Enemy 主对象块；不跟随指针，供慢速与聚簇快读共用。"""
        info = EnemyInfo(ep)
        if not blk or len(blk) < 0x148:
            info.alive = False
            return info
        info.hp = gs.fp_to_float(_u64(blk, gs.EntityFields.M_HP))
        info.es = gs.fp_to_float(_u64(blk, gs.EntityFields.M_ES))
        info.direction = _i32(blk, gs.EntityFields.M_DIRECTION)
        info.finish = _i32(blk, gs.EntityFields.FINISH_REASON)
        info.id_ptr = _u64(blk, gs.EntityFields.ID)
        info.attr_ptr = _u64(blk, gs.EntityFields.M_ATTRIBUTES)
        info.state_ptr = _u64(blk, gs.EntityFields.M_STATE_MACHINE)
        info.ep_ptr = _u64(blk, gs.EntityFields.M_EP_ARRAY)
        info.ep_controller_ptr = _u64(blk, gs.EntityFields.M_EP_CONTROLLER)
        info.shield_controller_ptr = _u64(blk, gs.EntityFields.M_SHIELD_CONTROLLER)
        info.buff_container_ptr = _u64(blk, gs.EntityFields.BUFF_CONTAINER)
        if len(blk) >= gs.EnemyFields.READ_SIZE:
            info.pos_x, info.pos_y = _f32x2(blk, gs.EnemyFields.M_POS_IN_LAST_FRAME)
            info.blk_x, info.blk_y = _f32x2(blk, gs.EnemyFields.M_BLOCK_POSITION)
            info.spawn_row = _i32(blk, gs.EnemyFields.ROUTE_SPAWN_POS)
            info.spawn_col = _i32(blk, gs.EnemyFields.ROUTE_SPAWN_POS + 4)
        info.alive = info.hp > 0 and info.finish == 0
        return info

    @staticmethod
    def _decode_short_array(data, limit):
        if not data or len(data) < gs.Il2CppArray.ITEMS:
            return [0] * limit
        count = min(max(0, _i32(data, gs.Il2CppArray.MAX_LENGTH)), limit)
        out = [0] * limit
        for idx in range(count):
            off = gs.Il2CppArray.ITEMS + idx * 2
            if off + 2 > len(data):
                break
            out[idx] = struct.unpack_from('<h', data, off)[0]
        return out

    @staticmethod
    def _decode_fp_array(data, limit):
        if not data or len(data) < gs.Il2CppArray.ITEMS:
            return {}
        count = min(max(0, _i32(data, gs.Il2CppArray.MAX_LENGTH)), limit)
        out = {}
        for idx in range(count):
            off = gs.Il2CppArray.ITEMS + idx * 8
            if off + 8 > len(data):
                break
            out[idx] = gs.fp_to_float(_u64(data, off))
        return out

    @staticmethod
    def _copy_runtime(info, runtime):
        if not runtime:
            return
        info.state_id = runtime.get('state_id', info.state_id)
        info.shield = runtime.get('shield', info.shield)
        info.ep_remaining = dict(runtime.get('ep_remaining', {}))
        info.ep_break_recovery = bool(runtime.get('ep_break_recovery', False))
        info.abnormal_flags = list(runtime.get('abnormal_flags', info.abnormal_flags))
        info.abnormal_immunes = list(runtime.get('abnormal_immunes', info.abnormal_immunes))
        info.abnormal_antis = list(runtime.get('abnormal_antis', info.abnormal_antis))
        info.abnormal_combos = list(runtime.get('abnormal_combos', info.abnormal_combos))
        info.abnormal_combo_immunes = list(
            runtime.get('abnormal_combo_immunes', info.abnormal_combo_immunes))

    def _fill_runtime_slow(self, info):
        """无 TCP 通道时的完整状态读取兜底。"""
        state = self.mc.read(info.state_ptr + gs.StateMachineFields.CURRENT_STATE_ID, 4) \
            if self.mc.is_ptr(info.state_ptr) else None
        ep = self.mc.read(
            info.ep_ptr, gs.Il2CppArray.ITEMS + gs.ElementType.E_NUM * 8) \
            if self.mc.is_ptr(info.ep_ptr) else None
        shield_ptr = info.shield_controller_ptr
        shield = self.mc.read(shield_ptr + gs.ShieldUIControllerFields.M_SHIELD_TO_SHOW, 8) \
            if self.mc.is_ptr(shield_ptr) else None
        epc = self.mc.read(info.ep_controller_ptr + gs.EPControllerFields.M_IS_IN_BREAK_RECOVERY, 1) \
            if self.mc.is_ptr(info.ep_controller_ptr) else None
        attr = self.mc.read(info.attr_ptr, 0x40) if self.mc.is_ptr(info.attr_ptr) else None
        ptrs = {}
        if attr:
            ptrs = {
                'flags': _u64(attr, gs.AttributesFields.M_ABNORMAL_FLAGS_COUNTER),
                'immunes': _u64(attr, gs.AttributesFields.M_ABNORMAL_IMMUNE_COUNTER),
                'antis': _u64(attr, gs.AttributesFields.M_ABNORMAL_ANTI_COUNTER),
            }
            combo_mgr = _u64(attr, gs.AttributesFields.M_ABNORMAL_COMBO_MGR)
            combo = self.mc.read(combo_mgr, 0x20) if self.mc.is_ptr(combo_mgr) else None
            if combo:
                ptrs['combos'] = _u64(combo, gs.AbnormalComboManagerFields.M_ABNORMAL_COMBO_COUNTER)
                ptrs['combo_immunes'] = _u64(
                    combo, gs.AbnormalComboManagerFields.M_ABNORMAL_COMBO_IMMUNE_COUNTER)
        arrays = {}
        sizes = {
            'flags': gs.AbnormalFlag.E_NUM, 'immunes': gs.AbnormalFlag.E_NUM,
            'antis': gs.AbnormalFlag.E_NUM, 'combos': gs.AbnormalCombo.E_NUM,
            'combo_immunes': gs.AbnormalCombo.E_NUM,
        }
        for key, count in sizes.items():
            p = ptrs.get(key, 0)
            arrays[key] = self._decode_short_array(
                self.mc.read(p, gs.Il2CppArray.ITEMS + count * 2)
                if self.mc.is_ptr(p) else None, count)
        runtime = {
            'state_id': _i32(state, 0) if state else gs.EnemyState.DEFAULT,
            'shield': gs.fp_to_float(_u64(shield, 0)) if shield else 0.0,
            'ep_remaining': self._decode_fp_array(ep, gs.ElementType.E_NUM),
            'ep_break_recovery': bool(epc and epc[0]),
            'abnormal_flags': arrays['flags'],
            'abnormal_immunes': arrays['immunes'],
            'abnormal_antis': arrays['antis'],
            'abnormal_combos': arrays['combos'],
            'abnormal_combo_immunes': arrays['combo_immunes'],
        }
        self._runtime_snapshot[info.addr] = runtime
        self._runtime_ptrs[info.addr] = dict(ptrs, state=info.state_ptr, ep=info.ep_ptr,
                                             epc=info.ep_controller_ptr, shield=shield_ptr)
        self._copy_runtime(info, runtime)

    def _read_enemy(self, ep, with_runtime=True):
        blk = self.mc.read(ep, gs.EnemyFields.READ_SIZE)
        info = self._parse_enemy_block(ep, blk)
        if not blk or len(blk) < 0x148:
            return info
        self._fill_name(ep, blk, info)
        self._fill_attrs(ep, blk, info)
        self._fill_skills(ep, blk, info)
        if with_runtime:
            self._fill_runtime_slow(info)
        return info

    def poll(self):
        """读取一帧快照; 返回 dict"""
        snap = {'ok': False, 'state': -1, 'speed_level': -1, 'time_scale': 0.0,
                'play_time': 0.0, 'enemies': [], 'msg': ''}
        d = self.mc.read(self.list_addr, 0x20)
        if not d:
            snap['msg'] = 'List 读取失败'
            return self._on_stale(snap)
        items, cnt = _u64(d, gs.ListInternal.ITEMS), _i32(d, gs.ListInternal.SIZE)
        if not (0 <= cnt <= 300) or (cnt > 0 and not self.mc.is_ptr(items)):
            snap['msg'] = f'List 数据异常 (cnt={cnt})'
            return self._on_stale(snap)

        if cnt > 0:
            arr = self.mc.read(items + gs.Il2CppArray.ITEMS, cnt * 8)
            if not arr:
                snap['msg'] = 'items 读取失败'
                return self._on_stale(snap)
            for i in range(cnt):
                ep = _u64(arr, i * 8)
                if not ep or not self.mc.is_ptr(ep):
                    continue
                # 回退路径避免为每个敌人逐指针启动十余次 adb 子进程；沿用最近一次
                # 快速通道的状态快照。详情按钮仍会按需做完整读取。
                info = self._read_enemy(ep, with_runtime=False)
                self._copy_runtime(info, self._runtime_snapshot.get(ep))
                snap['enemies'].append(info)

        if self.bc_addr:
            b = self.mc.read(self.bc_addr + 0x200, 0xC0)
            if b:
                snap['state'] = _i32(b, gs.BattleControllerFields.M_STATE - 0x200)
                snap['speed_level'] = _i32(b, gs.BattleControllerFields.M_SPEED_LEVEL - 0x200)
                snap['time_scale'] = struct.unpack_from(
                    '<f', b, gs.BattleControllerFields.M_TIME_SCALE - 0x200)[0]
                snap['play_time'] = struct.unpack_from(
                    '<f', b, gs.BattleControllerFields.M_REAL_PLAY_TIME - 0x200)[0]

        snap['ok'] = True
        self._stale_cnt = 0
        return snap

    def close(self):
        """关闭常驻 TCP 通道"""
        if self._chan is not None:
            try:
                self._chan.close()
            except Exception:
                pass
            self._chan = None

    CHAN_RETRY_SEC = 5.0   # 通道失败后的重建冷却 (open 含 adb 部署, 每帧重试太贵)

    def poll_fast(self):
        """准实时轮询 (稳态 ~15-25ms/帧): 常驻 TCP 通道 (设备侧 nc -L sh +
        adb forward, raw 二进制)。稳态每帧仅 1 次敌人簇 dd; List 头每 4
        帧/属性轮换每 3 帧/BC 每 10 帧搭车同批。通道异常 -> 回退慢速 poll()。"""
        if self._chan is None:
            if time.time() - self._chan_dead_ts < self.CHAN_RETRY_SEC:
                return self.poll()   # 冷却期内直接慢速, 避免每帧昂贵重连
            self._chan = TcpChannel(self.mc)
        try:
            snap = self._poll_fast_impl()
            self._chan_fail = 0
            return snap
        except Exception as e:
            self._chan_fail += 1
            if self._chan_fail <= 3 or self._chan_fail % 50 == 0:
                self.log(f'[轮询] 通道异常 ({type(e).__name__}: {e}), 本帧回退慢速读')
            self.close()
            self._chan_dead_ts = time.time()
            return self.poll()

    @staticmethod
    def _cluster_ptrs(ptrs, gap=0x10000):
        """敌人指针按地址聚簇 (每簇一次 dd)"""
        if not ptrs:
            return []
        sp = sorted(ptrs)
        clusters = [[sp[0]]]
        for p in sp[1:]:
            if p - clusters[-1][-1] <= gap:
                clusters[-1].append(p)
            else:
                clusters.append([p])
        return clusters

    def _refresh_runtime_chan(self, eps, infos):
        """批量刷新状态机、损伤条、异常状态/免疫计数和护盾。

        Attributes 里的五个计数数组需要一次跟随指针。指针只在对象换代时重建，
        稳态刷新全部敌人仍然只有一次 batch_read 往返。
        """
        if not eps:
            return

        # 主对象中可直接得到的指针每轮同步；Attributes 换对象时丢弃旧计数数组。
        missing = []
        for ep in eps:
            info = infos.get(ep)
            if info is None:
                continue
            rp = self._runtime_ptrs.setdefault(ep, {})
            if rp.get('attr_obj') != info.attr_ptr:
                for key in ('flags', 'immunes', 'antis', 'combos', 'combo_immunes'):
                    rp.pop(key, None)
                rp['attr_obj'] = info.attr_ptr
            rp.update(state=info.state_ptr, ep=info.ep_ptr, epc=info.ep_controller_ptr,
                      shield=info.shield_controller_ptr)
            if not all(rp.get(k) for k in ('flags', 'immunes', 'antis',
                                            'combos', 'combo_immunes')):
                missing.append(ep)

        # 第一次：Attributes -> 三个 flag 数组 + combo manager。
        attr_eps = [ep for ep in missing
                    if self.mc.is_ptr(self._runtime_ptrs[ep].get('attr_obj', 0))]
        if attr_eps:
            reqs = [(self._runtime_ptrs[ep]['attr_obj'], 0x40) for ep in attr_eps]
            combo_mgrs = {}
            for ep, data in zip(attr_eps, self._chan.batch_read(reqs)):
                if not data:
                    continue
                rp = self._runtime_ptrs[ep]
                rp['flags'] = _u64(data, gs.AttributesFields.M_ABNORMAL_FLAGS_COUNTER)
                rp['immunes'] = _u64(data, gs.AttributesFields.M_ABNORMAL_IMMUNE_COUNTER)
                rp['antis'] = _u64(data, gs.AttributesFields.M_ABNORMAL_ANTI_COUNTER)
                combo = _u64(data, gs.AttributesFields.M_ABNORMAL_COMBO_MGR)
                if self.mc.is_ptr(combo):
                    combo_mgrs[ep] = combo
            if combo_mgrs:
                ceps = list(combo_mgrs)
                for ep, data in zip(
                        ceps, self._chan.batch_read([(combo_mgrs[x], 0x20) for x in ceps])):
                    if data:
                        self._runtime_ptrs[ep]['combos'] = _u64(
                            data, gs.AbnormalComboManagerFields.M_ABNORMAL_COMBO_COUNTER)
                        self._runtime_ptrs[ep]['combo_immunes'] = _u64(
                            data, gs.AbnormalComboManagerFields.M_ABNORMAL_COMBO_IMMUNE_COUNTER)

        reqs, keys = [], []
        for ep in eps:
            rp = self._runtime_ptrs.get(ep, {})
            specs = (
                ('state', rp.get('state', 0) + gs.StateMachineFields.CURRENT_STATE_ID, 4),
                ('ep', rp.get('ep', 0), gs.Il2CppArray.ITEMS + gs.ElementType.E_NUM * 8),
                ('shield', rp.get('shield', 0) + gs.ShieldUIControllerFields.M_SHIELD_TO_SHOW, 8),
                ('epc', rp.get('epc', 0) + gs.EPControllerFields.M_IS_IN_BREAK_RECOVERY, 1),
                ('flags', rp.get('flags', 0),
                 gs.Il2CppArray.ITEMS + gs.AbnormalFlag.E_NUM * 2),
                ('immunes', rp.get('immunes', 0),
                 gs.Il2CppArray.ITEMS + gs.AbnormalFlag.E_NUM * 2),
                ('antis', rp.get('antis', 0),
                 gs.Il2CppArray.ITEMS + gs.AbnormalFlag.E_NUM * 2),
                ('combos', rp.get('combos', 0),
                 gs.Il2CppArray.ITEMS + gs.AbnormalCombo.E_NUM * 2),
                ('combo_immunes', rp.get('combo_immunes', 0),
                 gs.Il2CppArray.ITEMS + gs.AbnormalCombo.E_NUM * 2),
            )
            for kind, addr, size in specs:
                if self.mc.is_ptr(addr):
                    reqs.append((addr, size))
                    keys.append((ep, kind))

        runtime = {ep: dict(self._runtime_snapshot.get(ep, {})) for ep in eps}
        for (ep, kind), data in zip(keys, self._chan.batch_read(reqs) if reqs else []):
            if not data:
                continue
            cur = runtime[ep]
            if kind == 'state':
                cur['state_id'] = _i32(data, 0)
            elif kind == 'ep':
                cur['ep_remaining'] = self._decode_fp_array(data, gs.ElementType.E_NUM)
            elif kind == 'shield':
                cur['shield'] = gs.fp_to_float(_u64(data, 0))
            elif kind == 'epc':
                cur['ep_break_recovery'] = bool(data[0])
            elif kind in ('flags', 'immunes', 'antis'):
                cur['abnormal_' + kind] = self._decode_short_array(data, gs.AbnormalFlag.E_NUM)
            elif kind == 'combos':
                cur['abnormal_combos'] = self._decode_short_array(data, gs.AbnormalCombo.E_NUM)
            elif kind == 'combo_immunes':
                cur['abnormal_combo_immunes'] = self._decode_short_array(
                    data, gs.AbnormalCombo.E_NUM)

        for ep in eps:
            self._runtime_snapshot[ep] = runtime[ep]
            info = infos.get(ep)
            if info is not None:
                self._copy_runtime(info, runtime[ep])

    LIST_EVERY = 4    # List 头每 4 tick 读一次 (检测刷怪/退场; 其余帧沿用上一帧指针)
    ATTR_EVERY = 3    # 每 3 tick 轮换刷新 1 个敌人的属性 (摊平尖峰)
    BC_EVERY = 10     # BC 块 (状态/倍速/时间) 每 10 tick 读一次
    SKILL_EVERY = 5   # 每 5 tick 通道内批量刷新全部敌人技能 CD
    STATUS_EVERY = 2  # 状态/损伤条每 2 tick 批量刷新 (约 20-32ms)

    def _poll_fast_impl(self):
        t0 = time.time()
        snap = {'ok': False, 'state': -1, 'speed_level': -1, 'time_scale': 0.0,
                'play_time': 0.0, 'enemies': [], 'msg': '', 'frame_ms': 0.0}
        self._fast_tick += 1
        tick = self._fast_tick
        prev_ptrs = self._f_ptrs
        read_list = (tick % self.LIST_EVERY == 1) or not prev_ptrs

        # ---- 组装本帧唯一一批请求 (稳态 = 1 簇 dd; 辅助读取降频搭车) ----
        reqs, slot = [], {}
        if read_list:
            slot['list'] = len(reqs)
            reqs.append((self.list_addr, 0x20))
        clusters = self._cluster_ptrs(prev_ptrs)
        slot['c0'] = len(reqs)
        reqs += [(c[0], c[-1] + gs.EnemyFields.READ_SIZE - c[0]) for c in clusters]
        if prev_ptrs and tick % self.ATTR_EVERY == 0:
            aep = prev_ptrs[(tick // self.ATTR_EVERY) % len(prev_ptrs)]
            cdp = self._attr_cache.get(aep, 0)
            if cdp:
                slot['attr'] = (len(reqs), aep)
                reqs.append((cdp, 0x20 + gs.AttributeType.E_NUM * gs.OBSCURED_FP_SIZE))
            else:
                ap = self._attr_ptrs.get(aep, 0)
                if ap:
                    slot['attrp'] = (len(reqs), aep)
                    reqs.append((ap, 0x60))
        if self.bc_addr and tick % self.BC_EVERY == 0:
            slot['bc'] = len(reqs)
            reqs.append((self.bc_addr + 0x200, 0xC0))
        res = self._chan.batch_read(reqs) if reqs else []

        # ---- List 头 (仅降频帧): _version 捕捉一切列表修改 ----
        ptrs = prev_ptrs
        if read_list:
            d = res[slot['list']]
            if not d:
                snap['msg'] = 'List 读取失败'
                return self._on_stale(snap)
            items = _u64(d, gs.ListInternal.ITEMS)
            cnt = _i32(d, gs.ListInternal.SIZE)
            version = _i32(d, gs.ListInternal.VERSION)
            if not (0 <= cnt <= 300) or (cnt > 0 and not self.mc.is_ptr(items)):
                snap['msg'] = f'List 数据异常 (cnt={cnt})'
                return self._on_stale(snap)
            changed = (items != self._f_items or cnt != self._f_cnt
                       or version != self._f_version)
            if changed:
                if cnt > 0:
                    (arr,) = self._chan.batch_read([(items + gs.Il2CppArray.ITEMS, cnt * 8)])
                    if not arr:
                        snap['msg'] = 'items 读取失败'
                        return self._on_stale(snap)
                    ptrs = [p for p in (_u64(arr, i * 8) for i in range(cnt))
                            if p and self.mc.is_ptr(p)]
                else:
                    ptrs = []
                if ptrs != prev_ptrs:
                    clusters = self._cluster_ptrs(ptrs)
                    cluster_res = self._chan.batch_read(
                        [(c[0], c[-1] + gs.EnemyFields.READ_SIZE - c[0])
                         for c in clusters]) if clusters else []
                else:
                    cluster_res = None
            else:
                cluster_res = None
            self._f_items, self._f_cnt, self._f_ptrs, self._f_version = \
                items, cnt, ptrs, version
        else:
            cluster_res = None
        if cluster_res is None:
            cluster_res = res[slot['c0']:slot['c0'] + len(clusters)]

        # ---- 解析敌人块 (hp/direction/finish + id/attr 指针 + 坐标) ----
        infos = {}
        for c, data in zip(clusters, cluster_res):
            if not data:
                continue
            for ep in c:
                off = ep - c[0]
                if off + gs.EnemyFields.READ_SIZE > len(data):
                    continue
                blk = data[off:off + gs.EnemyFields.READ_SIZE]
                info = self._parse_enemy_block(ep, blk)
                infos[ep] = info
                self._attr_ptrs[ep] = info.attr_ptr
                skl = _u64(data, off + gs.EnemyFields.M_SKILLS)
                if self.mc.is_ptr(skl):
                    self._skill_lp[ep] = skl

        # ---- 新敌人: 通道内解析名称+属性 (仅列表变化帧触发) ----
        new_eps = [ep for ep in ptrs if ep not in self._names or ep not in self._attr_snapshot]
        if new_eps:
            self._fill_new_enemies_chan(new_eps, infos)

        # ---- 状态机 / 异常状态 / 免疫 / 五种损伤条 ----
        runtime_missing = any(ep not in self._runtime_snapshot for ep in ptrs)
        if ptrs and (runtime_missing or tick % self.STATUS_EVERY == 0):
            self._refresh_runtime_chan(ptrs, infos)

        # ---- 属性轮换刷新 (每 ATTR_EVERY 帧 1 个敌人) ----
        if 'attr' in slot:
            i, aep = slot['attr']
            cd = res[i]
            if cd and 0 < _i32(cd, gs.Il2CppArray.MAX_LENGTH) <= 64:
                tmp = EnemyInfo(aep)
                self._apply_cached_data(cd, tmp)
                self._attr_snapshot[aep] = dict(tmp.attributes)
            else:
                self._attr_cache.pop(aep, None)   # 数组已失效, 下轮重建
        elif 'attrp' in slot:
            i, aep = slot['attrp']
            d = res[i]
            cdp = _u64(d, gs.AttributesFields.M_CACHED_DATA) if d else 0
            if cdp and self.mc.is_ptr(cdp):
                self._attr_cache[aep] = cdp

        # ---- 技能 CD 批量刷新 (每 SKILL_EVERY 帧一轮) ----
        if ptrs and tick % self.SKILL_EVERY == 0:
            self._refresh_skills_chan(ptrs)

        live = set(ptrs)
        enemies = []
        for ep in ptrs:
            info = infos.get(ep)
            if info is None:
                continue
            nm = self._names.get(ep)
            if nm:
                info.eid, info.name, info.code = nm
            s = self._attr_snapshot.get(ep)
            if s:
                info.attributes = dict(s)
                info.max_hp = s.get(gs.AttributeType.MAX_HP, 0.0)
                info.atk = s.get(gs.AttributeType.ATK, 0.0)
                info.def_ = s.get(gs.AttributeType.DEF, 0.0)
                info.res = s.get(gs.AttributeType.MAGIC_RESISTANCE, 0.0)
                info.mspd = s.get(gs.AttributeType.MOVE_SPEED, 0.0)
                info.aspd = s.get(gs.AttributeType.ATTACK_SPEED, 0.0)
            self._copy_runtime(info, self._runtime_snapshot.get(ep))
            info.skills = self._skill_cd.get(ep, [])
            enemies.append(info)
        # 清理已退场敌人的缓存 (地址可能被 GC 复用)
        for cache in (self._names, self._attr_cache, self._attr_snapshot, self._attr_ptrs,
                      self._runtime_snapshot, self._runtime_ptrs,
                      self._skill_lp, self._skill_cd):
            for ep in list(cache):
                if ep not in live:
                    cache.pop(ep, None)
        snap['enemies'] = enemies

        # ---- BC 块 ----
        if 'bc' in slot:
            b = res[slot['bc']]
            if b:
                self._bc_snap = (
                    _i32(b, gs.BattleControllerFields.M_STATE - 0x200),
                    _i32(b, gs.BattleControllerFields.M_SPEED_LEVEL - 0x200),
                    struct.unpack_from('<f', b, gs.BattleControllerFields.M_TIME_SCALE - 0x200)[0],
                    struct.unpack_from('<f', b, gs.BattleControllerFields.M_REAL_PLAY_TIME - 0x200)[0])
        if self._bc_snap:
            (snap['state'], snap['speed_level'],
             snap['time_scale'], snap['play_time']) = self._bc_snap

        snap['ok'] = True
        snap['frame_ms'] = round((time.time() - t0) * 1000, 1)
        self._stale_cnt = 0
        return snap

    def _refresh_skills_chan(self, ptrs):
        """通道内批量刷新全部敌人技能 CD: 列表头 -> items -> EnemySkill 块 ->
        PeriodicTimer 共 4 轮 batch; 技能静态名 (ESkillData.prefabKey) 仅首见时
        再读 2 轮, 之后走 _skill_names 缓存"""
        eps = [ep for ep in ptrs if self.mc.is_ptr(self._skill_lp.get(ep, 0))]
        if not eps:
            return
        heads = self._chan.batch_read([(self._skill_lp[ep], 0x20) for ep in eps])
        n_of, reqs, keys = {}, [], []
        for ep, d in zip(eps, heads):
            if not d:
                continue                          # 读失败保留旧快照
            items, n = _u64(d, gs.ListInternal.ITEMS), _i32(d, gs.ListInternal.SIZE)
            if n == 0:
                self._skill_cd[ep] = []
            elif 0 < n <= 8 and self.mc.is_ptr(items):
                n_of[ep] = n
                reqs.append((items + gs.Il2CppArray.ITEMS, n * 8))
                keys.append(ep)
        sks_of, reqs2, keys2 = {}, [], []
        if reqs:
            for ep, d in zip(keys, self._chan.batch_read(reqs)):
                if not d:
                    continue
                sks = [s for s in (_u64(d, j * 8) for j in range(n_of[ep]))
                       if self.mc.is_ptr(s)]
                sks_of[ep] = sks
                for s in sks:
                    reqs2.append((s, 0x90))
                    keys2.append((ep, s))
        timers, datas = {}, {}
        if reqs2:
            for (ep, s), d in zip(keys2, self._chan.batch_read(reqs2)):
                if not d:
                    continue
                t = _u64(d, gs.EnemySkillFields.M_COOLDOWN_TIMER)
                dp = _u64(d, gs.EnemySkillFields.DATA)
                if self.mc.is_ptr(t):
                    timers[s] = t
                if s not in self._skill_names and self.mc.is_ptr(dp):
                    datas[s] = dp
        remain_of = {}
        if timers:
            sks = list(timers)
            for s, d in zip(sks, self._chan.batch_read([(timers[s], 0x20) for s in sks])):
                if not d:
                    continue
                period = gs.fp_to_float(_u64(d, gs.PeriodicTimerFields.M_PERIOD_TIME))
                remain = gs.fp_to_float(_u64(d, gs.PeriodicTimerFields.M_REMAINING_TIME))
                if 0 <= period <= 3600 and -1 <= remain <= 3600:
                    remain_of[s] = (remain, period)
        if datas:   # 首见技能: data 块 -> prefabKey 字符串
            pks = {}
            sks = list(datas)
            for s, d in zip(sks, self._chan.batch_read([(datas[s], 0x28) for s in sks])):
                if d:
                    pk = _u64(d, gs.ESkillDataFields.PREFAB_KEY)
                    if self.mc.is_ptr(pk):
                        pks[s] = pk
            if pks:
                sks = list(pks)
                for s, d in zip(sks, self._chan.batch_read([(pks[s], 0x80) for s in sks])):
                    if d and 0 < _i32(d, gs.Il2CppString.LENGTH) <= 64:
                        ln = _i32(d, gs.Il2CppString.LENGTH)
                        try:
                            self._skill_names[s] = d[gs.Il2CppString.CHARS:
                                                     gs.Il2CppString.CHARS + ln * 2
                                                     ].decode('utf-16-le') or '?'
                        except Exception:
                            pass
        for ep, sks in sks_of.items():
            self._skill_cd[ep] = [(self._skill_names.get(s, '?'), r, p)
                                  for s in sks if s in remain_of
                                  for r, p in (remain_of[s],)]
        # 技能对象随敌人退场释放, 修剪名称缓存防地址复用串名
        live_sks = {s for sks in sks_of.values() for s in sks}
        for s in list(self._skill_names):
            if s not in live_sks:
                self._skill_names.pop(s, None)

    def _fill_new_enemies_chan(self, new_eps, infos):
        """新敌人通道内解析: 第 1 批 id 字符串+Attributes 块, 第 2 批 cachedData"""
        if self._db is None:
            self._db = load_enemy_db()
        reqs, keys = [], []
        for ep in new_eps:
            info = infos.get(ep)
            if info is None:
                continue
            if info.id_ptr and self.mc.is_ptr(info.id_ptr):
                reqs.append((info.id_ptr, 0x80))
                keys.append(('id', ep))
            if info.attr_ptr and self.mc.is_ptr(info.attr_ptr):
                reqs.append((info.attr_ptr, 0x60))
                keys.append(('attr', ep))
        cdps = {}
        if reqs:
            for (kind, ep), d in zip(keys, self._chan.batch_read(reqs)):
                if kind == 'id':
                    eid = ''
                    if d and 0 < _i32(d, gs.Il2CppString.LENGTH) <= 128:
                        ln = _i32(d, gs.Il2CppString.LENGTH)
                        try:
                            eid = d[gs.Il2CppString.CHARS:
                                    gs.Il2CppString.CHARS + ln * 2].decode('utf-16-le')
                        except Exception:
                            eid = ''
                    ent = self._db.get(eid, {})
                    self._names[ep] = (eid, ent.get('name') or eid, ent.get('code') or '')
                else:
                    cdp = _u64(d, gs.AttributesFields.M_CACHED_DATA) if d else 0
                    if cdp and self.mc.is_ptr(cdp):
                        cdps[ep] = cdp
        if cdps:
            eps = list(cdps)
            reqs = [(cdps[ep], 0x20 + gs.AttributeType.E_NUM * gs.OBSCURED_FP_SIZE)
                    for ep in eps]
            for ep, cd in zip(eps, self._chan.batch_read(reqs)):
                if cd and 0 < _i32(cd, gs.Il2CppArray.MAX_LENGTH) <= 64:
                    self._attr_cache[ep] = cdps[ep]
                    tmp = EnemyInfo(ep)
                    self._apply_cached_data(cd, tmp)
                    self._attr_snapshot[ep] = dict(tmp.attributes)
        # 通道内未解决的走一次完整慢读兜底
        for ep in new_eps:
            if ep not in self._names or ep not in self._attr_snapshot:
                full = self._read_enemy(ep, with_runtime=False)
                if ep not in self._names:
                    self._names[ep] = (full.eid, full.name, full.code)
                if ep not in self._attr_snapshot:
                    self._attr_snapshot[ep] = dict(full.attributes)
                if ep not in infos:
                    infos[ep] = full

    def _detail_batch_read(self, reqs):
        """详情读取与高频轮询共用同一带锁通道；无通道时回退 MemCore。"""
        if not reqs:
            return []
        if self._chan is not None:
            return self._chan.batch_read(reqs)
        return [self.mc.read(addr, size) for addr, size in reqs]

    def _read_strings(self, ptrs, max_chars=256):
        unique = [p for p in dict.fromkeys(ptrs) if self.mc.is_ptr(p)]
        if not unique:
            return {}
        size = gs.Il2CppString.CHARS + max_chars * 2
        out = {}
        for ptr, data in zip(unique, self._detail_batch_read([(p, size) for p in unique])):
            if not data or len(data) < gs.Il2CppString.CHARS:
                continue
            count = _i32(data, gs.Il2CppString.LENGTH)
            if not (0 <= count <= max_chars):
                continue
            try:
                out[ptr] = data[gs.Il2CppString.CHARS:
                                gs.Il2CppString.CHARS + count * 2].decode('utf-16-le')
            except UnicodeDecodeError:
                continue
        return out

    def _read_blackboards(self, bb_ptrs):
        """读取 Blackboard(List<DataPair>)；DataPair 步长为 0x18。"""
        unique = [p for p in dict.fromkeys(bb_ptrs) if self.mc.is_ptr(p)]
        result = {p: [] for p in unique}
        if not unique:
            return result
        heads = self._detail_batch_read([(p, 0x20) for p in unique])
        arrays = {}
        reqs, owners = [], []
        for ptr, head in zip(unique, heads):
            if not head:
                continue
            items, count = _u64(head, gs.ListInternal.ITEMS), _i32(head, gs.ListInternal.SIZE)
            if 0 < count <= 256 and self.mc.is_ptr(items):
                reqs.append((items + gs.Il2CppArray.ITEMS, count * 0x18))
                owners.append((ptr, count))
        for (ptr, count), data in zip(owners, self._detail_batch_read(reqs)):
            if data:
                arrays[ptr] = (count, data)
        string_ptrs = []
        parsed = {}
        for ptr, (count, data) in arrays.items():
            rows = []
            for idx in range(count):
                off = idx * 0x18
                if off + 0x18 > len(data):
                    break
                key_ptr = _u64(data, off)
                value = struct.unpack_from('<f', data, off + 8)[0]
                value_str_ptr = _u64(data, off + 0x10)
                string_ptrs.extend((key_ptr, value_str_ptr))
                rows.append((key_ptr, value, value_str_ptr))
            parsed[ptr] = rows
        strings = self._read_strings(string_ptrs)
        for ptr, rows in parsed.items():
            result[ptr] = [
                {'key': strings.get(kp, ''), 'value': value,
                 'value_str': strings.get(sp, '') if sp else ''}
                for kp, value, sp in rows
            ]
        return result

    @staticmethod
    def _mask_names(mask, names):
        return [names.get(idx, str(idx)) for idx in range(64) if mask & (1 << idx)]

    def _read_plain_fp_arrays(self, ptrs):
        unique = [p for p in dict.fromkeys(ptrs) if self.mc.is_ptr(p)]
        if not unique:
            return {}
        size = gs.Il2CppArray.ITEMS + gs.AttributeType.E_NUM * 8
        return {ptr: self._decode_fp_array(data, gs.AttributeType.E_NUM)
                for ptr, data in zip(unique, self._detail_batch_read([(p, size) for p in unique]))
                if data}

    def _read_active_buffs(self, container_ptr):
        """读取敌人 BuffContainer 中当前有效的 Buff。"""
        if not self.mc.is_ptr(container_ptr):
            return []
        (container,) = self._detail_batch_read([(container_ptr, 0x30)])
        dbl_ptr = _u64(container, gs.BuffContainerFields.M_BUFFS) if container else 0
        if not self.mc.is_ptr(dbl_ptr):
            return []
        (dbl,) = self._detail_batch_read([(dbl_ptr, 0x28)])
        list_ptr = _u64(dbl, gs.DoubleBufferedListFields.M_INTERNAL_LIST) if dbl else 0
        if not self.mc.is_ptr(list_ptr):
            return []
        (head,) = self._detail_batch_read([(list_ptr, 0x20)])
        if not head:
            return []
        items, count = _u64(head, gs.ListInternal.ITEMS), _i32(head, gs.ListInternal.SIZE)
        if not (0 < count <= 512 and self.mc.is_ptr(items)):
            return []
        (array,) = self._detail_batch_read(
            [(items + gs.Il2CppArray.ITEMS, count * 0x10)])
        if not array:
            return []
        ptrs = [_u64(array, idx * 0x10) for idx in range(count)
                if idx * 0x10 + 8 <= len(array)]
        ptrs = [p for p in ptrs if self.mc.is_ptr(p)]
        blocks = self._detail_batch_read([(p, gs.BuffFields.READ_SIZE) for p in ptrs])
        records = [(p, data) for p, data in zip(ptrs, blocks) if data]
        if not records:
            return []

        string_ptrs, bb_ptrs, fp_ptrs = [], [], []
        for _, data in records:
            string_ptrs.extend((_u64(data, gs.BuffFields.KEY),
                                _u64(data, gs.BuffFields.OVERRIDE_KEY),
                                _u64(data, gs.BuffFields.EFFECT_KEY)))
            bb_ptrs.append(_u64(data, gs.BuffFields.M_BLACKBOARD))
            fp_ptrs.extend(_u64(data, off) for off in (
                gs.BuffFields.M_ATTRIBUTE_MULTIPLIERS,
                gs.BuffFields.M_ATTRIBUTE_ADDITIONS,
                gs.BuffFields.M_ATTRIBUTE_FINAL_ADDITIONS,
                gs.BuffFields.M_ATTRIBUTE_FINAL_SCALERS))
        strings = self._read_strings(string_ptrs)
        blackboards = self._read_blackboards(bb_ptrs)
        fp_arrays = self._read_plain_fp_arrays(fp_ptrs)

        out = []
        for ptr, data in records:
            mask = _u64(data, gs.BuffFields.ATTRIBUTE_MASK)
            mul_ptr = _u64(data, gs.BuffFields.M_ATTRIBUTE_MULTIPLIERS)
            add_ptr = _u64(data, gs.BuffFields.M_ATTRIBUTE_ADDITIONS)
            fadd_ptr = _u64(data, gs.BuffFields.M_ATTRIBUTE_FINAL_ADDITIONS)
            scale_ptr = _u64(data, gs.BuffFields.M_ATTRIBUTE_FINAL_SCALERS)
            mul = fp_arrays.get(mul_ptr, {})
            add = fp_arrays.get(add_ptr, {})
            fadd = fp_arrays.get(fadd_ptr, {})
            scale = fp_arrays.get(scale_ptr, {})
            modifiers = []
            for idx in range(gs.AttributeType.E_NUM):
                if not (mask & (1 << idx)):
                    continue
                modifiers.append({
                    'index': idx,
                    'key': gs.ATTRIBUTE_INTERNAL_NAMES.get(idx, str(idx)),
                    'name': gs.ATTRIBUTE_CN_NAMES.get(idx, str(idx)),
                    'addition': add.get(idx, 0.0),
                    'multiplier': mul.get(idx, 0.0),
                    'final_addition': fadd.get(idx, 0.0),
                    'final_scaler': scale.get(idx, 1.0),
                })
            source = _u64(data, gs.BuffFields.M_SOURCE)
            source_name = ''
            if source in self._names:
                source_name = self._names[source][1]
            key_ptr = _u64(data, gs.BuffFields.KEY)
            override_ptr = _u64(data, gs.BuffFields.OVERRIDE_KEY)
            effect_ptr = _u64(data, gs.BuffFields.EFFECT_KEY)
            bb_ptr = _u64(data, gs.BuffFields.M_BLACKBOARD)
            out.append({
                'addr': ptr,
                'key': strings.get(key_ptr, '') or '?',
                'override_key': strings.get(override_ptr, ''),
                'effect_key': strings.get(effect_ptr, ''),
                'instance_uid': struct.unpack_from('<I', data, gs.BuffFields.INSTANCE_UID)[0],
                'priority': _i32(data, gs.BuffFields.PRIORITY),
                'life_time': gs.fp_to_float(_u64(data, gs.BuffFields.M_LIFE_TIME)),
                'remaining_time': gs.fp_to_float(_u64(data, gs.BuffFields.M_REMAINING_TIME)),
                'existing_time': gs.fp_to_float(_u64(data, gs.BuffFields.M_EXISTING_TIME)),
                'trigger_count': _i32(data, gs.BuffFields.M_TRIGGER_CNT),
                'stack_count': _i32(data, gs.BuffFields.M_STACK_CNT),
                'max_valid_stack_count': _i32(data, gs.BuffFields.M_MAX_VALID_STACK_CNT),
                'enabled': bool(data[gs.BuffFields.IS_ACTUALLY_ENABLED]),
                'valid': bool(data[gs.BuffFields.IS_VALID]),
                'finished': bool(data[gs.BuffFields.IS_FINISHED]),
                'ep_break_buff': bool(data[gs.BuffFields.IS_EP_BREAK_BUFF]),
                'source_addr': source,
                'source': source_name or (hex(source) if source else '关卡/无实体来源'),
                'ability_addr': _u64(data, gs.BuffFields.M_ABILITY),
                'attribute_modifiers': modifiers,
                'abnormal_flags': self._mask_names(
                    _u64(data, gs.BuffFields.ABNORMAL_FLAG_MASK),
                    gs.ABNORMAL_FLAG_CN_NAMES),
                'abnormal_immunes': self._mask_names(
                    _u64(data, gs.BuffFields.ABNORMAL_IMMUNE_MASK),
                    gs.ABNORMAL_FLAG_CN_NAMES),
                'abnormal_antis': self._mask_names(
                    _u64(data, gs.BuffFields.ABNORMAL_ANTI_MASK),
                    gs.ABNORMAL_FLAG_CN_NAMES),
                'abnormal_combos': self._mask_names(
                    _u64(data, gs.BuffFields.ABNORMAL_COMBO_MASK),
                    gs.ABNORMAL_COMBO_CN_NAMES),
                'abnormal_combo_immunes': self._mask_names(
                    _u64(data, gs.BuffFields.ABNORMAL_COMBO_IMMUNE_MASK),
                    gs.ABNORMAL_COMBO_CN_NAMES),
                'has_shield': bool(data[gs.BuffFields.HAS_SHIELD]),
                'shield_mask': _i32(data, gs.BuffFields.SHIELD_MASK),
                'blackboard': blackboards.get(bb_ptr, []),
            })
        return out

    def _read_global_buffs(self, selected_addr=0):
        """读取 BattleController.m_globalBuffs，并解析精确目标映射。"""
        if not self.bc_addr:
            return []
        (slot,) = self._detail_batch_read(
            [(self.bc_addr + gs.BattleControllerFields.M_GLOBAL_BUFFS, 8)])
        list_ptr = _u64(slot, 0) if slot else 0
        if not self.mc.is_ptr(list_ptr):
            return []
        (head,) = self._detail_batch_read([(list_ptr, 0x20)])
        if not head:
            return []
        items, count = _u64(head, gs.ListInternal.ITEMS), _i32(head, gs.ListInternal.SIZE)
        if not (0 < count <= 256 and self.mc.is_ptr(items)):
            return []
        (array,) = self._detail_batch_read([(items + gs.Il2CppArray.ITEMS, count * 8)])
        if not array:
            return []
        ptrs = [_u64(array, idx * 8) for idx in range(count)]
        ptrs = [p for p in ptrs if self.mc.is_ptr(p)]
        records = [(p, data) for p, data in zip(
            ptrs, self._detail_batch_read([(p, gs.GlobalBuffFields.READ_SIZE) for p in ptrs]))
                   if data]
        if not records:
            return []

        string_ptrs = [_u64(data, gs.GlobalBuffFields.KEY) for _, data in records]
        bb_ptrs = [_u64(data, gs.GlobalBuffFields.BLACKBOARD) for _, data in records]
        strings = self._read_strings(string_ptrs)
        blackboards = self._read_blackboards(bb_ptrs)

        # Dictionary<ObjectPtr<Entity>, List<uint>>：Entry 步长 0x20，key 在 +8。
        map_ptrs = [_u64(data, gs.GlobalBuffFields.TARGET_MAP) for _, data in records]
        valid_maps = [p for p in map_ptrs if self.mc.is_ptr(p)]
        map_targets = {p: [] for p in valid_maps}
        map_heads = self._detail_batch_read([(p, 0x30) for p in valid_maps])
        entry_reqs, entry_owners = [], []
        for mp, mh in zip(valid_maps, map_heads):
            if not mh:
                continue
            entries, used = _u64(mh, 0x18), _i32(mh, 0x20)
            if 0 < used <= 2048 and self.mc.is_ptr(entries):
                entry_reqs.append((entries + gs.Il2CppArray.ITEMS, used * 0x20))
                entry_owners.append((mp, used))
        for (mp, used), data in zip(entry_owners, self._detail_batch_read(entry_reqs)):
            if not data:
                continue
            for idx in range(used):
                off = idx * 0x20
                if off + 0x20 > len(data) or _i32(data, off) < 0:
                    continue
                target = _u64(data, off + 8)
                if self.mc.is_ptr(target):
                    map_targets[mp].append(target)

        # GlobalBuff._buffs 中的静态 BuffData 概览。
        buff_arrays = [_u64(data, gs.GlobalBuffFields.BUFFS) for _, data in records]
        valid_arrays = [p for p in buff_arrays if self.mc.is_ptr(p)]
        array_heads = self._detail_batch_read([(p, 0x20) for p in valid_arrays])
        data_ptrs_by_array = {p: [] for p in valid_arrays}
        data_reqs, data_owners = [], []
        for ap, ah in zip(valid_arrays, array_heads):
            if not ah:
                continue
            n = _i32(ah, gs.Il2CppArray.MAX_LENGTH)
            if 0 < n <= 128:
                data_reqs.append((ap + gs.Il2CppArray.ITEMS, n * 8))
                data_owners.append((ap, n))
        all_data_ptrs = []
        for (ap, n), data in zip(data_owners, self._detail_batch_read(data_reqs)):
            if not data:
                continue
            vals = [_u64(data, idx * 8) for idx in range(n)]
            vals = [p for p in vals if self.mc.is_ptr(p)]
            data_ptrs_by_array[ap] = vals
            all_data_ptrs.extend(vals)
        data_blocks = {p: data for p, data in zip(
            all_data_ptrs,
            self._detail_batch_read([(p, gs.BuffDataFields.READ_SIZE) for p in all_data_ptrs]))
                       if data}
        data_string_ptrs = []
        for data in data_blocks.values():
            data_string_ptrs.extend((_u64(data, gs.BuffDataFields.BUFF_KEY),
                                     _u64(data, gs.BuffDataFields.TEMPLATE_KEY),
                                     _u64(data, gs.BuffDataFields.DURATION_KEY)))
        data_strings = self._read_strings(data_string_ptrs)

        side_names = {0: '友方', 1: '敌方', 2: '中立', 3: '全部'}
        out = []
        for ptr, data in records:
            key_ptr = _u64(data, gs.GlobalBuffFields.KEY)
            bb_ptr = _u64(data, gs.GlobalBuffFields.BLACKBOARD)
            map_ptr = _u64(data, gs.GlobalBuffFields.TARGET_MAP)
            buff_array = _u64(data, gs.GlobalBuffFields.BUFFS)
            targets = map_targets.get(map_ptr, [])
            buff_defs = []
            for dp in data_ptrs_by_array.get(buff_array, []):
                dd = data_blocks.get(dp)
                if not dd:
                    continue
                buff_defs.append({
                    'buff_key': data_strings.get(_u64(dd, gs.BuffDataFields.BUFF_KEY), ''),
                    'template_key': data_strings.get(
                        _u64(dd, gs.BuffDataFields.TEMPLATE_KEY), ''),
                    'duration_key': data_strings.get(
                        _u64(dd, gs.BuffDataFields.DURATION_KEY), ''),
                    'life_time_type': dd[gs.BuffDataFields.LIFE_TIME_TYPE],
                    'life_time': struct.unpack_from('<f', dd, gs.BuffDataFields.LIFE_TIME)[0],
                    'priority': _i32(dd, gs.BuffDataFields.PRIORITY),
                })
            source_type = _i32(data, gs.GlobalBuffFields.SOURCE_TYPE)
            out.append({
                'addr': ptr,
                'key': strings.get(key_ptr, '') or '?',
                'instance_uid': struct.unpack_from(
                    '<I', data, gs.GlobalBuffFields.INSTANCE_UID)[0],
                'source_type': source_type,
                'source_name': side_names.get(source_type, str(source_type)),
                'target_count': len(targets),
                'target_addrs': targets,
                'applies_to_selected': bool(selected_addr and selected_addr in targets),
                'blackboard': blackboards.get(bb_ptr, []),
                'buff_defs': buff_defs,
            })
        return out

    def read_enemy_detail(self, addr):
        """按需读取一个敌人的完整详情；供详情按钮调用，不增加常态轮询负担。"""
        if not self.mc.is_ptr(addr):
            return None
        (blk,) = self._detail_batch_read([(addr, gs.EnemyFields.READ_SIZE)])
        if not blk or len(blk) < 0x148:
            return None
        info = self._parse_enemy_block(addr, blk)
        self._fill_name(addr, blk, info)

        # 同时读取原始和最终属性，详情页可直接比较 Buff 前后变化。
        (attr_head,) = self._detail_batch_read([(info.attr_ptr, 0x60)]) \
            if self.mc.is_ptr(info.attr_ptr) else (None,)
        if attr_head:
            raw_ptr = _u64(attr_head, gs.AttributesFields.M_RAW_DATA)
            cached_ptr = _u64(attr_head, gs.AttributesFields.M_CACHED_DATA)
            reqs, kinds = [], []
            size = gs.Il2CppArray.ITEMS + gs.AttributeType.E_NUM * gs.OBSCURED_FP_SIZE
            if self.mc.is_ptr(raw_ptr):
                reqs.append((raw_ptr, size)); kinds.append('raw')
            if self.mc.is_ptr(cached_ptr):
                reqs.append((cached_ptr, size)); kinds.append('cached')
            for kind, data in zip(kinds, self._detail_batch_read(reqs)):
                if not data:
                    continue
                if kind == 'raw':
                    self._apply_raw_data(data, info)
                else:
                    self._apply_cached_data(data, info)
                    self._attr_cache[addr] = cached_ptr
                    self._attr_snapshot[addr] = dict(info.attributes)
        elif addr in self._attr_snapshot:
            info.attributes = dict(self._attr_snapshot[addr])

        if self._chan is not None:
            self._refresh_runtime_chan([addr], {addr: info})
        else:
            self._fill_runtime_slow(info)
        info.skills = list(self._skill_cd.get(addr, []))
        info.buffs = self._read_active_buffs(info.buff_container_ptr)
        info.global_buffs = self._read_global_buffs(addr)
        return info

    def _on_stale(self, snap):
        self._stale_cnt += 1
        if self._stale_cnt >= 3 and time.time() - self._last_bootstrap > 300:
            self.log("[轮询] 数据链失效, 重新扫描 ...")
            if self.bootstrap(force=True):
                self._stale_cnt = 0
                snap['msg'] += ' (已重建)'
            else:
                self._last_bootstrap = time.time()  # 5 分钟内不再重试
                snap['msg'] += ' (重建失败, 可能已退出关卡)'
        return snap
