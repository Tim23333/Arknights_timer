# -*- coding: utf-8 -*-
"""场上干员/召唤物表格定义与实时详情窗口。"""

import math
import time

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QTabWidget, QTableWidget, QVBoxLayout, QWidget,
)

from tools.enemy_health import game_structs as gs
from tools.enemy_health.enemy_reader import countdown_text

from .enemy_buff_descriptions import (
    buff_chinese_name, describe_active_buff, describe_blackboard,
    describe_global_buff, global_buff_chinese_name,
)
from .enemy_ui import (
    _ColumnOrderList, _PrecisionSpin, _bb_text, _fill_table, _fmt, _make_table,
)


OVERVIEW_COLORS = [
    '#4f8cff', '#55c271', '#ffad42', '#ed5f5f', '#9b72e8', '#35b7bd',
    '#e979b7', '#8caa3f', '#d17a45', '#6e8fd5', '#48a07a', '#b574d1',
    '#d3a52f', '#5ba3c9', '#c26d70', '#7f95a8',
]


def build_character_overview(characters):
    """按 charId 合并干员累计值；同一统计被多个实例引用时不重复相加。"""
    merged = {}
    for character in characters or ():
        if (getattr(character, 'is_global_damage_summary', False)
                or getattr(character, 'is_token', False)):
            continue
        cid = getattr(character, 'cid', '') or ''
        name = getattr(character, 'name', '') or cid or '未知干员'
        key = cid or name
        entry = merged.setdefault(key, {
            'cid': cid, 'name': name, 'damage': 0.0, 'healing': 0.0,
        })
        entry['damage'] = max(
            entry['damage'], max(0.0, float(
                getattr(character, 'damage_total', 0.0) or 0.0)))
        entry['healing'] = max(
            entry['healing'], max(0.0, float(
                getattr(character, 'healing_total', 0.0) or 0.0)))
    return sorted(merged.values(), key=lambda row: (
        -(row['damage'] + row['healing']), row['name'], row['cid']))


class CharacterPieChart(QWidget):
    """不依赖 QtCharts 的轻量饼图，避免增加打包组件。"""

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title = title
        self._data = []
        self.setMinimumSize(430, 420)

    def set_data(self, rows):
        data = []
        for label, value in rows:
            value = float(value or 0.0)
            if not math.isfinite(value):
                value = 0.0
            data.append((str(label), max(0.0, value)))
        data.sort(key=lambda row: (-row[1], row[0]))
        if data != self._data:
            self._data = data
            self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        text_color = self.palette().text().color()
        muted = QColor(text_color)
        muted.setAlpha(170)
        painter.setPen(QPen(text_color))

        title_font = painter.font()
        title_font.setPointSizeF(title_font.pointSizeF() + 2)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(QRectF(12, 8, self.width() - 24, 34),
                         Qt.AlignCenter, self.title)

        total = sum(value for _label, value in self._data)
        diameter = max(150.0, min(self.height() - 85.0, self.width() * 0.47))
        pie = QRectF(18.0, 55.0, diameter, diameter)
        if total > 0:
            start = 90 * 16
            for idx, (_label, value) in enumerate(self._data):
                if value <= 0:
                    continue
                span = -round(value / total * 360 * 16)
                painter.setBrush(QColor(OVERVIEW_COLORS[idx % len(OVERVIEW_COLORS)]))
                painter.setPen(QPen(self.palette().window().color(), 1.0))
                painter.drawPie(pie, start, span)
                start += span
            inner = pie.adjusted(
                diameter * 0.27, diameter * 0.27,
                -diameter * 0.27, -diameter * 0.27)
            painter.setPen(Qt.NoPen)
            painter.setBrush(self.palette().window())
            painter.drawEllipse(inner)
            painter.setPen(text_color)
            total_font = painter.font()
            total_font.setBold(True)
            painter.setFont(total_font)
            painter.drawText(inner, Qt.AlignCenter,
                             f'合计\n{total:,.2f}')
        else:
            painter.setPen(QPen(muted, 2.0))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(pie)
            painter.drawText(pie, Qt.AlignCenter, '暂无数据')

        legend_x = pie.right() + 22.0
        legend_y = 56.0
        legend_width = max(80.0, self.width() - legend_x - 12.0)
        painter.setFont(self.font())
        metrics = painter.fontMetrics()
        for idx, (label, value) in enumerate(self._data):
            y = legend_y + idx * 25.0
            if y + 22 > self.height():
                break
            color = QColor(OVERVIEW_COLORS[idx % len(OVERVIEW_COLORS)])
            if value <= 0:
                color.setAlpha(80)
            painter.fillRect(QRectF(legend_x, y + 4, 12, 12), color)
            ratio = value / total * 100 if total > 0 else 0.0
            value_text = f'{value:,.2f}  {ratio:.1f}%'
            value_width = metrics.horizontalAdvance(value_text) + 8
            label_width = max(30, int(legend_width - value_width - 20))
            short_label = metrics.elidedText(label, Qt.ElideRight, label_width)
            painter.setPen(text_color if value > 0 else muted)
            painter.drawText(QRectF(legend_x + 18, y, label_width, 22),
                             Qt.AlignLeft | Qt.AlignVCenter, short_label)
            painter.drawText(QRectF(
                legend_x + 18 + label_width, y, value_width, 22),
                Qt.AlignRight | Qt.AlignVCenter, value_text)


