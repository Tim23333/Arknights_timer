"""Timeline 字段合同、三层开关及配置代际。

此模块不导入 Qt 或读取游戏内存。读取器在采样入口固定 PolicySnapshot；
消费者用同一注册表投影。身份/帧守卫仍属内部基础设施，不由公开字段开关关闭。
"""
from __future__ import annotations

import copy
import logging
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .custom_options import CustomOptions

POLICY_VERSION = 1
LAYERS = ('collect', 'display', 'publish')


@dataclass(frozen=True)
class FieldSpec:
    """稳定字段 ID 对应读取组、公开 JSON 路径及采集硬依赖。

    ``paths`` 使用实体相对路径；``*`` 表示字典值/数组元素。
    ``capture_required`` 仅用于不可关闭的内部安全前提。
    """
    id: str
    domain: str
    group: str
    paths: tuple[str, ...]
    label: str
    dependencies: tuple[str, ...] = ()
    capture_required: bool = False
    default_display: bool = True
    default_collect: bool = True
    default_publish: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {'id': self.id, 'domain': self.domain, 'group': self.group,
                'paths': list(self.paths), 'label': self.label,
                'dependencies': list(self.dependencies),
                'captureRequired': self.capture_required,
                'defaults': {'collect': self.default_collect,
                             'display': self.default_display,
                             'publish': self.default_publish}}


