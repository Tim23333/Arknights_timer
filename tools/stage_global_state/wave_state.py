"""活动波次及等待读取；配置名单不等同于必定出场的实体。

原生链偏移仅针对已研究的 Android 2.7.81。活动链表现场验收未完成时
默认关闭动态波次解析，调用方不能靠非零反向引用自动升级证据等级。
"""

import math
import struct

from tools.enemy_health import game_structs as gs
from .memory import ReadFailure


ROOT = "<_DoSchedule>d__117"
WAVE = "<_DealWave>d__121"
FRAGMENT = "<_DealFragment>d__122"
PHASES = {1: "pre_delay", 2: "spawning", 3: "timeout_wait", 4: "clearance_wait", 5: "post_delay"}
WAVE_FIELDS = frozenset({"currentWave", "nextWave", "nextWaveEnemies", "waveGate", "waveWait"})


def project_wait(name, raw, phase):
    """计数就是恢复次数；未经当前模式 Tick 对照，不自动除以30。"""
    finite = name == "<WaitWhileForFixedSeconds>d__1"
    offset = 0x30 if finite else 0x24 if name == "<WaitForFixedSeconds>d__0" else None
    if offset is None:
        raise ReadFailure("unsupported_layout")
    state = struct.unpack_from("<i", raw, 0x10)[0]
    configured = struct.unpack_from("<f", raw, 0x20)[0]
    total, elapsed = struct.unpack_from("<ii", raw, offset)
    if state != 1 or not 0 <= elapsed < total <= 100_000_000 or not math.isfinite(configured):
        raise ReadFailure("read_failed")
    return {
        "kind": "timeout_budget" if finite else "fixed_wait",
        "configuredSeconds": configured,
        "totalResumeCount": total,
        "elapsedResumeCount": elapsed,
        "remainingResumeCount": total - elapsed,
        "remainingSeconds": None,
        "secondsBasis": "unknown",
        "mayFinishEarlier": finite,
        "phase": phase,
        "source": "coroutine_counter",
        "precision": "conditional_budget" if finite else "resume_count",
    }


