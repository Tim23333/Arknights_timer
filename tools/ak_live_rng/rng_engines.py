"""明日方舟战斗 RNG 引擎纯 Python 复刻 (不依赖 pymem, 可离线单测)

逆向依据 (Ark_data/dump.cs + 现网实测):

  Torappu.LegacyRandom : System.Random   (dump.cs:1256570)
      Knuth 减法门 (与 .NET System.Random 同型), 56 个 int32 种子
      字段: inext@0x20, inextp@0x24, SeedArray@0x28
      mscorlib System.Random 基类同名字段: _inext@0x10, _inextp@0x14, _seedArray@0x18
      ★ 现网实测游标间距 31 (mscorlib 为 21): (inext,inextp)=(31,0)/(0,31)。
        追踪/推演均从观测快照克隆出发, 双游标同步自增, 与间距常量无关,
        故同一复刻代码兼容两者; 仅 tracker 游标合法性校验区分间距。

  现网指针链 (新版, dump.cs 旧版无包装层):
      BattleController.static_fields +0x30/+0x38
        -> Torappu.Battle.BattleRandomWrapper (+0x10) -> LegacyRandom

  Rei.Random.MersenneTwister : RandomBase (dump.cs:1256334)
      标准 MT19937, 字段: mt@0x10, mti@0x18, mag01@0x20

  TrueSync.TSRandom              (dump.cs:1228942)
      标准 MT19937, 字段: mag01@0x10, mt@0x18, mti@0x20

  BattleController               (dump.cs:317283)
      private static Random s_randomImp;     // 静态块 +0x30  (关键随机: 暴击/闪避等)
      private static Random s_randomTrivial; // 静态块 +0x38  (表现随机: 特效等)
      由 RandomFactory.Create(seed, RANDOM_ALGORITHM=DEFAULT) 创建
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

    def matches(self, seeds, inext):
        return self.inext == inext and self.seeds == list(seeds)


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

    observed_state: Knuth -> (seeds, inext) ; MT -> (mt, mti)
    返回 (消耗次数, [原始输出...]) ; 推演 max_steps 步仍不匹配 (换种子/GC) 返回 None。
    """
    work = engine.clone()
    values = []
    step_fn = work.next_int if isinstance(work, DotNetRandom) else work.next_uint32
    for step in range(1, max_steps + 1):
        values.append(step_fn())
        if work.matches(*observed_state):
            return step, values
    return None