def _registry() -> dict[str, FieldSpec]:
    result: dict[str, FieldSpec] = {}

    def add(domain, key, group, paths, label, dependencies=(), display=True,
            required=False, collect=True, publish=True):
        field_id = f'{domain}.{key}'
        public_paths = tuple(paths) if isinstance(paths, tuple) else (paths,)
        if domain in ('enemy', 'character'):
            public_paths += (f'columns.{key}',)
        result[field_id] = FieldSpec(field_id, domain, group, public_paths,
                                     label, tuple(dependencies), required, display,
                                     collect, publish)

    # 列键与既有敌我表格保持一致，附加 columns 路径令格式化文本同样受策略约束。
    common = (
        ('name', 'identity', 'name', '名称'),
        ('hp', 'base', ('hp', 'maxHp'), '生命'),
        ('pos', 'base', 'position', '坐标'),
        ('action_state', 'runtime', ('action.state_name', 'action.state_id'), '行为状态'),
        ('action_phase', 'runtime', ('action.name', 'action.phase', 'action.detail',
                                   'action.elapsed_frames', 'action.skill_name',
                                   'action.ready_skills', 'action.clock_source'), '动作阶段'),
        ('remaining_time', 'runtime', ('action.remaining', 'action.remaining_frames',
                                     'action.remaining_kind'), '剩余帧/时间'),
        ('next_action', 'runtime', ('action.next_action', 'action.next_action_detail',
                                  'action.next_action_confidence', 'action.next_action_lane',
                                  'action.next_action_candidates', 'action.next_action_rule',
                                  'action.next_action_rule_detail', 'action.next_action_rule_confidence',
                                  'action.next_action_rule_candidates'), '下一动作预测'),
        ('abnormal_status', 'runtime', ('abnormalStatus', 'abnormalFlags',
                                       'abnormalCombos', 'statusTimers'), '异常状态'),
        ('shield', 'runtime', ('shield', 'specialShield'), '伤害护盾'),
        ('es', 'base', 'elementShield', '元素护盾'),
        ('skill', 'skills', 'skill', '技能'),
    )
    for domain in ('enemy', 'character'):
        for key, group, paths, label in common:
            dependencies = {
                'hp': (f'{domain}.attr_0',),
                'action_phase': (f'{domain}.skill',),
                'remaining_time': (f'{domain}.action_phase',),
                'next_action': (f'{domain}.skill', f'{domain}.abnormal_status',
                                f'{domain}.action_phase'),
                'skill': ('character.sp',) if domain == 'character' else (),
            }.get(key, ())
            if domain == 'enemy' and key == 'skill':
                paths = ('skill', 'skills', 'skillsDetail')
            add(domain, key, group, paths, label, dependencies,
                display=key != 'es' and not (key == 'shield' and domain == 'character'))

    for key, group, paths, label in (
        ('code', 'identity', 'code', '编号'),
        ('eid', 'identity', 'enemyId', '敌人 ID'),
        ('precise_pos', 'precise', 'precisePosition', '精确坐标'),
        ('intent_end', 'pathing', 'pathing.intentEnd', '意图终点'),
        ('current_route', 'pathing', 'pathing.route', '当前路线'),
        ('next_waypoint', 'pathing', 'pathing.nextWaypoint', '下一路点'),
        ('next_checkpoint', 'pathing', 'pathing.nextCheckpoint', '下一检查点'),
        ('checkpoint_countdown', 'pathing', 'pathing.checkpointCountdown', '检查点倒计时'),
        ('immune_status', 'runtime', ('abnormalImmunes', 'abnormalComboImmunes'), '状态免疫'),
        ('ep_sanity', 'runtime', 'elementRemaining.1', '神经损伤剩余'),
        ('ep_water', 'runtime', 'elementRemaining.2', '侵蚀损伤剩余'),
        ('ep_fire', 'runtime', 'elementRemaining.3', '灼燃损伤剩余'),
        ('ep_dark', 'runtime', 'elementRemaining.4', '凋亡损伤剩余'),
        ('ep_anger', 'runtime', 'elementRemaining.5', '狂躁损伤剩余'),
        ('ep_break', 'runtime', 'elementBreakRecovery', '元素爆发恢复'),
        ('life_status', 'base', ('lifecycle', 'alive'), '生存状态'),
        ('end_reason', 'roster', 'endReason', '离场原因'),
        ('finish_reason', 'roster', 'finishReason', '原始离场原因编号'),
        ('end_frame', 'roster', 'endFrame', '观测离场逻辑帧'),
        ('spawn_wait', 'roster', ('spawnEta', 'spawnCondition', 'spawnKind',
                                'spawnSource', 'planned', 'spawnOrder'), '距离出场'),
    ):
        dependencies = (('enemy.next_checkpoint', 'battle.gameTime')
                        if key == 'checkpoint_countdown' else ())
        add('enemy', key, group, paths, label, dependencies,
            display=key not in ('immune_status', 'ep_sanity', 'ep_water',
                               'ep_fire', 'ep_dark', 'ep_anger', 'ep_break'))
    for key, group, paths, label in (
        ('cid', 'identity', 'characterId', '干员 ID'),
        ('kind', 'identity', 'kind', '类别'),
        ('profession', 'identity', 'profession', '职业'),
        ('level', 'identity', ('level', 'phase'), '等级'),
        ('sp', 'base', ('sp', 'maxSp'), '技力'),
        ('alive', 'base', 'alive', '存活状态'),
        ('blocked', 'blocking', ('blockedCount', 'blockedVolume'), '阻挡敌人'),
        ('buff_count', 'buffs', 'buffCount', 'Buff 数'),
        ('damage_total', 'damage', 'damageTotal', '累计伤害'),
        ('global_total_damage', 'damage', 'globalDamageSummary', '全局总伤'),
        ('damage_physical', 'damage', 'damageByType.physical', '物理伤害'),
        ('damage_magical', 'damage', 'damageByType.magical', '法术伤害'),
        ('damage_pure', 'damage', 'damageByType.pure', '真实伤害'),
        ('damage_element', 'damage', 'damageByType.element', '元素伤害'),
        ('element_output_total', 'damage', 'elementOutputTotal', '元素损伤累计'),
        ('healing_total', 'damage', 'healingTotal', '累计治疗'),
        ('unattributed_damage', 'damage', 'unattributedDamage', '未归属伤害跟踪'),
    ):
        dependencies = {
            'alive': ('character.hp',),
            'global_total_damage': ('character.damage_total',),
            'unattributed_damage': ('enemy.hp', 'character.damage_total'),
        }.get(key, ())
        add('character', key, group, paths, label, dependencies,
            display=key not in ('cid', 'alive', 'unattributed_damage',
                               'damage_physical', 'damage_magical', 'damage_pure',
                               'damage_element', 'element_output_total'),
            collect=key != 'unattributed_damage')

    # 属性槽采用既有 ATTRIBUTE_DEFS 的完整可见槽集合（9–12 为保留槽）。
    attributes = (
        (0, '最大生命'), (1, '攻击'), (2, '防御'), (3, '法术抗性'),
        (4, '部署费用'), (5, '阻挡数'), (6, '移动速度'), (7, '攻击速度'),
        (8, '基础攻击间隔'), (13, '每秒生命恢复'), (14, '每秒技力恢复'),
        (15, '技能范围前向延伸'), (16, '最大部署数'), (17, '物理穿透比例'),
        (18, '法抗穿透比例'), (19, '按最大生命每秒恢复'), (20, '嘲讽等级'),
        (21, '再部署时间'), (22, '最大卡组堆叠数'), (23, '重量等级'),
        (24, '基础力度等级'), (25, '固定物理穿透'), (26, '状态抗性'),
        (27, '固定法抗穿透'), (28, '损伤条上限'), (29, '每秒损伤恢复'),
        (30, '技力恢复倍率'), (31, '元素损伤减免'), (32, '元素抗性'),
        (33, '物理伤害命中倍率'), (34, '法术伤害命中倍率'),
        (35, '元素爆发恢复速度'), (36, '减速倍率'), (37, '阻挡半径倍率'),
    )
    for domain in ('enemy', 'character'):
        default_attrs = {1, 2, 3, 6, 7} if domain == 'enemy' else {1, 2, 3, 5, 7}
        for index, label in attributes:
            add(domain, f'attr_{index}', 'attributes', f'attributes.{index}',
                label, display=index in default_attrs)
    for key in ('state', 'stateCode', 'gameTime', 'fixedFrame', 'clockSource',
                'connected', 'configured', 'sampledAt', 'message', 'speedLevel',
                'timeScale', 'isPaused', 'frameConsistent'):
        add('battle', key, 'timer' if key in ('gameTime', 'fixedFrame', 'clockSource',
                                            'connected', 'configured', 'sampledAt', 'message')
            else 'runtime', key, key)
    for domain, keys in (
        ('stage', ('stage', 'squad')), ('deploy', ('events', 'journal')),
        ('quality', ('sampleHz', 'loopMs', 'frameMs', 'ioMs', 'frameConsistent',
                     'pausedSnapshot', 'droppedOutboundFrames', 'resyncCount')),
    ):
        for key in keys:
            add(domain, key, key, key, key)
    for key in ('status', 'selected_id'):
        add('rng', key, 'state', key, key)
    for key in ('id', 'role', 'kind', 'label', 'status', 'total', 'cursor', 'cursor2',
                'history', 'predictions', 'rate', 'activity', 'paired', 'rawOnly'):
        # status 根键和单引擎状态用同一开关；所有角色及 selected 一起过滤。
        paths = (f'selected.{key}', f'by_role.*.{key}')
        if key == 'status':
            paths += ('status',)
        add('rng', key, key if key in ('history', 'predictions', 'rate', 'activity')
            else 'state', paths, key)
    for domain in ('enemy_detail', 'character_detail'):
        for key in ('attributes', 'rawAttributes', 'buffs', 'globalBuffs', 'skills',
                    'talents', 'specialShield', 'dynamicAbilities', 'equipment',
                    'attackRange', 'effectFrames'):
            add(domain, key, key, key, key)
    for key in ('frame_guard', 'enemy_identity', 'character_identity', 'session'):
        add('internal', key, 'required', (), key, display=False, required=True, publish=False)
    return result


