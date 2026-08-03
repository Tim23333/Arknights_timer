# -*- coding: utf-8 -*-
"""敌人血量/属性实时监控

用法:
    python -m tools.enemy_health              # 实时监控 (默认 2.5 秒刷新)
    python -m tools.enemy_health --once       # 只读一次
    python -m tools.enemy_health --rebuild    # 强制重新扫描地址
    python -m tools.enemy_health --interval 1 # 自定义刷新间隔(秒)
    python -m tools.enemy_health --desc       # 显示敌人描述
    python -m tools.enemy_health --adb <adb.exe路径>

原理: 通过 adb 读取 MuMu 模拟器中游戏进程内存 (需要 adb root)。
首次运行需全堆扫描定位敌人列表 (~1-3 分钟), 结果缓存后秒级启动。
"""

import argparse
import os
import sys
import time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(errors='replace')  # 防止控制台编码无法表示的字符导致崩溃

if __package__ in (None, ''):  # 允许直接 python main.py 运行
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    __package__ = 'tools.enemy_health'

from .enemy_reader import EnemyReader
from . import game_structs as gs

STATE_NAMES = {0: 'NONE', 1: 'INITED', 2: '战斗中', 3: '已结束'}


def hp_bar(cur, max_hp, width=20):
    if max_hp <= 0:
        return '?' * width
    ratio = max(0.0, min(1.0, cur / max_hp))
    filled = int(ratio * width + 0.5)
    return '█' * filled + '░' * (width - filled)


def fmt_time(sec):
    sec = int(sec)
    return f"{sec // 60:02d}:{sec % 60:02d}"


def render(snap, reader, show_desc=False):
    lines = []
    st = STATE_NAMES.get(snap['state'], f"?({snap['state']})") if snap['state'] >= 0 else '未知'
    spd = gs.SpeedLevel.NAMES.get(snap['speed_level'], '?') if snap['speed_level'] >= 0 else '?'
    if snap.get('read_mode') == 'fast':
        channel = '高速/memsrv' if snap.get('read_backend') == 'srv' else '高速/TCP'
    else:
        channel = '慢速/ADB'
    lines.append(f"通道: {channel}   状态: {st}   倍速: {spd} (x{snap['time_scale']:g})   "
                 f"战斗时间: {fmt_time(snap['play_time'])}   敌人数: {len(snap['enemies'])}"
                 + (f"   {snap['frame_ms']:.0f}ms/帧" if snap.get('frame_ms') else ''))
    lines.append('')
    header = f"{'#':<3}{'名称':<14}{'编号':<5}{'血量':<38}{'坐标':<18}{'攻击':>7}{'防御':>6}{'法抗':>6}{'移速':>6}{'攻速':>7}  状态"
    lines.append(header)
    lines.append('-' * len(header))
    for i, e in enumerate(snap['enemies']):
        bar = f"{int(e.hp):>6}/{int(e.max_hp):<6} {hp_bar(e.hp, e.max_hp)}"
        status = '存活' if e.alive else ('退场' if e.finish else '阵亡')
        name = (e.name or e.eid or '?')[:12]
        pos = f"({e.pos_x:.2f},{e.pos_y:.2f})"
        lines.append(f"{i:<3}{name:<14}{(e.code or '-'):<5}{bar:<38}{pos:<18}"
                     f"{e.atk:>7.0f}{e.def_:>6.0f}{e.res:>6.0f}{e.mspd:>6.2f}{e.aspd:>7.0f}  {status}")
        if show_desc and e.eid in (reader._db or {}):
            desc = reader._db[e.eid].get('desc')
            if desc:
                lines.append(f"    └ {desc}")
    if not snap['enemies']:
        lines.append('  (场上无敌人)')
    if snap.get('msg'):
        lines.append(f"\n[!] {snap['msg']}")
    return '\n'.join(lines)


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def main(argv=None):
    ap = argparse.ArgumentParser(description='明日方舟敌人血量/属性实时监控 (MuMu 模拟器)')
    ap.add_argument('--adb', help='adb.exe 路径 (默认自动查找 MuMu)')
    ap.add_argument('--serial', help='ADB 设备地址，例如 127.0.0.1:16384（默认自动选择）')
    ap.add_argument('--interval', type=float, default=2.5, help='刷新间隔秒 (默认 2.5)')
    ap.add_argument('--once', action='store_true', help='只读取一次')
    ap.add_argument('--rebuild', action='store_true', help='忽略缓存强制重新扫描')
    ap.add_argument('--no-bc', action='store_true', help='不定位 BattleController (省一遍扫描, 无战斗状态)')
    ap.add_argument('--desc', action='store_true', help='显示敌人描述')
    args = ap.parse_args(argv)

    reader = EnemyReader(
        adb_path=args.adb, adb_serial=args.serial, with_bc=not args.no_bc)
    try:
        reader.connect()
    except RuntimeError as e:
        print(f"[错误] {e}")
        print("请确认 MuMu 模拟器已启动, 且游戏已进入关卡。")
        return 1

    if not reader.bootstrap(force=args.rebuild):
        print("[错误] 敌人定位失败。请确认游戏已进入关卡且场上有敌人。")
        return 1

    try:
        while True:
            t0 = time.time()
            snap = reader.poll_fast()
            clear_screen()
            print(f"明日方舟 敌人实时监控   PID={reader.mc.pid}   "
                  f"刷新 {time.strftime('%H:%M:%S')} (耗时 {time.time()-t0:.2f}s, Ctrl+C 退出)")
            print('=' * 100)
            print(render(snap, reader, args.desc))
            if args.once:
                break
            dt = time.time() - t0
            time.sleep(max(0.01, args.interval - dt))
    except KeyboardInterrupt:
        print("\n已退出。")
    finally:
        reader.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