class CharacterOverviewDialog(QDialog):
    def __init__(self, parent, characters=()):
        super().__init__(parent)
        self._last_update = 0.0
        self.setWindowTitle('干员数据总览')
        self.resize(1120, 620)
        root = QVBoxLayout(self)
        self.status = QLabel(
            '随干员数据实时更新，已撤退干员保留本局累计；召唤物/装置不单独计入。')
        self.status.setProperty('role', 'muted')
        root.addWidget(self.status)
        charts = QHBoxLayout()
        self.damage_chart = CharacterPieChart('干员总输出占比')
        self.healing_chart = CharacterPieChart('干员治疗量占比')
        charts.addWidget(self.damage_chart, 1)
        charts.addWidget(self.healing_chart, 1)
        root.addLayout(charts, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.update_characters(characters, force=True)

    def update_characters(self, characters, force=False):
        now = time.monotonic()
        if not force and now - self._last_update < 0.2:
            return
        self._last_update = now
        rows = build_character_overview(characters)
        self.damage_chart.set_data(
            [(row['name'], row['damage']) for row in rows])
        self.healing_chart.set_data(
            [(row['name'], row['healing']) for row in rows])
        self.status.setText(
            f'实时更新中 · 干员 {len(rows)} · '
            f'总输出 {sum(row["damage"] for row in rows):,.2f} · '
            f'总治疗 {sum(row["healing"] for row in rows):,.2f}')


def _col(key, label, width=80, default=False, precision=False):
    return {
        'key': key, 'label': label, 'width': width,
        'default': default, 'precision': precision,
    }


CHARACTER_COLUMN_DEFS = [
    _col('row', '#', 38, True),
    _col('name', '名称', 130, True),
    _col('kind', '类别', 84, True),
    _col('cid', '干员 ID', 145, False),
    _col('profession', '职业', 74, True),
    _col('level', '等级', 62, True),
    _col('hp', '生命', 185, True, True),
    _col('sp', '技力', 125, True, True),
    _col('pos', '位置', 86, True),
    _col('action_state', '行为状态', 84, True),
    _col('action_phase', '动作阶段', 190, True),
    _col('remaining_time', '剩余帧/时间', 170, True),
    _col('next_action', '下一动作', 190, True),
    _col('abnormal_status', '异常状态', 150, True),
]

_DEFAULT_ATTRS = {
    gs.AttributeType.ATK, gs.AttributeType.DEF,
    gs.AttributeType.MAGIC_RESISTANCE, gs.AttributeType.ATTACK_SPEED,
    gs.AttributeType.BLOCK_CNT,
}
for _idx, _internal, _name in gs.ATTRIBUTE_DEFS:
    _label = '状态抗性' if _idx == gs.AttributeType.ONE_MINUS_STATUS_RESISTANCE else _name
    CHARACTER_COLUMN_DEFS.append(
        _col(f'attr_{_idx}', _label, max(68, min(140, len(_label) * 15)),
             _idx in _DEFAULT_ATTRS, True))

CHARACTER_COLUMN_DEFS.extend([
    _col('shield', '伤害护盾', 96, False, True),
    _col('es', '元素护盾', 96, False, True),
    _col('blocked', '阻挡敌人', 86, True),
    _col('buff_count', 'Buff 数', 72, True),
    _col('damage_total', '累计伤害', 110, True, True),
    _col('global_total_damage', '全局总伤', 110, True, True),
    _col('damage_physical', '物理伤害', 105, False, True),
    _col('damage_magical', '法术伤害', 105, False, True),
    _col('damage_pure', '真实伤害', 105, False, True),
    _col('damage_element', '元素伤害', 105, False, True),
    _col('element_output_total', '元素损伤累计', 125, False, True),
    _col('healing_total', '累计治疗', 105, False, True),
    _col('skill', '主技能', 205, True, True),
    _col('detail', '详情', 64, True),
])

CHARACTER_COLUMN_INDEX = {
    col['key']: idx for idx, col in enumerate(CHARACTER_COLUMN_DEFS)}
CHARACTER_COLS = [col['label'] for col in CHARACTER_COLUMN_DEFS]
CHARACTER_COL_WIDTHS = [col['width'] for col in CHARACTER_COLUMN_DEFS]
DEFAULT_VISIBLE_COLUMNS = {
    col['key'] for col in CHARACTER_COLUMN_DEFS if col['default']}


def precision_column_defs(visible=None):
    selected = None if visible is None else set(visible)
    return [(col['key'], col['label']) for col in CHARACTER_COLUMN_DEFS
            if col['precision'] and (selected is None or col['key'] in selected)]


def default_character_precision(value=2):
    result = {key: value for key, _label in precision_column_defs()}
    result['default'] = value
    return result


def load_character_columns(settings, key):
    value = settings.value(key, '')
    if isinstance(value, str):
        selected = {part for part in value.split(',') if part}
    elif isinstance(value, (list, tuple)):
        selected = set(value)
    else:
        selected = set()
    selected &= set(CHARACTER_COLUMN_INDEX)
    if not selected:
        selected = set(DEFAULT_VISIBLE_COLUMNS)
    migration_key = key + '/damage_stats_v1'
    marker = settings.value(migration_key, False)
    migrated = marker is True or str(marker).lower() in ('1', 'true', 'yes')
    if not migrated:
        selected.add('damage_total')
        settings.setValue(migration_key, True)
    migration_key = key + '/damage_stats_v2'
    marker = settings.value(migration_key, False)
    migrated = marker is True or str(marker).lower() in ('1', 'true', 'yes')
    if not migrated:
        selected.add('global_total_damage')
        settings.setValue(migration_key, True)
    migration_key = key + '/action_phase_v1'
    marker = settings.value(migration_key, False)
    migrated = marker is True or str(marker).lower() in ('1', 'true', 'yes')
    if not migrated:
        selected.update(('action_phase', 'remaining_time'))
        settings.setValue(migration_key, True)
    migration_key = key + '/next_action_v1'
    marker = settings.value(migration_key, False)
    migrated = marker is True or str(marker).lower() in ('1', 'true', 'yes')
    if not migrated:
        selected.add('next_action')
        settings.setValue(migration_key, True)
    return selected


def save_character_columns(settings, key, selected):
    ordered = [col['key'] for col in CHARACTER_COLUMN_DEFS
               if col['key'] in selected]
    settings.setValue(key, ','.join(ordered))


def _skill_text(character, precision=2):
    skill = character.skill or {}
    if not skill:
        return '-'
    name = skill.get('name') or skill.get('skill_id') or '未命名技能'
    runtime = skill.get('runtime') or {}
    if runtime.get('wait_for_end') or runtime.get('casting'):
        return f'{name}\n生效中  SP {character.sp:.{precision}f}/{character.max_sp}'
    remain = runtime.get('cooldown_remaining')
    period = runtime.get('cooldown_period')
    # 持续/无限技能的 Timer 会使用约 180000 秒哨兵值，不显示成巨型 CD。
    if remain is not None and period is not None and 0 <= period < 3600:
        return (f'{name}\nCD {remain:.{precision}f}/{period:.{precision}f}s  '
                f'SP {character.sp:.{precision}f}/{character.max_sp}')
    return f'{name}\nSP {character.sp:.{precision}f}/{character.max_sp}'


def format_character_column(key, character, decimals, row=0):
    precision = decimals.get(key, decimals.get('default', 2))
    if getattr(character, 'is_global_damage_summary', False):
        if key == 'row':
            return str(row + 1)
        if key == 'name':
            return character.name
        if key == 'kind':
            return character.unit_kind
        if key == 'damage_total':
            return f'{character.unattributed_damage_total:.{precision}f}'
        if key == 'global_total_damage':
            return f'{character.global_total_damage:.{precision}f}'
        if key in ('damage_physical', 'damage_magical', 'damage_pure',
                   'damage_element', 'element_output_total'):
            return '未分类'
        return '-'
    if key == 'row':
        return str(row + 1)
    if key == 'name':
        return character.name or character.cid or '?'
    if key == 'kind':
        return character.unit_kind
    if key == 'cid':
        return character.cid or '-'
    if key == 'profession':
        return character.profession_name
    if key == 'level':
        phase = f'E{character.evolve_phase}' if character.evolve_phase else 'E0'
        return f'{phase} Lv.{character.level}'
    if key == 'pos':
        return character.position_text
    if key == 'action_state':
        return character.state_name
    if key == 'action_phase':
        return character.action_text
    if key == 'remaining_time':
        return countdown_text(getattr(character, 'action', {}))
    if key == 'next_action':
        action = getattr(character, 'action', {}) or {}
        value = action.get('next_action') or '-'
        prefix = {
            'confirmed': '[确定] ', 'unselected': '[未预选] ',
        }.get(action.get('next_action_confidence'), '')
        return prefix + value if value != '-' else value
    if key == 'abnormal_status':
        return character.status_text()
    if key.startswith('attr_'):
        idx = int(key[5:])
        value = (character.status_resistance
                 if idx == gs.AttributeType.ONE_MINUS_STATUS_RESISTANCE
                 else character.attribute(idx))
        return f'{value:.{precision}f}'
    if key == 'shield':
        return f'{character.shield:.{precision}f}'
    if key == 'es':
        return f'{character.es:.{precision}f}'
    if key == 'blocked':
        return f'{character.blocked_count}（体积 {character.blocked_total_volume}）'
    if key == 'buff_count':
        return str(character.buff_count)
    damage_keys = {
        'damage_physical': gs.DamageType.PHYSICAL,
        'damage_magical': gs.DamageType.MAGICAL,
        'damage_pure': gs.DamageType.PURE,
        'damage_element': gs.DamageType.ELEMENT,
    }
    if key == 'damage_total':
        return f'{character.damage_total:.{precision}f}'
    if key == 'global_total_damage':
        if not character.unattributed_tracking_enabled:
            return '未启用'
        return f'{character.global_total_damage:.{precision}f}'
    if key in damage_keys:
        return f'{character.damage_by_type.get(damage_keys[key], 0.0):.{precision}f}'
    if key == 'element_output_total':
        return f'{sum(character.output_element_damage.values()):.{precision}f}'
    if key == 'healing_total':
        return f'{character.healing_total:.{precision}f}'
    if key == 'skill':
        return _skill_text(character, decimals.get('skill', precision))
    return ''


class CharacterColumnDialog(QDialog):
    def __init__(self, parent, visible, order=None):
        super().__init__(parent)
        self.setWindowTitle('自定义干员列表列')
        self.resize(900, 520)
        root = QVBoxLayout(self)
        root.addWidget(QLabel(
            '左侧勾选需要显示的字段（完整数据始终保留在“详情”中）；'
            '右侧为当前显示顺序，拖动条目即可调整，新勾选的列排在末尾。'))
        body_row = QHBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        grid = QGridLayout(body)
        self.checks = {}
        for idx, col in enumerate(CHARACTER_COLUMN_DEFS):
            cb = QCheckBox(col['label'])
            cb.setChecked(col['key'] in visible)
            cb.setToolTip(col['key'])
            cb.toggled.connect(
                lambda checked, key=col['key']: self._on_toggled(key, checked))
            grid.addWidget(cb, idx // 3, idx % 3)
            self.checks[col['key']] = cb
        scroll.setWidget(body)
        body_row.addWidget(scroll, 1)

        order_host = QWidget()
        order_box = QVBoxLayout(order_host)
        order_box.setContentsMargins(0, 0, 0, 0)
        order_box.addWidget(QLabel('显示顺序（拖动调整）:'))
        labels = {col['key']: col['label'] for col in CHARACTER_COLUMN_DEFS}
        self.order_list = _ColumnOrderList(labels)
        order_box.addWidget(self.order_list, 1)
        order_host.setFixedWidth(220)
        body_row.addWidget(order_host)
        root.addLayout(body_row, 1)

        # 初始列表 = 存档顺序中当前可见的列；存档未覆盖的可见列补到末尾
        full_order = (list(order) if order
                      else [col['key'] for col in CHARACTER_COLUMN_DEFS])
        for key in full_order:
            if key in visible:
                self.order_list.append_key(key)
        for col in CHARACTER_COLUMN_DEFS:
            if col['key'] in visible:
                self.order_list.append_key(col['key'])

        presets = QHBoxLayout()
        for label, values in (
                ('恢复默认', DEFAULT_VISIBLE_COLUMNS),
                ('全部显示', set(self.checks)), ('全部隐藏', set())):
            button = QPushButton(label)
            button.clicked.connect(
                lambda _checked=False, values=set(values): self._set(values))
            presets.addWidget(button)
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

    def _set(self, values):
        for key, checkbox in self.checks.items():
            checkbox.setChecked(key in values)
        # 勾选信号同步会让状态未变的列保留原位；预设统一重置为定义顺序
        self.order_list.clear()
        for col in CHARACTER_COLUMN_DEFS:
            if col['key'] in values:
                self.order_list.append_key(col['key'])

    def values(self):
        return {key for key, checkbox in self.checks.items() if checkbox.isChecked()}

    def ordered_keys(self):
        return self.order_list.keys()


class CharacterPrecisionDialog(QDialog):
    def __init__(self, parent, decimals, visible=None):
        super().__init__(parent)
        self.setWindowTitle('干员表小数位设置')
        self.resize(620, 460)
        root = QVBoxLayout(self)
        root.addWidget(QLabel('只列出当前显示的数值列（0-6 位）。'))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        grid = QGridLayout(body)
        self.controls = {}
        columns = precision_column_defs(visible)
        for idx, (key, label) in enumerate(columns):
            row, base = idx // 2, (idx % 2) * 2
            grid.addWidget(QLabel(label + '：'), row, base)
            control = _PrecisionSpin(decimals.get(key, decimals.get('default', 2)))
            grid.addWidget(control, row, base + 1)
            self.controls[key] = control
        scroll.setWidget(body)
        root.addWidget(scroll, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def values(self):
        return {key: control.value() for key, control in self.controls.items()}


class GlobalDamageDetailDialog(QDialog):
    """BattleStats 全局总伤与无法归属到 charId 的伤害差值。"""

    def __init__(self, parent, summary):
        super().__init__(parent)
        self.summary = summary
        self._first_update = True
        self.setWindowTitle('无来源&全局伤害统计')
        self.resize(820, 430)
        root = QVBoxLayout(self)
        self.title = QLabel('无来源&全局伤害统计')
        self.title.setStyleSheet('font-size:16px;font-weight:600;')
        root.addWidget(self.title)
        self.live_status = QLabel('随干员数据实时更新')
        self.live_status.setStyleSheet('color:#888888;')
        root.addWidget(self.live_status)
        self.table = _make_table(['类别', '项目', '数值/说明'])
        root.addWidget(self.table, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.update_summary(summary)

    def update_summary(self, summary):
        self.summary = summary
        global_total = max(0.0, summary.global_total_damage)
        unattributed = max(0.0, summary.unattributed_damage_total)
        ratio = unattributed / global_total * 100 if global_total > 0 else 0.0
        rows = [
            ('全局', '全局总伤', global_total),
            ('观测', '敌人生命下降累计',
             summary.observed_enemy_damage_total),
            ('有来源', 'BattleStats 有来源伤害',
             summary.attributed_damage_total),
            ('归属统计', '按干员/召唤物归属伤害合计',
             summary.character_attributed_damage_total),
            ('无来源', '无来源&未归属伤害合计（全部）', unattributed),
            ('无来源', '占全局总伤比例', f'{ratio:.4f}%'),
            ('统计口径', '计算方式',
             '敌人生命下降累计 - BattleStats 有来源伤害；两者取值不足时以较大可靠累计兜底'),
            ('统计口径', '提交延迟',
             '等待约 0.8 秒让有来源统计追平，再提交无来源累计，避免数值反复增减'),
            ('统计口径', '类型拆分',
             '游戏累计结构未提供无来源伤害的逐类型/逐触发者明细，因此不伪造分类'),
            ('统计口径', '包含范围',
             '包含神经损伤爆发及其他没有有效 source 的实际生命伤害'),
        ]
        _fill_table(self.table, rows, resize_columns=self._first_update)
        self._first_update = False


class CharacterDetailDialog(QDialog):
    """随主表刷新动态数据，重型 Buff/天赋数据由独立通道约 20Hz 补全。"""

    def __init__(self, parent, character):
        super().__init__(parent)
        self.character = character
        self._first_update = True
        self.setWindowTitle('干员详情')
        self.resize(1120, 780)
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
        self.skill = _make_table(['类别', '项目', '值'])
        self.damage = _make_table(['类别', '项目', '数值'])
        self.statuses = _make_table(
            ['类别', '状态', '内部名', '生效计数', '免疫计数', '反制计数'])
        self.buffs = _make_table([
            '中文名称', '内部键', '效果说明', '来源分类', '来源', '时间', '层数',
            '属性修改', '状态/免疫', '护盾', '运行类', '静态定义', '参数'])
        self.talents = _make_table([
            '名称', '描述', '预制键', '能力类', '需求潜能', '模式数', '模式', '参数'])
        self.elements = _make_table([
            '损伤类型', '已累积', '剩余', '上限', '爆发', '恢复中'])
        self.effects = _make_table(['类别', '名称/类', '地址', '参数/说明'])
        for label, table in (
                ('概览', self.overview), ('属性', self.attrs), ('伤害统计', self.damage),
                ('主技能', self.skill),
                ('状态与免疫', self.statuses), ('当前 Buff', self.buffs),
                ('天赋', self.talents), ('元素损伤', self.elements),
                ('其他效果', self.effects)):
            self.tabs.addTab(table, label)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.update_character(character)
        self.live_status.setText('正在获取完整详情 ...')

    def set_live_error(self, message):
        self.live_status.setText(message)
        self.live_status.setStyleSheet('color:#d99034;')

    def update_character(self, character):
        self.character = character
        resize = self._first_update
        self.title.setText(
            f'{character.name or character.cid or "?"}  ·  {character.unit_kind}  ·  '
            f'{character.profession_name}  ·  {character.cid or "-"}')
        action = getattr(character, 'action', {}) or {}
        overview = [
            ('实例地址', hex(character.addr)), ('实例 UID', character.unique_id),
            ('模板 ID', character.tmpl_id or '-'), ('别名', character.alias or '-'),
            ('英文名', character.name_en or '-'), ('类别', character.unit_kind),
            ('等级', f'E{character.evolve_phase} Lv.{character.level}'),
            ('稀有度枚举', character.rarity), ('潜能等级', character.potential_rank),
            ('信赖阶段', character.favor_phase), ('助战', '是' if character.is_assist else '否'),
            ('预定义单位', '是' if character.is_predefined else '否'),
            ('隐藏单位', '是' if character.is_hidden else '否'),
            ('队伍键', character.team_key or '-'), ('国家', character.nation_id or '-'),
            ('阵营', character.group_id or '-'), ('小队', character.team_id or '-'),
            ('当前生命', character.hp), ('最大生命', character.max_hp),
            ('当前技力', character.sp), ('最大技力', character.max_sp),
            ('元素护盾', character.es), ('伤害护盾', character.shield),
            ('位置', character.position_text), ('朝向枚举', character.direction),
            ('行为状态', character.state_name), ('动作阶段', character.action_text),
            ('动作说明', action.get('detail') or '-'),
            ('剩余帧/时间', countdown_text(action)),
            ('倒计时含义', action.get('remaining_kind') or '-'),
            ('倒计时来源', action.get('clock_source') or '-'),
            ('精确动画计时', '是（当前速度且未被中断）'
             if action.get('animation_exact') else '否/不适用'),
            ('下一动作', action.get('next_action') or '-'),
            ('下一动作可信度', {
                'confirmed': '游戏已写入', 'unselected': '游戏尚未预选',
            }.get(action.get('next_action_confidence'), '-')),
            ('下一动作依据', action.get('next_action_detail') or '-'),
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
            ('异常状态', character.status_text()),
            ('存活', '是' if character.alive else '否'), ('离场原因枚举', character.finish_reason),
            ('阻挡敌人数', character.blocked_count),
            ('阻挡敌人体积', character.blocked_total_volume),
            ('本次部署费用', character.deploy_cost_this_time),
            ('卡片 UID', character.card_uid), ('Buff 数量', character.buff_count),
            ('召唤/宿主键', character.token_or_host_key or '-'),
            ('召唤/宿主 UID', character.token_or_host_uid),
        ]
        _fill_table(self.overview, overview, resize_columns=resize)

        attr_rows = []
        for idx, internal, name in gs.ATTRIBUTE_DEFS:
            raw = character.raw_attributes.get(idx)
            final = character.attributes.get(idx)
            delta = final - raw if raw is not None and final is not None else None
            if idx == gs.AttributeType.ONE_MINUS_STATUS_RESISTANCE:
                name += f'（实际抗性 {_fmt(character.status_resistance)}）'
            attr_rows.append((name, internal, '-' if raw is None else raw,
                              '-' if final is None else final,
                              '-' if delta is None else delta))
        _fill_table(self.attrs, attr_rows, resize_columns=resize)

        damage_rows = [
            ('汇总', '累计伤害', character.damage_total),
            ('伤害类型', '物理伤害', character.damage_by_type.get(
                gs.DamageType.PHYSICAL, 0.0)),
            ('伤害类型', '法术伤害', character.damage_by_type.get(
                gs.DamageType.MAGICAL, 0.0)),
            ('伤害类型', '真实伤害', character.damage_by_type.get(
                gs.DamageType.PURE, 0.0)),
            ('伤害类型', '元素类型直接伤害', character.damage_by_type.get(
                gs.DamageType.ELEMENT, 0.0)),
            ('治疗', '累计治疗量', character.healing_total),
            ('单次输出', '绝对值范围',
             f'{character.damage_range_min} ~ {character.damage_range_max}'),
        ]
        for idx, internal, name in gs.ELEMENT_DEFS:
            damage_rows.append((
                '元素损伤', name + '累计',
                character.output_element_damage.get(idx, 0.0)))
            damage_rows.append((
                '元素爆发', name + '触发次数',
                character.output_ep_break_count.get(idx, 0)))
        _fill_table(self.damage, damage_rows, resize_columns=resize)

        skill = character.skill or {}
        runtime = skill.get('runtime') or {}
        sp_data = skill.get('sp') or {}
        skill_rows = [
            ('基础', '名称', skill.get('name') or '-'),
            ('基础', '技能 ID', skill.get('skill_id') or '-'),
            ('基础', '描述', skill.get('description') or '-'),
            ('基础', '等级', skill.get('level', '-')),
            ('基础', '技能类型', gs.SKILL_TYPE_NAMES.get(skill.get('type'), skill.get('type', '-'))),
            ('基础', '持续类型', gs.SKILL_DURATION_TYPE_NAMES.get(
                skill.get('duration_type'), skill.get('duration_type', '-'))),
            ('基础', '标称持续时间', skill.get('duration', '-')),
            ('技力', '回复类型', gs.SP_TYPE_NAMES.get(sp_data.get('type'), sp_data.get('type', '-'))),
            ('技力', '初始/消耗/最大充能',
             f"{sp_data.get('init_sp', '-')} / {sp_data.get('cost', '-')} / {sp_data.get('max_charge', '-')}") ,
            ('运行时', '当前/最大技力', f'{character.sp} / {character.max_sp}'),
            ('运行时', '就绪', '是' if skill.get('ready') else '否'),
            ('运行时', '技能中', '是' if runtime.get('wait_for_end') or runtime.get('casting') else '否'),
            ('运行时', '冷却剩余/总计',
             ('持续/无限' if float(runtime.get('cooldown_period', 0) or 0) >= 3600
              else f"{runtime.get('cooldown_remaining', '-')} / {runtime.get('cooldown_period', '-')}s")),
            ('运行时', '技能类', runtime.get('class') or '-'),
            ('运行时', '能力类', runtime.get('ability_class') or '-'),
            ('运行时', '触发次数', runtime.get('trigger_count', '-')),
            ('参数', '静态 Blackboard', _bb_text(skill.get('blackboard', []))),
            ('参数', '运行时 Blackboard', _bb_text(runtime.get('blackboard', []))),
            ('参数', '能力 Blackboard', _bb_text(runtime.get('ability_blackboard', []))),
        ]
        _fill_table(self.skill, skill_rows, resize_columns=resize)

        status_rows = []
        for idx, internal, name in gs.ABNORMAL_FLAG_DEFS:
            status_rows.append(('状态', name, internal, character.abnormal_flags[idx],
                                character.abnormal_immunes[idx], character.abnormal_antis[idx]))
        for idx, internal, name in gs.ABNORMAL_COMBO_DEFS:
            status_rows.append(('组合状态', name, internal, character.abnormal_combos[idx],
                                character.abnormal_combo_immunes[idx], '-'))
        _fill_table(self.statuses, status_rows, resize_columns=resize)

        buff_rows = []
        for buff in character.buffs:
            life = buff.get('life_time', -1)
            if life < 0:
                time_text = f"无限；已存在 {_fmt(buff.get('existing_time', 0))}s"
            else:
                time_text = (f"剩余/总计 {_fmt(buff.get('remaining_time', 0))}/"
                             f"{_fmt(life)}s；已存在 {_fmt(buff.get('existing_time', 0))}s")
            modifiers = '; '.join(
                f"{m.get('name', '?')}: +{_fmt(m.get('addition', 0))}, "
                f"倍率+{_fmt(m.get('multiplier', 0))}, 最终+{_fmt(m.get('final_addition', 0))}, "
                f"最终×{_fmt(m.get('final_scaler', 1))}"
                for m in buff.get('attribute_modifiers', [])) or '-'
            statuses = []
            for label, key in (('状态', 'abnormal_flags'), ('免疫', 'abnormal_immunes'),
                               ('反制', 'abnormal_antis'), ('组合', 'abnormal_combos'),
                               ('组合免疫', 'abnormal_combo_immunes')):
                if buff.get(key):
                    statuses.append(label + ':' + '、'.join(buff[key]))
            definition = buff.get('definition') or {}
            def_flags = ', '.join(
                label for label, key in (
                    ('可沉默', 'silenceable'), ('可眩晕', 'stunnable'),
                    ('可冻结', 'freezable'), ('可浮空', 'levitatable'),
                    ('可束缚', 'ground_boundable'), ('持久', 'durable'))
                if definition.get(key)) or '-'
            runtime_info = (
                f"UID={buff.get('instance_uid', '-')}；优先级={buff.get('priority', '-')}；"
                f"触发={buff.get('trigger_count', '-')}；"
                f"启用={'是' if buff.get('enabled') else '否'}；"
                f"有效={'是' if buff.get('valid') else '否'}；"
                f"结束={'是' if buff.get('finished') else '否'}；"
                f"能力={hex(buff.get('ability_addr', 0)) if buff.get('ability_addr') else '-'}；"
                f"特效键={buff.get('effect_key') or '-'}；覆盖键={buff.get('override_key') or '-'}")
            static_info = (
                f"模板={definition.get('template_key') or '-'}；"
                f"优先级={definition.get('priority', '-')}；"
                f"持续类型={definition.get('life_time_type', '-')}；"
                f"触发生命类型={definition.get('trigger_life_type', '-')}；"
                f"触发次数/间隔={definition.get('trigger_count', '-')} / "
                f"{definition.get('trigger_interval', '-')}；"
                f"最大层数={definition.get('max_stack_count', '-')}；{def_flags}")
            shield = '-'
            if buff.get('custom_shield_value', 0) > 0:
                shield = f"特殊 {_fmt(buff['custom_shield_value'])}"
            elif buff.get('has_shield'):
                shield = f"是（mask={buff.get('shield_mask', 0)}）"
            buff_rows.append((
                buff_chinese_name(buff), buff.get('key', '?'),
                describe_active_buff(buff), buff.get('source_category', '-'),
                buff.get('source', '-'), time_text,
                f"{buff.get('stack_count', 0)}/{buff.get('max_valid_stack_count', 0)}",
                modifiers, '; '.join(statuses) or '-', shield,
                (buff.get('ability_class') or '-') + '；' + runtime_info,
                static_info,
                ('运行时：' + describe_blackboard(buff.get('blackboard', []))
                 + '；静态：' + describe_blackboard(definition.get('blackboard', [])))))
        _fill_table(self.buffs, buff_rows, resize_columns=resize)

        talent_rows = [(
            talent.get('name') or '-', talent.get('description') or '-',
            talent.get('prefab_key') or '-', talent.get('ability_class') or '-',
            talent.get('required_potential', '-'), talent.get('mode_count', 1),
            ', '.join(talent.get('parent_modes', [])) or '-',
            describe_blackboard(talent.get('blackboard', [])))
            for talent in character.talents]
        _fill_table(self.talents, talent_rows, resize_columns=resize)

        element_rows = []
        for idx, _internal, name in gs.ELEMENT_DEFS:
            damage, remaining, maximum = character.element_damage(idx)
            element_rows.append((name, damage, remaining, maximum,
                                 '是' if maximum > 0 and remaining <= 0 else '否',
                                 '是' if character.ep_break_recovery else '否'))
        _fill_table(self.elements, element_rows, resize_columns=resize)

        effect_rows = []
        for row in character.global_buffs:
            effect_rows.append((
                '全局/关卡 Buff', global_buff_chinese_name(row), hex(row.get('addr', 0)),
                describe_global_buff(row, character).replace(
                    '当前选中敌人', '当前干员')))
        for row in character.dynamic_abilities:
            effect_rows.append(('动态能力', row.get('class') or '-', hex(row.get('addr', 0)), '-'))
        for row in character.module_settings:
            effect_rows.append(('模组设置', row.get('class') or '-', hex(row.get('addr', 0)), '-'))
        if character.deck_buff_blackboard:
            effect_rows.append(('编队 Buff', 'DeckBuff Blackboard', '-',
                                describe_blackboard(character.deck_buff_blackboard)))
        _fill_table(self.effects, effect_rows, resize_columns=resize)

        self._first_update = False
        self.live_status.setText(f'实时更新中 · 最近刷新 {time.strftime("%H:%M:%S")}')
        self.live_status.setStyleSheet('color:#58a66a;')
