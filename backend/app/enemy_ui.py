# -*- coding: utf-8 -*-
"""主程序敌人表格列定义、列选择器和详情窗口。"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractSpinBox, QCheckBox, QDialog, QDialogButtonBox, QGridLayout,
    QHBoxLayout, QLabel, QPushButton, QScrollArea, QSpinBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout, QWidget,
)

from tools.enemy_health import game_structs as gs

from .enemy_buff_descriptions import (
    buff_chinese_name, describe_active_buff, describe_blackboard, describe_buff_def,
    describe_global_buff, global_buff_chinese_name,
)


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
    _col('shield', '普通护盾', 90, False, True),
    _col('ep_sanity', '神经损伤', 125, False, True),
    _col('ep_water', '侵蚀损伤', 125, False, True),
    _col('ep_fire', '灼燃损伤', 125, False, True),
    _col('ep_dark', '凋亡损伤', 125, False, True),
    _col('ep_anger', '狂躁损伤', 125, False, True),
    _col('ep_break', '元素爆发恢复', 95, False),
    _col('skill', '技能 CD', 150, True, True),
    _col('life_status', '生存状态', 72, True),
    _col('detail', '详情', 64, True),
])

ENEMY_COLUMN_INDEX = {col['key']: idx for idx, col in enumerate(ENEMY_COLUMN_DEFS)}
DEFAULT_VISIBLE_COLUMNS = {col['key'] for col in ENEMY_COLUMN_DEFS if col['default']}


def precision_column_defs(visible=None):
    """返回精度设置项；传入 visible 时仅包含当前显示的数值列。"""
    chosen = None if visible is None else set(visible)
    return [
        (col['key'], col['label'])
        for col in ENEMY_COLUMN_DEFS
        if col['precision'] and (chosen is None or col['key'] in chosen)
    ]


def default_precision_values(value=4):
    values = {key: value for key, _label in precision_column_defs()}
    values['default'] = value
    return values


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
    return chosen or set(DEFAULT_VISIBLE_COLUMNS)


def save_visible_columns(settings, key, columns):
    ordered = [col['key'] for col in ENEMY_COLUMN_DEFS if col['key'] in columns]
    settings.setValue(key, ','.join(ordered))


class EnemyColumnDialog(QDialog):
    def __init__(self, parent, visible):
        super().__init__(parent)
        self.setWindowTitle('自定义敌人列表列')
        self.resize(620, 520)
        root = QVBoxLayout(self)
        root.addWidget(QLabel('勾选主表需要显示的字段；未勾选的数据仍会在“详情”中保留。'))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        grid = QGridLayout(body)
        self.checks = {}
        for idx, col in enumerate(ENEMY_COLUMN_DEFS):
            cb = QCheckBox(col['label'])
            cb.setChecked(col['key'] in visible)
            cb.setToolTip(col['key'])
            grid.addWidget(cb, idx // 3, idx % 3)
            self.checks[col['key']] = cb
        grid.setRowStretch((len(ENEMY_COLUMN_DEFS) + 2) // 3, 1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

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

    def _set_checked(self, selected):
        for key, cb in self.checks.items():
            cb.setChecked(key in selected)

    def values(self):
        return {key for key, cb in self.checks.items() if cb.isChecked()}


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
            control = _PrecisionSpin(decimals.get(key, decimals.get('default', 4)))
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
    precision = decimals.get(key, decimals.get('default', 4))
    if key == 'row':
        return str(row)
    if key == 'name':
        return enemy.name or enemy.eid or '?'
    if key == 'code':
        return enemy.code or '-'
    if key == 'eid':
        return enemy.eid
    if key == 'pos':
        p = decimals.get('pos', precision)
        return f'({enemy.pos_x:.{p}f}, {enemy.pos_y:.{p}f})'
    if key == 'action_state':
        return gs.ENEMY_STATE_NAMES.get(enemy.state_id, f'未知({enemy.state_id})')
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
        value = enemy.status_resistance if idx == gs.AttributeType.ONE_MINUS_STATUS_RESISTANCE \
            else enemy.attribute(idx)
        return f'{value:.{precision}f}'
    if key == 'es':
        return f'{enemy.es:.{precision}f}'
    if key == 'shield':
        return f'{enemy.shield:.{precision}f}'
    ep_types = {
        'ep_sanity': gs.ElementType.SANITY,
        'ep_water': gs.ElementType.WATER,
        'ep_fire': gs.ElementType.FIRE,
        'ep_dark': gs.ElementType.DARK,
        'ep_anger': gs.ElementType.ANGER,
    }
    if key in ep_types:
        damage, _, maximum = enemy.element_damage(ep_types[key])
        percent = damage / maximum * 100 if maximum > 0 else 0.0
        return f'{damage:.{precision}f}/{maximum:.{precision}f} ({percent:.{precision}f}%)'
    if key == 'ep_break':
        return '恢复中' if enemy.ep_break_recovery else '-'
    if key == 'skill':
        return format_skill_cd(enemy.skills, sep='\n', prec=decimals.get('skill', precision))
    if key == 'life_status':
        return '存活' if enemy.alive else ('退场' if enemy.finish else '阵亡')
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


def _fill_table(table, rows, max_column_width=420):
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            text = _fmt(value)
            item = QTableWidgetItem(text)
            item.setToolTip(text)
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            table.setItem(r, c, item)
    table.resizeColumnsToContents()
    for column in range(table.columnCount()):
        if table.columnWidth(column) > max_column_width:
            table.setColumnWidth(column, max_column_width)


class EnemyDetailDialog(QDialog):
    """敌人完整详情：属性、五类损伤、状态/免疫、Buff、关卡 Buff 和技能。"""

    def __init__(self, parent, enemy, refresh_callback=None):
        super().__init__(parent)
        self.enemy = enemy
        self.refresh_callback = refresh_callback
        self.setWindowTitle('敌人详情')
        self.resize(1080, 760)
        root = QVBoxLayout(self)
        self.title = QLabel()
        self.title.setStyleSheet('font-size:16px;font-weight:600;')
        root.addWidget(self.title)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        self.overview = _make_table(['项目', '数值'])
        self.attrs = _make_table(['属性', '内部名', '原始值', '最终值', '变化'])
        self.elements = _make_table(['损伤类型', '内部名', '已累积', '剩余', '上限', '比例', '爆发'])
        self.statuses = _make_table(['类别', '状态', '内部名', '生效计数', '免疫计数', '反制计数'])
        self.buffs = _make_table([
            '中文名称', '内部键', '效果说明', '来源', '运行信息', '时间', '层数',
            '属性公式', '状态/免疫', '护盾', '参数说明', '原始 Blackboard'])
        self.globals = _make_table([
            '中文名称', '内部键', '效果说明', '来源阵营', '作用当前敌人', '目标数',
            '实例信息', '生成 Buff', '参数说明', '原始 Blackboard'])
        self.skills = _make_table(['技能', '剩余CD', '总CD', '状态'])
        for label, table in (
                ('概览', self.overview), ('属性', self.attrs), ('损伤条', self.elements),
                ('状态与免疫', self.statuses), ('当前 Buff', self.buffs),
                ('关卡效果', self.globals), ('技能', self.skills)):
            self.tabs.addTab(table, label)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        if refresh_callback is not None:
            refresh = QPushButton('重新读取详情')
            refresh.clicked.connect(self._refresh)
            buttons.addButton(refresh, QDialogButtonBox.ActionRole)
        root.addWidget(buttons)
        self.update_enemy(enemy)

    def _refresh(self):
        if self.refresh_callback is None:
            return
        enemy = self.refresh_callback(self.enemy.addr)
        if enemy is not None:
            self.update_enemy(enemy)

    def update_enemy(self, enemy):
        self.enemy = enemy
        self.title.setText(
            f'{enemy.name or enemy.eid or "?"}  ·  {enemy.code or "-"}  ·  {enemy.eid}')
        state = gs.ENEMY_STATE_NAMES.get(enemy.state_id, f'未知({enemy.state_id})')
        overview = [
            ('实例地址', hex(enemy.addr)), ('实例ID', enemy.eid), ('敌人编号', enemy.code or '-'),
            ('生存状态', '存活' if enemy.alive else ('退场' if enemy.finish else '阵亡')),
            ('行为状态', state), ('异常状态', enemy.status_text()),
            ('当前生命', enemy.hp), ('最大生命', enemy.max_hp),
            ('元素护盾', enemy.es), ('普通护盾汇总', enemy.shield),
            ('位置', f'({enemy.pos_x}, {enemy.pos_y})'),
            ('阻挡位置', f'({enemy.blk_x}, {enemy.blk_y})'),
            ('出生格', f'({enemy.spawn_row}, {enemy.spawn_col})'),
            ('方向枚举', enemy.direction),
            ('元素爆发恢复', '是' if enemy.ep_break_recovery else '否'),
            ('状态抗性', enemy.status_resistance),
            ('元素损伤减免', enemy.attribute(gs.AttributeType.EP_DAMAGE_RESISTANCE)),
            ('元素抗性', enemy.attribute(gs.AttributeType.EP_RESISTANCE)),
        ]
        _fill_table(self.overview, overview)

        attr_rows = []
        for idx, internal, name in gs.ATTRIBUTE_DEFS:
            raw = enemy.raw_attributes.get(idx)
            final = enemy.attributes.get(idx)
            delta = final - raw if raw is not None and final is not None else None
            if idx == gs.AttributeType.ONE_MINUS_STATUS_RESISTANCE:
                name += '（实际状态抗性=' + _fmt(enemy.status_resistance) + '）'
            attr_rows.append((name, internal, '-' if raw is None else raw,
                              '-' if final is None else final,
                              '-' if delta is None else delta))
        _fill_table(self.attrs, attr_rows)

        element_rows = []
        for idx, internal, name in gs.ELEMENT_DEFS:
            damage, remaining, maximum = enemy.element_damage(idx)
            ratio = damage / maximum * 100 if maximum > 0 else 0.0
            element_rows.append((name, internal, damage, remaining, maximum,
                                 f'{ratio:.4f}%', '是' if maximum > 0 and remaining <= 0 else '否'))
        _fill_table(self.elements, element_rows)

        status_rows = []
        for idx, internal, name in gs.ABNORMAL_FLAG_DEFS:
            status_rows.append(('状态', name, internal, enemy.abnormal_flags[idx],
                                enemy.abnormal_immunes[idx], enemy.abnormal_antis[idx]))
        for idx, internal, name in gs.ABNORMAL_COMBO_DEFS:
            status_rows.append(('组合状态', name, internal, enemy.abnormal_combos[idx],
                                enemy.abnormal_combo_immunes[idx], '-'))
        _fill_table(self.statuses, status_rows)

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
            shield = ('是 (' + ('/'.join(shield_types) or f"mask={buff['shield_mask']}") + ')') \
                if buff['has_shield'] else '-'
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
        _fill_table(self.buffs, buff_rows)

        global_rows = []
        for buff in enemy.global_buffs:
            defs = '；'.join(describe_buff_def(d) for d in buff['buff_defs']) or '-'
            applies = '是' if buff['applies_to_selected'] else '否'
            global_rows.append((
                global_buff_chinese_name(buff), buff['key'], describe_global_buff(buff, enemy),
                buff['source_name'], applies, buff['target_count'],
                f"实例UID={buff['instance_uid']}", defs,
                describe_blackboard(buff['blackboard']), _bb_text(buff['blackboard'])))
        _fill_table(self.globals, global_rows)

        skill_rows = [(key, remain, period, '就绪' if remain <= 0.05 else '冷却中')
                      for key, remain, period in enemy.skills]
        _fill_table(self.skills, skill_rows)
