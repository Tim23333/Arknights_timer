"""共享 EnemyReader 的关卡全局状态来源；不持有线程或额外通道。"""

import copy
import hashlib
import json
import re
import struct
from time import monotonic

from tools.enemy_health import game_structs as gs
from tools.runtime_log import StateLog
from .engine_clock import CLIENT_VERSION, EngineClock, read_pause
from .memory import MemoryAccess, ReadFailure
from .optional_memory import OptionalMemoryAccess
from .wave_state import WaveStateReader
from .profiling import StageProfiler
from .blackboard import board_fields, read_boards


FIELDS = (
    "stageName",
    "state",
    "isPaused",
    "speedLevel",
    "timeScale",
    "mode",
    "currentWave",
    "nextWave",
    "nextWaveEnemies",
    "waveGate",
    "waveWait",
    "mapId",
    "map",
    "mapRuntime",
)
WAVE_FIELDS = ("currentWave", "nextWave", "nextWaveEnemies", "waveGate", "waveWait")
STATE_NAMES = {0: "none", 1: "inited", 2: "playing", 3: "finished"}


class StageGlobalReader:
    """prepare 在共享定位工作线程调用；sample 在同一完整帧窗口调用。

    输出 values 是 FieldSpec ID→值，field_states 是待宿主补帧/代际的记录。
    Clock/stageInfo/敌我布局由纯聚合服务复用原来源，本对象不重复读取。
    内部地址只用于核验，绝不出现在返回数据。lifecycle_verified 不是自动
    推测能力：只有受控现场完成活动链成员验证后才可由宿主启用。
    """

    def __init__(self, enemy_reader=None, *, lifecycle_verified=False):
        self.reader = enemy_reader
        self.lifecycle_verified = bool(lifecycle_verified)
        self.profiler = StageProfiler()
        self.invalidate()

    def invalidate(self):
        self.memory = self.engine = self.wave = None
        self.runtime_memory = None
        self._retry_at = 0.0
        self.bc = self.scheduler = self.level = self.map_address = 0
        self.process_instance = None
        self._prepare_identity = None
        self.base = None
        self._base_current = False
        self._base_ref = None
        self._base_source_frame = None
        self.prepare_reason = "binding_invalid"
        self.engine_reason = "unsupported_layout"
        self._engine_attempted = False
        self._engine_retry_at = 0.0
        self.client_version = None
        self._stage_attempted = False
        self.stage_info = None
        self._static_frames = {}
        self._wave_state_log = StateLog()

    def _log_wave_failure(self, error):
        """Bounded local diagnostics; no addresses/traceback enter public fields."""
        log = getattr(self.reader, 'log', None)
        trace = error.__traceback__
        sites = []
        while trace is not None:
            sites.append(f'{trace.tb_frame.f_code.co_name}:{trace.tb_lineno}')
            trace = trace.tb_next
        # Only code sites, never frame locals or pointers. The parent site
        # distinguishes Current/owner/array failures ending in the same read().
        site = ' > '.join(sites[-6:]) or 'unknown'
        reason = getattr(error, 'reason', 'read_failed')
        self._wave_state_log.emit(log, reason,
            f'[关卡全局状态] 波次校验拒绝: {reason} ({site})')

    def _log_wave_recovery(self):
        self._wave_state_log.emit(getattr(self.reader, 'log', None), None,
                                  '[关卡全局状态] 波次校验恢复')

    @staticmethod
    def _enabled(policy, name):
        if policy is None:
            return True
        try:
            return bool(policy.enabled(name, "collect"))
        except (KeyError, AttributeError):
            return False

    def _needed(self, policy, key):
        return self._enabled(policy, "stage_global." + key) or (
            key in ("state", "isPaused", "speedLevel", "timeScale")
            and self._enabled(policy, "battle." + key)
        )

    def prepare(self, enemy_reader=None, policy=None):
        if enemy_reader is not None:
            self.reader = enemy_reader
        reader = self.reader
        if reader is None or getattr(reader, "mc", None) is None:
            self.prepare_reason = "binding_invalid"
            return
        # Preparing is optional when all consumers disable capture. Never scan
        # merely because an external client subscribed to a topic.
        if not any(self._needed(policy, key) for key in FIELDS):
            return
        memory = getattr(reader, "mc", None)
        channel = getattr(reader, "_chan", None)
        if channel is None:
            self.prepare_reason = "binding_invalid"
            return
        new_identity = (getattr(memory, "process_instance", None), getattr(reader, "bc_addr", 0))
        if (self.memory is not None and new_identity == self._prepare_identity
                and (not self.prepare_reason or self.prepare_reason == 'unsupported_layout'
                     or monotonic() < self._retry_at)):
            if self.memory.channel is not channel or self.memory.mc is not memory:
                # A healed connection may replace TcpChannel while the game
                # process/controller stays unchanged. Rebind every nested
                # source to the new owner channel, retaining process-scoped
                # verified addresses but not old transport ownership.
                self.memory = OptionalMemoryAccess(memory, channel)
                self.runtime_memory = MemoryAccess(memory, channel)
                if self.engine is not None:
                    self.engine.memory = self.runtime_memory
                if self.wave is not None:
                    self.wave.memory = self.memory
            if (
                self._needed(policy, "timeScale")
                and (not self._engine_attempted or (
                    self.engine is None and self.engine_reason == 'read_failed'
                    and monotonic() >= self._engine_retry_at))
                and self.client_version == CLIENT_VERSION
            ):
                self._prepare_engine()
            if (
                self._needed(policy, "stageName")
                and self._enabled(policy, "stage.stage")
                and not self._stage_attempted
                and not self.prepare_reason
            ):
                self._prepare_stage()
            return
        self.invalidate()
        self.reader = reader
        self.memory = OptionalMemoryAccess(memory, channel)
        self.runtime_memory = MemoryAccess(memory, channel)
        self.process_instance = getattr(memory, "process_instance", None)
        self._prepare_identity = new_identity
        try:
            package = str(getattr(memory, "package", ""))
            # The source transport's own validated package name is used; do not
            # accept a shell command embedded in arbitrary field policy input.
            if not re.fullmatch(r"[A-Za-z0-9_.]+", package):
                raise ReadFailure("binding_invalid")
            info = memory.shell("dumpsys package " + package, timeout=10)
            match = re.search(r"\bversionName=([^\s]+)", info or "")
            self.client_version = match.group(1) if match else None
            if self.client_version != CLIENT_VERSION:
                raise ReadFailure("unsupported_layout")
            self.bc = int(getattr(reader, "bc_addr", 0))
            self.memory.identity(self.bc, "BattleController")
            # Native clock discovery is independent of Map/Scheduler/LevelData.
            if self._needed(policy, "timeScale"):
                self._prepare_engine()
            self._validate_binding(initial=True)
            self.wave = WaveStateReader(
                self.memory, self.bc, self.scheduler, lifecycle_verified=self.lifecycle_verified
            )
            self.prepare_reason = ""
            if self._needed(policy, "stageName") and self._enabled(policy, "stage.stage"):
                self._prepare_stage()
        except Exception as error:
            # Discovery is an external transport/scanner boundary. Failure is
            # local to this module; no retry loop blocks shared sampling.
            self.prepare_reason = getattr(error, "reason", "read_failed")
            self._retry_at = monotonic() + 2.0

    def _prepare_engine(self):
        self._engine_attempted = True
        candidate = EngineClock(self.runtime_memory or self.memory)
        try:
            candidate.resolve()
            self.engine, self.engine_reason = candidate, ""
        except Exception as error:
            self.engine_reason = getattr(error, "reason", "read_failed")
            self._engine_retry_at = monotonic() + 2.0

    def _prepare_stage(self):
        """一次最小身份定位；不查 BattleLogger，也不定位/读取操作历史。"""
        from tools.deploy_tracker.ak_deploy_reader import DeployTrackerReader

        self._stage_attempted = True
        m, owner = self.memory, self
        try:
            level_id = m.string(m.pointer(self.level + gs.LevelDataFields.LEVEL_ID))
            cached = getattr(self.reader, "_stage_info", None)
            if (
                isinstance(cached, dict)
                and getattr(self.reader, "_stage_info_level_data", None) == self.level
                and cached.get("levelId") == level_id
                and cached.get("name")
                and level_id
            ):
                self.stage_info = {key: cached.get(key) for key in ("name", "stageId", "levelId")}
                return

            class BorrowedStage(DeployTrackerReader):
                def _get_channel(self):
                    return owner.memory.channel

                def _read(self, address, size):
                    return owner.memory.read(address, size)

                def close(self):
                    pass

            scanner = BorrowedStage(m.mc)
            found = scanner._scan_class_objects(("BattleInOut",))
            if not found:
                return
            scanner._locate_stage_from_objects(found.get("BattleInOut", []), [self.bc])
            candidate = getattr(scanner, "_battle_in_out_addr", 0)
            if not candidate:
                return
            decoded = scanner._read_stage_info_candidate(candidate)
            if not decoded:
                return
            info, level = decoded
            # Existing helper may rank a same-levelId old object as a fallback;
            # this module requires exact active LevelData ownership instead.
            if level == self.level and info.get("levelId") == level_id and info.get("name"):
                self.stage_info = {key: info.get(key) for key in ("name", "stageId", "levelId")}
        except Exception:
            self.stage_info = None

    def _validate_binding(self, initial=False):
        m = self.memory
        raw = m.read(self.bc + 0x10, 0x168)
        native = struct.unpack_from("<Q", raw)[0]
        map_address = struct.unpack_from("<Q", raw, gs.BattleControllerFields.MAP - 0x10)[0]
        scheduler = struct.unpack_from("<Q", raw, gs.BattleControllerFields.SCHEDULER - 0x10)[0]
        level = struct.unpack_from("<Q", raw, gs.BattleControllerFields.LEVEL_DATA - 0x10)[0]
        if not m.mc.is_ptr(native):
            raise ReadFailure("binding_invalid")
        if initial:
            m.identity(level, "LevelData")
            m.identity(scheduler, "Scheduler")
            m.identity(map_address, "Map")
            self.level, self.scheduler, self.map_address = level, scheduler, map_address
        elif (
            (level, scheduler, map_address) != (self.level, self.scheduler, self.map_address)
            or self.bc != getattr(self.reader, "bc_addr", self.bc)
            or self.process_instance != getattr(m.mc, "process_instance", None)
        ):
            raise ReadFailure("binding_invalid")
        if m.pointer(scheduler + 0x130) != self.bc:
            raise ReadFailure("binding_invalid")

    def base_map(self, cached):
        """Concentrate the sole top-row→bottom-row conversion here."""
        rows, cols = cached.get("rows"), cached.get("cols")
        tiles = cached.get("tiles", [])
        if (
            not isinstance(rows, int)
            or not isinstance(cols, int)
            or not 0 < rows <= 128
            or not 0 < cols <= 128
            or len(tiles) != rows * cols
        ):
            raise ReadFailure("read_failed")
        grid = [[None for _ in range(cols)] for _ in range(rows)]
        keys = (
            "tileKey",
            "heightType",
            "buildableType",
            "passableMask",
            "playerSideMask",
            "advancedBuildableMask",
        )
        for tile in tiles:
            r, c = tile.get("row"), tile.get("col")
            if (
                not isinstance(r, int)
                or not isinstance(c, int)
                or not 0 <= r < rows
                or not 0 <= c < cols
                or not isinstance(tile.get("tileKey"), str)
            ):
                raise ReadFailure("read_failed")
            if grid[rows - 1 - r][c] is not None:
                raise ReadFailure("read_failed")
            grid[rows - 1 - r][c] = {key: tile.get(key) for key in keys}
        if any(tile is None for row in grid for tile in row):
            raise ReadFailure("read_failed")
        revision = hashlib.sha256(
            json.dumps(grid, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()[:20]
        return {
            "rows": rows,
            "cols": cols,
            "coordinates": {"origin": "bottom-left", "x": "col", "y": "row"},
            "revision": revision,
            "layer": "base",
            "tiles": grid,
        }

    def _read_base(self, snapshot):
        m = self.memory
        data = m.pointer(self.level + gs.LevelDataFields.MAP_DATA)
        m.identity(data, "MapData")
        array = m.pointer(data + gs.MapDataFields.MAP)
        header = m.read(array, 0x20)
        bounds, total = struct.unpack_from("<QQ", header, 0x10)
        dimensions = m.read(bounds, 0x20)
        rows, cols = (
            struct.unpack_from("<Q", dimensions)[0],
            struct.unpack_from("<Q", dimensions, 0x10)[0],
        )
        if not 0 < rows <= 128 or not 0 < cols <= 128 or rows * cols != total:
            raise ReadFailure("read_failed")
        # Validate real bounds; existing EnemyReader may downgrade missing bounds
        # to a synthetic one-row export, which cannot be a successful base map.
        cached = getattr(self.reader, "_level_map_data", None)
        if not cached or cached.get("rows") != rows or cached.get("cols") != cols:
            raise ReadFailure("read_failed")
        ref = (data, array, rows, cols, id(cached))
        if (
            self._base_ref is not None
            and ref[:4] != self._base_ref[:4]
            and id(cached) == self._base_ref[4]
        ):
            # Current MapData changed but the borrowed legacy export still
            # points at the old configuration. Require its shared re-locate.
            raise ReadFailure("binding_invalid")
        retry_boards = self.base is not None and any(
            tile.get('blackboardMeta', {}).get('state') == 'unavailable'
            for row in self.base['tiles'] for tile in row)
        if self._base_ref != ref or retry_boards:
            changed = self._base_ref != ref
            self.base = self.base_map(cached)
            self._base_blackboards(data, cached)
            self._base_ref = ref
            if changed:
                self._base_source_frame = (
                    snapshot.get("fixed_frame", snapshot.get("fixedFrame"))
                    if isinstance(snapshot, dict)
                    else getattr(snapshot, "fixed_frame", None)
                )
        self._base_current = True
        return copy.deepcopy(self.base)

    def _base_blackboards(self, data, cached):
        """Add initial parameters without changing legacy EnemyReader exports."""
        m = self.memory
        try:
            definitions = m.array(m.pointer(data + gs.MapDataFields.TILES))
            blocks = m.read_many([(ptr, gs.TileDataFields.READ_SIZE) for ptr in definitions])
            for block in blocks:
                if m.class_identity(struct.unpack_from('<Q', block)[0]) != ('TileData', 'Torappu'):
                    raise ReadFailure('unsupported_layout')
            keys = m.strings([struct.unpack_from('<Q', block, gs.TileDataFields.TILE_KEY)[0]
                              for block in blocks])
            pointers = [struct.unpack_from('<Q', block, gs.TileDataFields.BLACKBOARD)[0]
                        for block in blocks]
            boards = read_boards(m, pointers)
            additions = []
            for tile in cached['tiles']:
                index = tile.get('tileIndex')
                if type(index) is not int or not 0 <= index < len(pointers):
                    raise ReadFailure('binding_invalid')
                key_pointer = struct.unpack_from('<Q', blocks[index], gs.TileDataFields.TILE_KEY)[0]
                if keys[key_pointer] != tile.get('tileKey'):
                    raise ReadFailure('binding_invalid')
                additions.append((tile['row'], tile['col'], board_fields(boards[pointers[index]])))
            for row, col, fields in additions:
                self.base['tiles'][self.base['rows'] - 1 - row][col].update(fields)
        except (ReadFailure, OSError, ValueError, struct.error) as error:
            for row in self.base['tiles']:
                for tile in row:
                    tile.update(board_fields(reason=getattr(error, 'reason', 'read_failed')))
        # Include parameter changes in the existing configuration revision.
        self.base['revision'] = hashlib.sha256(json.dumps(
            self.base['tiles'], sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:20]

    def _read_map_runtime(self):
        m = self.memory
        if self.base is None or not self._base_current:
            raise ReadFailure("read_failed")
        tiles2d = m.pointer(self.map_address + 0x30)
        m.identity(tiles2d, "Tiles2D")
        raw = m.read(tiles2d + 0x10, 16)
        array, cols, rows = struct.unpack("<Qii", raw)
        if rows != self.base["rows"] or cols != self.base["cols"]:
            raise ReadFailure("binding_invalid")
        pointers = m.array(array)
        if len(pointers) != rows * cols or len(set(pointers)) != len(pointers):
            raise ReadFailure("binding_invalid")
        # Batch all tile payloads; m_cachedOptions is inline (not a pointer).
        blocks = m.read_many([(ptr, 0xA8) for ptr in pointers])
        for block in blocks:
            m.derived_identity(struct.unpack_from('<Q', block)[0], 'Tile', 'Torappu.Battle')
        strings = m.strings([struct.unpack_from('<Q', block, 0x18)[0] for block in blocks])
        board_pointers = [struct.unpack_from('<Q', block, 0x68)[0] for block in blocks]
        board_reason = ''
        try:
            boards = read_boards(m, board_pointers, runtime=True)
        except (ReadFailure, OSError, ValueError, struct.error) as error:
            boards = {}
            board_reason = getattr(error, 'reason', 'read_failed')
        tiles = []
        for ptr, block in zip(pointers, blocks):
            key_ptr = struct.unpack_from("<Q", block, 0x18)[0]
            build, passable, advanced, height = [
                struct.unpack_from("<i", block, offset)[0] for offset in (0x90, 0x94, 0x9C, 0xA0)
            ]
            tiles.append(
                {
                    "tileKey": strings[key_ptr],
                    "heightType": height,
                    "buildableType": build,
                    "passableMask": passable,
                    "playerSideMask": None,
                    "advancedBuildableMask": advanced,
                    **board_fields(boards.get(struct.unpack_from('<Q', block, 0x68)[0]),
                                   runtime=True, reason=board_reason),
                }
            )
        # Tile's player-side mask is not present in cachedOptions. Preserve null
        # with explicit reason; do not borrow the base configuration's value.
        return {
            "revision": self.base["revision"],
            "rows": rows,
            "cols": cols,
            "tiles": [tiles[r * cols : (r + 1) * cols] for r in range(rows)],
            "fieldStates": {
                "playerSideMask": {"collectionState": "unavailable", "reason": "not_provided"}
            },
        }

    def sample(self, policy=None, snapshot=None):
        try:
            return self.profiler.call('sample', lambda: self._sample(policy, snapshot))
        finally:
            self.profiler.report(getattr(self.reader, 'log', None))

    def _transport_ready(self):
        """Rebind transport only; changed game ownership always needs a scan."""
        reader = self.reader
        mc, channel = getattr(reader, 'mc', None), getattr(reader, '_chan', None)
        if (self.client_version != CLIENT_VERSION or self.runtime_memory is None
                or channel is None or (getattr(mc, 'process_instance', None),
                    getattr(reader, 'bc_addr', 0)) != self._prepare_identity):
            return False
        if self.runtime_memory.channel is not channel:
            self.runtime_memory = MemoryAccess(mc, channel)
            self.memory = OptionalMemoryAccess(mc, channel)
            if self.engine is not None:
                self.engine.memory = self.runtime_memory
            if self.wave is not None:
                self.wave.memory = self.memory
        return True

    def sample_runtime(self, policy=None):
        """Core pause/engine reads, independent of maps, waves and stage names.

        Discovery never runs here. Unknown versions/changed processes require
        a new scan; transport-only reconnects can safely rebind verified roots.
        """
        result = {'isPaused': None, 'timeScale': None}
        if not self._transport_ready():
            return result
        for key, read in (
            ('isPaused', lambda: read_pause(self.runtime_memory, self.bc)),
            ('timeScale', lambda: self.engine.sample() if self.engine is not None else None),
        ):
            if self._needed(policy, key):
                try:
                    result[key] = read()
                except (ReadFailure, OSError, ValueError, struct.error):
                    pass
        return result

    def begin_optional(self, guard_address):
        """Read next to the core device transaction, before Python parsing."""
        if self._transport_ready():
            self.memory.begin_sample(guard_address)

    def clear_capture_plan(self):
        """Policy changes drop optional read demand before the next transaction."""
        if self.memory is not None:
            self.memory = OptionalMemoryAccess(self.memory.mc, self.memory.channel)
            if self.wave is not None:
                self.wave.memory = self.memory

    def sample_optional(self, policy, snapshot, guard_address):
        """Keep optional topology misses out of the core frame guard."""
        if not self._transport_ready():
            return {'values': {}, 'field_states': {}, 'runtime': {}}, False
        memory = self.memory
        if memory is None:
            return self.sample(policy, snapshot), False
        try:
            result = self.sample(policy, snapshot)
            guard = memory.guard
            frame = snapshot.get('fixed_frame')
            consistent = (type(frame) is int and guard.get('complete') is True
                          and guard.get('start') == frame == guard.get('end'))
            return result, consistent
        finally:
            memory.end_sample()

    def _sample(self, policy=None, snapshot=None):
        values, states, runtime = {}, {}, {}
        enabled = {key: self._enabled(policy, "stage_global." + key) for key in FIELDS}
        for key in FIELDS:
            states["stage_global." + key] = {
                "collectionState": "unavailable" if enabled[key] else "not_collected",
                "reason": "read_failed" if enabled[key] else "not_collected",
            }
            values["stage_global." + key] = None
        result = {"values": values, "field_states": states, "runtime": runtime}
        needed = {key: self._needed(policy, key) for key in FIELDS}
        if not any(needed.values()):
            return result
        # Retry only the small ownership binding here. Version/engine scans and
        # BattleInOut discovery belong to EnemyScanWorker, never the hot loop.
        if (self.memory is not None and self.client_version == CLIENT_VERSION
                and self.prepare_reason not in ('', 'unsupported_layout')
                and monotonic() >= self._retry_at):
            self._retry_at = monotonic() + 2.0
            try:
                self._validate_binding(initial=True)
                self.wave = WaveStateReader(self.memory, self.bc, self.scheduler,
                                           lifecycle_verified=self.lifecycle_verified)
                self.prepare_reason = ''
            except (ReadFailure, OSError, ValueError, struct.error) as error:
                self.prepare_reason = getattr(error, 'reason', 'read_failed')
        if self.memory is None or self.prepare_reason:
            for key in FIELDS:
                if enabled[key]:
                    states["stage_global." + key]["reason"] = self.prepare_reason
            for key in ("state", "stateCode", "isPaused", "speedLevel", "timeScale"):
                runtime[key] = None
            return result
        try:
            self._validate_binding()
        except (ReadFailure, OSError, struct.error) as error:
            reason = getattr(error, "reason", "read_failed")
            for key in FIELDS:
                if enabled[key]:
                    states["stage_global." + key]["reason"] = reason
            runtime.update(
                state=None, stateCode=None, isPaused=None, speedLevel=None, timeScale=None
            )
            return result

        self._base_current = False

        def capture(key, callback, *, static=False):
            if not needed[key]:
                return
            try:
                value = self.profiler.call(key, callback)
                if key in ("state", "isPaused", "speedLevel", "timeScale"):
                    if key == "state":
                        runtime.update(value)
                    else:
                        runtime[key] = value
                if enabled[key]:
                    fid = "stage_global." + key
                    values[fid] = value
                    states[fid] = {
                        "collectionState": "static" if static else "current",
                        "reason": "",
                    }
                    if static:
                        if key not in self._static_frames:
                            self._static_frames[key] = (
                                snapshot.get("fixed_frame", snapshot.get("fixedFrame"))
                                if isinstance(snapshot, dict)
                                else getattr(snapshot, "fixed_frame", None)
                            )
                        states[fid]["sourceFrame"] = (
                            self._base_source_frame if key == "map" else self._static_frames[key]
                        )
            except (ReadFailure, OSError, ValueError, struct.error) as error:
                if key in ("state", "isPaused", "speedLevel", "timeScale"):
                    runtime[key] = None
                    if key == "state":
                        runtime["stateCode"] = None
                if enabled[key]:
                    reason = getattr(error, "reason", "read_failed")
                    states["stage_global." + key]["reason"] = reason
                    if reason == "not_collected":
                        states["stage_global." + key]["collectionState"] = "not_collected"

        def state_value():
            code = self.memory.integer(self.bc + gs.BattleControllerFields.M_STATE)
            return {"state": STATE_NAMES.get(code, "unknown"), "stateCode": code}

        def stage_name():
            if not self._enabled(policy, "stage.stage"):
                raise ReadFailure("not_collected")
            if not self.stage_info or not self.stage_info.get("name"):
                raise ReadFailure("read_failed")
            return {
                "stageName": self.stage_info["name"],
                "stageId": self.stage_info.get("stageId"),
                "levelId": self.stage_info.get("levelId"),
            }

        capture("stageName", stage_name, static=True)

        capture("state", state_value)
        core_runtime = snapshot.get('_stage_runtime') if isinstance(snapshot, dict) else None
        def pause():
            if core_runtime is not None:
                value = core_runtime.get('isPaused')
                if value is None:
                    raise ReadFailure()
                return value
            return read_pause(self.memory, self.bc)
        capture("isPaused", pause)
        capture(
            "speedLevel",
            lambda: self.memory.integer(self.bc + gs.BattleControllerFields.M_SPEED_LEVEL),
        )

        def scale():
            if core_runtime is not None:
                value = core_runtime.get('timeScale')
                if value is None:
                    raise ReadFailure()
                return value
            if self.engine is None:
                raise ReadFailure(self.engine_reason)
            return self.engine.sample()

        capture("timeScale", scale)
        capture(
            "mapId",
            lambda: self.memory.string(self.memory.pointer(self.level + gs.LevelDataFields.MAP_ID)),
            static=True,
        )
        if (
            enabled["mapId"]
            and states["stage_global.mapId"]["collectionState"] == "static"
            and values["stage_global.mapId"] is None
        ):
            states["stage_global.mapId"]["reason"] = "not_provided"
        capture("map", lambda: self._read_base(snapshot), static=True)
        capture("mapRuntime", self._read_map_runtime)

        def mode():
            address = self.memory.pointer(self.bc + gs.BattleControllerFields.GAME_MODE)
            mode_name = self.memory.identity(address)[1]
            handler = self.memory.pointer(self.scheduler + 0x118)
            handler_name = self.memory.identity(handler)[1]
            supported = mode_name == "DefaultGameMode" and handler_name == "DefaultWaveHandler"
            return {
                "name": mode_name,
                "handler": handler_name,
                "supported": supported,
                "reason": "" if supported else "unsupported_layout",
            }

        capture("mode", mode)
        if any(enabled[key] for key in WAVE_FIELDS):
            try:
                output = self.profiler.call('waves', lambda: self.wave.sample(
                    demand={key for key in WAVE_FIELDS if enabled[key]}))
                self._log_wave_recovery()
                for key in WAVE_FIELDS:
                    if enabled[key]:
                        values["stage_global." + key] = output[key]
                        states["stage_global." + key] = {"collectionState": "current", "reason": ""}
                if enabled["nextWave"]:
                    selection = output["nextWave"]["nextSelection"]
                    states["stage_global.nextWave"]["reason"] = {
                        "none": "no_next_wave",
                        "pending": "selection_pending",
                    }.get(selection, "")
                if enabled["nextWaveEnemies"] and output["nextWaveEnemies"] is None:
                    selection = output.get("_nextSelection") or (output.get("nextWave") or {}).get(
                        "nextSelection"
                    )
                    states["stage_global.nextWaveEnemies"]["reason"] = (
                        "selection_pending" if selection == "pending" else "read_failed"
                    )
                if enabled["waveWait"] and output["waveWait"]["remainingSeconds"] is None:
                    states["stage_global.waveWait"]["reason"] = "timing_basis_unverified"
            except (ReadFailure, OSError, ValueError, struct.error) as error:
                self._log_wave_failure(error)
                for key in WAVE_FIELDS:
                    if enabled[key]:
                        states["stage_global." + key]["reason"] = getattr(
                            error, "reason", "read_failed"
                        )
        return result