class WaveStateReader:
    def __init__(self, memory, bc, scheduler, *, lifecycle_verified=False):
        self.memory, self.bc, self.scheduler = memory, bc, scheduler
        self.lifecycle_verified = bool(lifecycle_verified)

    def active_root(self, signatures=None):
        """Validate membership, not just Coroutine forward/backward references.

        NativeMonoBehaviour +0x70 is the circular-list sentinel itself; +0x78
        is its next/head slot. The sentinel address is not a stored pointer.
        Prove reachability from that sentinel up to the target, then reread
        that prefix and ownership before accept. Unrelated nodes after the
        target may start/finish normally without invalidating the wave root.
        """
        if not self.lifecycle_verified:
            raise ReadFailure("unsupported_layout")
        m, s = self.memory, self.scheduler
        checks = signatures if signatures is not None else []

        def read(address, size):
            raw = m.read(address, size)
            checks.append((address, raw))
            return raw

        m.identity(self.bc, "BattleController")
        m.identity(s, "Scheduler")
        bcraw = read(self.bc + 0x10, 0x28)
        if (
            not m.mc.is_ptr(struct.unpack_from("<Q", bcraw)[0])
            or struct.unpack_from("<Q", bcraw, 0x20)[0] != s
        ):
            raise ReadFailure("binding_invalid")
        if struct.unpack("<Q", read(s + 0x130, 8))[0] != self.bc:
            raise ReadFailure("binding_invalid")
        native_owner = struct.unpack("<Q", read(s + 0x10, 8))[0]
        if not m.mc.is_ptr(native_owner):
            raise ReadFailure("binding_invalid")
        wrapper, uid = struct.unpack("<QQ", read(s + 0x100, 16))
        if uid or not wrapper:
            raise ReadFailure("unsupported_layout")
        _, name, namespace = m.identity(wrapper, "Coroutine")
        if namespace != "UnityEngine":
            raise ReadFailure("unsupported_layout")
        read(wrapper, 8)
        native = struct.unpack("<Q", read(wrapper + 0x10, 8))[0]
        sentinel = native_owner + 0x70
        node = struct.unpack("<Q", read(sentinel + 8, 8))[0]
        if node == sentinel:
            raise ReadFailure("inactive_coroutine")
        seen, previous, found = set(), sentinel, False
        for _ in range(256):
            if node == sentinel:
                break
            if node in seen or not m.mc.is_ptr(node):
                raise ReadFailure("binding_invalid")
            seen.add(node)
            # The target's outgoing link and sentinel's last link concern
            # unrelated later coroutines. Membership only needs the incoming
            # path plus the target's reciprocal previous link.
            prev_link = struct.unpack("<Q", read(node, 8))[0]
            if prev_link != previous:
                raise ReadFailure("binding_invalid")
            if node == native:
                found = True
                break
            next_link = struct.unpack("<Q", read(node + 8, 8))[0]
            if not next_link:
                raise ReadFailure("binding_invalid")
            previous, node = node, next_link
        else:
            raise ReadFailure("unsupported_layout")
        if not found:
            raise ReadFailure("inactive_coroutine")
        raw = read(native + 0x18, 0x28)
        if struct.unpack_from("<I", raw)[0] != 2:
            raise ReadFailure("unsupported_layout")
        root = struct.unpack_from("<Q", raw, 8)[0]
        if struct.unpack_from("<Q", raw, 0x20)[0] != wrapper:
            raise ReadFailure("binding_invalid")
        m.identity(root, ROOT)
        read(root, 8)
        if struct.unpack("<Q", read(root + 0x20, 8))[0] != s:
            raise ReadFailure("binding_invalid")
        if signatures is None:
            tail = m.read_many(
                [(address, len(raw)) for address, raw in checks], structural_check=True
            )
            if any(a != b for (_, a), b in zip(checks, tail)):
                raise ReadFailure("inconsistent_capture")
        return root

    def _wave(self, address, waves):
        m = self.memory
        m.identity(address, "WaveData")
        if address not in waves:
            raise ReadFailure("binding_invalid")
        raw = m.read(address + 0x10, 0x20)
        delays = struct.unpack_from("<fff", raw)
        if not all(math.isfinite(value) for value in delays):
            raise ReadFailure()
        index = waves.index(address)
        return {
            "index": index,
            "ordinal": index + 1,
            "totalConfigured": len(waves),
            "preDelay": delays[0],
            "postDelay": delays[1],
            "maxWait": delays[2],
            "advancedTag": m.string(struct.unpack_from("<Q", raw, 0x18)[0]),
        }

    def _next_enemies(self, wave):
        """Future hidden/random inputs are conditional, never reroll RNG."""
        m, result = self.memory, []
        fragments = m.array(m.pointer(wave + 0x20), 1024)
        for fi, fragment in enumerate(fragments):
            m.identity(fragment, "FragmentData")
            actions = m.array(m.pointer(fragment + 0x18), 8192)
            blocks = m.read_many([(address, gs.SpawnActionFields.READ_SIZE) for address in actions])
            for ai, (address, raw) in enumerate(zip(actions, blocks)):
                m.identity(address, "ActionData")
                if struct.unpack_from("<i", raw, gs.SpawnActionFields.ACTION_TYPE)[0] != 0:
                    continue
                hidden, group, pack = [
                    m.string(struct.unpack_from("<Q", raw, offset)[0])
                    for offset in (0x38, 0x40, 0x48)
                ]
                count = struct.unpack_from("<i", raw, 0x20)[0]
                pre, interval = struct.unpack_from("<ff", raw, 0x24)
                if not 0 <= count <= 100000 or not all(
                    math.isfinite(v) and v >= 0 for v in (pre, interval)
                ):
                    raise ReadFailure()
                # isValid is mutable phase-selection output; future configurations
                # are not discarded solely because an old selection wrote false.
                result.append(
                    {
                        "enemyId": m.string(struct.unpack_from("<Q", raw, 0x18)[0]),
                        "count": count,
                        "fragmentIndex": fi,
                        "actionIndex": ai,
                        "routeIndex": struct.unpack_from("<i", raw, 0x30)[0],
                        "preDelay": pre,
                        "interval": interval,
                        "selection": "conditional" if hidden or group or pack else "confirmed",
                        "hiddenGroup": hidden,
                        "randomGroup": group,
                        "randomPack": pack,
                    }
                )
        return result

    def sample(self, *, demand=None):
        """Collect only requested public values; safety topology stays shared.

        Closed descriptors never cause configuration strings/delays to parse;
        closed waits never read or derive resume counters. Current/owner/type
        checks remain mandatory even when their descriptive fields are closed.
        """
        demand = WAVE_FIELDS if demand is None else frozenset(demand)
        if not demand <= WAVE_FIELDS:
            raise ReadFailure("unsupported_layout")
        if not demand:
            return {}
        m, checks = self.memory, []
        root = self.active_root(checks)
        rootraw = m.read(root, 0x48)
        checks.append((root, rootraw))
        rootstate = struct.unpack_from("<i", rootraw, 0x10)[0]
        if rootstate not in (2, 3):
            raise ReadFailure("unsupported_layout")
        wave_iterator = struct.unpack_from("<Q", rootraw, 0x18)[0]
        m.identity(wave_iterator, WAVE)
        raw = m.read(wave_iterator, 0x48)
        checks.append((wave_iterator, raw))
        if struct.unpack_from("<Q", raw, 0x20)[0] != self.scheduler:
            raise ReadFailure("binding_invalid")
        wave, next_wave = struct.unpack_from("<QQ", raw, 0x28)
        array = m.pointer(self.scheduler + gs.SchedulerFields.M_WAVES)
        checks.append((self.scheduler + gs.SchedulerFields.M_WAVES, struct.pack("<Q", array)))
        waves = m.array(array, 1024)
        array_bytes = m.read(array + 0x18, 8 + len(waves) * 8)
        if struct.unpack_from("<i", array_bytes)[0] != len(waves):
            raise ReadFailure("inconsistent_capture")
        checks.append((array + 0x18, array_bytes))
        m.identity(wave, "WaveData")
        if wave not in waves:
            raise ReadFailure("binding_invalid")
        current_index = waves.index(wave)
        current = self._wave(wave, waves) if "currentWave" in demand else None
        phase = PHASES.get(struct.unpack_from("<i", raw, 0x10)[0])
        if phase is None:
            raise ReadFailure("unsupported_layout")
        if rootstate == 3:
            expected = waves[current_index + 1] if current_index + 1 < len(waves) else 0
            if next_wave != expected:
                raise ReadFailure("binding_invalid")
            selection = "known" if next_wave else "none"
        else:
            if next_wave:
                raise ReadFailure("binding_invalid")
            selection = "pending"
        next_info = self._wave(next_wave, waves) if next_wave and "nextWave" in demand else None
        fragment_index = struct.unpack_from("<i", raw, 0x38)[0] if phase == "spawning" else None
        gate = (
            {
                "kind": phase,
                "fragmentIndex": fragment_index,
                "actionIndex": None,
                "blockingEnemyCount": None,
                "blockCounter": None,
                "conditions": [],
            }
            if "waveGate" in demand
            else None
        )
        handler = m.pointer(self.scheduler + 0x118)
        handler_name = m.identity(handler)[1]
        mode_address = m.pointer(self.bc + gs.BattleControllerFields.GAME_MODE)
        mode_name = m.identity(mode_address)[1]
        if handler_name != "DefaultWaveHandler" or mode_name != "DefaultGameMode":
            raise ReadFailure("unsupported_layout")
        if m.pointer(handler + 0x18) != self.scheduler:
            raise ReadFailure("binding_invalid")
        wait_phase = "clearance" if phase in ("clearance_wait", "timeout_wait") else phase
        wait = (
            {
                "kind": "undetermined",
                "configuredSeconds": None,
                "totalResumeCount": None,
                "elapsedResumeCount": None,
                "remainingResumeCount": None,
                "remainingSeconds": None,
                "secondsBasis": "unknown",
                "mayFinishEarlier": None,
                "phase": wait_phase,
                "source": "unknown",
                "precision": "unknown",
            }
            if "waveWait" in demand
            else None
        )
        address, seen = struct.unpack_from("<Q", raw, 0x18)[0], set()
        for _ in range(16):
            if address in seen:
                raise ReadFailure("binding_invalid")
            seen.add(address)
            _, name, _ = m.identity(address)
            is_counter = name in ("<WaitForFixedSeconds>d__0", "<WaitWhileForFixedSeconds>d__1")
            # Exclusive wait counters lie outside the shared Current/state
            # prefix. Read them only if that field's collect switch is open.
            size = (
                (0x48 if "waveWait" in demand else 0x20)
                if is_counter
                else (8 if name == "WaitForFixedUpdate" else 0x30)
            )
            block = m.read(address, size)
            # The shared device frame guard owns dynamic wait values. A later
            # independent topology read must compare type/state/Current, not
            # elapsed counters that legitimately advance while Python parses.
            # Changed Current, owner, stopped/unlinked roots still fail closed.
            checks.append((address, block[:0x20] if is_counter else block))
            if is_counter:
                if wait is not None:
                    wait = project_wait(name, block, wait_phase)
                elif struct.unpack_from("<i", block, 0x10)[0] != 1:
                    raise ReadFailure("inactive_coroutine")
                address = struct.unpack_from("<Q", block, 0x18)[0]
                m.identity(address, "WaitForFixedUpdate")
                checks.append((address, m.read(address, 8)))
                break
            if name == "WaitForFixedUpdate":
                if phase != "clearance_wait":
                    raise ReadFailure("unsupported_layout")
                break
            state, child = (
                struct.unpack_from("<i", block, 0x10)[0],
                struct.unpack_from("<Q", block, 0x18)[0],
            )
            if state <= 0 or not child:
                raise ReadFailure("inactive_coroutine")
            owner = struct.unpack_from("<Q", block, 0x20)[0]
            if name == FRAGMENT:
                if owner != self.scheduler:
                    raise ReadFailure("binding_invalid")
                fragments = m.array(m.pointer(wave + 0x20), 1024)
                if (
                    fragment_index is None
                    or not 0 <= fragment_index < len(fragments)
                    or struct.unpack_from("<Q", block, 0x28)[0] != fragments[fragment_index]
                ):
                    raise ReadFailure("binding_invalid")
            elif name in (
                "<WaitForPreDelay>d__19",
                "<WaitForPostDelay>d__20",
                "<ExecuteActionQueue>d__21",
            ):
                if owner != handler:
                    raise ReadFailure("binding_invalid")
                if name == "<ExecuteActionQueue>d__21":
                    if gate is not None:
                        gate["actionIndex"] = struct.unpack_from("<i", block, 0x28)[0]
                    if wait is not None:
                        wait_phase = "action_interval"
                        wait["phase"] = wait_phase
            elif name not in ("<WaitWhileFixed>d__4", "<WaitWhileFixed>d__9"):
                raise ReadFailure("unsupported_layout")
            address = child
        else:
            raise ReadFailure("unsupported_layout")
        if gate is not None and phase in ("clearance_wait", "timeout_wait"):
            managed = m.pointer(self.scheduler + gs.SchedulerFields.M_MANAGED_WAVE_ENEMIES)
            m.identity(managed, "List`1")
            count = m.integer(managed + 0x18)
            if not 0 <= count <= 16384:
                raise ReadFailure()
            gate["blockingEnemyCount"] = count
            gate["blockCounter"] = m.integer(self.scheduler + 0x20)
            gate["conditions"] = [
                {"key": "managed_enemies_empty", "satisfied": count == 0, "value": count}
            ]
        result = {}
        if "currentWave" in demand:
            result["currentWave"] = current
        if "nextWave" in demand:
            result["nextWave"] = {"next": next_info, "nextSelection": selection}
        if "nextWaveEnemies" in demand:
            # Internal selection evidence is needed even when its public
            # descriptor is disabled. It never enters the public values map.
            result["_nextSelection"] = selection
            result["nextWaveEnemies"] = (
                self._next_enemies(next_wave) if next_wave else [] if selection == "none" else None
            )
        if gate is not None:
            result["waveGate"] = gate
        if wait is not None:
            result["waveWait"] = wait
        # Independent trailing topology check must not simply reread the same
        # prefetched bytes. Only bounded structural signatures are live, never
        # all gameplay values or a second parser channel.
        after = m.read_many([(address, len(raw)) for address, raw in checks], structural_check=True)
        if any(raw != tail for (_, raw), tail in zip(checks, after)):
            raise ReadFailure("inconsistent_capture")
        return result
