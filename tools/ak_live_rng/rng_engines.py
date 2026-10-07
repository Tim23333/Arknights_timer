"""离线 RNG 状态推进工具；不凭类声明声称客户端算法已经核实。

本地 dump.cs 声明 LegacyRandom 的双游标/56元素数组，及 BattleController
的 IBattleRandom imp/trivial 字段与 BattleRandomWrapper.m_random。
方法正文为空，不能证明种子构造、DEFAULT工厂分支、转换或每个调用来源。
DotNetRandom(seed) 是显式 .NET兼容初始化（游标21），不是已恢复的现场
LegacyRandom游标31种子构造。31来自项目历史观测说明；用捕获数组和完整
双游标可跳过初始化，但仍需版本锁与独立原始快照/轨迹核实游戏准确性。
MT实现亦为离线数学模型，不同部署的实际引擎须逐次识别。
"""

MBIG = 2147483647
MSEED = 161803398


class DotNetRandom:
    """System.Random (Knuth subtractive) 复刻, 支持从内存快照恢复状态。"""

    __slots__ = ("seeds", "inext", "inextp")

    def __init__(self, seed=0, seeds=None, inext=0, inextp=21):
        if seeds is not None:
            assert len(seeds) == 56
            self.seeds = list(seeds)
            self.inext = inext
            self.inextp = inextp
        else:
            self.seeds = [0] * 56
            self.inext = 0
            self.inextp = 21
            self._init(seed)

    def _init(self, seed):
        # .NET Framework / Core CompatPrng 种子初始化 (参考源码)
        subtraction = MBIG if seed == -2147483648 else abs(seed)
        mj = MSEED - subtraction
        if mj < 0:
            mj += MBIG
        self.seeds[55] = mj
        mk = 1
        for i in range(1, 55):
            ii = (21 * i) % 55
            self.seeds[ii] = mk
            mk = mj - mk
            if mk < 0:
                mk += MBIG
            mj = self.seeds[ii]
        for _ in range(4):
            for i in range(1, 56):
                self.seeds[i] -= self.seeds[1 + (i + 30) % 55]
                if self.seeds[i] < 0:
                    self.seeds[i] += MBIG

    def clone(self):
        return DotNetRandom(seeds=self.seeds, inext=self.inext, inextp=self.inextp)

    def next_int(self):
        """InternalSample(): 推进一次, 返回 [0, MBIG) 的 int (即 Next() 的原始值)。"""
        seeds = self.seeds
        i = self.inext + 1
        if i >= 56:
            i = 1
        p = self.inextp + 1
        if p >= 56:
            p = 1
        ret = seeds[i] - seeds[p]
        if ret == MBIG:
            ret -= 1
        if ret < 0:
            ret += MBIG
        seeds[i] = ret
        self.inext = i
        self.inextp = p
        return ret

    def peek(self, count):
        """预测接下来 count 个输出, 不改动自身状态。返回 [int, ...]。"""
        work = self.clone()
        return [work.next_int() for _ in range(count)]

    def matches(self, seeds, inext, inextp):
        return self.inext == inext and self.inextp == inextp and self.seeds == list(seeds)


class MT19937:
    """标准 MT19937 (Rei.Random.MersenneTwister / TrueSync.TSRandom 共用算法)。"""

    N, M = 624, 397
    MATRIX_A = 0x9908B0DF
    UPPER_MASK = 0x80000000
    LOWER_MASK = 0x7FFFFFFF

    __slots__ = ("mt", "mti")

    def __init__(self, seed=None, mt=None, mti=None):
        if mt is not None:
            assert len(mt) == self.N
            self.mt = list(mt)
            self.mti = mti
        else:
            self.mt = [0] * self.N
            self.mt[0] = seed & 0xFFFFFFFF
            for i in range(1, self.N):
                self.mt[i] = (1812433253 * (self.mt[i - 1] ^ (self.mt[i - 1] >> 30)) + i) & 0xFFFFFFFF
            self.mti = self.N

    def clone(self):
        return MT19937(mt=self.mt, mti=self.mti)

    def twist(self):
        mt = self.mt
        for k in range(self.N):
            y = (mt[k] & self.UPPER_MASK) | (mt[(k + 1) % self.N] & self.LOWER_MASK)
            mt[k] = mt[(k + self.M) % self.N] ^ (y >> 1)
            if y & 1:
                mt[k] ^= self.MATRIX_A

    def next_uint32(self):
        if self.mti >= self.N:
            self.twist()
            self.mti = 0
        y = self.mt[self.mti]
        self.mti += 1
        y ^= (y >> 11)
        y ^= (y << 7) & 0x9D2C5680
        y ^= (y << 15) & 0xEFC60000
        y ^= (y >> 18)
        return y & 0xFFFFFFFF

    def peek(self, count):
        work = self.clone()
        return [work.next_uint32() for _ in range(count)]

    def matches(self, mt, mti):
        return self.mti == mti and self.mt == list(mt)


def recover_advanced(engine, observed_state, max_steps=8192):
    """从 engine (克隆的上次观测状态) 向前推演, 直到与本次观测完全一致。

    observed_state: Knuth -> (seeds, inext, inextp) ; MT -> (mt, mti)
    返回 (消耗次数, [原始输出...]) ; 推演 max_steps 步仍不匹配 (换种子/GC) 返回 None。
    """
    expected_fields = 3 if isinstance(engine, DotNetRandom) else 2
    if not isinstance(observed_state, (list, tuple)) or len(observed_state) != expected_fields:
        raise ValueError("Observed endpoint must include complete RNG state/cursors")
    work = engine.clone()
    values = []
    step_fn = work.next_int if isinstance(work, DotNetRandom) else work.next_uint32
    for step in range(1, max_steps + 1):
        values.append(step_fn())
        if work.matches(*observed_state):
            return step, values
    return None
