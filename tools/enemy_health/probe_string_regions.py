# -*- coding: utf-8 -*-
"""验证 il2cpp 字符串所在内存区域的权限 (只读)

在游戏运行时扫描全部映射, 查找 "conveyor_speed" / "mass_level" 的
UTF-16LE (Il2CppString) 命中, 打印命中地址所在区域的权限位。
用于确认 blackboard 模板键字符串是否落在 r-- 只读区 (is_ptr 只认 rw)。
"""

import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(errors='replace')

if __package__ in (None, ''):
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    __package__ = 'tools.enemy_health'

from .memcore import MemCore, TcpChannel

PROBE_PORT = 27275
NEEDLES = [
    'conveyor_speed'.encode('utf-16-le'),
    'mass_level'.encode('utf-16-le'),
    'conveyor_speed'.encode('utf-8'),
]


def main():
    serial = sys.argv[1] if len(sys.argv) > 1 else '127.0.0.1:16384'
    mc = MemCore(adb_serial=serial)
    pid = mc.connect()
    print(f'pid={pid}, regions={len(mc.regions)}')
    chan = TcpChannel(mc, port=PROBE_PORT)
    try:
        hits = {nd: [] for nd in NEEDLES}
        for s, e, perms, name in mc.regions:
            if e - s < 0x1000 or e - s > 0x40000000:
                continue
            n = name or ''
            if any(k in n for k in ('stack', 'vsyscall', 'vvar', 'vdso')):
                continue
            try:
                res = chan.scan(s, e - s, NEEDLES)
            except Exception as ex:
                print(f'scan 失败 @{hex(s)}: {ex}')
                continue
            if not res:
                continue
            for nd in NEEDLES:
                for addr in res.get(nd) or []:
                    hits[nd].append((addr, perms, n))
        for nd in NEEDLES:
            label = nd.decode('utf-16-le' if nd.endswith(b'\x00') else 'utf-8',
                              errors='replace')
            got = hits[nd]
            print(f'\n== {label!r} ({len(nd)}B needle): {len(got)} 处命中 ==')
            for addr, perms, name in got[:12]:
                print(f'  {hex(addr)}  perms={perms:<6} region={name or "(anon)"}')
            if got:
                from collections import Counter
                print('  perms 统计:', dict(Counter(p for _, p, _ in got)))
    finally:
        chan.close()


if __name__ == '__main__':
    main()
