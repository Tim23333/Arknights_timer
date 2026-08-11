"""Deterministic RNG for reproducible battles.

The game uses System.Random (Knuth subtraction generator, 56xint32 seed) for
important battle randomness (see tools/ak_live_rng/rng_engines.py, verified
against live memory). This is a faithful reimplementation with 1-based cursor
semantics so replays stay identical given the same seed.
"""

MBIG = 2147483647
MSEED = 161803398


class SystemRandomClone:
    """Clone of mscorlib System.Random (Knuth subtractive), 1-based cursors.

    Cursor layout matches the live-verified Torappu.LegacyRandom:
    (inext, inextp) start as (0, 21) and advance to 1-based indices on read,
    mirroring InternalSample() in the .NET reference implementation.
    """

    __slots__ = ("_seed", "_inext", "_inextp")

    def __init__(self, seed, seeds=None, inext=0, inextp=21):
        if seeds is not None:
            if len(seeds) != 56:
                raise ValueError("seeds must have 56 entries")
            self._seed = list(seeds)
            self._inext = inext
            self._inextp = inextp
            return
        self._seed = [0] * 56
        self._inext = 0
        self._inextp = 21
        self._init(seed)

    def _init(self, seed):
        # .NET Framework / Core CompatPrng seed initialisation
        subtraction = MBIG if seed == -2147483648 else abs(seed)
        mj = MSEED - subtraction
        if mj < 0:
            mj += MBIG
        self._seed[55] = mj
        mk = 1
        for i in range(1, 55):
            ii = (21 * i) % 55
            self._seed[ii] = mk
            mk = mj - mk
            if mk < 0:
                mk += MBIG
            mj = self._seed[ii]
        for _k in range(4):
            for i in range(1, 56):
                self._seed[i] -= self._seed[1 + (i + 30) % 55]
                if self._seed[i] < 0:
                    self._seed[i] += MBIG

    def clone(self):
        return SystemRandomClone(0, seeds=self._seed, inext=self._inext,
                                 inextp=self._inextp)

    def _sample(self):
        """InternalSample(): returns [0, MBIG) int (raw Next() value)."""
        seeds = self._seed
        i = self._inext + 1
        if i >= 56:
            i = 1
        p = self._inextp + 1
        if p >= 56:
            p = 1
        ret = seeds[i] - seeds[p]
        if ret == MBIG:
            ret -= 1
        if ret < 0:
            ret += MBIG
        seeds[i] = ret
        self._inext = i
        self._inextp = p
        return ret

    def next(self, max_exclusive=None):
        """next() -> raw sample; next(max) -> int in [0, max) like Next(max)."""
        if max_exclusive is None:
            return self._sample()
        if max_exclusive <= 0:
            raise ValueError("max_exclusive must be > 0")
        if max_exclusive <= MBIG:
            return int(self._sample() * max_exclusive / MBIG)
        # double-range path (rare; mirrors Next(max) for huge ranges)
        return int(self._sample() * MBIG + self._sample()) % max_exclusive

    def next_float(self):
        """NextDouble(): InternalSample() * (1/MBIG) in [0, 1)."""
        return self._sample() / MBIG

    def chance(self, probability):
        """True with given probability (0..1); mirrors NextDouble() < p."""
        return self.next_float() < probability

    def peek(self, count):
        """Predict next `count` raw samples without mutating self."""
        work = self.clone()
        return [work.next() for _ in range(count)]

    def matches(self, seeds, inext):
        return self._inext == inext and self._seed == list(seeds)


def _selftest():
    a = SystemRandomClone(978975386)
    b = SystemRandomClone(0, seeds=a._seed[:], inext=a._inext, inextp=a._inextp)
    assert [a.next() for _ in range(5)] == [b.next() for _ in range(5)]
    assert a._inext == b._inext and a._inextp == b._inextp
    c = SystemRandomClone(42)
    d = c.clone()
    assert [c.next() for _ in range(10)] == [d.next() for _ in range(10)]
    e = SystemRandomClone(1)
    seq = e.peek(8)
    assert [e.next() for _ in range(8)] == seq
    print("rng selftest OK")


if __name__ == "__main__":
    _selftest()
