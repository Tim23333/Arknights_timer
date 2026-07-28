"""代理作战序列 Web 可视化服务

用法:
    python -m tools.deploy_tracker.web_server [--port 8793]

启动后自动连接模拟器进程并定位 BattleLogger / ReplayController,
浏览器打开 http://127.0.0.1:8793/ 即可实时查看部署/技能/撤退时间轴,
支持一键导出 JSON。

接口:
    GET  /            可视化页面
    GET  /api/state   当前状态 + 事件序列 (JSON)
    GET  /api/export  导出完整序列 (JSON 附件下载)
    POST /api/scan    重新定位 (进新关卡/链失效时使用)
"""

import argparse
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.deploy_tracker.ak_deploy_reader import DeployTrackerReader
from tools.enemy_health.memcore import MemCore

STATIC_DIR = Path(__file__).resolve().parent / "static"


class TrackerService:
    """连接管理 + 定位 + 数据读取 (线程安全)。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._mc = None
        self._reader = None
        self.process_name = ""
        self.message = "等待模拟器/游戏进程 ..."
        self._stage_snapshot = {}
        self._scanning = False
        self._stop = False
        self._last_ensure = 0.0

    # ---- 后台连接循环 ----

    def run(self):
        while not self._stop:
            try:
                self._tick()
            except Exception as exc:
                self.message = f"内部错误: {exc}"
            time.sleep(2)

    def stop(self):
        self._stop = True
        if self._reader is not None:
            self._reader.close()

    def _tick(self):
        with self._lock:
            if self._mc is None:
                self._try_attach()
                return
            if self._reader is None or self._scanning:
                return
            now = time.time()
            located = bool(self._reader._logs_list_addr or
                           self._reader._journal_logs_list_addr)
            if located:
                # 已锁定: 每 5s 廉价校验链, 失效则后台重扫
                if now - self._last_ensure > 5:
                    self._last_ensure = now
                    if not self._reader.is_chain_valid():
                        self.message = "地址链失效 (关卡结束?), 重新定位 ..."
                        self.start_scan()
            else:
                # 未锁定: 每 60s 自动重试一次全量定位
                if now - self._last_ensure > 60:
                    self._last_ensure = now
                    self.start_scan()

    def _try_attach(self):
        try:
            mc = MemCore()
            pid = mc.connect()
        except Exception as exc:
            self._mc = None
            self.message = f"未连接: {exc}"
            return
        self._mc = mc
        self.process_name = f"{mc.package} (pid {pid})"
        self._reader = DeployTrackerReader(mc)
        self._reader.set_stage_callback(self._on_stage)
        self.message = "已连接游戏进程, 定位中 ..."
        self.start_scan()

    def _on_stage(self, info):
        """扫描线程的阶段 1 回调；此时 API 不触碰尚在扫描的内存通道。"""
        self._stage_snapshot = dict(info or {})
        stage = self._stage_snapshot
        label = " ".join(x for x in (stage.get("code"), stage.get("name")) if x)
        self.message = f"已识别关卡 {label or stage.get('levelId', '')}, 正在定位操作记录 ..."

    def start_scan(self):
        """后台触发一次定位。"""
        if self._reader is None or self._scanning:
            return False
        self._scanning = True
        self._stage_snapshot = {}
        self.message = "阶段 1/2: 正在扫描关卡信息 ..."

        def task():
            try:
                # locate 扫描期间 snapshot() 返回阶段缓存，不并发使用同一 TCP 内存通道。
                ok = self._reader.locate()
                self.message = ("定位成功, 实时读取中" if ok
                                else "定位失败 — 请确认已进入作战关卡后点「重新定位」")
            except Exception as exc:
                self.message = f"定位异常: {exc}"
            finally:
                self._last_ensure = time.time()
                self._scanning = False

        threading.Thread(target=task, daemon=True).start()
        return True

    # ---- 数据 ----

    def snapshot(self):
        with self._lock:
            base = {
                "connected": self._mc is not None,
                "processName": self.process_name,
                "scanning": self._scanning,
                "message": self.message,
            }
            if self._reader is None:
                return base
            if self._scanning:
                stage = dict(self._stage_snapshot)
                base.update({
                    "located": False,
                    "stageLocated": bool(stage.get("stageId") or stage.get("levelId")),
                    "stageId": stage.get("stageId", ""),
                    "levelId": stage.get("levelId", ""),
                    "stageCode": stage.get("code", ""),
                    "stageName": stage.get("name", ""),
                    "zoneId": stage.get("zoneId", ""),
                    "stage": stage,
                })
                return base
            try:
                state = self._reader.get_state()
            except Exception as exc:
                base["message"] = f"读取失败: {exc}"
                return base
            base.update(state)
            return base


class ApiHandler(BaseHTTPRequestHandler):
    service: TrackerService = None  # 由 main 注入

    def log_message(self, fmt, *args):  # 静音访问日志
        pass

    def _send_json(self, obj, status=200, download_name=None):
        body = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        if download_name:
            self.send_header("Content-Disposition",
                             f'attachment; filename="{download_name}"')
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type):
        try:
            body = path.read_bytes()
        except OSError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._send_file(STATIC_DIR / "timeline.html", "text/html; charset=utf-8")
        elif path == "/api/state":
            self._send_json(self.service.snapshot())
        elif path == "/api/export":
            snap = self.service.snapshot()
            events = snap.get("journalEvents") or snap.get("events") or []
            payload = {
                "stageId": snap.get("stageId", ""),
                "levelId": snap.get("levelId", ""),
                "stage": snap.get("stage", {}),
                "source": snap.get("source", ""),
                "exportTime": time.strftime("%Y-%m-%d %H:%M:%S"),
                "journalMeta": snap.get("journalMeta", {}),
                "squad": snap.get("squad", []),
                "events": events,
            }
            stage = snap.get("stageId") or "unknown"
            fname = f"deploy_timeline_{stage}_{time.strftime('%H%M%S')}.json"
            self._send_json(payload, download_name=fname)
        else:
            self.send_error(404)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/scan":
            started = self.service.start_scan()
            self._send_json({"started": started})
        else:
            self.send_error(404)


def main():
    ap = argparse.ArgumentParser(description="代理作战序列 Web 可视化")
    ap.add_argument("--port", type=int,
                    default=int(os.getenv("AK_DEPLOY_PORT", "8793")))
    args = ap.parse_args()

    service = TrackerService()
    ApiHandler.service = service
    worker = threading.Thread(target=service.run, daemon=True)
    worker.start()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), ApiHandler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"代理作战序列可视化已启动: {url}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        service.stop()
        server.shutdown()


if __name__ == "__main__":
    main()