FIELD_REGISTRY: Mapping[str, FieldSpec] = MappingProxyType(_registry())


@dataclass(frozen=True)
class FieldSwitches:
    collect: bool = True
    display: bool = True
    publish: bool = True


@dataclass(frozen=True)
class PolicySnapshot:
    """整轮采样固定的不可变策略；消费层不能倒过来改变采集。"""
    generation: int
    fields: Mapping[str, FieldSwitches]
    _projection_trees: Mapping = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        # 即使通过公开构造器传入普通 dict，调用方也不能在本轮中途篡改策略。
        object.__setattr__(self, 'fields', MappingProxyType(dict(self.fields)))
        # Compile once per immutable policy generation, not once per entity/frame.
        # A terminal None means the whole branch is absent; longer paths below it
        # cannot require another copy. Nested mapping proxies preserve immutability.
        trees = {}
        for spec in FIELD_REGISTRY.values():
            switches = self.fields[spec.id]
            for layer in LAYERS:
                if switches.collect and getattr(switches, layer):
                    continue
                root = trees.setdefault((spec.domain, layer), {})
                for path in spec.paths:
                    components = path.split('.')
                    target = root
                    for component in components[:-1]:
                        if component in target and target[component] is None:
                            break
                        target = target.setdefault(component, {})
                    else:
                        target[components[-1]] = None
        object.__setattr__(self, '_projection_trees', MappingProxyType({
            key: _freeze_projection_tree(tree) for key, tree in trees.items()}))

    def __deepcopy__(self, memo):
        # 所有成员均为不可变值，Qt/快照复制可安全复用，避免 mappingproxy 无法 pickle。
        return self

    def enabled(self, field_id: str, layer: str = 'collect') -> bool:
        if layer not in LAYERS:
            raise ValueError(f'未知策略层: {layer}')
        return getattr(self.fields[field_id], layer)

    def group_enabled(self, domain: str, group: str) -> bool:
        return any(self.enabled(spec.id) for spec in FIELD_REGISTRY.values()
                   if spec.domain == domain and spec.group == group)

    @property
    def collected_ids(self) -> frozenset[str]:
        return frozenset(key for key, switches in self.fields.items() if switches.collect)

    def to_dict(self) -> dict[str, Any]:
        return {'version': POLICY_VERSION, 'generation': self.generation,
                'fields': {key: {layer: getattr(value, layer) for layer in LAYERS}
                           for key, value in self.fields.items()}}


