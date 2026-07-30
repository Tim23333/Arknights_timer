"""RNG 追踪服务: 连接 / 定位 / 轮询 / 地址缓存 / 快照 的一站式封装

与展示层完全解耦, 供控制台 UI / tkinter UI / 其他程序复用。

用法:

    from rng_service import RngService
    import time

    svc = RngService(prefer_role="imp")          # adb 后端 (默认, 免管理员)
    while not svc.attach():
        time.sleep(10)                            # 连接失败重试
    svc.locate()                                  # 缓存 -> 静态链 (-> 可选启发式)
    svc.start()                                   # 后台轮询线程
    ...
    snap = svc.snapshot(history_len=50, predict_len=12)
    # snap["engines"]    各引擎摘要 (label/cursor/total/rate/status)
    # snap["selected"]   选中引擎详情: history(已消耗序列) + predictions(未来序列)
    #                    + cursor(游标, 指向下一个随机数位置) 等
    svc.stop()

测试/嵌入时可直接注入自己的 reader (实现 read/regions 即可, 如 FakeMem):

    svc = RngService(reader=my_reader, use_cache=False)

定位成功后地址缓存进 ak_rng_cache.pkl (与 memscan.validate_engine 四重校验,
游戏重启自动失效); use_cache=False 时读写均禁用。
"""

import os
import pickle
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import memscan
from tracker import EngineTracker

if getattr(sys, "frozen", False):
    # 打包环境: 缓存放 exe 同目录 (__file__ 指向 _MEIPASS 临时目录, 每次启动即丢失)
    CACHE_FILE = os.path.join(os.path.dirname(sys.executable), "ak_rng_cache.pkl")
else:
    CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "ak_rng_cache.pkl")   # 定位地址缓存
RESCAN_DELAY = 5.0     # 未定位到引擎时的自动重试间隔 (秒)
WATCH_INTERVAL = 2.0   # 静态槽看门狗周期 (秒): 检测新一局对象更换


