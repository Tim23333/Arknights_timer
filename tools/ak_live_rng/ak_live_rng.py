"""明日方舟 实时 RNG 追踪器 (控制台版)

读取游戏内存, 经 BattleController 静态指针链精确定位 randomImp/randomTrivial,
实时还原每次随机数调用的结果, 并预测接下来的随机数序列。

读取后端:
  adb   (默认, 推荐): 经 adb + 设备侧 memsrv 直读游戏进程 /proc/pid/mem,
        区域按 maps 分区扫描, 速度远胜全盘虚拟内存扫描, 且无需 Windows 管理员。
  pymem (备选):       从 Windows 侧读模拟器进程内存, 需要管理员权限。

实现结论 (解包 + 联网考证):
  战斗随机 = System.Random (mono mscorlib, Knuth 减法门, 56 种子),
  判定方式 NextDouble() < 阈值; 种子来自代理数据或开局随机生成 (PRTS 代理学)。
  指针链: Il2CppClass("Torappu.Battle.BattleController").static_fields (+0xB8)
          +0x30 -> s_randomImp, +0x38 -> s_randomTrivial
          -> LegacyRandom.SeedArray@0x28 / inext@0x20。

用法:
  python ak_live_rng.py                          # adb 后端 (默认)
  python ak_live_rng.py --backend pymem          # pymem 后端 (需管理员)
  python ak_live_rng.py --package com.hypergryph.arknights.bilibili
  python ak_live_rng.py --no-cache               # 忽略地址缓存, 强制全量扫描
  python ak_live_rng.py --heuristic              # 静态链外追加启发式兜底 (调试)

定位成功后地址缓存进 ak_rng_cache.pkl (游戏重启后三重校验自动失效重扫)。
"""

import argparse
import ctypes
import os
import pickle
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import memscan
from tracker import EngineTracker

POLL_INTERVAL = 0.005       # 引擎轮询间隔
PREDICT_COUNT = 12          # 未来预测发数
HISTORY_SHOW = 18           # 显示最近消耗条数
THRESHOLD = 0.2             # 触发判定阈值 (仅用于着色标记)
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "ak_rng_cache.pkl")   # 定位地址缓存 (游戏重启自动失效)


