"""明日方舟 实时 RNG 追踪器 (控制台版 —— 瘦展示壳)

功能逻辑全部在 rng_service.RngService (连接/定位/轮询/缓存), 本文件只做
命令行参数与控制台渲染; tkinter 图形界面见 ak_rng_ui.py。

读取后端:
  adb   (默认, 推荐): 经 adb + 设备侧 memsrv 直读游戏进程 /proc/pid/mem,
        区域按 maps 分区扫描, 速度远胜全盘虚拟内存扫描, 且无需 Windows 管理员。
  pymem (备选):       从 Windows 侧读模拟器进程内存, 需要管理员权限。

实现结论 (解包 + 联网考证 + 现网实测):
  战斗随机 = Knuth 减法门 (56 种子), 判定方式 NextDouble() < 阈值;
  指针链: BattleController.static_fields +0x30/+0x38
          -> BattleRandomWrapper (+0x10) -> LegacyRandom.SeedArray@0x28。
  详见 AGENTS.md "实时 RNG 追踪器" 一节。

用法:
  python ak_live_rng.py                          # adb 后端 (默认)
  python ak_live_rng.py --backend pymem          # pymem 后端 (需管理员)
  python ak_live_rng.py --package com.hypergryph.arknights.bilibili
  python ak_live_rng.py --no-cache               # 忽略地址缓存, 强制全量扫描
  python ak_live_rng.py --heuristic              # 静态链外追加启发式兜底 (调试)
"""

import argparse
import ctypes
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rng_service import RngService

PREDICT_COUNT = 12          # 未来预测发数
HISTORY_SHOW = 18           # 显示最近消耗条数
THRESHOLD = 0.2             # 触发判定阈值 (仅用于着色标记)


class ConsoleView:
    """定时清屏渲染 svc.snapshot() 的只读视图。"""

    def __init__(self, svc):
        self.svc = svc

    @staticmethod
    def _mark(frac):
        return "*" if frac < THRESHOLD else " "

    def render(self):
        snap = self.svc.snapshot(history_len=HISTORY_SHOW, predict_len=PREDICT_COUNT)
        os.system("cls")
        print("=" * 64)
        print(" 真理之眼 · 明日方舟实时 RNG 序列追踪    %s" % time.strftime("%H:%M:%S"))
        print("=" * 64)
        print(" 进程: %s    定位: %s    %s" %
              (snap["process"] or "未连接", snap["via"] or "--", snap["status"]))
        print("-" * 64)
        for e in snap["engines"]:
            cur = ">>" if e["id"] == snap["selected_id"] else "  "
            print(" %s #%d %-44s 游标=%-4s 消耗=%-7d %.1f/s" % (
                cur, e["id"], e["label"][:44], str(e["cursor"]), e["total"], e["rate"]))
        sel = snap["selected"]
        if not sel:
            print("\n 等待引擎 ...")
            return
        print("-" * 64)
        print(" 最近消耗 (旧 -> 新, * 表示 <%.0f%% 触发):" % (THRESHOLD * 100))
        hist = sel["history"]
        if not hist:
            print("   (暂无 — 等待游戏消耗随机数, 让干员攻击几次)")
        for p in hist:
            print("   #%-6d  %.6f%s  (%d)" % (p["seq"], p["frac"], self._mark(p["frac"]), p["raw"]))
        print("-" * 64)
        print(" 未来 %d 发预测 (下一发在最左):" % PREDICT_COUNT)
        preds = sel["predictions"]
        if preds:
            line1 = " ".join("%+d" % p["n"] for p in preds)
            line2 = " ".join("%.3f%s" % (p["frac"], self._mark(p["frac"])) for p in preds)
            print("   " + line1)
            print("   " + line2)
            nxt = preds[0]
            judge = "触发 (<=%.0f%%)" % (THRESHOLD * 100) if nxt["frac"] < THRESHOLD else "安全区"
            print(" 下一发: %.6f  ->  %s" % (nxt["frac"], judge))
        print("=" * 64)
        print(" Ctrl+C 退出")

    def loop(self, interval):
        while True:
            try:
                self.render()
            except Exception:
                pass
            time.sleep(interval)


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="明日方舟 实时 RNG 追踪器")
    parser.add_argument("--backend", choices=["adb", "pymem"], default="adb",
                        help="内存读取后端 (默认 adb, 免管理员)")
    parser.add_argument("--package", default="com.hypergryph.arknights",
                        help="游戏包名 (adb 后端)")
    parser.add_argument("--adb", help="adb.exe 路径 (默认自动探测)")
    parser.add_argument("--process", help="pymem 后端: 指定模拟器进程名")
    parser.add_argument("--engine", choices=["imp", "trivial"], default="imp",
                        help="重点显示哪个引擎 (默认 imp=关键随机)")
    parser.add_argument("--no-cache", action="store_true",
                        help="忽略 ak_rng_cache.pkl 地址缓存, 强制全量扫描")
    parser.add_argument("--heuristic", action="store_true",
                        help="静态链失败时回退启发式全盘扫描 (会捞到无关 System.Random, 调试用)")
    parser.add_argument("--interval", type=float, default=0.15, help="界面刷新间隔秒")
    args = parser.parse_args()

    svc = RngService(
        backend=args.backend, package=args.package, adb_path=args.adb,
        process_names=[args.process] if args.process else None,
        prefer_role=args.engine, use_cache=not args.no_cache,
        allow_heuristic=args.heuristic,
        on_status=lambda m: print("[*] %s" % m, flush=True))

    print("[*] 连接 %s 后端 ..." % args.backend)
    while not svc.attach():
        print("[!] 连接失败, 10 秒后重试 (Ctrl+C 退出) ...")
        time.sleep(10)
    print("[*] 已连接: %s" % svc.process)

    svc.locate()
    svc.start()
    try:
        ConsoleView(svc).loop(args.interval)
    except KeyboardInterrupt:
        svc.stop()


if __name__ == "__main__":
    # adb 后端直读游戏进程, 无需管理员; pymem 读模拟器进程需要提权
    wants_pymem = "--backend" in sys.argv and "pymem" in sys.argv
    if not wants_pymem or is_admin():
        main()
    else:
        script = os.path.abspath(sys.argv[0])
        params = " ".join('"%s"' % a for a in sys.argv[1:])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable,
                                            '"%s" %s' % (script, params), None, 1)
        sys.exit()