class PolicyValidationError(ValueError):
    """携带可供 Web UI 按字段定位的错误，而非只返回失败布尔值。"""
    def __init__(self, errors: list[dict[str, str]]) -> None:
        self.errors = errors
        super().__init__('; '.join(error['message'] for error in errors))


class PolicyStore:
    """集中验证、原子持久化并发布不可变代际的字段策略权威。"""
    def __init__(self, options: CustomOptions | None = None) -> None:
        self._lock = threading.RLock()
        self._options = options
        self._listeners: list[Callable[[PolicySnapshot], None]] = []
        defaults = {key: FieldSwitches(collect=spec.default_collect,
                                     display=spec.default_display,
                                     publish=spec.default_publish)
                    for key, spec in FIELD_REGISTRY.items()}
        self._snapshot = PolicySnapshot(0, MappingProxyType(defaults))
        self.load_errors: list[dict[str, str]] = []
        if options is not None:
            stored = options.get('field_policy')
            if (not isinstance(stored, dict) or type(stored.get('version')) is not int
                    or stored.get('version') != POLICY_VERSION):
                self.load_errors = [{'field': 'field_policy', 'message': '字段策略版本无效，使用默认值'}]
            else:
                try:
                    fields = self._validate(stored.get('fields', {}))
                    self._snapshot = PolicySnapshot(0, MappingProxyType(fields))
                except PolicyValidationError as error:
                    self.load_errors = error.errors

    def snapshot(self) -> PolicySnapshot:
        with self._lock:
            return self._snapshot

    def subscribe(self, callback: Callable[[PolicySnapshot], None]) -> None:
        with self._lock:
            self._listeners.append(callback)

    def validate(self, candidate: Mapping[str, Any]) -> list[dict[str, str]]:
        with self._lock:
            try:
                self._validate(candidate)
            except PolicyValidationError as error:
                return error.errors
        return []

    def _validate(self, candidate: Mapping[str, Any]) -> dict[str, FieldSwitches]:
        fields = dict(self._snapshot.fields)
        errors: list[dict[str, str]] = []
        if not isinstance(candidate, Mapping):
            raise PolicyValidationError([{'field': 'field_policy', 'message': '字段策略必须是对象'}])
        for key, incoming in candidate.items():
            if key not in FIELD_REGISTRY:
                errors.append({'field': str(key), 'message': f'未知字段: {key}'})
                continue
            if not isinstance(incoming, Mapping):
                errors.append({'field': key, 'message': f'{key} 的开关必须是对象'})
                continue
            values = {layer: getattr(fields[key], layer) for layer in LAYERS}
            for layer, value in incoming.items():
                if layer not in LAYERS or type(value) is not bool:
                    errors.append({'field': key, 'message': f'{key}.{layer} 必须是合法布尔开关'})
                else:
                    values[layer] = value
            fields[key] = FieldSwitches(**values)
        for key, spec in FIELD_REGISTRY.items():
            if spec.capture_required and not fields[key].collect:
                errors.append({'field': key, 'message': f'{key} 是不可关闭的内部前提'})
            if fields[key].collect:
                for dependency in spec.dependencies:
                    if not fields[dependency].collect:
                        errors.append({'field': key, 'dependency': dependency,
                                       'message': f'{key} 采集依赖 {dependency}，请一起调整'})
        if errors:
            raise PolicyValidationError(errors)
        return fields

    def commit(self, candidate: Mapping[str, Any]) -> PolicySnapshot:
        """验证整份变更，写盘成功后一次发布新代际；失败保留全部旧状态。"""
        with self._lock:
            fields = self._validate(candidate)
            if fields == self._snapshot.fields:
                return self._snapshot
            next_policy = PolicySnapshot(self._snapshot.generation + 1, MappingProxyType(fields))
            if self._options is not None:
                serialized = next_policy.to_dict()
                serialized.pop('generation')
                self._options.replace_section('field_policy', serialized, notify=False)
            self._snapshot = next_policy
            listeners = list(self._listeners)
        if self._options is not None:
            self._options.notify_listeners()
        for callback in listeners:
            try:
                callback(next_policy)
            except Exception:
                logging.getLogger(__name__).exception('字段策略监听器失败')
        return next_policy

    def to_dict(self) -> dict[str, Any]:
        return self.snapshot().to_dict()


