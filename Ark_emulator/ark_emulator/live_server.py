"""Real-time battle output server (HTTP + SSE + WebSocket-style push).

Runs a thread that advances the simulator and broadcasts every snapshot
and event batch to connected clients (JSON lines / SSE). Used by the AI
layer or any external consumer to observe the battle in real time.

Run::

    from ark_emulator.live_server import LiveServer
    srv = LiveServer(sim, port=8794, speed=1.0)
    srv.start()

Clients:
  - GET /snapshot       -> latest full snapshot
  - GET /events?since=N -> events after seq N
  - GET /stream         -> SSE stream of {snapshot, events} batches
  - POST /action        -> deploy/withdraw/skill JSON control
"""

import json
import queue
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .api import Simulator


class LiveServer:
    """Advances a Simulator in a background thread and broadcasts state."""

    def __init__(self, sim, port=8794, speed=1.0, tick_interval=0.01,
                 level=None, squad=None, custom_enemies=None):
        self.sim = sim
        self.port = port
        self.speed = speed
        self.tick_interval = tick_interval
        self._level = level
        self._squad = squad
        self._custom = custom_enemies
        self._queue = queue.Queue()
        self._snapshot = None
        self._subscribers = set()
        self._thread = None
        self._httpd = None
        self._last_seq = 0
        self._running = False

    def _enemy_search(self, q=""):
        """Search the enemy roster (bundle enemyRoster: key -> {name,...})."""
        try:
            roster = self.sim.store.bundle.get("enemyRoster") or {}
        except Exception:
            roster = {}
        q = (q or "").strip().lower()
        out = []
        for key, info in roster.items():
            name = (info or {}).get("name") or key
            if q and q not in key.lower() and q not in str(name).lower():
                continue
            out.append({"key": key, "name": name})
            if len(out) >= 300:
                break
        out.sort(key=lambda x: (not x["key"].startswith(q), x["key"]))
        return out

    def reload(self, level_id):
        """Recreate the simulator for a new level (keeps server running)."""
        try:
            from .api import Simulator
            sim = Simulator(level_id=level_id, squad=self._squad,
                            custom_enemies=self._custom)
            # eagerly build the battle so immediate /status /snapshot calls
            # do not stall on lazy BattleController construction
            _ = sim.battle
            self.sim = sim
        except Exception as e:
            print(f"[live_server] reload failed: {e}")

    def reload_custom(self, level_dict):
        """Run a custom level definition (keeps server running)."""
        try:
            from .api import Simulator
            sim = Simulator(level_id="custom", squad=self._squad,
                            custom_enemies=self._custom,
                            custom_level=level_dict)
            _ = sim.battle
            self.sim = sim
            self._level = "custom"
        except Exception as e:
            print(f"[live_server] custom reload failed: {e}")

    # ---- lifecycle ----
    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        handler = self._make_handler()
        self._httpd = ThreadingHTTPServer(("127.0.0.1", self.port), handler)
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()

    def stop(self):
        self._running = False
        if self._httpd:
            try:
                self._httpd.shutdown()
            except Exception:
                pass
            try:
                self._httpd.server_close()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=1.0)

    # ---- simulator loop ----
    def _run(self):
        while self._running:
            try:
                if not self.sim.battle.paused and not self.sim.battle.finished:
                    self.sim.battle.tick_once()
                snap = self.sim.snapshot()
                batch = {
                    "tick": self.sim.tick,
                    "t": round(self.sim.tick / 30.0, 4),
                    "snapshot": snap,
                }
                self._snapshot = snap
                self._broadcast(batch)
            except Exception as e:
                print(f"[live_server] {e}")
            time.sleep(self.tick_interval / max(0.1, self.speed))

    def _broadcast(self, batch):
        for sub in list(self._subscribers):
            try:
                sub.put_nowait(batch)
            except queue.Full:
                pass

    # ---- http ----
    def _make_handler(self):
        srv = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send_json(self, obj, status=200):
                body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == "/" or self.path.startswith("/index"):
                    from .web_ui import page_html
                    body = page_html().encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                elif self.path.startswith("/new"):
                    from urllib.parse import parse_qs, urlparse
                    q = parse_qs(urlparse(self.path).query)
                    lid = (q.get("level") or [None])[0]
                    if lid:
                        srv.reload(lid)
                    self._send_json({"ok": True, "level": lid})
                elif self.path.startswith("/snapshot"):
                    self._send_json(srv.sim.snapshot())
                elif self.path.startswith("/events"):
                    since = 0
                    if "since=" in self.path:
                        try:
                            since = int(self.path.split("since=")[1].split("&")[0])
                        except ValueError:
                            pass
                    self._send_json({"events": srv.sim.snapshot(
                        since_seq=since)["events"]})
                elif self.path.startswith("/stream"):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    q = queue.Queue(maxsize=100)
                    srv._subscribers.add(q)
                    try:
                        while True:
                            batch = q.get(timeout=5)
                            line = "data: " + json.dumps(
                                batch, ensure_ascii=False) + "\n\n"
                            self.wfile.write(line.encode("utf-8"))
                            self.wfile.flush()
                    except queue.Empty:
                        pass
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                    finally:
                        srv._subscribers.discard(q)
                elif self.path.startswith("/levels"):
                    from .config import list_levels, search_levels
                    if "q=" in self.path:
                        kw = self.path.split("q=")[1].split("&")[0]
                        self._send_json({"hits": search_levels(kw)})
                    else:
                        self._send_json({"levels": list_levels()})
                elif self.path.startswith("/enemies"):
                    q = ""
                    if "q=" in self.path:
                        q = self.path.split("q=")[1].split("&")[0]
                    self._send_json({"hits": srv._enemy_search(q)})
                elif self.path == "/editor":
                    from .web_ui import editor_html
                    body = editor_html().encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                elif self.path == "/custom-levels":
                    from .custom_levels import list_levels
                    self._send_json({"levels": list_levels()})
                elif self.path == "/tiles":
                    from .tile_effects import load_tile_defs
                    defs = load_tile_defs()
                    self._send_json({"tiles": sorted(defs.keys())})
                elif self.path == "/config":
                    self._send_json({"squad": srv._squad,
                                     "custom_enemies": srv._custom})
                elif self.path == "/status":
                    self._send_json({
                        "tick": srv.sim.tick,
                        "paused": srv.sim.battle.paused,
                        "finished": srv.sim.battle.finished,
                        "lifePoint": srv.sim.battle.life_point,
                    })
                else:
                    self._send_json({"error": "not found"}, 404)

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length) or b"{}")
                if self.path == "/custom-level":
                    from .custom_levels import save_level
                    lv = body.get("level") or {}
                    path = save_level(lv)
                    if body.get("run"):
                        srv.reload_custom(lv)
                    self._send_json({"ok": True, "name": lv.get("name"),
                                     "path": path})
                elif self.path == "/config":
                    if "squad" in body:
                        srv._squad = body.get("squad") or []
                    if "custom_enemies" in body:
                        srv._custom = body.get("custom_enemies") or []
                    # apply to current sim if it supports squad refresh
                    try:
                        if hasattr(srv.sim, "squad"):
                            srv.sim.squad = srv._squad
                            srv.sim.custom_enemies = srv._custom
                            # rebuild battle with new squad/custom
                            srv.reload(srv.sim.level_id)
                    except Exception as e:
                        print(f"[live_server] config apply failed: {e}")
                    self._send_json({"ok": True, "squad": srv._squad,
                                     "custom_enemies": srv._custom})
                elif self.path == "/action":
                    act = body.get("action")
                    if act == "deploy":
                        ok, res = srv.sim.deploy(
                            body.get("charId"), body.get("row", 0),
                            body.get("col", 0), body.get("direction", 1))
                        self._send_json({"ok": ok, "result": res})
                    elif act == "withdraw":
                        ok, res = srv.sim.withdraw(body.get("instId"))
                        if not ok:
                            ok, res = srv.sim.withdraw_token(
                                body.get("instId"))
                        self._send_json({"ok": ok, "result": res})
                    elif act == "summon":
                        ok, res = srv.sim.deploy_summon(
                            body.get("charId"), body.get("row", 0),
                            body.get("col", 0), body.get("direction", 1))
                        self._send_json({"ok": ok, "result": res})
                    elif act == "deploy_gained":
                        ok, res = srv.sim.deploy_gained_token(
                            body.get("tokenKey"), body.get("row", 0),
                            body.get("col", 0), body.get("direction", 1))
                        self._send_json({"ok": ok, "result": res})
                    elif act == "skill":
                        ok, res = srv.sim.activate_skill(
                            body.get("instId"), body.get("skillIndex", 0))
                        self._send_json({"ok": ok, "result": res})
                    elif act == "pause":
                        srv.sim.pause()
                        self._send_json({"ok": True})
                    elif act == "resume":
                        srv.sim.resume()
                        self._send_json({"ok": True})
                    elif act == "step":
                        n = int(body.get("n", 1) or 1)
                        snap = srv.sim.step(n)
                        self._send_json({"ok": True, "snapshot": snap})
                    else:
                        self._send_json({"error": "unknown action"}, 400)
                else:
                    self._send_json({"error": "not found"}, 404)

        return H
