"""Read-only battle lifecycle, independent of clock advancement and UI policy.

Android 2.7.81 layout, checked against class identities on every binding.
Scene transitions are not atomic snapshots: re-read slots and scene scalars
before accepting a sample. A failure is unknown, never an observed null slot.
"""
import struct

from tools.stage_global_state.memory import MemoryAccess, ReadFailure


class LifecycleTracker:
    """Debounce readiness, not exit; emit each transition once per instance."""

    def __init__(self):
        self.active = None
        self.retired = None
        self.candidate = None
        self.stable = 0
        self.ready = False
        self.interval = .5

    def observe(self, value):
        self.ready = False
        if value is None:
            self.candidate, self.stable = None, 0
            self.interval = .5
            return []
        battle = value['battle']
        self.interval = .1 if battle or value['transiting'] else .5
        exiting = (value['transiting'] and value['source'].startswith('level_')
                   and value['target'] == 'battle_finish')
        events = []
        if self.active and (exiting or battle != self.active):
            events.append('exit')
            self.retired, self.active = self.active, None
        if battle is None:
            self.retired = None
        if (not value['ready'] or value['transiting'] or not battle
                or battle == self.retired):
            self.candidate, self.stable = None, 0
            return events
        self.stable = self.stable + 1 if battle == self.candidate else 1
        self.candidate = battle
        if self.stable >= 2:
            self.ready = True
            if self.active != battle:
                self.active = battle
                events.append('ready')
        return events


class LifecycleReader:
    """Small live reads on the supplied memory channel; no heap rescans."""

    def __init__(self, memory, battle_klass, flow_klass):
        self.m = memory
        self.battle_klass = battle_klass
        self.flow_klass = flow_klass
        self.battle_slot = self._slot(battle_klass, ('BattleController', 'Torappu.Battle'))
        self.flow_slot = self._slot(flow_klass, ('GameFlowController', 'Torappu'))

    def _slot(self, klass, identity):
        if self.m.class_identity(klass) != identity:
            raise ReadFailure('unsupported_layout')
        parent = self.m.pointer(klass + 0x58)
        if self.m.class_identity(parent) != ('SingletonMonoBehaviour`1', 'Torappu'):
            raise ReadFailure('unsupported_layout')
        slot = self.m.pointer(parent + 0xB8)
        if not self.m.mc.is_ptr(slot):
            raise ReadFailure('binding_invalid')
        return slot

    def _string(self, ptr):
        if not ptr:
            return ''
        size = self.m.integer(ptr + 0x10)
        if not 0 <= size <= 256:
            raise ReadFailure('unsupported_layout')
        return self.m.read(ptr + 0x14, size * 2).decode('utf-16-le') if size else ''

    def sample(self):
        m = self.m
        slots = m.read_many([(self.battle_slot, 8), (self.flow_slot, 8)], structural_check=True)
        bc, flow = [struct.unpack('<Q', raw)[0] for raw in slots]
        raw = m.read(flow, 0x38)
        if struct.unpack_from('<Q', raw)[0] != self.flow_klass or not struct.unpack_from('<Q', raw, 0x10)[0]:
            raise ReadFailure('binding_invalid')
        if raw[0x20] not in (0, 1):
            raise ReadFailure('unsupported_layout')
        source, target = [self._string(struct.unpack_from('<Q', raw, offset)[0]) for offset in (0x28, 0x30)]
        battle, ready = None, False
        if bc:
            block = m.read(bc, 0x2C0)
            if struct.unpack_from('<Q', block)[0] != self.battle_klass:
                raise ReadFailure('binding_invalid')
            native = struct.unpack_from('<Q', block, 0x10)[0]
            if native:
                battle = (bc, native)
                state = struct.unpack_from('<i', block, 0x220)[0]
                if state not in (0, 1, 2, 3):
                    raise ReadFailure('unsupported_layout')
                # No advancing-clock requirement: paused PLAYING is valid.
                if state == 2 and not raw[0x20]:
                    ready = True
                    for offset, name in ((0x30, 'Scheduler'), (0x158, 'LevelData'), (0x2B8, 'UnitManager')):
                        ptr = struct.unpack_from('<Q', block, offset)[0]
                        if not ptr:
                            ready = False
                            break
                        m.identity(ptr, name)
            # Reject teardown/rebinding while reading readiness roots.
            if m.read(bc, 0x18) != block[:0x18]:
                raise ReadFailure('binding_changed')
        after = m.read_many([(self.battle_slot, 8), (self.flow_slot, 8), (flow + 0x20, 0x18)], structural_check=True)
        if after[:2] != slots or after[2] != raw[0x20:0x38]:
            raise ReadFailure('binding_changed')
        return dict(battle=battle, ready=ready, transiting=bool(raw[0x20]),
                    source=source, target=target)


def locate_lifecycle(mc, battle_klass, locator):
    """One metadata-only lookup per clock location, never in the polling loop."""
    classes = locator.scan_classes(('GameFlowController',), namespace='Torappu')
    if not classes or len(classes) != 1:
        raise ReadFailure('flow_class_unavailable')
    return LifecycleReader(MemoryAccess(mc, mc.channel()), battle_klass, next(iter(classes)))
