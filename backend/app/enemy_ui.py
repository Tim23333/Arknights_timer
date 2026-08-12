# -*- coding: utf-8 -*-
"""主程序敌人表格列定义、列选择器和详情窗口。"""

import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QAbstractSpinBox, QCheckBox, QDialog, QDialogButtonBox,
    QGridLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
    QScrollArea, QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QToolButton, QVBoxLayout, QWidget,
)

from tools.enemy_health import game_structs as gs
from tools.enemy_health.enemy_reader import countdown_text

from .enemy_buff_descriptions import (
    buff_chinese_name, describe_active_buff, describe_blackboard, describe_buff_def,
    describe_global_buff, global_buff_chinese_name,
)
from .effect_frames_ui import COLUMNS as FRAMES_COLUMNS, enemy_frame_rows


def format_skill_cd(skills, sep='; ', prec=1):
    """技能 CD 列表转成主程序显示文本。"""
    if not skills:
        return '-'
    parts = []
    for key, remain, period in skills:
        if remain <= 0.05:
            parts.append(f'{key} 就绪')
        else:
            parts.append(f'{key} {remain:.{prec}f}/{period:.{prec}f}s')
    return sep.join(parts)


def _col(key, label, width=80, default=False, precision=False):
    return {
        'key': key,
        'label': label,
        'width': width,
        'default': default,
        'precision': precision,
    }


ENEMY_COLUMN_DEFS = [
    _col('row', '#', 36, True),
    _col('name', '名称', 130, True),
    _col('code', '编号', 60, True),
    _col('eid', '敌人ID', 150, True),
    _col('hp', '血量', 185, True, True),
    _col('pos', '坐标', 110, True, True),
    _col('action_state', '行为状态', 72, True),
    _col('action_phase', '动作阶段', 180, True),
    _col('remaining_time', '剩余帧/时间', 170, True),
    _col('next_action', '下一动作预测', 260, True),
    _col('abnormal_status', '异常状态', 160, True),
    _col('immune_status', '状态免疫', 160, False),
]

_DEFAULT_ATTRS = {1, 2, 3, 6, 7}
for _idx, _internal, _name in gs.ATTRIBUTE_DEFS:
    _label = '状态抗性' if _idx == gs.AttributeType.ONE_MINUS_STATUS_RESISTANCE else _name
    ENEMY_COLUMN_DEFS.append(
        _col(f'attr_{_idx}', _label, max(72, min(140, len(_label) * 15)),
             _idx in _DEFAULT_ATTRS, True))

ENEMY_COLUMN_DEFS.extend([
    _col('es', '元素护盾', 90, False, True),
    _col('shield', '伤害护盾', 170, True, True),
    _col('ep_sanity', '神经损伤剩余', 145, False, True),
    _col('ep_water', '侵蚀损伤剩余', 145, False, True),
    _col('ep_fire', '灼燃损伤剩余', 145, False, True),
    _col('ep_dark', '凋亡损伤剩余', 145, False, True),
    _col('ep_anger', '狂躁损伤剩余', 145, False, True),
    _col('ep_break', '元素爆发恢复', 95, False),
    _col('skill', '技能 CD', 150, True, True),
    _col('life_status', '生存状态', 72, True),
    _col('spawn_wait', '距离出场', 170, True),
    _col('detail', '详情', 64, True),
])

ENEMY_COLUMN_INDEX = {col['key']: idx for idx, col in enumerate(ENEMY_COLUMN_DEFS)}
SPAWN_KIND_NAMES = {
    'scheduled': '固定波次',
    'conditional': '条件触发',
    'summoned': '召唤/死亡转换',
    'after_death': '死亡后触发',
    'dynamic': '运行时生成',
}
DEFAULT_VISIBLE_COLUMNS = {col['key'] for col in ENEMY_COLUMN_DEFS if col['default']}


def precision_column_defs(visible=None):
    """返回精度设置项；传入 visible 时仅包含当前显示的数值列。"""
    chosen = None if visible is None else set(visible)
    return [
        (col['key'], col['label'])
        for col in ENEMY_COLUMN_DEFS
        if col['precision'] and (chosen is None or col['key'] in chosen)
    ]


def default_precision_values(value=2):
    values = {key: value for key, _label in precision_column_defs()}
    values['default'] = value
    return values


