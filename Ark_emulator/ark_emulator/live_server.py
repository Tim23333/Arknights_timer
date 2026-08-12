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
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .api import Simulator


class _ExclusiveThreadingHTTPServer(ThreadingHTTPServer):
    """Do not silently share a listening port with a stale web console.

    Windows may otherwise let two ``HTTPServer`` processes bind the same
    localhost port, leaving the browser connected to whichever process bound
    first.  That made freshly changed map/route code appear to have no effect.
    """

    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET,
                                   socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class LiveServer:
    """Advances a Simulator in a background thread and broadcasts state."""

    def __init__(self, sim, port=8794, speed=1.0, tick_interval=1.0 / 30.0,
                 level=None, squad=None, custom_enemies=None):
        self.sim = sim
        self.port = port
        self.speed = speed
        self.tick_interval = tick_interval
        self._level = level or getattr(sim, "level_id", None)
        self._squad = list(squad if squad is not None else
                           (getattr(sim, "squad", None) or []))
        self._custom = list(custom_enemies if custom_enemies is not None else
                           (getattr(sim, "custom_enemies", None) or []))
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

    def _operator_search(self, q=""):
        """Search deployable operators for the web squad/deployment UI."""
        try:
            characters = self.sim.store.characters
        except Exception:
            characters = {}
        q = (q or "").strip().lower()
        out = []
        for char_id, data in characters.items():
            if not char_id.startswith("char_") or not isinstance(data, dict):
                continue
            position = data.get("position")
            if position not in (1, 2):
                continue
            name = data.get("name") or char_id
            appellation = data.get("appellation") or ""
            haystack = "%s %s %s" % (char_id, name, appellation)
            if q and q not in haystack.lower():
                continue
            phases = data.get("phases") or []
            max_phase = max(0, len(phases) - 1)
            max_level = 1
            if phases:
                max_level = int((phases[max_phase] or {}).get("maxLevel") or 1)
            cost = 0
            try:
                frames = (phases[max_phase] or {}).get(
                    "attributesKeyFrames") or []
                cost = int((((frames[-1] or {}).get("data") or {}).get(
                    "cost")) or 0)
            except (IndexError, TypeError, ValueError):
                cost = 0
            skills = []
            for item in data.get("skills") or []:
                skill_id = (item or {}).get("skillId")
                if not skill_id:
                    continue
                skill = self.sim.store.character_skills.get(skill_id) or {}
                levels = skill.get("levels") or []
                skills.append({
                    "skillId": skill_id,
                    "name": ((levels[-1] or {}).get("name") if levels else
                             None) or skill_id,
                })
            out.append({
                "charId": char_id, "name": name,
                "appellation": appellation,
                "rarity": int(data.get("rarity") or 0) + 1,
                "position": position,
                "subProfession": data.get("subProfessionId"),
                "maxPhase": max_phase, "maxLevel": max_level,
                "cost": cost, "skills": skills,
            })
        out.sort(key=lambda x: (
            not (x["charId"].lower().startswith(q) or
                 str(x["name"]).lower().startswith(q)),
            -x["rarity"], x["charId"]))
        return out[:120] if q else out

    def update_squad(self, squad):
        """Update the live deck without resetting the current battle.

        Existing deployed units keep their instantiated attributes; future
        deployments use the new phase/level/skill configuration immediately.
        """
        cleaned = []
        seen = set()
        for item in squad or []:
            if not isinstance(item, dict):
                continue
            char_id = item.get("charId")
            if not char_id or char_id in seen:
                continue
            seen.add(char_id)
            cleaned.append(dict(item))
        self._squad = cleaned
        self.sim.squad = self._squad
        if getattr(self.sim, "_battle", None) is not None:
            self.sim.battle.squad = self._squad
        return self._squad

    def _level_meta(self):
        level_id = getattr(self.sim, "level_id", None)
        stages = self.sim.store.bundle.get("stages") or {}
        for stage_id, info in stages.items():
            if isinstance(info, dict) and info.get("levelId") == level_id:
                return {"stageId": stage_id, "levelId": level_id,
                        "name": info.get("name") or stage_id}
        return {"stageId": level_id, "levelId": level_id,
                "name": "自定义关卡" if level_id == "custom" else level_id}

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
            self._level = level_id
            self._last_seq = 0
            return True, None
        except Exception as e:
            print(f"[live_server] reload failed: {e}")
            return False, str(e)

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
            self._last_seq = 0
            return True, None
        except Exception as e:
            print(f"[live_server] custom reload failed: {e}")
            return False, str(e)

    # ---- lifecycle ----
    def start(self):
        # Bind first.  If another console owns the port, fail immediately
        # without leaving an invisible simulator thread behind.
        handler = self._make_handler()
        self._httpd = _ExclusiveThreadingHTTPServer(
            ("127.0.0.1", self.port), handler)
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
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
                # SSE batches carry incremental events.  Without since_seq the
                # complete event history would be serialized every frame.
                snap = self.sim.snapshot(since_seq=self._last_seq)
                events = snap.get("events") or []
                if events:
                    self._last_seq = max(e.get("seq", 0) for e in events)
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
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                request_path = self.path.split("?", 1)[0]
                if request_path == "/" or request_path.startswith("/index"):
                    from .web_ui import page_html
                    body = page_html().encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                elif self.path.startswith("/new"):
                    from urllib.parse import parse_qs, urlparse
                    q = parse_qs(urlparse(self.path).query)
                    lid = (q.get("level") or [None])[0]
                    if lid:
                        ok, error = srv.reload(lid)
                    else:
                        ok, error = False, "missing level"
                    self._send_json({"ok": ok, "level": lid,
                                     "error": error}, 200 if ok else 400)
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
                    from urllib.parse import parse_qs, urlparse
                    params = parse_qs(urlparse(self.path).query)
                    if "q" in params:
                        kw = (params.get("q") or [""])[0]
                        self._send_json({"hits": search_levels(kw)[:200]})
                    else:
                        self._send_json({"levels": list_levels()})
                elif self.path.startswith("/enemies"):
                    from urllib.parse import parse_qs, urlparse
                    q = (parse_qs(urlparse(self.path).query).get("q")
                         or [""])[0]
                    self._send_json({"hits": srv._enemy_search(q)})
                elif self.path.startswith("/operators"):
                    from urllib.parse import parse_qs, urlparse
                    q = (parse_qs(urlparse(self.path).query).get("q")
                         or [""])[0]
                    self._send_json({"hits": srv._operator_search(q)})
                elif self.path == "/editor":
                    from .web_ui import editor_html
                    body = editor_html().encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
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
                        "speed": srv.speed,
                        "level": srv._level_meta(),
                        "squad": srv._squad,
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
                        srv.update_squad(body.get("squad") or [])
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
                elif self.path == "/squad":
                    squad = srv.update_squad(body.get("squad") or [])
                    self._send_json({"ok": True, "squad": squad})
                elif self.path == "/action":
                    act = body.get("action")
                    if act == "deploy":
                        ok, res = srv.sim.deploy(
                            body.get("charId"), body.get("row", 0),
                            body.get("col", 0), body.get("direction", 1),
                            skill_index=body.get("skillIndex"))
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
                    elif act == "speed":
                        try:
                            srv.speed = max(0.1, min(8.0, float(
                                body.get("speed", 1.0) or 1.0)))
                        except (TypeError, ValueError):
                            self._send_json({"ok": False,
                                             "result": "invalid_speed"}, 400)
                            return
                        self._send_json({"ok": True, "speed": srv.speed})
                    elif act == "restart":
                        was_paused = srv.sim.battle.paused
                        if getattr(srv.sim, "custom_level", None) is not None:
                            ok, error = srv.reload_custom(srv.sim.custom_level)
                        else:
                            ok, error = srv.reload(getattr(
                                srv.sim, "level_id", None) or srv._level)
                        if ok and was_paused:
                            srv.sim.pause()
                        self._send_json({"ok": ok, "error": error},
                                        200 if ok else 400)
                    elif act == "step":
                        n = int(body.get("n", 1) or 1)
                        snap = srv.sim.step(n)
                        self._send_json({"ok": True, "snapshot": snap})
                    else:
                        self._send_json({"error": "unknown action"}, 400)
                else:
                    self._send_json({"error": "not found"}, 404)

        return H
