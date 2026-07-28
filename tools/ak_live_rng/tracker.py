"""RNG 引擎实时追踪: 高频轮询游标, 漏值推演恢复, 未来序列预测

工作原理:
  每次轮询读取引擎的完整状态 (Knuth: 56 种子 + 双游标; MT: 624 状态 + mti)。
  若与本地克隆状态不一致, 用 rng_engines.recover_advanced 从本地状态向前
  逐步推演, 直到与观测状态逐字节一致 —— 推演经过的每一步就是游戏在两次
  轮询之间真实消耗的随机数, 一个不漏 (只要消耗数 < max_steps)。
  预测同理: 从当前状态克隆推演, 不碰游戏内存。
"""

import struct
import threading
import time
from collections import deque

from rng_engines import DotNetRandom, MT19937, MBIG, recover_advanced

MT_MOD = 1 << 32
READ_FAIL_LIMIT = 400      # 连续读失败上限 (~2s @5ms): 超限按状态丢失处理


class EngineTracker:
    def __init__(self, reader, engine):
        self.reader = reader
        self.engine = engine            # memscan.probe_engines 产出的记录
        self.state = None               # DotNetRandom / MT19937 克隆
        self.status = "init"            # init / ok / lost
        self.total = 0                  # 本次跟踪累计消耗
        self.seq = 0
        self.history = deque(maxlen=600)
        self.call_times = deque(maxlen=4000)   # (ts, count)
        self.lock = threading.Lock()
        self.last_poll_ok = 0.0
        self._none_reads = 0            # 连续读失败计数

    # ---------------- 内存状态读取 ----------------

    def _read_pair(self, requests):
        """批量读 (reader 支持 read_many 时单次往返); FakeMem 等退化为逐个读。"""
        fn = getattr(self.reader, "read_many", None)
        if fn is not None:
            return fn(requests)
        return [self.reader.read(a, s) for a, s in requests]

    def _read_knuth_state(self):
        e = self.engine
        raw, cur = self._read_pair([(e["array"], 56 * 4), (e["cursor_addr"], 8)])
        if not raw or not cur:
            return None
        seeds = list(struct.unpack("<56i", raw))
        inext, inextp = struct.unpack("<ii", cur)
        if not (0 <= inext < 56 and 0 <= inextp < 56):
            return None
        # 游标间距校验: mscorlib System.Random 间距 21 (环回 -34);
        # Torappu LegacyRandom 现网实测间距 31 (环回 -24, 同进程两次
        # 读取 (inext,inextp)=(31,0)/(0,31) 证实)
        if inextp - inext not in (21, -34, 31, -24):
            return None
        # 防撕裂: 再读一次游标, 不一致说明读取中途游戏在消耗, 放弃本次
        cur2 = self.reader.read(e["cursor_addr"], 8)
        if cur2 != cur:
            return None
        return DotNetRandom(seeds=seeds, inext=inext, inextp=inextp)

    def _read_mt_state(self):
        e = self.engine
        raw, cur = self._read_pair([(e["array"], 624 * 4), (e["cursor_addr"], 4)])
        if not raw or not cur:
            return None
        mti = struct.unpack("<i", cur)[0]
        if not (0 <= mti <= 624):
            return None
        cur2 = self.reader.read(e["cursor_addr"], 4)
        if cur2 != cur:
            return None
        return MT19937(mt=list(struct.unpack("<624I", raw)), mti=mti)

    def read_state(self):
        if self.engine["kind"] == "knuth":
            return self._read_knuth_state()
        return self._read_mt_state()

    # ---------------- 轮询 ----------------

    def poll(self):
        """返回本次新恢复的输出值列表 [(seq, raw, frac), ...]; 状态丢失返回 None。"""
        observed = self.read_state()
        if observed is None:
            # 读失败 (对象被释放/映射失效) 与"无消耗"同形; 已建基线后
            # 连续失败说明引擎对象大概率已死, 按丢失处理触发上层重扫
            self._none_reads += 1
            if self._none_reads >= READ_FAIL_LIMIT and self.state is not None:
                self.status = "lost"
                return None
            return []
        self._none_reads = 0
        with self.lock:
            if self.state is None:
                self.state = observed
                self.status = "ok"
                self.last_poll_ok = time.time()
                return []
            if self._same_state(observed, self.state):
                self.last_poll_ok = time.time()
                return []
            key = self._observed_key(observed)
            rec = recover_advanced(self.state, key)
            if rec is None:
                self.status = "lost"
                return None
            count, values = rec
            now = time.time()
            out = []
            is_knuth = self.engine["kind"] == "knuth"
            for v in values:
                self.seq += 1
                frac = v / MBIG if is_knuth else v / MT_MOD
                self.history.append({
                    "seq": self.seq,
                    "raw": v,
                    "frac": round(frac, 6),
                    "ts": round(now, 3),
                })
                out.append((self.seq, v, frac))
            self.total += count
            self.call_times.append((now, count))
            # 本地状态直接采用观测快照 (recover_advanced 的 work 与之等价)
            self.state = observed
            self.status = "ok"
            self.last_poll_ok = now
            return out

    @staticmethod
    def _observed_key(state):
        if isinstance(state, DotNetRandom):
            return state.seeds, state.inext
        return state.mt, state.mti

    @staticmethod
    def _same_state(a, b):
        if isinstance(a, DotNetRandom):
            return a.seeds == b.seeds and a.inext == b.inext and a.inextp == b.inextp
        return a.mt == b.mt and a.mti == b.mti

    # ---------------- 对外 ----------------

    def predict(self, count=16):
        with self.lock:
            if self.state is None:
                return []
            raws = self.state.peek(count)
            is_knuth = self.engine["kind"] == "knuth"
            mod = MBIG if is_knuth else MT_MOD
            return [{"n": i + 1, "raw": v, "frac": round(v / mod, 6)}
                    for i, v in enumerate(raws)]

    def rate(self, window=5.0):
        now = time.time()
        while self.call_times and self.call_times[0][0] < now - max(window, 10):
            self.call_times.popleft()
        return round(sum(c for t, c in self.call_times if t >= now - window) / window, 1)

    def activity(self):
        """最近 2 秒的消耗次数 (用于引擎活跃度排序/自动选择)。"""
        now = time.time()
        return sum(c for t, c in self.call_times if t >= now - 2.0)

    def snapshot(self, history_len=120, predict_len=16):
        with self.lock:
            hist = list(self.history)[-history_len:] if history_len > 0 else []
            is_knuth = isinstance(self.state, DotNetRandom)
            cursor = -1
            cursor2 = -1
            if self.state is not None:
                cursor = self.state.inext if is_knuth else self.state.mti
                cursor2 = self.state.inextp if is_knuth else -1
        return {
            "id": self.engine["id"],
            "label": self.engine["label"],
            "kind": self.engine["kind"],
            "rawOnly": self.engine["kind"] != "knuth",
            "role": self.engine["role"],
            "paired": self.engine["paired"],
            "obj": hex(self.engine["obj"]),
            "array": hex(self.engine["array"]),
            "status": self.status,
            "total": self.total,
            "rate": self.rate(),
            "activity": self.activity(),
            "cursor": cursor,      # knuth=inext / mt=mti (指向下一个随机数的位置)
            "cursor2": cursor2,    # knuth=inextp (另一游标), mt 为 -1
            "history": hist,
            "predictions": self.predict(predict_len),
        }