def visible_enemy_rows(enemies, hide_departed=True):
    """过滤并稳定排序：场上存活置顶，未出场居中，阵亡/离场置底。"""
    rows = list(enemies)
    if hide_departed:
        rows = [enemy for enemy in rows
                if getattr(enemy, 'lifecycle', 'active') != 'departed']

    def priority(enemy):
        lifecycle = getattr(enemy, 'lifecycle', 'active')
        if lifecycle == 'active' and getattr(enemy, 'alive', True):
            return 0
        if lifecycle == 'pending':
            return 1
        return 2

    # sorted 是稳定排序，同一状态组内继续保持关卡预定/首次发现顺序。
    return sorted(rows, key=priority)


def load_visible_columns(settings, key):
    value = settings.value(key, '')
    if isinstance(value, str):
        chosen = {x for x in value.split(',') if x}
    elif isinstance(value, (list, tuple)):
        chosen = set(value)
    else:
        chosen = set()
    valid = set(ENEMY_COLUMN_INDEX)
    chosen &= valid
    if not chosen:
        chosen = set(DEFAULT_VISIBLE_COLUMNS)
    migration_key = key + '/damage_shield_v2'
    marker = settings.value(migration_key, False)
    migrated = marker is True or str(marker).lower() in ('1', 'true', 'yes')
    # 旧版本的“普通护盾”默认隐藏。升级后仅自动展示一次新的伤害护盾列；用户
    # 此后若主动取消勾选，迁移标记会阻止下一次启动再次强制打开。
    if not migrated:
        chosen.add('shield')
        settings.setValue(migration_key, True)
    migration_key = key + '/action_phase_v1'
    marker = settings.value(migration_key, False)
    migrated = marker is True or str(marker).lower() in ('1', 'true', 'yes')
    if not migrated:
        chosen.update(('action_phase', 'remaining_time'))
        settings.setValue(migration_key, True)
    migration_key = key + '/next_action_v1'
    marker = settings.value(migration_key, False)
    migrated = marker is True or str(marker).lower() in ('1', 'true', 'yes')
    if not migrated:
        chosen.add('next_action')
        settings.setValue(migration_key, True)
    return chosen


def save_visible_columns(settings, key, columns):
    ordered = [col['key'] for col in ENEMY_COLUMN_DEFS if col['key'] in columns]
    settings.setValue(key, ','.join(ordered))


def load_column_order(settings, key, all_keys):
    """读取列显示顺序，返回包含全部合法 key 的列表：存档顺序优先，
    存档缺失的列（如版本更新新增的列）按定义顺序附在末尾。"""
    value = settings.value(key, '')
    if isinstance(value, str):
        saved = [part for part in value.split(',') if part]
    elif isinstance(value, (list, tuple)):
        saved = list(value)
    else:
        saved = []
    valid = set(all_keys)
    order = [k for k in saved if k in valid]
    order.extend(k for k in all_keys if k not in order)
    return order


def save_column_order(settings, key, order):
    settings.setValue(key, ','.join(order))


def apply_column_order(table, order, column_index):
    """按 key 顺序重排表格的视觉列。仅移动表头 section，逻辑列不变，
    单元格寻址 (column_index) 与列宽/可见性逻辑均不受影响。"""
    header = table.horizontalHeader()
    for visual, key in enumerate(order):
        logical = column_index.get(key)
        if logical is None:
            continue
        current = header.visualIndex(logical)
        if 0 <= current != visual:
            header.moveSection(current, visual)


class _ColumnOrderList(QListWidget):
    """显示列顺序列表：条目可拖动换位 (InternalMove)，与勾选状态双向同步。"""

    def __init__(self, labels):
        super().__init__()
        self._labels = labels
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

    def append_key(self, key):
        if self.find_key(key) is not None:
            return
        item = QListWidgetItem(self._labels.get(key, key))
        item.setData(Qt.ItemDataRole.UserRole, key)
        item.setToolTip(key)
        self.addItem(item)

    def remove_key(self, key):
        item = self.find_key(key)
        if item is not None:
            self.takeItem(self.row(item))

    def find_key(self, key):
        for row in range(self.count()):
            item = self.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == key:
                return item
        return None

    def keys(self):
        return [self.item(row).data(Qt.ItemDataRole.UserRole)
                for row in range(self.count())]