def _freeze_projection_tree(tree):
    return MappingProxyType({key: None if child is None else _freeze_projection_tree(child)
                             for key, child in tree.items()})


def _copy_without_paths(value, tree):
    """Copy only branches whose registered keys are actually removed."""
    result = value
    wildcard = tree.get('*', False)
    if isinstance(value, dict):
        if wildcard is None:
            return {}
        if wildcard is not False:
            for key, child in value.items():
                projected = _copy_without_paths(child, wildcard)
                if projected is not child:
                    if result is value:
                        result = dict(value)
                    result[key] = projected
        for key, subtree in tree.items():
            if key == '*':
                continue
            actual = int(key) if key.isdecimal() and int(key) in result else key
            if actual not in result:
                continue
            if subtree is None:
                if result is value:
                    result = dict(value)
                result.pop(actual)
            else:
                child = result[actual]
                projected = _copy_without_paths(child, subtree)
                if projected is not child:
                    if result is value:
                        result = dict(value)
                    result[actual] = projected
    elif isinstance(value, list) and wildcard is not False:
        if wildcard is None:
            return []
        for index, child in enumerate(value):
            projected = _copy_without_paths(child, wildcard)
            if projected is not child:
                if result is value:
                    result = list(value)
                result[index] = projected
    return result


def project_snapshot(domain: str, payload: Mapping[str, Any], policy: PolicySnapshot,
                     layer: str = 'publish') -> dict[str, Any]:
    """Project an owned, immutable canonical snapshot without copying its metadata.

    Use only inside a publication boundary that never mutates accepted snapshots.
    The root is always independent; changed nested paths are cloned, unchanged
    values are shared read-only. In particular, replace rather than mutate meta
    and fieldStates. Untrusted/mutable caller data must use project_payload.
    """
    if layer not in LAYERS:
        raise ValueError(f'未知策略层: {layer}')
    tree = policy._projection_trees.get((domain, layer))
    projected = _copy_without_paths(payload, tree) if tree else payload
    return dict(projected)


def project_payload(domain: str, payload: Mapping[str, Any], policy: PolicySnapshot,
                    layer: str = 'publish') -> dict[str, Any]:
    """投影注册字段及格式化列，采集关压过消费者偏好，不改变源快照。

    数据应先经过领域白名单；本函数负责开关，不能代替 WS 的指针/地址过滤。
    调用方对 ``items`` 中每个实体分别调用。字段状态元数据保持可见用于解释空值。
    """
    return copy.deepcopy(project_snapshot(domain, payload, policy, layer))


def collection_record(source_frame: int | None, latest_known_frame: int | None,
                      generation: int, state: str, reason: str = '', *,
                      accepted_frame: int | None = None) -> dict[str, Any]:
    """记录来源与完成时缓存帧；落后不自动改变发布策略或把来源洗成新帧。

    static 表示已验证的进程静态元数据（例如图鉴编号），不是实时属性采样；
    未采样过的 HP/位置不能借用此状态绕过不可用掩码。
    """
    if state not in ('current', 'static', 'not_collected', 'unavailable', 'historical'):
        raise ValueError(f'未知采集状态: {state}')
    return {'sourceFrame': source_frame, 'latestKnownFrame': latest_known_frame,
            'acceptedFrame': accepted_frame, 'generation': generation,
            'collectionState': state, 'reason': reason}


def field_status_text(entity, field_id: str) -> str | None:
    """Explain unavailable runtime defaults consistently in both local frontends."""
    state = getattr(entity, 'field_states', {}).get(field_id, {}).get('collectionState')
    return {'not_collected': '未采集', 'unavailable': '不可用'}.get(state)
