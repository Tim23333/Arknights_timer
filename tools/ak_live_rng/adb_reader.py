"""ADB 直读后端: 复用 tools/enemy_health 的 MemCore + TcpChannel(memsrv)

与 pymem 全盘虚拟内存扫描的本质区别:
  - 直读游戏进程 /proc/<pid>/mem, 地址即 Android 虚拟地址, 指针可直接追踪
  - 区域来自 /proc/<pid>/maps, 按用途分区 (scope), 只扫该扫的部分:
      'meta'     libil2cpp.so 只读映射 (类名字符串所在, ~几十 MB)
      'metaheap' 非 GC 的 rw 区域 (Il2CppClass 等元数据 malloc 堆)
      'gc'       il2cpp Boehm GC 堆 (匿名大 rw, Random 对象/种子数组所在)
      'rw'       全部 rw (兜底)
  - 设备侧 memsrv v4 常驻服务: 单批请求 ~2-5ms (一个 pread64), 轮询游标无压力
  - memsrv v4 是唯一 ADB 内存后端；握手或通道失败直接报错
  - 无需 Windows 管理员权限
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from tools.enemy_health.memcore import MemCore, TcpChannel  # noqa: E402

SRV_MAX = 4 * 1024 * 1024   # memsrv 单请求上限 (memsrv.c MAX_SIZE)
SCAN_MERGE_MAX = 256 * 1024 * 1024   # 设备侧扫描单调用合并上限 (防单次过久无进度)
RNG_TCP_PORT = 27272   # RNG 通道独立端口, 与敌人监控 (默认 27271) 的 adb forward 互不干扰


class AdbReader:
    """memscan 读取协议实现: read(addr, size) + regions(scope) + scan_regions。"""

    def __init__(self, mc: MemCore):
        self.mc = mc
        self.chan = None

    # ---------------- 连接 ----------------

    @classmethod
    def connect(cls, adb_path=None, package="com.hypergryph.arknights", status=print,
                adb_serial=None):
        mc = MemCore(adb_path=adb_path, package=package, adb_serial=adb_serial)
        pid = mc.connect()          # devices/root/pidof/maps
        status("[adb] 已连接 %s / %s pid=%d, maps %d 区域" % (
            mc.adb_serial, mc.package, pid, len(mc.regions)))
        reader = cls(mc)
        reader._open_channel(status)
        return reader

    def _open_channel(self, status=print):
        self.chan = TcpChannel(self.mc, port=RNG_TCP_PORT)
        self.chan.open()
        if self.chan.srv_version != 4:
            self.chan.close()
            self.chan = None
            raise RuntimeError("RNG 读取仅支持 memsrv v4")
        status("[adb] memsrv v4 通道已建立")

    def ensure_alive(self, status=print):
        """游戏重启后自愈: pid 变化则重连。"""
        try:
            pid_s = self.mc.shell("pidof %s" % self.mc.package, timeout=10).strip()
            pid = int(pid_s.split()[0]) if pid_s else None
        except Exception:
            pid = None
        if pid and pid == self.mc.pid:
            return True
        if pid is None:
            return False
        status("[adb] 游戏 pid 变化 (%s -> %s), 重新连接" % (self.mc.pid, pid))
        self.mc.pid = pid
        self.mc.reload_maps()
        if self.chan:
            self.chan.close()
            self.chan = None
        self._open_channel(status)
        return True

    # ---------------- 设备侧扫描 ----------------

    def scan_regions(self, regions, needles):
        """memscan 扫描协议: 在 regions 内搜索全部 needles (bytes, 1..64B)。

        下沉到设备侧 memsrv v4 执行 (内部 4MB 滑动窗口+64B 重叠, 跨块不漏)；
        合并相邻块减少往返与边界漏报。服务或通道异常直接上抛。"""
        if not needles:
            return {}
        if self.chan is None:
            self._open_channel()
        if self.chan.srv_version != 4:
            raise RuntimeError("RNG 扫描仅支持 memsrv v4")
        merged = []
        for base, size in sorted(regions):
            if (merged and base == merged[-1][0] + merged[-1][1]
                    and merged[-1][1] + size <= SCAN_MERGE_MAX):
                merged[-1] = (merged[-1][0], merged[-1][1] + size)
            else:
                merged.append((base, size))
        out = {nd: [] for nd in needles}
        for base, size in merged:
            # memsrv 单次扫描上限 MAX_NEEDLES=256 (超出直接断连):
            # 针数过多时分批合并结果
            for i in range(0, len(needles), 256):
                part = list(needles[i:i + 256])
                r = self.chan.scan(base, size, part)
                for nd in part:
                    out[nd].extend(r.get(nd) or [])
        return out

    # ---------------- 读取协议 ----------------

    def read(self, addr, size):
        if size <= 0:
            return b""
        if self.chan is None:
            self._open_channel()
        reqs = []
        a = addr
        while a < addr + size:
            n = min(addr + size - a, SRV_MAX)
            reqs.append((a, n))
            a += n
        parts = self.chan.batch_read(reqs)
        if all(p is not None for p in parts):
            return b"".join(parts)
        return None

    def read_many(self, requests):
        """批量读取 [(addr, size), ...] -> [bytes|None, ...] (单次 TCP 往返)。

        轮询/批量校验的延迟关键路径；通道异常直接上抛。"""
        if not requests:
            return []
        if self.chan is None:
            self._open_channel()
        flat = []
        spans = []
        for a, s in requests:
            n_parts = 0
            while s > 0:
                n = min(s, SRV_MAX)
                flat.append((a, n))
                a += n
                s -= n
                n_parts += 1
            spans.append(n_parts)
        data = self.chan.batch_read(flat)
        out = []
        i = 0
        for n in spans:
            chunk = data[i:i + n]
            i += n
            out.append(b"".join(chunk)
                       if all(p is not None for p in chunk) else None)
        return out

    def regions(self, scope="all"):
        if not self.mc.regions:
            self.mc.reload_maps()
        picks = []
        for s, e, p, n in self.mc.regions:
            if scope == "meta":
                # libil2cpp.so 只读映射 (rodata: 类名/元数据字符串)
                if "r" in p and "il2cpp" in n.lower():
                    picks.append((s, e))
            elif scope == "metaheap":
                # 非 GC 的 rw: 元数据 malloc 堆 (scudo/dalvik/具名/小匿名)
                if "rw" in p and not self._is_gc(s, e, p, n):
                    picks.append((s, e))
            elif scope == "gc":
                if self._is_gc(s, e, p, n):
                    picks.append((s, e))
            elif scope == "rw":
                if "rw" in p:
                    picks.append((s, e))
            else:
                if "r" in p:
                    picks.append((s, e))
        if scope == "meta" and not picks:
            # 兜底: 全部只读映射 (某些版本映射名可能不含 il2cpp)
            picks = [(s, e) for s, e, p, n in self.mc.regions
                     if "r" in p and "w" not in p]
        chunks = []
        for s, e in picks:
            a = s
            while a < e:
                n = min(e - a, SRV_MAX)
                chunks.append((a, n))
                a += n
        return chunks

    @staticmethod
    def _is_gc(s, e, p, n):
        """il2cpp Boehm GC 堆特征 (与 enemy_health.scan_targets 同标准)"""
        if "rw" not in p or e - s < 0x10000:
            return False
        if n and "[anon" not in n:
            return False
        return not any(k in n for k in ("scudo", "dalvik", "jit", "stack"))
