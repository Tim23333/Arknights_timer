# -*- coding: utf-8 -*-
"""通过 BattleController -> UnitManager.characters 读取场上干员。

定位和设备侧 TCP 通道复用 ``EnemyReader``，避免敌人、干员各自扫描一次内存。
本模块只负责友方 Character/Token 的身份、属性、状态、技能、天赋和 Buff。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import deque
import math
import struct
import time

from tools.enemy_health import game_structs as gs
from tools.enemy_health.enemy_reader import (
    EnemyInfo, EnemyReader, _i32, _u64, seconds_to_frames,
)
from tools.enemy_health.memcore import TcpChannel


GLOBAL_DAMAGE_SUMMARY_ADDR = -1
GLOBAL_DAMAGE_SUMMARY_NAME = '无来源&全局伤害统计'
UNATTRIBUTED_DAMAGE_EPSILON = 0.01
UNATTRIBUTED_RECONCILE_SEC = 0.8


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from('<I', data, offset)[0]


def _f32(data: bytes, offset: int) -> float:
    return struct.unpack_from('<f', data, offset)[0]


def _decrypt_obscured_int(data: bytes, offset: int) -> int:
    value = _u32(data, offset) ^ _u32(data, offset + 4)
    return value - 0x100000000 if value & 0x80000000 else value


@dataclass
class CharacterInfo:
    addr: int
    cid: str = ''
    alias: str = ''
    tmpl_id: str = ''
    name: str = ''
    name_en: str = ''
    level: int = 0
    evolve_phase: int = 0
    potential_rank: int = 0
    favor_phase: int = 0
    unique_id: int = 0
    profession: int = 0
    rarity: int = 0
    deploy_position: int = 0
    team_key: str = ''
    nation_id: str = ''
    group_id: str = ''
    team_id: str = ''
    is_token: bool = False
    is_predefined: bool = False
    is_hidden: bool = False
    is_assist: bool = False
    token_or_host_key: str = ''
    token_or_host_uid: int = 0
    token_initial_count: int = 0
    main_skill_index: int = -1
    card_uid: int = 0
    deploy_cost_this_time: int = 0
    hp: float = 0.0
    max_hp: float = 0.0
    es: float = 0.0
    shield: float = 0.0
    sp: float = 0.0
    max_sp: int = 0
    direction: int = 0
    finish_reason: int = 0
    alive: bool = True
    state_id: int = gs.CharacterState.DEFAULT
    grid_row: int | None = None
    grid_col: int | None = None
    blocked_count: int = 0
    blocked_total_volume: int = 0
    buff_count: int = 0
    attr_ptr: int = 0
    state_ptr: int = 0
    ep_ptr: int = 0
    ep_controller_ptr: int = 0
    shield_controller_ptr: int = 0
    buff_container_ptr: int = 0
    root_tile_ptr: int = 0
    skill_ptr: int = 0
    skill_data_ptr: int = 0
    data_ptr: int = 0
    current_mode_ptr: int = 0
    action: dict = field(default_factory=dict)
    attributes: dict = field(default_factory=dict)
    raw_attributes: dict = field(default_factory=dict)
    ep_remaining: dict = field(default_factory=dict)
    ep_break_recovery: bool = False
    abnormal_flags: list = field(default_factory=lambda: [0] * gs.AbnormalFlag.E_NUM)
    abnormal_immunes: list = field(default_factory=lambda: [0] * gs.AbnormalFlag.E_NUM)
    abnormal_antis: list = field(default_factory=lambda: [0] * gs.AbnormalFlag.E_NUM)
    abnormal_combos: list = field(default_factory=lambda: [0] * gs.AbnormalCombo.E_NUM)
    abnormal_combo_immunes: list = field(
        default_factory=lambda: [0] * gs.AbnormalCombo.E_NUM)
    skill: dict = field(default_factory=dict)
    talents: list = field(default_factory=list)
    buffs: list = field(default_factory=list)
    global_buffs: list = field(default_factory=list)
    dynamic_abilities: list = field(default_factory=list)
    module_settings: list = field(default_factory=list)
    deck_buff_blackboard: list = field(default_factory=list)
    damage_total: float = 0.0
    healing_total: float = 0.0
    damage_range_min: float = 0.0
    damage_range_max: float = 0.0
    damage_by_type: dict = field(default_factory=dict)
    output_element_damage: dict = field(default_factory=dict)
    output_ep_break_count: dict = field(default_factory=dict)
    global_total_damage: float = 0.0
    attributed_damage_total: float = 0.0
    unattributed_damage_total: float = 0.0
    character_attributed_damage_total: float = 0.0
    observed_enemy_damage_total: float = 0.0
    unattributed_tracking_enabled: bool = False
    is_global_damage_summary: bool = False

    @property
    def profession_name(self) -> str:
        return gs.PROFESSION_CATEGORY_NAMES.get(self.profession, str(self.profession))

    @property
    def unit_kind(self) -> str:
        if self.is_global_damage_summary:
            return '全局统计'
        if self.is_token:
            return '召唤物/装置'
        return '干员'

    @property
    def position_text(self) -> str:
        # 显示约定与敌方一致：(列, 行) = (x, y)，横坐标在前
        if self.grid_row is None or self.grid_col is None:
            return '-'
        return f'({self.grid_col},{self.grid_row})'

    @property
    def state_name(self) -> str:
        return gs.CharacterState.NAMES.get(self.state_id, f'未知({self.state_id})')

    @property
    def action_text(self) -> str:
        return (self.action or {}).get('name') or self.state_name

    @property
    def status_resistance(self) -> float:
        one_minus = self.attributes.get(
            gs.AttributeType.ONE_MINUS_STATUS_RESISTANCE, 1.0)
        return 1.0 - one_minus

    def attribute(self, index: int, default: float = 0.0) -> float:
        return float(self.attributes.get(index, default))

    def status_text(self) -> str:
        values = [gs.ABNORMAL_FLAG_CN_NAMES.get(i, str(i))
                  for i, count in enumerate(self.abnormal_flags) if count > 0]
        values += [gs.ABNORMAL_COMBO_CN_NAMES.get(i, str(i))
                   for i, count in enumerate(self.abnormal_combos) if count > 0]
        return '、'.join(values) if values else '-'

    def element_damage(self, element_type: int):
        maximum = max(0.0, self.attribute(gs.AttributeType.MAX_EP))
        remaining = min(maximum, max(0.0, float(
            self.ep_remaining.get(element_type, maximum)))) if maximum > 0 else 0.0
        return max(0.0, maximum - remaining), remaining, maximum


class CharacterReader:
    """依附 EnemyReader 的轻量服务；不拥有、也不关闭共享 MemCore。"""

    LIST_EVERY = 4
    SKILL_EVERY = 3
    BUFF_COUNT_EVERY = 10
    DAMAGE_LAYOUT_EVERY = 60

    def __init__(self, core: EnemyReader):
        self.core = core
        self.mc = core.mc
        self.unit_manager_addr = 0
        self.characters_addr = 0
        self.character_addrs: list[int] = []
        self._tick = 0
        self._items = 0
        self._count = 0
        self._identities: dict[int, dict] = {}
        self._attr_cached: dict[int, int] = {}
        self._attr_snapshots: dict[int, dict] = {}
        self._runtime_ptrs: dict[int, dict] = {}
        self._runtime_snapshots: dict[int, dict] = {}
        self._positions: dict[int, tuple[int, int, int]] = {}
        self._skill_static: dict[int, dict] = {}
        self._skill_runtime: dict[int, dict] = {}
        self._buff_counts: dict[int, int] = {}
        self._klass_cache: dict[int, str] = {}
        self._damage_stats_addr = 0
        self._damage_list_addr = 0
        self._damage_layout_tick = 0
        self._damage_entries: dict[str, dict] = {}
        self._damage_snapshots: dict[str, dict] = {}
        self._damage_history: dict[str, dict] = {}
        self._battle_stats_total_damage = 0.0
        self._observed_enemy_damage_total = 0.0
        self._observed_enemy_hp: dict[tuple[int, int], float] = {}
        self._seen_enemy_damage_keys: set[tuple[int, int]] = set()
        self._unattributed_tracking_enabled = False
        self._committed_unattributed_damage = 0.0
        self._pending_observed_damage = deque()
        self._pending_attributed_damage = deque()
        self._last_observed_damage_total = 0.0
        self._last_attributed_damage_total = 0.0
        self._global_damage_summary = self._make_global_damage_summary(
            0.0, {}, 0.0, 0.0, False)

    def _reset_damage_tracking(self) -> None:
        self._damage_snapshots.clear()
        self._damage_history.clear()
        self._battle_stats_total_damage = 0.0
        self._observed_enemy_damage_total = 0.0
        self._observed_enemy_hp.clear()
        self._seen_enemy_damage_keys.clear()
        self._unattributed_tracking_enabled = False
        self._committed_unattributed_damage = 0.0
        self._pending_observed_damage.clear()
        self._pending_attributed_damage.clear()
        self._last_observed_damage_total = 0.0
        self._last_attributed_damage_total = 0.0
        self._global_damage_summary = self._make_global_damage_summary(
            0.0, {}, 0.0, 0.0, False)

    def bootstrap(self) -> bool:
        if not self.core.unit_manager_addr:
            if not self.core.bc_addr or not self.core._resolve_unit_manager(
                    self.core.bc_addr):
                return False
        unit_manager = self.core.unit_manager_addr
        characters = self.core._read_ptr(
            unit_manager + gs.UnitManagerFields.CHARACTERS)
        if not self.mc.is_ptr(characters):
            return False
        self.unit_manager_addr = unit_manager
        self.characters_addr = characters
        return True

    def _ensure_channel(self):
        if self.core._chan is None:
            self.core._chan = TcpChannel(self.mc)
        return self.core._chan

    def _batch(self, reqs):
        if not reqs:
            return []
        # 详情页有自己的 TCP 通道；避免它和 10~20ms 一次的主轮询争抢同一
        # socket，造成帧数据错位或把敌人高速通道误判为失效。
        if getattr(self.core._detail_context, 'active', False):
            return self.core._detail_batch_read(reqs)
        return self._ensure_channel().batch_read(reqs)

    def _class_name(self, ptr: int) -> str:
        if not self.mc.is_ptr(ptr):
            return ''
        if ptr not in self._klass_cache:
            self._klass_cache[ptr] = self.mc.read_klass_name(ptr) or ''
        return self._klass_cache[ptr]

    def _read_container(self) -> list[int] | None:
        if not self.mc.is_ptr(self.characters_addr) and not self.bootstrap():
            return None
        (head,) = self._batch([(self.characters_addr, 0x28)])
        if not head:
            return None
        items = _u64(head, gs.UnorderedArrayFields.ITEMS)
        count = _i32(head, gs.UnorderedArrayFields.COUNT)
        if not (0 <= count <= 256) or (count and not self.mc.is_ptr(items)):
            return None
        if not count:
            self._items, self._count, self.character_addrs = items, 0, []
            return []
        (body,) = self._batch([(items + gs.Il2CppArray.ITEMS, count * 8)])
        if not body:
            return None
        ptrs = [p for p in (_u64(body, i * 8) for i in range(count))
                if self.mc.is_ptr(p)]
        self._items, self._count, self.character_addrs = items, count, ptrs
        return ptrs

    @staticmethod
    def _parse_main(addr: int, block: bytes) -> CharacterInfo:
        info = CharacterInfo(addr)
        info.hp = gs.fp_to_float(_u64(block, gs.EntityFields.M_HP))
        info.es = gs.fp_to_float(_u64(block, gs.EntityFields.M_ES))
        info.sp = gs.obscured_fp_to_float(
            _u64(block, gs.EntityFields.M_SP),
            _u64(block, gs.EntityFields.M_SP + 8))
        info.max_sp = _i32(block, gs.EntityFields.MAX_SP)
        info.direction = _i32(block, gs.EntityFields.M_DIRECTION)
        info.finish_reason = _i32(block, gs.EntityFields.FINISH_REASON)
        info.alive = info.hp > 0 and info.finish_reason == 0
        info.attr_ptr = _u64(block, gs.EntityFields.M_ATTRIBUTES)
        info.state_ptr = _u64(block, gs.EntityFields.M_STATE_MACHINE)
        info.ep_ptr = _u64(block, gs.EntityFields.M_EP_ARRAY)
        info.ep_controller_ptr = _u64(block, gs.EntityFields.M_EP_CONTROLLER)
        info.shield_controller_ptr = _u64(
            block, gs.EntityFields.M_SHIELD_CONTROLLER)
        info.buff_container_ptr = _u64(block, gs.EntityFields.BUFF_CONTAINER)
        info.current_mode_ptr = _u64(block, gs.UnitFields.CURRENT_MODE)
        animator = _u64(block, gs.UnitFields.ANIMATOR)
        if not animator:
            animator = _u64(block, gs.CharacterFields.RUNTIME_ANIMATOR)
        info.action = {
            'animator_addr': animator,
            'current_mode_addr': info.current_mode_ptr,
            'override_attack_addr': _u64(block, gs.UnitFields.OVERRIDE_ATTACK),
            'override_combat_addr': _u64(block, gs.UnitFields.OVERRIDE_COMBAT),
        }
        info.root_tile_ptr = _u64(block, gs.CharacterFields.ROOT_TILE)
        info.skill_ptr = _u64(block, gs.CharacterFields.SKILL)
        info.skill_data_ptr = _u64(block, gs.CharacterFields.SKILL_DATA)
        info.data_ptr = _u64(block, gs.CharacterFields.DATA)
        info.deploy_cost_this_time = _i32(
            block, gs.CharacterFields.DEPLOY_COST_THIS_TIME)
        info.card_uid = _u32(block, gs.CharacterFields.CARD_UID)
        return info

    def _fill_new_identities(self, infos: dict[int, CharacterInfo]) -> None:
        targets = [info for info in infos.values()
                   if info.addr not in self._identities and self.mc.is_ptr(info.data_ptr)]
        if not targets:
            return
        blocks = self._batch([
            (info.data_ptr, gs.BattleCharacterDataFields.READ_SIZE)
            for info in targets])
        parsed = []
        string_ptrs = []
        string_fields = (
            ('cid', gs.BattleCharacterDataFields.ID),
            ('alias', gs.BattleCharacterDataFields.ALIAS),
            ('tmpl_id', gs.BattleCharacterDataFields.TMPL_ID),
            ('name', gs.BattleCharacterDataFields.NAME_CN),
            ('name_en', gs.BattleCharacterDataFields.NAME_EN),
            ('team_key', gs.BattleCharacterDataFields.TEAM_KEY),
            ('token_or_host_key', gs.BattleCharacterDataFields.TOKEN_OR_HOST_KEY),
            ('nation_id', gs.BattleCharacterDataFields.NATION_ID),
            ('group_id', gs.BattleCharacterDataFields.GROUP_ID),
            ('team_id', gs.BattleCharacterDataFields.TEAM_ID),
        )
        for info, data in zip(targets, blocks):
            if not data:
                continue
            record = {'data_ptr': info.data_ptr}
            for key, offset in string_fields:
                ptr = _u64(data, offset)
                record[key + '_ptr'] = ptr
                string_ptrs.append(ptr)
            record.update({
                'level': _i32(data, gs.BattleCharacterDataFields.LEVEL),
                'evolve_phase': _i32(data, gs.BattleCharacterDataFields.EVOLVE_PHASE),
                'potential_rank': _i32(data, gs.BattleCharacterDataFields.POTENTIAL_RANK),
                'favor_phase': _i32(data, gs.BattleCharacterDataFields.FAVOR_BATTLE_PHASE),
                'unique_id': _u32(data, gs.BattleCharacterDataFields.UNIQUE_ID),
                'profession': _i32(data, gs.BattleCharacterDataFields.PROFESSION),
                'rarity': _i32(data, gs.BattleCharacterDataFields.RARITY),
                'deploy_position': _i32(data, gs.BattleCharacterDataFields.DEPLOY_POSITION),
                'is_token': bool(data[gs.BattleCharacterDataFields.IS_TOKEN]),
                'is_predefined': bool(data[gs.BattleCharacterDataFields.IS_PREDEFINED]),
                'is_hidden': bool(data[gs.BattleCharacterDataFields.IS_HIDDEN]),
                'is_assist': bool(data[gs.BattleCharacterDataFields.IS_ASSIST]),
                'token_or_host_uid': _u32(data, gs.BattleCharacterDataFields.TOKEN_OR_HOST_UID),
                'token_initial_count': _i32(data, gs.BattleCharacterDataFields.TOKEN_INITIAL_COUNT),
                'main_skill_index': _i32(data, gs.BattleCharacterDataFields.MAIN_SKILL_INDEX),
            })
            parsed.append((info.addr, record))
        strings = self.core._read_strings(string_ptrs)
        for addr, record in parsed:
            for key, _ in string_fields:
                record[key] = strings.get(record.pop(key + '_ptr'), '')
            self._identities[addr] = record
            self.core._names[addr] = (
                record.get('cid', ''), record.get('name', ''), '')

    @staticmethod
    def _apply_identity(info: CharacterInfo, identity: dict) -> None:
        for key, value in identity.items():
            if hasattr(info, key):
                setattr(info, key, value)

    def _refresh_attributes(self, infos: dict[int, CharacterInfo]) -> None:
        missing = [info for info in infos.values()
                   if info.addr not in self._attr_cached and self.mc.is_ptr(info.attr_ptr)]
        for info, data in zip(
                missing, self._batch([(x.attr_ptr, 0x60) for x in missing])):
            ptr = _u64(data, gs.AttributesFields.M_CACHED_DATA) if data else 0
            if self.mc.is_ptr(ptr):
                self._attr_cached[info.addr] = ptr
        size = gs.Il2CppArray.ITEMS + gs.AttributeType.E_NUM * gs.OBSCURED_FP_SIZE
        targets = [(addr, ptr) for addr, ptr in self._attr_cached.items()
                   if addr in infos and self.mc.is_ptr(ptr)]
        for (addr, _), data in zip(targets, self._batch([(ptr, size) for _, ptr in targets])):
            if not data or not (0 < _i32(data, gs.Il2CppArray.MAX_LENGTH) <= 64):
                self._attr_cached.pop(addr, None)
                continue
            tmp = EnemyInfo(addr)
            self.core._apply_cached_data(data, tmp)
            self._attr_snapshots[addr] = dict(tmp.attributes)
        for addr, info in infos.items():
            info.attributes = dict(self._attr_snapshots.get(addr, {}))
            info.max_hp = info.attribute(gs.AttributeType.MAX_HP)

    def _refresh_runtime(self, infos: dict[int, CharacterInfo]) -> None:
        missing = []
        for addr, info in infos.items():
            pointers = self._runtime_ptrs.setdefault(addr, {})
            if pointers.get('attr_obj') != info.attr_ptr:
                pointers.clear()
                pointers['attr_obj'] = info.attr_ptr
            pointers.update(state=info.state_ptr, ep=info.ep_ptr,
                            epc=info.ep_controller_ptr,
                            shield=info.shield_controller_ptr)
            if not all(pointers.get(key) for key in (
                    'flags', 'immunes', 'antis', 'combos', 'combo_immunes')):
                missing.append((addr, info.attr_ptr))
        combo_mgrs = {}
        for (addr, _), data in zip(
                missing, self._batch([(ptr, 0x40) for _, ptr in missing])):
            if not data:
                continue
            rp = self._runtime_ptrs[addr]
            rp['flags'] = _u64(data, gs.AttributesFields.M_ABNORMAL_FLAGS_COUNTER)
            rp['immunes'] = _u64(data, gs.AttributesFields.M_ABNORMAL_IMMUNE_COUNTER)
            rp['antis'] = _u64(data, gs.AttributesFields.M_ABNORMAL_ANTI_COUNTER)
            combo = _u64(data, gs.AttributesFields.M_ABNORMAL_COMBO_MGR)
            if self.mc.is_ptr(combo):
                combo_mgrs[addr] = combo
        for addr, data in zip(
                combo_mgrs, self._batch([(ptr, 0x20) for ptr in combo_mgrs.values()])):
            if data:
                self._runtime_ptrs[addr]['combos'] = _u64(
                    data, gs.AbnormalComboManagerFields.M_ABNORMAL_COMBO_COUNTER)
                self._runtime_ptrs[addr]['combo_immunes'] = _u64(
                    data, gs.AbnormalComboManagerFields.M_ABNORMAL_COMBO_IMMUNE_COUNTER)

        snapshots = {addr: dict(self._runtime_snapshots.get(addr, {}))
                     for addr in infos}
        for addr, info in infos.items():
            action = dict(snapshots[addr].get('action', {}))
            action.update(info.action or {})
            snapshots[addr]['action'] = action

        reqs, keys = [], []
        for addr in infos:
            rp = self._runtime_ptrs.get(addr, {})
            specs = (
                ('state', rp.get('state', 0) + gs.StateMachineFields.CURRENT_STATE_ID, 0x10),
                ('ep', rp.get('ep', 0), gs.Il2CppArray.ITEMS + gs.ElementType.E_NUM * 8),
                ('shield', rp.get('shield', 0) + gs.ShieldUIControllerFields.M_SHIELD_TO_SHOW, 8),
                ('epc', rp.get('epc', 0) + gs.EPControllerFields.M_IS_IN_BREAK_RECOVERY, 1),
                ('flags', rp.get('flags', 0), gs.Il2CppArray.ITEMS + gs.AbnormalFlag.E_NUM * 2),
                ('immunes', rp.get('immunes', 0), gs.Il2CppArray.ITEMS + gs.AbnormalFlag.E_NUM * 2),
                ('antis', rp.get('antis', 0), gs.Il2CppArray.ITEMS + gs.AbnormalFlag.E_NUM * 2),
                ('combos', rp.get('combos', 0), gs.Il2CppArray.ITEMS + gs.AbnormalCombo.E_NUM * 2),
                ('combo_immunes', rp.get('combo_immunes', 0),
                 gs.Il2CppArray.ITEMS + gs.AbnormalCombo.E_NUM * 2),
            )
            for kind, ptr, size in specs:
                if self.mc.is_ptr(ptr):
                    reqs.append((ptr, size)); keys.append((addr, kind))
            mode = snapshots[addr]['action'].get('current_mode_addr', 0)
            if self.mc.is_ptr(mode):
                reqs.append((mode, gs.UnitModeFields.READ_SIZE))
                keys.append((addr, 'unit_mode'))
            animator = snapshots[addr]['action'].get('animator_addr', 0)
            if self.mc.is_ptr(animator):
                for kind, offset in (
                        ('anim_spine', gs.UnitAnimatorFields.SPINE_CURRENT_STATE),
                        ('anim_mesh', gs.UnitAnimatorFields.MESH_CURRENT_STATE)):
                    reqs.append((animator + offset,
                                 gs.UnitAnimatorFields.CURRENT_STATE_SIZE))
                    keys.append((addr, kind))
        for (addr, kind), data in zip(keys, self._batch(reqs)):
            if not data:
                continue
            snap = snapshots[addr]
            if kind == 'state':
                snap['state_id'] = _i32(data, 0)
                state_node = _u64(data, 8)
                if snap['action'].get('state_node_addr') != state_node:
                    snap['action'].pop('state_time', None)
                    snap['action'].pop('status_remaining', None)
                snap['action']['state_node_addr'] = state_node
            elif kind == 'ep':
                snap['ep_remaining'] = self.core._decode_fp_array(
                    data, gs.ElementType.E_NUM)
            elif kind == 'shield':
                snap['shield'] = gs.fp_to_float(_u64(data, 0))
            elif kind == 'epc':
                snap['ep_break_recovery'] = bool(data[0])
            elif kind in ('flags', 'immunes', 'antis'):
                snap['abnormal_' + kind] = self.core._decode_short_array(
                    data, gs.AbnormalFlag.E_NUM)
            elif kind == 'combos':
                snap['abnormal_combos'] = self.core._decode_short_array(
                    data, gs.AbnormalCombo.E_NUM)
            elif kind == 'combo_immunes':
                snap['abnormal_combo_immunes'] = self.core._decode_short_array(
                    data, gs.AbnormalCombo.E_NUM)
            elif kind == 'unit_mode':
                snap['action']['mode_combat_addr'] = _u64(
                    data, gs.UnitModeFields.COMBAT)
                snap['action']['mode_attack_addr'] = _u64(
                    data, gs.UnitModeFields.ATTACK)
            elif kind in ('anim_spine', 'anim_mesh'):
                snap['action'].setdefault('animation_candidates', []).append({
                    'key_ptr': _u64(data, 0),
                    'speed': _f32(data, 8),
                    'backend': 'Spine' if kind == 'anim_spine' else 'Mesh',
                })

        self.core._resolve_animation_states_chan({
            addr: snapshots[addr]['action'] for addr in infos})
        self.core._refresh_animation_tracks_chan({
            addr: snapshots[addr]['action'] for addr in infos})

        ability_reqs, ability_keys = [], []
        for addr, info in infos.items():
            action = snapshots[addr]['action']
            for role in ('attack', 'combat'):
                ability = (action.get(f'override_{role}_addr', 0)
                           or action.get(f'mode_{role}_addr', 0))
                action[f'{role}_ability_addr'] = ability
                action.pop(role, None)
                if self.mc.is_ptr(ability):
                    ability_reqs.append((ability, gs.AbilityFields.READ_SIZE))
                    ability_keys.append((addr, role))
            state_node = action.get('state_node_addr', 0)
            if self.mc.is_ptr(state_node):
                ability_reqs.append((
                    state_node + gs.StateNodeFields.ACTION_TIME, 8))
                ability_keys.append((addr, 'state_time'))
        for (addr, kind), data in zip(ability_keys, self._batch(ability_reqs)):
            if not data:
                continue
            action = snapshots[addr]['action']
            if kind == 'state_time':
                action['state_time'] = gs.fp_to_float(_u64(data, 0))
                continue
            target = action.setdefault(kind, {})
            target['casting'] = bool(data[gs.AbilityFields.IS_CASTING])
            target['cast_start_frame'] = _u32(data, gs.AbilityFields.CAST_START_FRAME)
            target['attached'] = bool(data[gs.AbilityFields.IS_ATTACHED])
            target['finish_reason'] = _i32(data, gs.AbilityFields.FINISH_REASON)
            target['timer_addr'] = _u64(data, gs.AbilityFields.COOLDOWN_TIMER)

        timer_keys = []
        for addr, kind in ability_keys:
            if kind == 'state_time':
                continue
            timer = snapshots[addr]['action'].get(kind, {}).get('timer_addr', 0)
            if self.mc.is_ptr(timer):
                timer_keys.append((addr, kind, timer))
        for (addr, kind, _timer), data in zip(
                timer_keys, self._batch([(timer, 0x20)
                                         for _addr, _kind, timer in timer_keys])):
            if not data:
                continue
            target = snapshots[addr]['action'].setdefault(kind, {})
            target['cd_period'] = gs.fp_to_float(_u64(
                data, gs.PeriodicTimerFields.M_PERIOD_TIME))
            target['cd_remaining'] = gs.fp_to_float(_u64(
                data, gs.PeriodicTimerFields.M_REMAINING_TIME))

        abnormal_bits = {
            gs.CharacterState.STUN: (0, None),
            gs.CharacterState.FROZEN: (16, None),
            gs.CharacterState.DOZE: (43, 0),
        }
        status_targets = []
        for addr, info in infos.items():
            state_id = snapshots[addr].get('state_id', gs.CharacterState.DEFAULT)
            bits = abnormal_bits.get(state_id)
            if bits:
                status_targets.append((addr, info.buff_container_ptr, state_id,
                                       bits[0], bits[1]))
        self.core._refresh_status_timers_chan(
            status_targets, snapshots, self._tick)
        self._runtime_snapshots = snapshots
        for addr, info in infos.items():
            for key, value in snapshots.get(addr, {}).items():
                setattr(info, key, value if not isinstance(value, (list, dict))
                        else type(value)(value))

    def _refresh_positions_and_blocking(self, infos: dict[int, CharacterInfo]) -> None:
        changed = [info for info in infos.values()
                   if self._positions.get(info.addr, (0, 0, 0))[0] != info.root_tile_ptr
                   and self.mc.is_ptr(info.root_tile_ptr)]
        graphics = {}
        for info, data in zip(
                changed, self._batch([(x.root_tile_ptr, 0x38) for x in changed])):
            graphic = _u64(data, gs.TileFields.GRAPHIC) if data else 0
            if self.mc.is_ptr(graphic):
                graphics[info.addr] = graphic
        for addr, data in zip(
                graphics, self._batch([(ptr, 0x30) for ptr in graphics.values()])):
            if data:
                info = infos[addr]
                self._positions[addr] = (
                    info.root_tile_ptr,
                    _i32(data, gs.TileGraphicFields.GRID_ROW),
                    _i32(data, gs.TileGraphicFields.GRID_COL))
        # manager 指针在主对象块中解析后不单独保存；从固定字段批量取一次即可。
        manager_slots = self._batch([
            (info.addr + gs.CharacterFields.BLOCKED_ENEMY_MANAGER, 8)
            for info in infos.values()])
        manager_ptrs = {
            info.addr: _u64(data, 0) for info, data in zip(infos.values(), manager_slots)
            if data and self.mc.is_ptr(_u64(data, 0))
        }
        blocked_lists = {}
        for addr, data in zip(
                manager_ptrs, self._batch([(ptr, 0x20) for ptr in manager_ptrs.values()])):
            if not data:
                continue
            infos[addr].blocked_total_volume = _i32(
                data, gs.BlockedEnemyManagerFields.TOTAL_VOLUME)
            lp = _u64(data, gs.BlockedEnemyManagerFields.BLOCKED_ENEMIES)
            if self.mc.is_ptr(lp):
                blocked_lists[addr] = lp
        for addr, data in zip(
                blocked_lists, self._batch([(ptr, 0x20) for ptr in blocked_lists.values()])):
            if data:
                count = _i32(data, gs.ListInternal.SIZE)
                infos[addr].blocked_count = count if 0 <= count <= 128 else 0
        for addr, info in infos.items():
            position = self._positions.get(addr)
            if position:
                _, info.grid_row, info.grid_col = position

    def _parse_skill_static(self, data_ptr: int, data: bytes) -> dict:
        strings = self.core._read_strings([
            _u64(data, gs.SkillDataFields.NAME),
            _u64(data, gs.SkillDataFields.SKILL_ID),
            _u64(data, gs.SkillDataFields.RANGE_ID),
            _u64(data, gs.SkillDataFields.ICON_ID),
            _u64(data, gs.SkillDataFields.DESCRIPTION),
            _u64(data, gs.SkillDataFields.PREFAB_KEY),
        ])
        sp_ptr = _u64(data, gs.SkillDataFields.SP_DATA)
        sp = {}
        if self.mc.is_ptr(sp_ptr):
            (sp_data,) = self._batch([(sp_ptr, gs.SpDataFields.READ_SIZE)])
            if sp_data:
                sp = {
                    'type': _i32(sp_data, gs.SpDataFields.SP_TYPE),
                    'max_charge': _decrypt_obscured_int(
                        sp_data, gs.SpDataFields.MAX_CHARGE_TIME),
                    'cost': _decrypt_obscured_int(sp_data, gs.SpDataFields.SP_COST),
                    'init_sp': _decrypt_obscured_int(sp_data, gs.SpDataFields.INIT_SP),
                }
        return {
            'data_addr': data_ptr,
            'name': strings.get(_u64(data, gs.SkillDataFields.NAME), ''),
            'skill_id': strings.get(_u64(data, gs.SkillDataFields.SKILL_ID), ''),
            'range_id': strings.get(_u64(data, gs.SkillDataFields.RANGE_ID), ''),
            'icon_id': strings.get(_u64(data, gs.SkillDataFields.ICON_ID), ''),
            'description': strings.get(_u64(data, gs.SkillDataFields.DESCRIPTION), ''),
            'prefab_key': strings.get(_u64(data, gs.SkillDataFields.PREFAB_KEY), ''),
            'level': _i32(data, gs.SkillDataFields.LEVEL),
            'type': _i32(data, gs.SkillDataFields.SKILL_TYPE),
            'duration_type': _i32(data, gs.SkillDataFields.DURATION_TYPE),
            'duration': _f32(data, gs.SkillDataFields.DURATION),
            'blackboard_ptr': _u64(data, gs.SkillDataFields.BLACKBOARD),
            'sp': sp,
        }

    def _refresh_skills(self, infos: dict[int, CharacterInfo]) -> None:
        new_data = {info.skill_data_ptr for info in infos.values()
                    if self.mc.is_ptr(info.skill_data_ptr)
                    and info.skill_data_ptr not in self._skill_static}
        for ptr, data in zip(
                new_data, self._batch([(p, gs.SkillDataFields.READ_SIZE) for p in new_data])):
            if data:
                self._skill_static[ptr] = self._parse_skill_static(ptr, data)
        targets = [info for info in infos.values() if self.mc.is_ptr(info.skill_ptr)]
        skill_blocks = self._batch([
            (info.skill_ptr, gs.BasicSkillFields.READ_SIZE) for info in targets])
        abilities = {}
        runtime = {}
        for info, data in zip(targets, skill_blocks):
            if not data:
                continue
            ability = _u64(data, gs.BasicSkillFields.ABILITY)
            runtime[info.addr] = {
                # 类名不是主表高频字段；首次逐级读 klass 会让四名干员的第一帧
                # 多等待约 2 秒，详情页读取过后再从缓存带回即可。
                'class': self._klass_cache.get(info.skill_ptr, ''),
                'trigger_count': _i32(data, gs.BasicSkillFields.TRIGGER_COUNT),
                'wait_for_end': bool(data[gs.BasicSkillFields.WAIT_FOR_SKILL_END]),
                'early_finished': bool(data[gs.BasicSkillFields.IS_EARLY_FINISHED]),
                'overloaded': bool(data[gs.BasicSkillFields.IS_OVERLOADED]),
                'min_sp': _i32(data, gs.BasicSkillFields.COST_MIN_SP),
                'max_triggers': _i32(data, gs.BasicSkillFields.MAX_TRIGGER_TIME),
                'ability_addr': ability,
                'blackboard_ptr': _u64(data, gs.BasicSkillFields.BLACKBOARD),
            }
            if self.mc.is_ptr(ability):
                abilities[info.addr] = ability
        timers = {}
        for addr, data in zip(
                abilities, self._batch([(p, gs.AbilityFields.READ_SIZE)
                                        for p in abilities.values()])):
            if not data:
                continue
            cur = runtime[addr]
            cur.update({
                'ability_class': self._klass_cache.get(abilities[addr], ''),
                'casting': bool(data[gs.AbilityFields.IS_CASTING]),
                'cast_start_frame': _u32(data, gs.AbilityFields.CAST_START_FRAME),
                'attached': bool(data[gs.AbilityFields.IS_ATTACHED]),
                'finish_reason': _i32(data, gs.AbilityFields.FINISH_REASON),
                'ability_blackboard_ptr': _u64(data, gs.AbilityFields.BLACKBOARD),
            })
            timer = _u64(data, gs.AbilityFields.COOLDOWN_TIMER)
            if self.mc.is_ptr(timer):
                timers[addr] = timer
        for addr, data in zip(
                timers, self._batch([(p, 0x20) for p in timers.values()])):
            if data:
                runtime[addr]['cooldown_period'] = gs.fp_to_float(
                    _u64(data, gs.PeriodicTimerFields.M_PERIOD_TIME))
                runtime[addr]['cooldown_remaining'] = gs.fp_to_float(
                    _u64(data, gs.PeriodicTimerFields.M_REMAINING_TIME))
        self._skill_runtime.update(runtime)
        for addr, info in infos.items():
            static = dict(self._skill_static.get(info.skill_data_ptr, {}))
            static['runtime'] = dict(self._skill_runtime.get(addr, {}))
            static['current_sp'] = info.sp
            static['max_sp'] = info.max_sp
            sp_cost = static.get('sp', {}).get('cost', info.max_sp)
            static['ready'] = bool(sp_cost > 0 and info.sp >= sp_cost
                                   and not static['runtime'].get('wait_for_end'))
            info.skill = static

    def _predict_character_next_action(self, info: CharacterInfo, action: dict) -> None:
        """只展示游戏已排队的下一动画；不把技力/CD 候选冒充下一动作。"""
        for key in ('next_action', 'next_action_detail', 'next_action_confidence'):
            action.pop(key, None)
        state_id = info.state_id
        if state_id in (gs.CharacterState.TERMINAL, gs.CharacterState.DEAD):
            action.update(next_action='无', next_action_detail='实体已结束',
                          next_action_confidence='confirmed')
            return

        queued_animation = action.get('animation_next_track_name', '')
        if queued_animation:
            action.update(
                next_action=f'已排队动画：{queued_animation}',
                next_action_detail='Spine TrackEntry.next 已存在；这是游戏已排队的下一段动画',
                next_action_confidence='confirmed')
            return

        if state_id == gs.CharacterState.ATTACK:
            detail = ('游戏尚未写入下一动作；AttackState 会在当前攻击结束后的 '
                      '_NextAttackOrExit 中重新检查目标、技能与普通攻击')
        elif state_id == gs.CharacterState.SKILL:
            detail = '技能结束前没有独立的下一 Ability 字段，结束回调触发后才决定'
        elif state_id == gs.CharacterState.IDLE and (info.skill or {}).get('ready'):
            detail = '技能虽已就绪，但玩家输入/自动触发尚未发生，不能视为已预选动作'
        else:
            detail = '当前没有已排队动画，下一动作尚未由游戏状态机决定'
        action.update(next_action='等待游戏判定', next_action_detail=detail,
                      next_action_confidence='unselected')

    def _finalize_character_action(self, info: CharacterInfo) -> dict:
        """合成我方状态机、普攻/战斗 Ability 与主技能的动作阶段。"""
        action = dict(info.action or {})
        for key in (
                'phase', 'name', 'detail', 'remaining', 'remaining_frames',
                'remaining_kind', 'elapsed_frames', 'current_frame',
                'clock_source', 'next_action', 'next_action_detail',
                'next_action_confidence'):
            action.pop(key, None)
        now = self.core._scheduler_time_snap
        frame = self.core._fixed_frame_snap
        frame_duration = self.core._frame_duration_snap or 1.0 / 30.0
        if not isinstance(now, (int, float)) or not math.isfinite(now):
            now = None
        if not isinstance(frame, int) or frame < 0:
            frame = None
        action['current_frame'] = frame
        action['state_name'] = info.state_name
        skill = info.skill or {}
        skill_runtime = dict(skill.get('runtime') or {})
        action['skill_runtime'] = skill_runtime

        def set_countdown(seconds, kind, source='runtime'):
            if not isinstance(seconds, (int, float)) or not math.isfinite(seconds):
                return False
            seconds = max(0.0, float(seconds))
            action['remaining'] = seconds
            action['remaining_frames'] = (
                seconds_to_frames(seconds, frame_duration)
                if frame is not None else None)
            action['remaining_kind'] = kind
            action['clock_source'] = source
            return True

        state_id = info.state_id
        ability = {}
        if state_id == gs.CharacterState.ATTACK:
            ability = action.get('attack') or {}
        elif state_id == gs.CharacterState.COMBAT:
            ability = action.get('combat') or {}
        elif state_id == gs.CharacterState.SKILL:
            ability = skill_runtime
        if ability.get('casting') and frame is not None:
            start = ability.get('cast_start_frame')
            if isinstance(start, int) and 0 <= start <= frame:
                action['elapsed_frames'] = frame - start

        animation_remaining = action.get('animation_remaining')
        animation_remaining = (
            float(animation_remaining)
            if isinstance(animation_remaining, (int, float))
            and math.isfinite(animation_remaining) and animation_remaining >= 0
            else None)

        if state_id in (gs.CharacterState.TERMINAL, gs.CharacterState.DEAD):
            action.update(phase='finished', name=info.state_name,
                          detail='状态已结束，不再进入下一动作', remaining=0.0,
                          remaining_frames=0, remaining_kind='完成态',
                          clock_source='state')
        elif state_id in (gs.CharacterState.BORN, gs.CharacterState.REBORN):
            action.update(phase='state_countdown', name=info.state_name,
                          detail='状态节点自身倒计时')
            if not set_countdown(action.get('state_time'), '状态剩余', 'state_node'):
                action['remaining_kind'] = '等待状态节点退出'
        elif state_id in (gs.CharacterState.ATTACK, gs.CharacterState.COMBAT):
            role = '普通攻击' if state_id == gs.CharacterState.ATTACK else '战斗动作'
            if ability.get('casting'):
                action.update(phase='ability_casting', name=f'{role}中',
                              detail='Ability 正在施放；倒计时取当前非循环 Spine 动画终点')
                deadline = action.get('state_time')
                gate = deadline - now if now is not None and isinstance(
                    deadline, (int, float)) and math.isfinite(deadline) else None
                gates = [value for value in (animation_remaining, gate)
                         if isinstance(value, (int, float)) and value > 0]
                if gates:
                    kind = ('动作可退出剩余（未中断）' if gate and gate > 0
                            else '当前动画剩余（未中断）')
                    set_countdown(max(gates), kind, 'spine/state_gate')
                else:
                    action['remaining_kind'] = '动画/能力回调决定'
            else:
                deadline = action.get('state_time')
                remaining = deadline - now if now is not None and isinstance(
                    deadline, (int, float)) and math.isfinite(deadline) else None
                if remaining is not None and remaining > 0.0001:
                    action.update(phase='ability_recovery', name=f'{role}后摇',
                                  detail='Ability 已结束，等待状态节点可退出时刻')
                    set_countdown(max(remaining, animation_remaining or 0.0),
                                  '后摇/动画剩余（未中断）',
                                  'spine/state_node_deadline')
                else:
                    action.update(phase='ability_transition', name=f'{role}收尾',
                                  detail='等待动画或状态机切回待机',
                                  remaining_kind='动画/状态切换条件')
                    if animation_remaining is not None:
                        set_countdown(animation_remaining,
                                      '收尾动画剩余（未中断）', 'spine_track')
        elif state_id == gs.CharacterState.SKILL:
            skill_name = skill.get('name') or skill.get('skill_id') or '主技能'
            if skill_runtime.get('casting') or skill_runtime.get('wait_for_end'):
                action.update(phase='skill_active', name=f'技能中：{skill_name}',
                              detail='技能 Ability 正在施放或持续生效')
                timers = [value for value in (
                    animation_remaining, action.get('state_time'))
                    if isinstance(value, (int, float))
                    and math.isfinite(value) and value >= 0]
                if not (timers and set_countdown(
                        max(timers), '技能动画/可退出剩余（未中断）',
                        'spine/skill_state')):
                    action['remaining_kind'] = '技能/动画回调决定'
            else:
                action.update(phase='skill_transition', name=f'技能收尾：{skill_name}',
                              detail='等待技能状态退出',
                              remaining_kind='状态切换条件')
                if animation_remaining is not None:
                    set_countdown(animation_remaining,
                                  '收尾动画剩余（未中断）', 'spine_track')
        elif state_id in (gs.CharacterState.STUN, gs.CharacterState.FROZEN,
                          gs.CharacterState.DOZE):
            action.update(phase='abnormal', name=info.state_name,
                          detail='异常状态由一个或多个 Buff/组合标志维持')
            if not set_countdown(action.get('status_remaining'),
                                 '异常持续剩余', 'buff'):
                action['remaining_kind'] = 'Buff/异常条件解除'
        elif state_id == gs.CharacterState.IDLE:
            skill_name = skill.get('name') or skill.get('skill_id') or '主技能'
            skill_type = skill.get('type')
            if skill.get('ready'):
                if skill_type == 1:
                    action.update(phase='idle_skill_manual', name='待机 / 技能可手动释放',
                                  detail=f'{skill_name} 技力已满，等待玩家输入',
                                  remaining_kind='玩家操作')
                else:
                    action.update(phase='idle_skill_auto', name='待机 / 技能已就绪',
                                  detail=f'{skill_name} 等待目标、触发器和状态机允许施放',
                                  remaining_kind='目标/触发/状态条件')
            else:
                candidates = []
                for role in ('attack', 'combat'):
                    remain = (action.get(role) or {}).get('cd_remaining')
                    if isinstance(remain, (int, float)) and 0 < remain < 3600:
                        candidates.append(float(remain))
                skill_cd = skill_runtime.get('cooldown_remaining')
                if isinstance(skill_cd, (int, float)) and 0 < skill_cd < 3600:
                    candidates.append(float(skill_cd))
                if candidates:
                    action.update(phase='idle_cooldown', name='待机 / 等待下一动作',
                                  detail='显示最早 Ability 可用时间；仍可能受目标条件限制')
                    set_countdown(min(candidates), '下一动作可用', 'ability_cooldown')
                else:
                    action.update(phase='idle', name='待机',
                                  detail='等待目标、技力或触发条件',
                                  remaining_kind='目标/技力/触发条件')
        else:
            action.update(phase='state_wait', name=info.state_name,
                          detail='该状态没有统一倒计时槽，由状态节点条件退出',
                          remaining_kind='状态节点条件')

        self._predict_character_next_action(info, action)
        info.action = action
        snap = self._runtime_snapshots.get(info.addr)
        if snap is not None:
            snap['action'] = dict(action)
        return action

    def _refresh_buff_counts(self, infos: dict[int, CharacterInfo]) -> None:
        targets = [info for info in infos.values()
                   if self.mc.is_ptr(info.buff_container_ptr)]
        dbls = {}
        for info, data in zip(
                targets, self._batch([(x.buff_container_ptr, 0x30) for x in targets])):
            ptr = _u64(data, gs.BuffContainerFields.M_BUFFS) if data else 0
            if self.mc.is_ptr(ptr):
                dbls[info.addr] = ptr
        lists = {}
        for addr, data in zip(dbls, self._batch([(p, 0x28) for p in dbls.values()])):
            ptr = _u64(data, gs.DoubleBufferedListFields.M_INTERNAL_LIST) if data else 0
            if self.mc.is_ptr(ptr):
                lists[addr] = ptr
        for addr, data in zip(lists, self._batch([(p, 0x20) for p in lists.values()])):
            if data:
                count = _i32(data, gs.ListInternal.SIZE)
                if 0 <= count <= 512:
                    self._buff_counts[addr] = count
        for addr, info in infos.items():
            info.buff_count = self._buff_counts.get(addr, 0)

    def _refresh_damage_layout(self) -> None:
        """解析 BattleLogger 的按 charId 累计统计表；结构低频刷新，数值每帧读。"""
        if not self.mc.is_ptr(self.core.bc_addr):
            return
        (logger_slot,) = self._batch([(
            self.core.bc_addr + gs.BattleControllerFields.M_LOGGER, 8)])
        logger = _u64(logger_slot, 0) if logger_slot else 0
        if not self.mc.is_ptr(logger):
            self._damage_stats_addr = 0
            self._damage_entries.clear()
            self._reset_damage_tracking()
            return
        (logger_block,) = self._batch([(logger, gs.BattleLoggerFields.READ_SIZE)])
        stats = _u64(logger_block, gs.BattleLoggerFields.STATS) if logger_block else 0
        if not self.mc.is_ptr(stats):
            self._damage_stats_addr = 0
            self._damage_entries.clear()
            self._reset_damage_tracking()
            return
        (stats_block,) = self._batch([(stats, gs.BattleStatsFields.READ_SIZE)])
        stats_list = (_u64(stats_block, gs.BattleStatsFields.CHAR_ADVANCED_STATS)
                      if stats_block else 0)
        if not self.mc.is_ptr(stats_list):
            self._damage_stats_addr = 0
            self._damage_entries.clear()
            self._reset_damage_tracking()
            return
        if stats != self._damage_stats_addr:
            # BattleLogger 会在新战斗中整体重建；不能把上一局的累计值带进来。
            self._reset_damage_tracking()
        self._damage_stats_addr = stats
        self._damage_list_addr = stats_list

        (head,) = self._batch([(stats_list, 0x20)])
        if not head:
            return
        items = _u64(head, gs.ListInternal.ITEMS)
        count = _i32(head, gs.ListInternal.SIZE)
        if not (0 <= count <= 256) or (count and not self.mc.is_ptr(items)):
            return
        if not count:
            self._damage_entries.clear()
            self._damage_layout_tick = self._tick
            return
        # ListDict<string, CharAdvancedStats> 继承 List<KeyValuePair<...>>；
        # KeyValuePair 引用类型实参在数组中为 key/value 两个 8 字节指针。
        (body,) = self._batch([(items + gs.Il2CppArray.ITEMS, count * 0x10)])
        if not body:
            return
        pairs = [(_u64(body, idx * 0x10), _u64(body, idx * 0x10 + 8))
                 for idx in range(count)]
        pairs = [(key, value) for key, value in pairs
                 if self.mc.is_ptr(key) and self.mc.is_ptr(value)]
        strings = self.core._read_strings([key for key, _value in pairs])
        named = [(strings.get(key, ''), value) for key, value in pairs]
        named = [(cid, value) for cid, value in named if cid]
        blocks = self._batch([
            (value, gs.CharAdvancedStatsFields.READ_SIZE)
            for _cid, value in named])

        entries = {}
        list_owners, list_reqs = [], []
        for (cid, value), data in zip(named, blocks):
            if not data:
                continue
            record = {'addr': value, 'lists': {}}
            entries[cid] = record
            for kind, offset in (
                    ('elements', gs.CharAdvancedStatsFields.OUTPUT_ELEMENT_DAMAGE_TOTAL),
                    ('breaks', gs.CharAdvancedStatsFields.OUTPUT_EP_BREAK_COUNT),
                    ('types', gs.CharAdvancedStatsFields.OUTPUT_DAMAGE_BY_TYPE_TOTAL)):
                ptr = _u64(data, offset)
                if self.mc.is_ptr(ptr):
                    list_owners.append((cid, kind, ptr))
                    list_reqs.append((ptr, 0x20))
        for (cid, kind, ptr), head in zip(list_owners, self._batch(list_reqs)):
            if not head:
                continue
            items = _u64(head, gs.ListInternal.ITEMS)
            count = _i32(head, gs.ListInternal.SIZE)
            if 0 <= count <= 32 and (not count or self.mc.is_ptr(items)):
                entries[cid]['lists'][kind] = {
                    'list': ptr, 'data': items + gs.Il2CppArray.ITEMS,
                    'count': count,
                }
        self._damage_entries = entries
        self._damage_layout_tick = self._tick

    @staticmethod
    def _safe_float(value: float) -> float:
        return float(value) if math.isfinite(value) else 0.0

    @classmethod
    def _make_global_damage_summary(cls, battle_stats_total: float,
                                    snapshots: dict[str, dict],
                                    observed_enemy_total: float,
                                    unattributed_total: float = 0.0,
                                    tracking_enabled: bool = True) -> CharacterInfo:
        battle_stats_total = abs(cls._safe_float(battle_stats_total))
        observed_enemy_total = max(
            0.0, cls._safe_float(observed_enemy_total))
        character_attributed = sum(max(0.0, cls._safe_float(
            snapshot.get('damage_total', 0.0))) for snapshot in snapshots.values())
        # BattleStats.totalDamage 在 LogModifier 中只统计有玩家侧 source 的伤害；
        # charAdvancedStats 读取可能比它早/晚一帧，因此取二者较大值作为有来源值。
        attributed = max(battle_stats_total, character_attributed)
        unattributed = max(0.0, cls._safe_float(unattributed_total))
        global_total = attributed + unattributed
        if unattributed <= max(UNATTRIBUTED_DAMAGE_EPSILON, global_total * 1e-6):
            unattributed = 0.0
            global_total = attributed
        return CharacterInfo(
            addr=GLOBAL_DAMAGE_SUMMARY_ADDR,
            cid='global_damage_summary',
            name=GLOBAL_DAMAGE_SUMMARY_NAME,
            alive=False,
            damage_total=unattributed,
            global_total_damage=global_total,
            attributed_damage_total=attributed,
            unattributed_damage_total=unattributed,
            character_attributed_damage_total=character_attributed,
            observed_enemy_damage_total=observed_enemy_total,
            unattributed_tracking_enabled=bool(tracking_enabled),
            is_global_damage_summary=True,
        )

    def _observe_enemy_damage(self, enemies, include_damage=True) -> float:
        """累计敌方实际 HP 正向损失，用来补齐 BattleStats 漏掉的无来源伤害。"""
        if enemies is None:
            return 0.0
        current: dict[tuple[int, int], float] = {}
        initial_visible_loss = 0.0
        for enemy in enemies:
            addr = int(getattr(enemy, 'addr', 0) or 0)
            lifecycle = getattr(enemy, 'lifecycle', 'active')
            if addr <= 0 or lifecycle == 'pending':
                continue
            roster_id = int(getattr(enemy, 'roster_id', 0) or 0)
            key = (addr, roster_id)
            hp = max(0.0, self._safe_float(getattr(enemy, 'hp', 0.0)))
            maximum = max(hp, self._safe_float(
                getattr(enemy, 'max_hp', hp)))
            initial_visible_loss += max(0.0, maximum - hp)
            previous = self._observed_enemy_hp.get(key)
            if include_damage and previous is not None:
                self._observed_enemy_damage_total += max(0.0, previous - hp)
            self._seen_enemy_damage_keys.add(key)
            if lifecycle == 'active':
                current[key] = hp
        self._observed_enemy_hp = current
        return initial_visible_loss

    def _update_unattributed_tracking(self, enabled: bool, enemies,
                                      attributed_floor: float) -> None:
        enabled = bool(enabled)
        if not enabled:
            if self._unattributed_tracking_enabled:
                self._observed_enemy_hp.clear()
                self._seen_enemy_damage_keys.clear()
            self._unattributed_tracking_enabled = False
            self._observed_enemy_damage_total = 0.0
            self._committed_unattributed_damage = 0.0
            self._pending_observed_damage.clear()
            self._pending_attributed_damage.clear()
            self._last_observed_damage_total = 0.0
            self._last_attributed_damage_total = 0.0
            return
        if not self._unattributed_tracking_enabled:
            self._unattributed_tracking_enabled = True
            self._observed_enemy_hp.clear()
            self._seen_enemy_damage_keys.clear()
            # 中途启用时以“有来源累计”和当前敌人可见生命损失的较大值开局，
            # 不把同一段有来源伤害重复算成无来源。
            visible_loss = self._observe_enemy_damage(
                enemies, include_damage=False)
            self._observed_enemy_damage_total = max(
                max(0.0, attributed_floor), visible_loss)
            self._committed_unattributed_damage = 0.0
            self._pending_observed_damage.clear()
            self._pending_attributed_damage.clear()
            self._last_observed_damage_total = max(0.0, attributed_floor)
            self._last_attributed_damage_total = max(0.0, attributed_floor)
        else:
            self._observe_enemy_damage(enemies)
        self._reconcile_unattributed_damage(attributed_floor)

    @staticmethod
    def _consume_damage_queues(left, right) -> None:
        while left and right:
            amount = min(left[0][1], right[0][1])
            left[0][1] -= amount
            right[0][1] -= amount
            if left[0][1] <= UNATTRIBUTED_DAMAGE_EPSILON:
                left.popleft()
            if right[0][1] <= UNATTRIBUTED_DAMAGE_EPSILON:
                right.popleft()

    def _reconcile_unattributed_damage(self, attributed_total: float,
                                       now: float | None = None) -> None:
        """给 BattleStats 最多 0.8s 追平 HP 变化，再提交真正的无来源差值。"""
        now = time.monotonic() if now is None else now
        attributed_total = max(0.0, self._safe_float(attributed_total))
        observed_delta = max(
            0.0, self._observed_enemy_damage_total
            - self._last_observed_damage_total)
        attributed_delta = max(
            0.0, attributed_total - self._last_attributed_damage_total)
        self._last_observed_damage_total = self._observed_enemy_damage_total
        self._last_attributed_damage_total = attributed_total
        if observed_delta > UNATTRIBUTED_DAMAGE_EPSILON:
            self._pending_observed_damage.append([now, observed_delta])
        if attributed_delta > UNATTRIBUTED_DAMAGE_EPSILON:
            self._pending_attributed_damage.append([now, attributed_delta])
        self._consume_damage_queues(
            self._pending_observed_damage, self._pending_attributed_damage)

        cutoff = now - UNATTRIBUTED_RECONCILE_SEC
        while (self._pending_observed_damage
               and self._pending_observed_damage[0][0] <= cutoff):
            _timestamp, amount = self._pending_observed_damage.popleft()
            self._committed_unattributed_damage += amount
        # 有来源伤害可能命中了尚未建立基线或已离场的敌人；过期后不能继续
        # 抵消未来真正的无来源伤害。
        while (self._pending_attributed_damage
               and self._pending_attributed_damage[0][0] <= cutoff):
            self._pending_attributed_damage.popleft()

    def _refresh_damage_stats(self, infos: dict[int, CharacterInfo],
                              enemies=None,
                              track_unattributed_damage=False) -> None:
        if (not self._damage_entries
                or self._tick - self._damage_layout_tick >= self.DAMAGE_LAYOUT_EVERY):
            self._refresh_damage_layout()
        if not self.mc.is_ptr(self._damage_stats_addr):
            return

        reqs = [(self._damage_stats_addr + gs.BattleStatsFields.TOTAL_DAMAGE, 4)]
        tags = [('', 'global_total')]
        for cid, entry in self._damage_entries.items():
            reqs.append((entry['addr'] + gs.CharAdvancedStatsFields.OUTPUT_DAMAGE_RANGE,
                         0x14))
            tags.append((cid, 'summary'))
            for kind, layout in entry['lists'].items():
                if layout['count']:
                    reqs.append((layout['data'], layout['count'] * 4))
                    tags.append((cid, kind))
        snapshots = {cid: dict(self._damage_snapshots.get(cid, {}))
                     for cid in self._damage_entries}
        battle_stats_total = self._battle_stats_total_damage
        for (cid, kind), data in zip(tags, self._batch(reqs)):
            if not data:
                continue
            if kind == 'global_total':
                battle_stats_total = self._safe_float(
                    struct.unpack_from('<f', data, 0)[0])
                continue
            snap = snapshots[cid]
            if kind == 'summary':
                first, second = struct.unpack_from('<ff', data, 0)
                raw_total = struct.unpack_from('<f', data, 0x10)[0]
                magnitudes = [abs(self._safe_float(first)),
                              abs(self._safe_float(second))]
                snap['damage_range_min'] = min(magnitudes)
                snap['damage_range_max'] = max(magnitudes)
                snap['raw_output_total'] = self._safe_float(raw_total)
            elif kind == 'breaks':
                values = struct.unpack('<' + 'i' * (len(data) // 4), data)
                snap['output_ep_break_count'] = {
                    idx + 1: max(0, int(value))
                    for idx, value in enumerate(values)}
            else:
                values = struct.unpack('<' + 'f' * (len(data) // 4), data)
                values = [self._safe_float(value) for value in values]
                if kind == 'elements':
                    snap['output_element_damage'] = {
                        idx + 1: abs(value) for idx, value in enumerate(values)}
                else:
                    snap['damage_by_type'] = {
                        idx: max(0.0, value) for idx, value in enumerate(values)}

        for cid, snap in snapshots.items():
            by_type = snap.get('damage_by_type', {})
            total = sum(by_type.get(idx, 0.0) for idx in (
                gs.DamageType.PHYSICAL, gs.DamageType.MAGICAL,
                gs.DamageType.PURE, gs.DamageType.ELEMENT))
            if total <= 0:
                total = max(0.0, -snap.get('raw_output_total', 0.0))
            snap['damage_total'] = total
            snap['healing_total'] = by_type.get(gs.DamageType.HEAL, 0.0)
        self._damage_snapshots = snapshots
        self._battle_stats_total_damage = abs(battle_stats_total)
        character_attributed = sum(max(0.0, self._safe_float(
            snapshot.get('damage_total', 0.0))) for snapshot in snapshots.values())
        self._update_unattributed_tracking(
            track_unattributed_damage, enemies,
            max(self._battle_stats_total_damage, character_attributed))
        self._global_damage_summary = self._make_global_damage_summary(
            self._battle_stats_total_damage, snapshots,
            self._observed_enemy_damage_total,
            self._committed_unattributed_damage,
            self._unattributed_tracking_enabled)

        for info in infos.values():
            snap = snapshots.get(info.cid, {})
            info.damage_total = snap.get('damage_total', 0.0)
            info.healing_total = snap.get('healing_total', 0.0)
            info.damage_range_min = snap.get('damage_range_min', 0.0)
            info.damage_range_max = snap.get('damage_range_max', 0.0)
            info.damage_by_type = dict(snap.get('damage_by_type', {}))
            info.output_element_damage = dict(
                snap.get('output_element_damage', {}))
            info.output_ep_break_count = dict(
                snap.get('output_ep_break_count', {}))
            info.global_total_damage = (
                self._global_damage_summary.global_total_damage)
            info.attributed_damage_total = (
                self._global_damage_summary.attributed_damage_total)
            info.unattributed_damage_total = (
                self._global_damage_summary.unattributed_damage_total)
            info.unattributed_tracking_enabled = (
                self._global_damage_summary.unattributed_tracking_enabled)

        self._record_damage_history(infos, snapshots)

    def _record_damage_history(self, infos: dict[int, CharacterInfo],
                               snapshots: dict[str, dict]) -> None:
        """按 charId 记录本局伤害/治疗峰值，干员撤退后总览仍能显示其累计值。

        历史随 _reset_damage_tracking 在新战斗（BattleLogger 重建）时清空。
        """
        live_cids = set()
        for info in infos.values():
            if not info.cid:
                continue
            live_cids.add(info.cid)
            entry = self._damage_history.setdefault(info.cid, {
                'name': '', 'is_token': False,
                'damage_total': 0.0, 'healing_total': 0.0})
            if info.name:
                entry['name'] = info.name
            entry['is_token'] = bool(info.is_token)
            entry['damage_total'] = max(
                entry['damage_total'],
                max(0.0, self._safe_float(info.damage_total)))
            entry['healing_total'] = max(
                entry['healing_total'],
                max(0.0, self._safe_float(info.healing_total)))
        # 已撤退但游戏仍保留统计条目的干员，继续跟踪其累计值。
        for cid, snap in snapshots.items():
            if not cid or cid in live_cids:
                continue
            entry = self._damage_history.setdefault(cid, {
                'name': '', 'is_token': False,
                'damage_total': 0.0, 'healing_total': 0.0})
            entry['damage_total'] = max(
                entry['damage_total'],
                max(0.0, self._safe_float(snap.get('damage_total', 0.0))))
            entry['healing_total'] = max(
                entry['healing_total'],
                max(0.0, self._safe_float(snap.get('healing_total', 0.0))))

    def poll_fast(self, enemies=None, track_unattributed_damage=False) -> dict:
        t0 = time.time()
        snap = {'ok': False, 'characters': [], 'msg': '', 'frame_ms': 0.0}
        try:
            self._tick += 1
            if (self._tick % self.LIST_EVERY == 1
                    or not self.character_addrs):
                ptrs = self._read_container()
                if ptrs is None:
                    snap['msg'] = '干员容器读取失败'
                    return snap
            else:
                ptrs = list(self.character_addrs)
            blocks = self._batch([
                (ptr, gs.CharacterFields.READ_SIZE) for ptr in ptrs])
            infos = {ptr: self._parse_main(ptr, data)
                     for ptr, data in zip(ptrs, blocks)
                     if data and len(data) >= gs.CharacterFields.READ_SIZE}
            self._fill_new_identities(infos)
            for addr, info in infos.items():
                self._apply_identity(info, self._identities.get(addr, {}))
                self.core._names[addr] = (info.cid, info.name, '')
            self._refresh_attributes(infos)
            self._refresh_runtime(infos)
            self._refresh_positions_and_blocking(infos)
            self._refresh_damage_stats(
                infos, enemies, track_unattributed_damage)
            if self._tick % self.SKILL_EVERY == 1 or any(
                    addr not in self._skill_runtime for addr in infos):
                self._refresh_skills(infos)
            else:
                for addr, info in infos.items():
                    static = dict(self._skill_static.get(info.skill_data_ptr, {}))
                    runtime = dict(self._skill_runtime.get(addr, {}))
                    static['runtime'] = runtime
                    static['current_sp'] = info.sp
                    static['max_sp'] = info.max_sp
                    sp_cost = static.get('sp', {}).get('cost', info.max_sp)
                    static['ready'] = bool(
                        sp_cost > 0 and info.sp >= sp_cost
                        and not runtime.get('wait_for_end'))
                    info.skill = static
            if self._tick % self.BUFF_COUNT_EVERY == 1 or any(
                    addr not in self._buff_counts for addr in infos):
                self._refresh_buff_counts(infos)
            else:
                for addr, info in infos.items():
                    info.buff_count = self._buff_counts.get(addr, 0)

            for info in infos.values():
                self._finalize_character_action(info)

            live = set(infos)
            for cache in (self._identities, self._attr_cached, self._attr_snapshots,
                          self._runtime_ptrs, self._runtime_snapshots, self._positions,
                          self._skill_runtime, self._buff_counts):
                for addr in list(cache):
                    if addr not in live:
                        cache.pop(addr, None)
            characters = sorted(
                infos.values(), key=lambda x: (x.is_token, x.unique_id, x.addr))
            if self._global_damage_summary.unattributed_damage_total > 0:
                characters.append(self._global_damage_summary)
            snap['characters'] = characters
            # 本局曾上场、当前不在场的干员伤害/治疗峰值，供数据总览合并显示。
            snap['character_stats_history'] = [
                CharacterInfo(
                    addr=0, cid=cid, name=entry['name'] or cid,
                    is_token=entry['is_token'], alive=False,
                    damage_total=entry['damage_total'],
                    healing_total=entry['healing_total'])
                for cid, entry in sorted(
                    self._damage_history.items(),
                    key=lambda item: (
                        -(item[1]['damage_total']
                          + item[1]['healing_total']), item[0]))
                if cid not in {info.cid for info in infos.values()}
            ]
            snap['global_damage_summary'] = self._global_damage_summary
            snap['ok'] = True
            snap['frame_ms'] = round((time.time() - t0) * 1000, 1)
            return snap
        except Exception as exc:
            snap['msg'] = f'干员轮询失败: {exc}'
            return snap

    def _read_pointer_list(self, list_ptr: int, limit=256) -> list[int]:
        if not self.mc.is_ptr(list_ptr):
            return []
        (head,) = self.core._detail_batch_read([(list_ptr, 0x20)])
        if not head:
            return []
        items, count = _u64(head, gs.ListInternal.ITEMS), _i32(
            head, gs.ListInternal.SIZE)
        if not (0 <= count <= limit) or (count and not self.mc.is_ptr(items)):
            return []
        if not count:
            return []
        (body,) = self.core._detail_batch_read([
            (items + gs.Il2CppArray.ITEMS, count * 8)])
        return [ptr for ptr in (_u64(body, i * 8) for i in range(count))
                if self.mc.is_ptr(ptr)] if body else []

    def _read_talents(self, block: bytes) -> list[dict]:
        array_ptr = _u64(block, gs.UnitFields.TALENTS)
        talent_ptrs = self.core._read_object_array(array_ptr, 128)
        talent_blocks = self.core._detail_batch_read([
            (ptr, gs.BasicTalentFields.READ_SIZE) for ptr in talent_ptrs])
        rows = []
        for ptr, data in zip(talent_ptrs, talent_blocks):
            if not data:
                continue
            data_ptr = _u64(data, gs.BasicTalentFields.DATA)
            (talent_data,) = self.core._detail_batch_read([
                (data_ptr, gs.TalentDataFields.READ_SIZE)]) \
                if self.mc.is_ptr(data_ptr) else (None,)
            if not talent_data:
                continue
            strings = self.core._read_strings([
                _u64(talent_data, gs.TalentDataFields.PREFAB_KEY),
                _u64(talent_data, gs.TalentDataFields.NAME),
                _u64(talent_data, gs.TalentDataFields.DESCRIPTION),
                _u64(talent_data, gs.TalentDataFields.RANGE_ID),
                _u64(talent_data, gs.TalentDataFields.TOKEN_KEY),
            ])
            bb_ptr = _u64(talent_data, gs.TalentDataFields.BLACKBOARD)
            ability = _u64(data, gs.BasicTalentFields.ABILITY)
            parent_mode = _u64(data, gs.BasicTalentFields.PARENT_MODE)
            rows.append({
                'addr': ptr,
                'data_addr': data_ptr,
                'class': self._class_name(ptr),
                'ability_addr': ability,
                'ability_class': self._class_name(ability),
                'parent_mode_addr': parent_mode,
                'parent_mode_class': self._class_name(parent_mode),
                'required_potential': _i32(
                    talent_data, gs.TalentDataFields.REQUIRED_POTENTIAL_RANK),
                'prefab_key': strings.get(_u64(
                    talent_data, gs.TalentDataFields.PREFAB_KEY), ''),
                'name': strings.get(_u64(
                    talent_data, gs.TalentDataFields.NAME), ''),
                'description': strings.get(_u64(
                    talent_data, gs.TalentDataFields.DESCRIPTION), ''),
                'range_id': strings.get(_u64(
                    talent_data, gs.TalentDataFields.RANGE_ID), ''),
                'token_key': strings.get(_u64(
                    talent_data, gs.TalentDataFields.TOKEN_KEY), ''),
                'hidden': bool(talent_data[gs.TalentDataFields.IS_HIDDEN]),
                'blackboard': self.core._read_blackboards([bb_ptr]).get(bb_ptr, []),
            })
        # 同一天赋会为多个 UnitMode 建立运行时副本；按可见语义合并并保留模式数。
        grouped = {}
        for row in rows:
            signature = (
                row['data_addr'], row['name'], row['prefab_key'],
                row['ability_class'], tuple((x.get('key'), x.get('value'),
                                             x.get('value_str'))
                                            for x in row['blackboard']))
            if signature not in grouped:
                row['mode_count'] = 1
                row['parent_modes'] = [row['parent_mode_class'] or
                                       hex(row['parent_mode_addr'])]
                grouped[signature] = row
            else:
                grouped[signature]['mode_count'] += 1
                mode = row['parent_mode_class'] or hex(row['parent_mode_addr'])
                if mode not in grouped[signature]['parent_modes']:
                    grouped[signature]['parent_modes'].append(mode)
        return list(grouped.values())

    def _annotate_buffs(self, buffs: list[dict]) -> None:
        for identity_addr, identity in self._identities.items():
            self.core._names[identity_addr] = (
                identity.get('cid', ''), identity.get('name', ''), '')
        for buff in buffs:
            ability = buff.get('ability_addr', 0)
            buff['ability_class'] = self._class_name(ability)
            source = buff.get('source_addr', 0)
            key = str(buff.get('key', '')).lower()
            if source in self._identities:
                identity = self._identities[source]
                buff['source_category'] = (
                    '召唤物/装置' if identity.get('is_token') else '干员')
                buff['source'] = identity.get('name') or identity.get('cid') or hex(source)
            elif source:
                buff['source_category'] = '敌人/其他实体'
            elif 'uniequip' in key or '_e_' in key:
                buff['source_category'] = '模组/编队效果'
            elif key.startswith('tile_'):
                buff['source_category'] = '地块效果'
            elif key.startswith('global_'):
                buff['source_category'] = '全局效果'
            else:
                buff['source_category'] = '无实体来源（技能/天赋/关卡）'

    def read_character_detail(self, addr: int) -> CharacterInfo | None:
        if not self.mc.is_ptr(addr):
            return None
        self.core._detail_context.active = True
        try:
            (block,) = self.core._detail_batch_read([
                (addr, gs.CharacterFields.READ_SIZE)])
            if not block or len(block) < gs.CharacterFields.READ_SIZE:
                return None
            info = self._parse_main(addr, block)
            # 身份数据会在换对象后重新读取；详情页不依赖主轮询是否已跑过。
            self._fill_new_identities({addr: info})
            self._apply_identity(info, self._identities.get(addr, {}))
            self.core._names[addr] = (info.cid, info.name, '')

            if self.mc.is_ptr(info.attr_ptr):
                (attr_head,) = self.core._detail_batch_read([(info.attr_ptr, 0x60)])
                if attr_head:
                    raw_ptr = _u64(attr_head, gs.AttributesFields.M_RAW_DATA)
                    cached_ptr = _u64(attr_head, gs.AttributesFields.M_CACHED_DATA)
                    size = (gs.Il2CppArray.ITEMS
                            + gs.AttributeType.E_NUM * gs.OBSCURED_FP_SIZE)
                    reqs, kinds = [], []
                    if self.mc.is_ptr(raw_ptr):
                        reqs.append((raw_ptr, size)); kinds.append('raw')
                    if self.mc.is_ptr(cached_ptr):
                        reqs.append((cached_ptr, size)); kinds.append('cached')
                    for kind, data in zip(kinds, self.core._detail_batch_read(reqs)):
                        tmp = EnemyInfo(addr)
                        if kind == 'raw':
                            self.core._apply_raw_data(data, tmp)
                            info.raw_attributes = dict(tmp.raw_attributes)
                        else:
                            self.core._apply_cached_data(data, tmp)
                            info.attributes = dict(tmp.attributes)
                            info.max_hp = info.attribute(gs.AttributeType.MAX_HP)

            self._refresh_runtime({addr: info})
            self._refresh_positions_and_blocking({addr: info})
            self._refresh_skills({addr: info})
            skill = info.skill
            if skill:
                runtime = skill.get('runtime', {})
                runtime['class'] = self._class_name(info.skill_ptr)
                runtime['ability_class'] = self._class_name(
                    runtime.get('ability_addr', 0))
                bb_ptr = skill.get('blackboard_ptr', 0)
                skill['blackboard'] = self.core._read_blackboards([bb_ptr]).get(
                    bb_ptr, [])
                for key in ('blackboard_ptr', 'ability_blackboard_ptr'):
                    ptr = runtime.get(key, 0)
                    runtime[key.replace('_ptr', '')] = \
                        self.core._read_blackboards([ptr]).get(ptr, [])

            info.talents = self._read_talents(block)
            dynamic_list = _u64(block, gs.UnitFields.DYNAMIC_ABILITIES)
            info.dynamic_abilities = [
                {'addr': ptr, 'class': self._class_name(ptr)}
                for ptr in self._read_pointer_list(dynamic_list)]
            settings_list = 0
            if self.mc.is_ptr(info.data_ptr):
                (data,) = self.core._detail_batch_read([
                    (info.data_ptr, gs.BattleCharacterDataFields.READ_SIZE)])
                if data:
                    settings_list = _u64(
                        data, gs.BattleCharacterDataFields.UNI_EQUIP_SETTINGS)
            info.module_settings = [
                {'addr': ptr, 'class': self._class_name(ptr)}
                for ptr in self._read_pointer_list(settings_list)]
            deck_bb = _u64(block, gs.CharacterFields.DECK_BUFF_BLACKBOARD)
            info.deck_buff_blackboard = self.core._read_blackboards([deck_bb]).get(
                deck_bb, [])
            info.buffs = self.core._read_active_buffs(info.buff_container_ptr)
            self._annotate_buffs(info.buffs)
            info.buff_count = len(info.buffs)
            info.global_buffs = self.core._read_global_buffs(addr)
            return info
        finally:
            self.core._detail_context.active = False

    @staticmethod
    def merge_detail(live: CharacterInfo, detail: CharacterInfo) -> CharacterInfo:
        for key in ('raw_attributes', 'buffs', 'global_buffs', 'talents',
                    'dynamic_abilities', 'module_settings',
                    'deck_buff_blackboard'):
            setattr(live, key, getattr(detail, key))
        if detail.skill:
            # 静态说明/Blackboard 来自详情通道；SP、冷却和施法状态必须保留
            # 主高速轮询的最新一帧，不能被稍早完成的详情快照倒灌。
            live_runtime = dict((live.skill or {}).get('runtime', {}))
            live_current_sp = (live.skill or {}).get('current_sp', live.sp)
            live_max_sp = (live.skill or {}).get('max_sp', live.max_sp)
            merged = dict(live.skill or {})
            merged.update(detail.skill)
            merged['runtime'] = live_runtime
            merged['current_sp'] = live_current_sp
            merged['max_sp'] = live_max_sp
            live.skill = merged
        live.buff_count = detail.buff_count
        return live
