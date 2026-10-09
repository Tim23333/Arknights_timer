"""Local Web UI host: Qt command dispatch, immutable state and app lifecycle.

HTTP threads never call widgets directly. A queued Qt signal executes each
command on the owner thread; timed-out requests are cancelled before execution.
"""
from __future__ import annotations

import copy
import threading
import time
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal, Slot, Qt

from ..field_policy import FIELD_REGISTRY
from ..enemy_ui import ENEMY_COLUMN_DEFS, format_column_value
from ..character_ui import CHARACTER_COLUMN_DEFS, format_character_column, build_character_overview
from ..version import VERSION
from .webui_server import WebUiServer
from .adb_selection import AdbSelection
from .runtime_diagnostics import RuntimeDiagnostics
from .webui_stream import LatestStream


class WebUiRuntime(QObject):
    """Serve the new UI while existing workers own game memory and sampling."""
    request = Signal(object)
    sourceChanged = Signal()

    def __init__(self, window, *, port=8768):
        super().__init__(window)
        self.window = window
        self.adb_selection = AdbSelection(window)
        self.diagnostics = RuntimeDiagnostics(window)
        self._lock = threading.RLock()
        self._state = {}
        self._streams = {key: LatestStream() for key in ('clock', 'modules')}
        self._stream_stop = threading.Event()
        self._module_pending = threading.Event()
        self._stream_threads = []
        self._values = {}
        self._values_signature = None
        self._versions = {}
        # A restarted backend must explicitly clear every previously visible
        # source even before scanning. Otherwise reconnect retains the old map.
        self._source_keys = {'stage', 'enemies', 'enemy_pathing', 'characters',
                             'enemy_detail', 'character_detail', 'deploy', 'rng', 'quality'}
        self._module_keys = set(self._source_keys)
        self._columns = {"enemy": self._column_defs("enemy", ENEMY_COLUMN_DEFS),
                         "character": self._column_defs("character", CHARACTER_COLUMN_DEFS)}
        self.request.connect(self._execute, Qt.ConnectionType.QueuedConnection)
        self.sourceChanged.connect(self._refresh_source, Qt.ConnectionType.QueuedConnection)
        self.server = WebUiServer(
            self.state, self.policy,
            lambda fields, generation: self.call("policy", {"fields": fields, "generation": generation}),
            lambda action, params: self.call(action, params), self.docs, port=port,
            asset_dir=self._root() / "webui", download=self.diagnostics.download,
            streams=self._streams)
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.refresh)
        self.refresh()

    @staticmethod
    def _column_defs(domain, definitions):
        return [{**column, "path": FIELD_REGISTRY[f"{domain}.{column['key']}"].paths[0]
                 if f"{domain}.{column['key']}" in FIELD_REGISTRY
                 and FIELD_REGISTRY[f"{domain}.{column['key']}"].paths else column['key']}
                for column in definitions]

    def start(self):
        url = self.server.start()
        if not self._stream_threads:
            for channel in self._streams:
                thread = threading.Thread(target=self._watch_source, args=(channel,),
                                          name='webui-' + channel, daemon=True)
                self._stream_threads.append(thread)
                thread.start()
        self.timer.start()
        return url

    def stop(self):
        self.timer.stop()
        self._stream_stop.set()
        for thread in self._stream_threads:
            thread.join(timeout=1.5)
        self.adb_selection.close()
        self.diagnostics.close()
        self.server.stop()

    def _watch_source(self, channel):
        """Observe existing accepted batches; never add game IO or touch widgets."""
        revision = 0
        api = self.window._websocket_api
        if api is None:
            return
        while not self._stream_stop.is_set():
            current, data = api.wait_local_update(channel, revision, timeout=.25)
            if current == revision or self._stream_stop.is_set():
                continue
            revision = current
            if channel == 'clock':
                self._streams[channel].publish('clock', data)
            elif not self._module_pending.is_set():
                # Coalesce Qt wakeups as well as network packets. While Qt is
                # busy, replace source snapshots rather than queue old frames.
                self._module_pending.set()
                self.sourceChanged.emit()

    @Slot()
    def _refresh_source(self):
        self._module_pending.clear()
        if not self._stream_stop.is_set():
            self.refresh()

    def state(self):
        with self._lock:
            result = copy.deepcopy(self._state)
        api = self.window._websocket_api
        if api is not None:
            result['clock'] = api.wait_local_update('clock', -1, timeout=0)[1] or {}
        return result

    @staticmethod
    def _root():
        return Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[3]

    def policy(self):
        return {**self.window._field_policy.to_dict(),
                "registry": [spec.to_dict() for spec in FIELD_REGISTRY.values() if spec.domain != "internal"]}

    def _character_overview(self, values, snapshot, policy):
        """Project the desktop's cumulative overview, including retired operators.

        History is deliberately last-known cumulative data, not a current HP or
        position. An invalidated source/generation must never revive it as live.
        Only local display policy applies; WS publishing is independent.
        """
        meta = values.get('characters', {}).get('meta', {})
        available = (meta.get('collectionState') == 'current'
                     and meta.get('policyGeneration') == policy.generation)
        enabled = lambda key: policy.enabled('character.' + key) and policy.enabled('character.' + key, 'display')
        result = {'available': available, 'meta': copy.deepcopy(meta), 'rows': [],
                  'damageAvailable': available and enabled('damage_total'),
                  'healingAvailable': available and enabled('healing_total'),
                  'globalTotal': None}
        if not available:
            return result
        history = self.window._character_stats_history
        characters = snapshot.get('characters', ())
        rows = build_character_overview([*characters, *history])
        metrics = {}
        for key, metric in (('damage_total', 'damage'), ('healing_total', 'healing')):
            eligible = [character for character in characters
                        if getattr(character, 'field_states', {}).get('character.' + key, {}).get(
                            'collectionState') in {'current', 'historical'}]
            metrics[metric] = {row['cid'] or row['name']: row[metric]
                               for row in build_character_overview([*eligible, *history])}
        for index, row in enumerate(rows):
            key = row['cid'] or row['name']
            result['rows'].append({'id': str(index),
                'name': row['name'] if enabled('name') else f'干员 {index + 1}',
                'damage': metrics['damage'].get(key) if result['damageAvailable'] else None,
                'healing': metrics['healing'].get(key) if result['healingAvailable'] else None})
        if enabled('global_total_damage'):
            summary = values.get('characters', {}).get('globalDamageSummary') or {}
            result['globalTotal'] = summary.get('globalDamageSummary')
        return result

    def refresh(self):
        window = self.window
        api = window._websocket_api
        policy = window._field_policy.snapshot()
        versions = api.local_versions() if api is not None else {}
        signature = (policy.generation, repr(window._enemy_dec), repr(window._character_dec))
        configuration_changed = signature != self._values_signature
        updated = {key for key in versions.keys() | self._versions.keys()
                   if configuration_changed or versions.get(key) != self._versions.get(key)}
        values = dict(self._values)
        for key in updated:
            values.pop(key, None)
        if updated and api is not None:
            values.update(api.local_snapshot(updated))
        ws = api.status_snapshot() if api is not None else {"state": "stopped", "enabled": False}
        ws["gameUrl"] = f"ws://127.0.0.1:{ws.get('port') or 8765}/v2/game"
        snapshot = getattr(window, '_webui_runtime_snapshot', {})
        for domain, key, formatter in (("enemy", "enemies", format_column_value),
                                       ("character", "characters", format_character_column)):
            if key not in updated:
                continue
            rows = values.get(key, {}).get("items", [])
            raw_rows = snapshot.get(key, ())
            from .websocket_api import entity_public_id
            by_id = {entity_public_id(domain, entity, index): entity
                     for index, entity in enumerate(raw_rows, 1)}
            for row in rows:
                entity = by_id.get(row.get("id"))
                if entity is None:
                    continue
                row["columns"] = {}
                for col in self._columns[domain]:
                    field_id = f"{domain}.{col['key']}"
                    if col['key'] in {"row", "detail"}:
                        continue
                    if not policy.enabled(field_id, "display") or not policy.enabled(field_id):
                        continue
                    record = getattr(entity, 'field_states', {}).get(field_id, {})
                    if record and record.get("state", record.get("collectionState")) not in {"current", "static", "historical"}:
                        row["columns"][col['key']] = "未采集" if not policy.enabled(field_id) else "不可用"
                        continue
                    decimals = window._enemy_dec if domain == "enemy" else window._character_dec
                    row["columns"][col['key']] = formatter(col['key'], entity, decimals)
        self._values, self._values_signature = values, signature
        self._versions = versions
        # Status values are copied on the Qt owner thread. HTTP only sees these
        # plain dictionaries, including when the WS service is disabled.
        result = {**values, "clock": values.get("battle", {}), "version": VERSION,
                  "characterOverview": self._character_overview(values, snapshot, policy)
                      if 'characters' in updated or configuration_changed
                      else self._state.get('characterOverview', {}),
                  "columns": self._columns, "policyGeneration": policy.generation,
                  "notifications": self.diagnostics.notifications(),
                  "service": {"ws": ws, "logs": self.diagnostics.metadata(),
                    "autoRefresh": copy.deepcopy(window._auto_refresh_status),
                    "enemy": window.lbl_enemy_status.text(),
                    "character": window.lbl_character_status.text(),
                    "deploy": window.lbl_deploy_status.text(),
                    "rng": window.lbl_rng_status.text(),
                    "adb": {"path": window._enemy_reader.mc.adb_path,
                            "serial": window._enemy_reader.mc.adb_serial}},
                  "options": {key: window._custom_options.get(key) for key in
                              ("toast", "auto_detect_stage_change", "auto_addressing", "websocket_api")}}
        with self._lock:
            self._state = result
        # Modules are independently versioned; only changed encoded values go
        # over the wire. Never send the clock/battle via this bulky channel.
        modules = {key: value for key, value in result.items() if key not in {'clock', 'battle'}}
        for key in self._module_keys | modules.keys():
            if key in self._source_keys and key not in updated and not configuration_changed:
                continue
            if key == 'characterOverview' and 'characters' not in updated and not configuration_changed:
                continue
            self._streams['modules'].publish(key, modules.get(key))
        self._module_keys = set(modules) | self._source_keys

    def call(self, action, params):
        request = {"action": action, "params": params, "event": threading.Event(),
                   "deadline": time.monotonic() + 4.0, "cancelled": False}
        self.request.emit(request)
        if not request["event"].wait(4.0):
            request["cancelled"] = True
            raise TimeoutError("Timeline 主线程未及时处理命令，请稍后重试")
        if "error" in request:
            raise request["error"]
        return request.get("result", {})

    @Slot(object)
    def _execute(self, request):
        if request["cancelled"] or time.monotonic() >= request["deadline"]:
            request["event"].set()
            return
        try:
            request["result"] = self._command(request["action"], request["params"])
            self.refresh()
        except Exception as exc:
            request["error"] = exc
        finally:
            request["event"].set()

    def _command(self, action, params):
        w = self.window
        if action.startswith('logs-'):
            return self.diagnostics.command(action, params)
        if action == "policy":
            if params.get("generation") != w._field_policy.snapshot().generation:
                raise ValueError("策略已被其他窗口更新，请刷新后重试")
            w._field_policy.commit(params["fields"])
            return self.policy()
        handlers = {"enemy-scan": w._on_enemy_scan, "character-scan": w._on_character_scan,
                    "enemy-stop": w._stop_enemy_poll, "character-stop": w._stop_enemy_poll,
                    "deploy-scan": w._on_deploy_scan, "deploy-stop": w._on_deploy_stop,
                    "rng-scan": w._on_rng_scan, "rng-stop": w._on_rng_stop,
                    "timer": w._on_open_timer_tool, "mini": w._enter_enemy_mini_mode}
        if action in handlers:
            if action.endswith("-scan"):
                if self.adb_selection.switching:
                    raise ValueError("正在切换 ADB，请等待旧监控停止完成")
                path = w._enemy_reader.mc.adb_path
                if not path or not Path(path).is_file():
                    raise ValueError("请先设置有效的 ADB 路径，再启动扫描")
            handlers[action]()
            return {"accepted": True, "message": "命令已交给 Timeline；扫描结果请查看模块状态"}
        if action == "auto-address-once":
            if self.adb_selection.switching:
                raise ValueError("正在切换 ADB，请等待切换完成后再寻址")
            w._start_guest_addressing_once()
            return {"accepted": True, "message": "已启动单次自动寻址；结果请查看游戏时钟和气泡提示"}
        if action == "timeline":
            if w._timeline_httpd is None and w._timeline_static_dir() is None:
                raise ValueError("排轴工具资源尚未构建，请先构建已有 frontend")
            w._on_open_timeline_tool()
            return {"accepted": True, "message": "排轴工具已在浏览器打开"}
        if action in {"cache", "stage-export", "deploy-export"}:
            if action == "cache":
                payload = w._battle_cache.bundle()
            elif action == "stage-export":
                payload = w._battle_cache.stage_export()
                if not payload:
                    raise ValueError("尚无已采集的关卡数据，请先扫描关卡")
            else:
                payload = w._build_deploy_export_payload(w._deploy_events, w._deploy_stage_info)
            return {"payload": payload, "filename": action + ".json"}
        if action == "detail":
            kind = params.get("kind")
            if kind not in {"enemy", "character"}:
                raise ValueError("未知对象类型")
            if params.get("id") is None:
                if w._enemy_poll is not None:
                    target = w._enemy_poll.set_detail_target if kind == "enemy" else w._enemy_poll.set_character_detail_target
                    target(0)
                return {"accepted": True}
            from .websocket_api import entity_public_id
            rows = getattr(w, '_webui_runtime_snapshot', {}).get("enemies" if kind == "enemy" else "characters", [])
            entity = next((row for index, row in enumerate(rows, 1)
                           if entity_public_id(kind, row, index) == params.get("id")), None)
            if entity is None or w._enemy_poll is None:
                raise ValueError("对象已离场或监控未启动")
            target = w._enemy_poll.set_detail_target if kind == "enemy" else w._enemy_poll.set_character_detail_target
            target(entity.addr)
            return {"accepted": True}
        if action == "precision":
            kind, places = params.get("kind"), params.get("places")
            if kind not in {"enemy", "character"} or isinstance(places, bool) or not isinstance(places, int) or not 0 <= places <= 6:
                raise ValueError("小数位数必须为 0–6 的整数")
            decimals = w._enemy_dec if kind == "enemy" else w._character_dec
            decimals.update({key: places for key in decimals})
            decimals["default"] = places
            return {"accepted": True}
        if action == "ws-toggle":
            enabled = params.get("enabled")
            if not isinstance(enabled, bool):
                raise ValueError("enabled 必须为布尔值")
            w.chk_websocket_api.setChecked(enabled)
            return {"accepted": True}
        if action == "rng-count":
            count = params.get("count")
            if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= 500:
                raise ValueError("预测数必须为 1–500 的整数")
            w.rng_pred_spin.setValue(count)
            return {"accepted": True}
        if action == "setting":
            if self.adb_selection.switching:
                raise ValueError("正在切换 ADB，请完成后再修改运行设置")
            section, key, value = params.get("section"), params.get("key"), params.get("value")
            toggles = {"auto_detect_stage_change": w.chk_auto_refresh,
                       "auto_addressing": w.chk_auto_addressing,
                       "toast": w.chk_toast_enabled}
            if key == "enabled" and section in toggles and isinstance(value, bool):
                toggles[section].setChecked(value)
                return {"accepted": True}
            if section == "toast" and key == "duration_ms" and isinstance(value, dict):
                from ..toast import LEVELS
                if set(value) - set(LEVELS) or any(isinstance(n, bool) or not isinstance(n, int)
                                                  or not 10 <= n <= 120000 for n in value.values()):
                    raise ValueError("气泡时长必须为 10–120000 毫秒")
                current = (w._custom_options.get("toast") or {}).get("duration_ms", {})
                w._custom_options.set(section, key, {**current, **value})
                return {"accepted": True}
            raise ValueError("未知运行设置")
        if action == "adb":
            if params.get("path") is None:
                return {"path": w._enemy_reader.mc.adb_path, "serial": w._enemy_reader.mc.adb_serial}
            return self.adb_selection.start("apply", params)
        if action in {"adb-detect", "adb-devices", "adb-browse"}:
            return self.adb_selection.start(action.removeprefix("adb-"), params)
        if action == "adb-job":
            return self.adb_selection.snapshot(params.get("id"))
        if action == "adb-cancel":
            return self.adb_selection.cancel(params.get("id"))
        raise ValueError(f"未知命令：{action}")

    def docs(self, name):
        if name == "guide":
            path = self._root() / "docs" / "新手使用教程.md"
            return path.read_text(encoding="utf-8") if path.is_file() else "# 使用教程\n\n教程文件尚未安装。"
        from .websocket_docs import api_documentation
        return api_documentation()