class EnemyColumnDialog(QDialog):
    def __init__(self, parent, visible, order=None):
        super().__init__(parent)
        self.setWindowTitle('自定义敌人列表列')
        self.resize(880, 520)
        root = QVBoxLayout(self)
        root.addWidget(QLabel(
            '左侧勾选需要显示的字段（未勾选的数据仍在“详情”中保留）；'
            '右侧为当前显示顺序，拖动条目即可调整，新勾选的列排在末尾。'))

        body_row = QHBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        grid = QGridLayout(body)
        self.checks = {}
        for idx, col in enumerate(ENEMY_COLUMN_DEFS):
            cb = QCheckBox(col['label'])
            cb.setChecked(col['key'] in visible)
            cb.setToolTip(col['key'])
            cb.toggled.connect(
                lambda checked, key=col['key']: self._on_toggled(key, checked))
            grid.addWidget(cb, idx // 3, idx % 3)
            self.checks[col['key']] = cb
        grid.setRowStretch((len(ENEMY_COLUMN_DEFS) + 2) // 3, 1)
        scroll.setWidget(body)
        body_row.addWidget(scroll, 1)

        order_host = QWidget()
        order_box = QVBoxLayout(order_host)
        order_box.setContentsMargins(0, 0, 0, 0)
        order_box.addWidget(QLabel('显示顺序（拖动调整）:'))
        labels = {col['key']: col['label'] for col in ENEMY_COLUMN_DEFS}
        self.order_list = _ColumnOrderList(labels)
        order_box.addWidget(self.order_list, 1)
        order_host.setFixedWidth(220)
        body_row.addWidget(order_host)
        root.addLayout(body_row, 1)

        # 初始列表 = 存档顺序中当前可见的列；存档未覆盖的可见列补到末尾
        full_order = list(order) if order else [col['key'] for col in ENEMY_COLUMN_DEFS]
        for key in full_order:
            if key in visible:
                self.order_list.append_key(key)
        for col in ENEMY_COLUMN_DEFS:
            if col['key'] in visible:
                self.order_list.append_key(col['key'])

        presets = QHBoxLayout()
        btn_default = QPushButton('恢复默认')
        btn_default.clicked.connect(
            lambda: self._set_checked(DEFAULT_VISIBLE_COLUMNS))
        btn_all = QPushButton('全部显示')
        btn_all.clicked.connect(lambda: self._set_checked(set(self.checks)))
        btn_none = QPushButton('全部隐藏')
        btn_none.clicked.connect(lambda: self._set_checked(set()))
        presets.addWidget(btn_default)
        presets.addWidget(btn_all)
        presets.addWidget(btn_none)
        presets.addStretch(1)
        root.addLayout(presets)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _on_toggled(self, key, checked):
        if checked:
            self.order_list.append_key(key)
        else:
            self.order_list.remove_key(key)

    def _set_checked(self, selected):
        for key, cb in self.checks.items():
            cb.setChecked(key in selected)
        # 勾选信号同步会让状态未变的列保留原位；预设统一重置为定义顺序
        self.order_list.clear()
        for col in ENEMY_COLUMN_DEFS:
            if col['key'] in selected:
                self.order_list.append_key(col['key'])

    def values(self):
        return {key for key, cb in self.checks.items() if cb.isChecked()}

    def ordered_keys(self):
        return self.order_list.keys()


class _PrecisionSpin(QWidget):
    """使用独立加减按钮，避免 QSpinBox 原生按钮受全局样式挤压。"""

    def __init__(self, value, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.minus = QToolButton()
        self.minus.setText('−')
        self.minus.setToolTip('减少一位小数')
        self.minus.setFixedSize(30, 28)

        self.spin = QSpinBox()
        self.spin.setRange(0, 6)
        self.spin.setValue(value)
        self.spin.setSuffix(' 位')
        self.spin.setAlignment(Qt.AlignCenter)
        self.spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin.setMinimumWidth(76)
        self.spin.setFixedHeight(28)

        self.plus = QToolButton()
        self.plus.setText('+')
        self.plus.setToolTip('增加一位小数')
        self.plus.setFixedSize(30, 28)

        self.minus.clicked.connect(self.spin.stepDown)
        self.plus.clicked.connect(self.spin.stepUp)
        layout.addWidget(self.minus)
        layout.addWidget(self.spin, 1)
        layout.addWidget(self.plus)

    def value(self):
        return self.spin.value()


class EnemyPrecisionDialog(QDialog):
    """当前显示数值列的小数位数设置（0-6）。"""

    def __init__(self, parent, decimals, visible=None):
        super().__init__(parent)
        self.setWindowTitle('小数位设置')
        self.resize(620, 460)
        root = QVBoxLayout(self)
        root.addWidget(QLabel(
            '仅列出当前显示的数值列；显示列变化后，本列表会自动同步。'))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        grid = QGridLayout(body)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)
        self.controls = {}
        columns = precision_column_defs(visible)
        for idx, (key, label) in enumerate(columns):
            row = idx // 2
            base = (idx % 2) * 2
            name = QLabel(f'{label}:')
            control = _PrecisionSpin(decimals.get(key, decimals.get('default', 2)))
            grid.addWidget(name, row, base)
            grid.addWidget(control, row, base + 1)
            self.controls[key] = control
        if not columns:
            grid.addWidget(QLabel('当前没有已显示的数值列。'), 0, 0, 1, 4)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        grid.setRowStretch((len(columns) + 1) // 2, 1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def values(self):
        return {key: control.value() for key, control in self.controls.items()}


def format_column_value(key, enemy, decimals, row=0):
    precision = decimals.get(key, decimals.get('default', 2))
    lifecycle = getattr(enemy, 'lifecycle', 'active')
    if key == 'row':
        return str(getattr(enemy, 'spawn_order', 0) or (row + 1))
    if key == 'name':
        return enemy.name or enemy.eid or '?'
    if key == 'code':
        return enemy.code or '-'
    if key == 'eid':
        return enemy.eid
    if lifecycle == 'pending' and key not in ('life_status', 'spawn_wait'):
        return '-'
    if key == 'pos':
        p = decimals.get('pos', precision)
        return f'({enemy.pos_x:.{p}f}, {enemy.pos_y:.{p}f})'
    if key == 'action_state':
        return gs.ENEMY_STATE_NAMES.get(enemy.state_id, f'未知({enemy.state_id})')
    if key == 'action_phase':
        return enemy.action_text
    if key == 'remaining_time':
        return countdown_text(getattr(enemy, 'action', {}))
    if key == 'next_action':
        action = getattr(enemy, 'action', {}) or {}
        confidence_prefix = {
            'confirmed': '[确定] ', 'unselected': '[未预选] ',
            'inferred': '[推断] ',
            'rule_calculated': '[规则计算] ',
            'rule_snapshot': '[规则快照] ',
            'rule_candidates': '[规则随机] ',
            'rule_partial': '[规则待判] ',
        }

        def line(label, value_key, confidence_key):
            value = action.get(value_key) or '-'
            prefix = confidence_prefix.get(action.get(confidence_key), '')
            return f'[{label}] {prefix}{value}' if value != '-' else f'[{label}] -'

        return '\n'.join((
            line('Boss规则', 'next_action_rule',
                 'next_action_rule_confidence'),
            line('含CD', 'next_action', 'next_action_confidence'),
        ))
    if key == 'abnormal_status':
        return enemy.status_text()
    if key == 'immune_status':
        values = [gs.ABNORMAL_FLAG_CN_NAMES.get(i, str(i))
                  for i, count in enumerate(enemy.abnormal_immunes) if count > 0]
        values += [gs.ABNORMAL_COMBO_CN_NAMES.get(i, str(i))
                   for i, count in enumerate(enemy.abnormal_combo_immunes) if count > 0]
        return '、'.join(values) if values else '-'
    if key.startswith('attr_'):
        idx = int(key[5:])
        legacy_precision_key = {
            gs.AttributeType.ATK: 'atk', gs.AttributeType.DEF: 'def',
            gs.AttributeType.MAGIC_RESISTANCE: 'res',
            gs.AttributeType.MOVE_SPEED: 'mspd', gs.AttributeType.ATTACK_SPEED: 'aspd',
        }.get(idx)
        if key not in decimals and legacy_precision_key:
            precision = decimals.get(legacy_precision_key, precision)
        if idx == gs.AttributeType.ONE_MINUS_STATUS_RESISTANCE:
            value = enemy.status_resistance
        elif idx == gs.AttributeType.MAX_EP:
            value = enemy.effective_max_ep
        else:
            value = enemy.attribute(idx)
        return f'{value:.{precision}f}'
    if key == 'es':
        return f'{enemy.es:.{precision}f}'
    if key == 'shield':
        parts = []
        if enemy.shield > 0:
            parts.append(f'通用 {enemy.shield:.{precision}f}')
        special = getattr(enemy, 'special_shield', 0.0)
        if special > 0:
            mask = getattr(enemy, 'special_shield_mask', 0)
            types = [name for bit, name in gs.DAMAGE_TYPE_MASK_CN_NAMES.items()
                     if mask & bit]
            label = '/'.join(types) if types else '特殊'
            parts.append(f'{label} {special:.{precision}f}')
        return '；'.join(parts) if parts else f'{0.0:.{precision}f}'
    ep_types = {
        'ep_sanity': gs.ElementType.SANITY,
        'ep_water': gs.ElementType.WATER,
        'ep_fire': gs.ElementType.FIRE,
        'ep_dark': gs.ElementType.DARK,
        'ep_anger': gs.ElementType.ANGER,
    }
    if key in ep_types:
        _, remaining, maximum = enemy.element_damage(ep_types[key])
        percent = remaining / maximum * 100 if maximum > 0 else 0.0
        return f'{remaining:.{precision}f}/{maximum:.{precision}f} ({percent:.{precision}f}%)'
    if key == 'ep_break':
        return '恢复中' if enemy.ep_break_recovery else '-'
    if key == 'skill':
        return format_skill_cd(enemy.skills, sep='\n', prec=decimals.get('skill', precision))
    if key == 'life_status':
        if lifecycle == 'pending':
            return '未出场'
        if lifecycle == 'departed':
            return '已离场'
        return '存活' if enemy.alive else ('退场' if enemy.finish else '阵亡')
    if key == 'spawn_wait':
        if lifecycle == 'pending':
            eta = getattr(enemy, 'spawn_eta', None)
            if eta is not None:
                return f'{max(0.0, float(eta)):.1f} 秒'
            return getattr(enemy, 'spawn_condition', '') or '等待关卡条件触发'
        if lifecycle == 'active':
            return '已出场'
        return '已离场'
    return ''


def _fmt(value, precision=6):
    if isinstance(value, float):
        return f'{value:.{precision}f}'.rstrip('0').rstrip('.') or '0'
    return str(value)


def _bb_text(rows):
    return '; '.join(f"{row.get('key') or '?'}=" +
                     (row.get('value_str') or _fmt(row.get('value', 0.0)))
                     for row in rows) or '-'


def _make_table(headers):
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectRows)
    table.setAlternatingRowColors(True)
    table.horizontalHeader().setStretchLastSection(True)
    return table


def _fill_table(table, rows, max_column_width=420, resize_columns=True):
    table.setUpdatesEnabled(False)
    table.setRowCount(len(rows))
    try:
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                text = _fmt(value)
                item = table.item(r, c)
                if item is None:
                    item = QTableWidgetItem()
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    table.setItem(r, c, item)
                if item.text() != text:
                    item.setText(text)
                    item.setToolTip(text)
        if resize_columns:
            table.resizeColumnsToContents()
            for column in range(table.columnCount()):
                if table.columnWidth(column) > max_column_width:
                    table.setColumnWidth(column, max_column_width)
    finally:
        table.setUpdatesEnabled(True)


class EnemyDetailDialog(QDialog):
    """敌人完整详情：属性、五类损伤、状态/免疫、Buff、关卡 Buff 和技能。"""

    def __init__(self, parent, enemy):
        super().__init__(parent)
        self.enemy = enemy
        self._first_update = True
        self.setWindowTitle('敌人详情')
        self.resize(1080, 760)
        root = QVBoxLayout(self)
        self.title = QLabel()
        self.title.setStyleSheet('font-size:16px;font-weight:600;')
        root.addWidget(self.title)
        self.live_status = QLabel('正在获取完整详情 ...')
        self.live_status.setStyleSheet('color:#888888;')
        root.addWidget(self.live_status)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        self.overview = _make_table(['项目', '数值'])
        self.attrs = _make_table(['属性', '内部名', '原始值', '最终值', '变化'])
        self.elements = _make_table([
            '损伤类型', '内部名', '已累积', '剩余', '上限',
            '已累积比例', '剩余比例', '爆发'])
        self.statuses = _make_table([
            '类别', '状态', '内部名', '生效计数', '剩余时间', '免疫计数', '反制计数'])
        self.buffs = _make_table([
            '中文名称', '内部键', '效果说明', '来源', '运行信息', '时间', '层数',
            '属性公式', '状态/免疫', '护盾', '参数说明', '原始 Blackboard'])
        self.globals = _make_table([
            '中文名称', '内部键', '效果说明', '来源阵营', '作用当前敌人', '目标数',
            '实例信息', '生成 Buff', '参数说明', '原始 Blackboard'])
        self.skills = _make_table(['技能', '优先级', '剩余CD', '总CD', '状态'])
        self.frames = _make_table(FRAMES_COLUMNS)
        for label, table in (
                ('概览', self.overview), ('属性', self.attrs), ('损伤条', self.elements),
                ('状态与免疫', self.statuses), ('当前 Buff', self.buffs),
                ('关卡效果', self.globals), ('技能', self.skills),
                ('生效帧', self.frames)):
            self.tabs.addTab(table, label)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.update_enemy(enemy)
        self.live_status.setText('正在获取完整详情 ...')

    def set_live_error(self, message):
        self.live_status.setText(message)
        self.live_status.setStyleSheet('color:#d99034;')

    def update_enemy(self, enemy):
        self.enemy = enemy
        resize_columns = self._first_update
        self.title.setText(
            f'{enemy.name or enemy.eid or "?"}  ·  {enemy.code or "-"}  ·  {enemy.eid}')
        state = gs.ENEMY_STATE_NAMES.get(enemy.state_id, f'未知({enemy.state_id})')
        lifecycle = getattr(enemy, 'lifecycle', 'active')
        life_text = {
            'pending': '未出场', 'departed': '已离场', 'active': '场上',
        }.get(lifecycle, '存活' if enemy.alive else '已离场')
        action = getattr(enemy, 'action', {}) or {}
        overview = [
            ('实例地址', hex(enemy.addr)), ('实例ID', enemy.eid), ('敌人编号', enemy.code or '-'),
            ('生存状态', life_text),
            ('行为状态', state), ('动作阶段', enemy.action_text),
            ('动作说明', action.get('detail') or '-'),
            ('剩余帧/时间', countdown_text(action)),
            ('倒计时含义', action.get('remaining_kind') or '-'),
            ('倒计时来源', action.get('clock_source') or '-'),
            ('精确动画计时', '是（当前速度且未被中断）'
             if action.get('animation_exact') else '否/不适用'),
            ('下一动作（Boss规则）', action.get('next_action_rule') or '-'),
            ('Boss规则预测可信度', {
                'confirmed': '游戏已写入', 'unselected': '游戏尚未预选',
                'inferred': '按敌人原始代码推断',
                'rule_calculated': '按敌人原始代码计算（未加入当前CD）',
                'rule_snapshot': '按敌人原始代码计算当前快照（未加入当前CD）',
                'rule_candidates': '敌人原始代码得到候选组（战斗 RNG 择一）',
                'rule_partial': '敌人原始代码仍有 Search/Lua/关卡条件待执行',
            }.get(action.get('next_action_rule_confidence'), '-')),
            ('Boss规则预测依据', action.get('next_action_rule_detail') or '-'),
            ('下一动作（含CD）', action.get('next_action') or '-'),
            ('含CD预测可信度', {
                'confirmed': '游戏已写入', 'unselected': '游戏尚未预选',
                'inferred': '按游戏判据推断（CD/触发次数/优先级）',
                'rule_calculated': '按客户端原始规则计算（当前判据唯一）',
                'rule_snapshot': '按客户端原始规则计算当前快照（动作结束时会重算）',
                'rule_candidates': '按客户端原始规则得到候选组（战斗 RNG 择一）',
                'rule_partial': '按客户端原始规则计算，但仍有 Search/Lua/关卡条件待执行',
            }.get(action.get('next_action_confidence'), '-')),
            ('含CD预测依据', action.get('next_action_detail') or '-'),
            ('当前逻辑帧', action.get('current_frame')
             if action.get('current_frame') is not None else '-'),
            ('动作已进行帧数', action.get('elapsed_frames')
             if action.get('elapsed_frames') is not None else '-'),
            ('当前动画', action.get('animation_track_name')
             or action.get('animation_key') or '-'),
            ('动画播放速度', action.get('animation_track_speed')
             if action.get('animation_track_speed') is not None
             else action.get('animation_speed', '-')),
            ('动画已播放时间', action.get('animation_track_time')
             if action.get('animation_track_time') is not None else '-'),
            ('循环动画', ('是' if action.get('animation_loop') else '否')
             if action.get('animation_loop') is not None else '-'),
            ('当前技能', action.get('skill_name') or '-'),
            ('已就绪技能', '、'.join(action.get('ready_skills') or ()) or '-'),
            ('异常状态', enemy.status_text()),
            ('当前生命', enemy.hp), ('最大生命', enemy.max_hp),
            ('元素护盾', enemy.es), ('通用伤害护盾', enemy.shield),
            ('特殊伤害护盾', getattr(enemy, 'special_shield', 0.0)),
            ('伤害护盾合计', getattr(enemy, 'total_shield', enemy.shield)),
            ('特殊护盾类型', '/'.join(
                name for bit, name in gs.DAMAGE_TYPE_MASK_CN_NAMES.items()
                if getattr(enemy, 'special_shield_mask', 0) & bit) or '-'),
            ('位置', f'({enemy.pos_x}, {enemy.pos_y})'),
            ('阻挡位置', f'({enemy.blk_x}, {enemy.blk_y})'),
            ('出生格', f'({enemy.spawn_col}, {enemy.spawn_row})'),  # (列, 行)，与实时位置一致
            ('方向枚举', enemy.direction),
            ('元素爆发恢复', '是' if enemy.ep_break_recovery else '否'),
            ('状态抗性', enemy.status_resistance),
            ('元素损伤减免', enemy.attribute(gs.AttributeType.EP_DAMAGE_RESISTANCE)),
            ('元素抗性', enemy.attribute(gs.AttributeType.EP_RESISTANCE)),
        ]
        if getattr(enemy, 'spawn_order', 0):
            path = '/'.join(
                str(value + 1) if value >= 0 else '-'
                for value in (enemy.wave_index, enemy.fragment_index, enemy.action_index))
            overview[0:0] = [
                ('预定出怪顺序', enemy.spawn_order),
                ('波次/片段/行动', path),
                ('行动内序号', enemy.spawn_index + 1 if enemy.spawn_index >= 0 else '-'),
                ('路线索引', enemy.route_index if enemy.route_index >= 0 else '-'),
                ('出场方式', SPAWN_KIND_NAMES.get(
                    getattr(enemy, 'spawn_kind', ''),
                    getattr(enemy, 'spawn_kind', '-') or '-')),
                ('触发来源', getattr(enemy, 'spawn_source', '') or '-'),
                ('距离/条件', format_column_value('spawn_wait', enemy, {})),
            ]
        _fill_table(self.overview, overview, resize_columns=resize_columns)

        attr_rows = []
        for idx, internal, name in gs.ATTRIBUTE_DEFS:
            raw = enemy.raw_attributes.get(idx)
            final = enemy.attributes.get(idx)
            if idx == gs.AttributeType.MAX_EP:
                effective = enemy.effective_max_ep
                if effective > max(0.0, final or 0.0):
                    name += '（运行时有效值）'
                    final = effective
            delta = final - raw if raw is not None and final is not None else None
            if idx == gs.AttributeType.ONE_MINUS_STATUS_RESISTANCE:
                name += '（实际状态抗性=' + _fmt(enemy.status_resistance) + '）'
            attr_rows.append((name, internal, '-' if raw is None else raw,
                              '-' if final is None else final,
                              '-' if delta is None else delta))
        _fill_table(self.attrs, attr_rows, resize_columns=resize_columns)

        element_rows = []
        for idx, internal, name in gs.ELEMENT_DEFS:
            damage, remaining, maximum = enemy.element_damage(idx)
            damage_ratio = damage / maximum * 100 if maximum > 0 else 0.0
            remaining_ratio = remaining / maximum * 100 if maximum > 0 else 0.0
            element_rows.append((name, internal, damage, remaining, maximum,
                                 f'{damage_ratio:.4f}%', f'{remaining_ratio:.4f}%',
                                 '是' if maximum > 0 and remaining <= 0 else '否'))
        _fill_table(self.elements, element_rows, resize_columns=resize_columns)

        status_rows = []
        for idx, internal, name in gs.ABNORMAL_FLAG_DEFS:
            timer = enemy.status_timers.get(f'flag:{idx}') or {}
            remaining = ('无限' if timer.get('infinite') else
                         f"{timer['remaining']:.2f}s"
                         if isinstance(timer.get('remaining'), (int, float)) else '-')
            status_rows.append(('状态', name, internal, enemy.abnormal_flags[idx],
                                remaining, enemy.abnormal_immunes[idx],
                                enemy.abnormal_antis[idx]))
        for idx, internal, name in gs.ABNORMAL_COMBO_DEFS:
            timer = enemy.status_timers.get(f'combo:{idx}') or {}
            remaining = ('无限' if timer.get('infinite') else
                         f"{timer['remaining']:.2f}s"
                         if isinstance(timer.get('remaining'), (int, float)) else '-')
            status_rows.append(('组合状态', name, internal, enemy.abnormal_combos[idx],
                                remaining, enemy.abnormal_combo_immunes[idx], '-'))
        _fill_table(self.statuses, status_rows, resize_columns=resize_columns)

        buff_rows = []
        for buff in enemy.buffs:
            if buff['life_time'] < 0:
                time_text = f"无限；已存在 {_fmt(buff['existing_time'])}s"
            else:
                time_text = (f"剩余/总计 {_fmt(buff['remaining_time'])}/"
                             f"{_fmt(buff['life_time'])}s；已存在 {_fmt(buff['existing_time'])}s")
            mods = '; '.join(
                f"{m['name']}：基础加算={_fmt(m['addition'])}，倍率加算={_fmt(m['multiplier'])}，"
                f"最终加算={_fmt(m['final_addition'])}，最终倍率=×{_fmt(m['final_scaler'])}"
                for m in buff['attribute_modifiers']) or '-'
            statuses = []
            for label, key in (('状态', 'abnormal_flags'), ('免疫', 'abnormal_immunes'),
                               ('反制', 'abnormal_antis'), ('组合', 'abnormal_combos'),
                               ('组合免疫', 'abnormal_combo_immunes')):
                if buff[key]:
                    statuses.append(f"{label}:" + '、'.join(buff[key]))
            shield_types = [name for bit, name in gs.DAMAGE_TYPE_MASK_CN_NAMES.items()
                            if buff['shield_mask'] & bit]
            custom_value = buff.get('custom_shield_value', 0.0)
            custom_mask = buff.get('custom_shield_mask', 0)
            custom_types = [name for bit, name in gs.DAMAGE_TYPE_MASK_CN_NAMES.items()
                            if custom_mask & bit]
            if custom_value > 0:
                shield = (f"是 ({'/'.join(custom_types) or '特殊'}；"
                          f"当前分段剩余 {_fmt(custom_value)})")
            elif buff['has_shield']:
                shield = '是 (' + ('/'.join(shield_types)
                                   or f"mask={buff['shield_mask']}") + ')'
            else:
                shield = '-'
            runtime = (
                f"实例UID={buff['instance_uid']}；优先级={buff['priority']}；"
                f"触发次数={buff['trigger_count']}；已启用={'是' if buff['enabled'] else '否'}；"
                f"有效={'是' if buff['valid'] else '否'}；已结束={'是' if buff['finished'] else '否'}；"
                f"元素爆发Buff={'是' if buff['ep_break_buff'] else '否'}；来源技能地址="
                f"{hex(buff['ability_addr']) if buff['ability_addr'] else '-'}；"
                f"覆盖键={buff['override_key'] or '-'}；特效键={buff['effect_key'] or '-'}")
            buff_rows.append((
                buff_chinese_name(buff),
                buff['key'] + ('' if buff['enabled'] else ' [未启用]'),
                describe_active_buff(buff), buff['source'], runtime, time_text,
                f"{buff['stack_count']}/{buff['max_valid_stack_count']}", mods,
                '; '.join(statuses) or '-', shield, describe_blackboard(buff['blackboard']),
                _bb_text(buff['blackboard'])))
        _fill_table(self.buffs, buff_rows, resize_columns=resize_columns)

        global_rows = []
        for buff in enemy.global_buffs:
            defs = '；'.join(describe_buff_def(d) for d in buff['buff_defs']) or '-'
            applies = '是' if buff['applies_to_selected'] else '否'
            global_rows.append((
                global_buff_chinese_name(buff), buff['key'], describe_global_buff(buff, enemy),
                buff['source_name'], applies, buff['target_count'],
                f"实例UID={buff['instance_uid']}", defs,
                describe_blackboard(buff['blackboard']), _bb_text(buff['blackboard'])))
        _fill_table(self.globals, global_rows, resize_columns=resize_columns)

        detail_rows = getattr(enemy, 'skills_detail', None) or []
        if detail_rows:
            skill_rows = [
                (row.get('name', '?'), row.get('priority', '-'),
                 row.get('remaining'), row.get('period'),
                 '就绪' if (row.get('remaining') if isinstance(
                     row.get('remaining'), (int, float)) else 9) <= 0.05
                 else '冷却中')
                for row in detail_rows]
        else:
            skill_rows = [(key, '-', remain, period,
                           '就绪' if remain <= 0.05 else '冷却中')
                          for key, remain, period in enemy.skills]
        _fill_table(self.skills, skill_rows, resize_columns=resize_columns)
        if self._first_update:
            frame_rows = enemy_frame_rows(enemy.eid)
            if frame_rows:
                _fill_table(self.frames, frame_rows, resize_columns=True)
            else:
                _fill_table(self.frames, [('-', '未提取到该敌人的生效帧数据',
                                           '-', '-', '-', '-', '-')],
                            resize_columns=True)
        self._first_update = False
        self.live_status.setText(f'实时更新中 · 最近刷新 {time.strftime("%H:%M:%S")}')
        self.live_status.setStyleSheet('color:#58a66a;')