class ConsoleApp:
    def __init__(self, args):
        self.args = args
        self.process_names = ([args.process] if args.process
                              else memscan.EMULATOR_PROCESSES)
        self.prefer_role = args.engine
        self.pm = None
        self.reader = None
        self.process = ""
        self.trackers = {}
        self.selected_id = None
        self.via = ""
        self.message = "初始化..."
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.rescan_event = threading.Event()

    def log(self, msg):
        with self.lock:
            self.message = msg
        print("[*] %s" % msg, flush=True)

    def attach(self):
        if self.args.backend == "adb":
            try:
                from adb_reader import AdbReader
                self.reader = AdbReader.connect(
                    adb_path=self.args.adb, package=self.args.package,
                    status=self.log)
                self.process = "%s (pid %d)" % (self.args.package, self.reader.mc.pid)
                return True
            except Exception as ex:
                self.log("adb 连接失败: %s" % ex)
                self.reader = None
                return False
        import pymem
        for name in self.process_names:
            try:
                self.pm = pymem.Pymem(name)
                self.reader = memscan.PymemReader(self.pm)
                self.process = name
                return True
            except Exception:
                continue
        return False

    def scan(self):
        self.log("扫描定位 RNG 引擎 ...")
        if self.args.backend == "adb":
            try:
                self.reader.ensure_alive(status=self.log)
            except Exception:
                pass
        engines = [] if self.args.no_cache else self._try_cache()
        if engines:
            self.via = "cache"
        else:
            try:
                if self.args.heuristic:
                    engines, self.via = memscan.locate_engines(self.reader, status=self.log)
                else:
                    # 默认只走静态链: 未开战时启发式会捞到几百个无关 System.Random
                    engines = memscan.locate_battle_random(self.reader, status=self.log)
                    self.via = "static-chain"
            except Exception as ex:
                self.log("扫描异常: %s" % ex)
                return False
            if engines:
                self._save_cache(engines)
        with self.lock:
            self.trackers = {e["id"]: EngineTracker(self.reader, e) for e in engines}
            self.selected_id = None
            for t in self.trackers.values():
                if t.engine["role"] == self.prefer_role or self.selected_id is None:
                    if t.engine["role"] == self.prefer_role:
                        self.selected_id = t.engine["id"]
                        break
                    self.selected_id = t.engine["id"]
        if not engines:
            self.log("未定位到引擎 (未开战?) — 5 秒后自动重试")
            self.request_rescan(5)
            return False
        sel = self.trackers.get(self.selected_id)
        self.log("定位方式=%s, 跟踪引擎 #%d: %s" % (self.via, self.selected_id, sel.engine["label"]))
        return True

    # ---------------- 地址缓存 ----------------

    def _try_cache(self):
        """读取 ak_rng_cache.pkl 并逐引擎校验; 全部失效返回 []。"""
        try:
            with open(CACHE_FILE, "rb") as f:
                data = pickle.load(f)
            engines = data.get("engines") if isinstance(data, dict) else None
        except Exception:
            return []
        if not engines:
            return []
        ok = []
        for e in engines:
            e = dict(e)
            if memscan.validate_engine(self.reader, e):
                e["via"] = "cache"
                ok.append(e)
        if ok:
            self.log("地址缓存命中 (%d 个引擎), 跳过扫描" % len(ok))
        return ok

    def _save_cache(self, engines):
        try:
            with open(CACHE_FILE, "wb") as f:
                pickle.dump({"time": time.time(),
                             "package": self.args.package,
                             "engines": engines}, f)
        except Exception:
            pass

    def request_rescan(self, delay=0):
        def fire():
            time.sleep(delay)
            self.rescan_event.set()
        threading.Thread(target=fire, daemon=True).start()

    def poll_loop(self):
        while not self.stop_event.is_set():
            if self.rescan_event.is_set():
                self.rescan_event.clear()
                self.scan()
            with self.lock:
                trackers = list(self.trackers.values())
            for t in trackers:
                try:
                    r = t.poll()
                    if r is None:
                        self.log("引擎 #%d 状态丢失 (换种子/新一局), 重扫..." % t.engine["id"])
                        self.request_rescan(1.5)
                except Exception:
                    pass
            time.sleep(POLL_INTERVAL)

    # ---------------- 显示 ----------------

    @staticmethod
    def _mark(frac):
        return "*" if frac < THRESHOLD else " "

    def render(self):
        with self.lock:
            trackers = list(self.trackers.values())
            sel = self.trackers.get(self.selected_id)
            msg = self.message
            via = self.via
        os.system("cls")
        print("=" * 64)
        print(" 真理之眼 · 明日方舟实时 RNG 序列追踪    %s" % time.strftime("%H:%M:%S"))
        print("=" * 64)
        print(" 进程: %s    定位: %s    %s" % (self.process or "未连接", via or "--", msg))
        print("-" * 64)
        for t in trackers:
            e = t.engine
            cur = ">>" if sel and e["id"] == sel.engine["id"] else "  "
            print(" %s #%d %-44s 游标=%-4s 消耗=%-7d %.1f/s" % (
                cur, e["id"], e["label"][:44], str(t.snapshot(0, 0)["cursor"]),
                t.total, t.rate()))
        if not sel:
            print("\n 等待引擎 ...")
            return
        snap = sel.snapshot(history_len=HISTORY_SHOW, predict_len=PREDICT_COUNT)
        print("-" * 64)
        print(" 最近消耗 (旧 -> 新, * 表示 <%.0f%% 触发):" % (THRESHOLD * 100))
        hist = snap["history"]
        if not hist:
            print("   (暂无 — 等待游戏消耗随机数, 让干员攻击几次)")
        for p in hist:
            print("   #%-6d  %.6f%s  (%d)" % (p["seq"], p["frac"], self._mark(p["frac"]), p["raw"]))
        print("-" * 64)
        print(" 未来 %d 发预测 (下一发在最左):" % PREDICT_COUNT)
        preds = snap["predictions"]
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

    def display_loop(self, interval):
        while not self.stop_event.is_set():
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

    app = ConsoleApp(args)

    print("[*] 连接 %s 后端 ..." % args.backend)
    while not app.attach():
        print("[!] 连接失败, 10 秒后重试 (Ctrl+C 退出) ...")
        time.sleep(10)
    print("[*] 已连接: %s" % app.process)

    app.scan()
    threading.Thread(target=app.poll_loop, daemon=True).start()
    try:
        app.display_loop(args.interval)
    except KeyboardInterrupt:
        app.stop_event.set()


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