class RngService:
    """线程模型: start() 起后台轮询线程; 数据经 snapshot() 锁保护读取。"""

    def __init__(self, backend="adb", package="com.hypergryph.arknights",
                 adb_path=None, adb_serial=None, process_names=None, prefer_role="imp",
                 use_cache=True, allow_heuristic=False, poll_interval=0.005,
                 reader=None, on_status=None):
        self.backend = backend
        self.package = package
        self.adb_path = adb_path
        self.adb_serial = adb_serial
        self.process_names = process_names
        self.prefer_role = prefer_role
        self.use_cache = use_cache
        self.allow_heuristic = allow_heuristic
        self.poll_interval = poll_interval
        self.reader = reader                # 注入 reader 时跳过 attach
        self.process = ""
        self.via = ""
        self.status_msg = "初始化..."
        self._on_status = on_status or (lambda m: None)
        self._lock = threading.Lock()
        self._trackers = {}                 # engine_id -> EngineTracker
        self._selected_id = None
        self._stop = threading.Event()
        self._rescan = threading.Event()
        self._rescan_lock = threading.Lock()
        self._rescan_due = None
        self._rescan_generation = 0
        self._thread = None

    # ---------------- 状态 ----------------

    def _status(self, msg):
        self.status_msg = msg
        self._on_status(msg)

    # ---------------- 连接 ----------------

    def attach(self):
        """连接一次 (成功 True); 重试策略由调用方决定。注入 reader 时恒 True。"""
        if self.reader is not None:
            return True
        if self.backend == "adb":
            try:
                from adb_reader import AdbReader
                self.reader = AdbReader.connect(
                    adb_path=self.adb_path, package=self.package,
                    status=self._status, adb_serial=self.adb_serial)
                self.package = self.reader.mc.package
                self.adb_serial = self.reader.mc.adb_serial
                self.process = "%s / %s (pid %d)" % (
                    self.adb_serial, self.package, self.reader.mc.pid)
                return True
            except Exception as ex:
                self._status("adb 连接失败: %s" % ex)
                self.reader = None
                return False
        try:
            import pymem
        except ImportError:
            self._status("未安装 pymem")
            return False
        for name in (self.process_names or memscan.EMULATOR_PROCESSES):
            try:
                pm = pymem.Pymem(name)
                self.reader = memscan.PymemReader(pm)
                self.process = name
                return True
            except Exception:
                continue
        self._status("未找到模拟器进程")
        return False

    # ---------------- 定位 ----------------

    def locate(self):
        """定位引擎并重建 tracker 组 (缓存优先, 成功写缓存)。"""
        self._status("扫描定位 RNG 引擎 ...")
        if self.backend == "adb" and self.reader is not None:
            try:
                self.reader.ensure_alive(status=self._status)
            except Exception:
                pass
        engines = self._try_cache() if self.use_cache else []
        if engines:
            self.via = "cache"
        else:
            try:
                if self.allow_heuristic:
                    engines, self.via = memscan.locate_engines(
                        self.reader, status=self._status)
                else:
                    # 默认只走静态链: 未开战时启发式会捞到几百个无关 System.Random
                    engines = memscan.locate_battle_random(
                        self.reader, status=self._status)
                    self.via = "static-chain"
            except Exception as ex:
                self._status("扫描异常: %s" % ex)
                return False
            if engines:
                self._save_cache(engines)
        with self._lock:
            self._trackers = {e["id"]: EngineTracker(self.reader, e) for e in engines}
            self._selected_id = None
            for t in self._trackers.values():
                if t.engine["role"] == self.prefer_role:
                    self._selected_id = t.engine["id"]
                    break
            if self._selected_id is None and self._trackers:
                self._selected_id = next(iter(self._trackers))
        if not engines:
            self._status("未定位到引擎 (未开战?) — %d 秒后自动重试" % RESCAN_DELAY)
            self.request_rescan(RESCAN_DELAY)
            return False
        sel = self._trackers.get(self._selected_id)
        self._status("定位方式=%s, 跟踪引擎 #%d: %s" %
                     (self.via, self._selected_id, sel.engine["label"]))
        return True

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
            self._status("地址缓存命中 (%d 个引擎), 跳过扫描" % len(ok))
        return ok

    def _save_cache(self, engines):
        try:
            with open(CACHE_FILE, "wb") as f:
                pickle.dump({"time": time.time(),
                             "package": self.package,
                             "engines": engines}, f)
        except Exception:
            pass

    # ---------------- 轮询 ----------------

    def start(self):
        """启动后台轮询线程 (幂等)。"""
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        with self._rescan_lock:
            self._rescan_generation += 1
            self._rescan_due = None
            self._rescan.clear()

    def request_rescan(self, delay=0):
        """安排一次重扫；已有更早任务时去重，更紧急的请求会替换较晚任务。"""
        delay = max(0.0, float(delay))
        due = time.monotonic() + delay
        with self._rescan_lock:
            if self._stop.is_set() or self._rescan.is_set():
                return False
            if self._rescan_due is not None and self._rescan_due <= due:
                return False
            self._rescan_generation += 1
            generation = self._rescan_generation
            self._rescan_due = due

        def fire():
            remaining = max(0.0, due - time.monotonic())
            if remaining and self._stop.wait(remaining):
                return
            with self._rescan_lock:
                if (self._stop.is_set()
                        or generation != self._rescan_generation):
                    return
                self._rescan_due = None
                self._rescan.set()

        if delay == 0:
            fire()
        else:
            threading.Thread(target=fire, daemon=True).start()
        return True

    def _poll_loop(self):
        last_watch = 0.0
        while not self._stop.is_set():
            if self._rescan.is_set():
                self._rescan.clear()
                self.locate()
            for t in self.trackers():
                try:
                    r = t.poll()
                    if r is None:
                        if self.request_rescan(1.5):
                            self._status("引擎 #%d 状态丢失 (换种子/新一局), 重扫..."
                                         % t.engine["id"])
                except Exception:
                    pass
            now = time.time()
            if now - last_watch >= WATCH_INTERVAL:
                last_watch = now
                self._watch_objects()
            time.sleep(self.poll_interval)

    def _watch_objects(self):
        """静态槽反查: 重新开战后 BattleController 静态字段指向新建的
        wrapper+引擎对象, 旧对象内存原样残留时轮询观测不到变化 (既不消耗
        也不 lost) —— 必须比对静态槽当前指向才能发现。"""
        for t in self.trackers():
            wa = t.engine.get("watch_addr")
            if not wa:
                continue
            try:
                cur = memscan.resolve_engine_obj(self.reader, wa)
            except Exception:
                continue
            if cur is not None and cur != t.engine["obj"]:
                if self.request_rescan(0.5):
                    self._status("检测到引擎对象更换 (新一局), 重新定位 ...")
                return

    # ---------------- 数据 (展示层读取入口) ----------------

    def trackers(self):
        with self._lock:
            return list(self._trackers.values())

    def selected(self):
        with self._lock:
            return self._trackers.get(self._selected_id)

    def select(self, engine_id):
        with self._lock:
            if engine_id in self._trackers:
                self._selected_id = engine_id
                return True
        return False

    def select_role(self, role):
        """按角色选引擎 ("imp"=关键随机 / "trivial"=表现随机)。"""
        with self._lock:
            for eid, t in self._trackers.items():
                if t.engine["role"] == role:
                    self._selected_id = eid
                    return True
        return False

    def snapshot(self, history_len=50, predict_len=12):
        """一帧完整展示数据: 状态行 + 各引擎摘要 + 选中引擎历史/预测/游标。"""
        with self._lock:
            trackers = list(self._trackers.values())
            sel = self._trackers.get(self._selected_id)
            sel_id = self._selected_id
        engines = []
        for t in trackers:
            s = t.snapshot(0, 0)
            engines.append({k: s[k] for k in
                            ("id", "label", "role", "cursor", "total", "rate", "status")})
        return {
            "process": self.process,
            "via": self.via,
            "status": self.status_msg,
            "engines": engines,
            "selected_id": sel_id,
            "selected": sel.snapshot(history_len, predict_len) if sel else None,
        }
