# -*- coding: utf-8 -*-
"""把战斗 Buff/GlobalBuff 的内部键和 Blackboard 转成可靠的中文说明。"""

from . import game_structs as gs


BUFF_NAME_OVERRIDES = {
    'common_silence_immue': '沉默免疫',       # 游戏资源键本身拼作 immue
    'common_silence_immune': '沉默免疫',
    'common_disarmed_immune': '缴械免疫',
    'disarmed_immune': '缴械免疫（关卡效果）',
    'damage_scale[type]': '指定伤害类型抗性',
    'reduce_cost_by_interval': '部署费用周期降低',
}

BUFF_DESCRIPTION_OVERRIDES = {
    'common_silence_immue': '使目标免疫沉默。',
    'common_silence_immune': '使目标免疫沉默。',
    'common_disarmed_immune': '使目标免疫缴械。',
    'disarmed_immune': '向符合筛选条件的单位施加缴械免疫。',
    'damage_scale[type]': (
        '按指定伤害类型执行伤害抗性规则。它属于受击事件中的动态结算效果，'
        '不能仅凭一个参数安全换算成固定减伤百分比。'),
    'reduce_cost_by_interval': '按固定时间间隔修改指定单位或装置的部署费用。',
}


BLACKBOARD_LABELS = {
    '@event_key': '事件键',
    'key': '效果键',
    'duration': '持续时间',
    'chant_duration': '吟唱时间',
    'dist': '距离',
    'min_dist': '最小距离',
    'max_dist': '最大距离',
    'atk': '攻击力',
    'def': '防御力',
    'attack_speed': '攻击速度',
    'magic_resistance': '法术抗性',
    'block_cnt': '阻挡数',
    'atk_scale': '攻击倍率',
    'atk_addition': '攻击加算',
    'heal_scale': '治疗倍率',
    'damage_scale': '伤害倍率',
    'damage_resistance': '伤害抗性参数',
    'range_scale': '范围倍率',
    'range_id': '范围ID',
    'scale': '倍率',
    'speed_scale': '速度倍率',
    'delay': '延迟',
    'times': '次数',
    'cnt': '数量',
    'interval': '间隔',
    'first_trigger_interval': '首次触发间隔',
    'reload_interval': '装填间隔',
    'hit_interval': '命中间隔',
    'hit_times': '命中次数',
    'max_target': '最大目标数',
    'prob': '概率',
    'value': '数值',
    'cost': '费用变化',
    'cost_scale': '费用倍率',
    'respawn_time': '再部署时间',
    'sp': '技力',
    'max_sp': '最大技力',
    'init_sp': '初始技力',
    'sp_ratio': '技力比例',
    'hp': '生命值',
    'max_hp': '最大生命值',
    'hp_ratio': '生命比例',
    'force': '力度',
    'range_radius': '作用半径',
    'ability_range_radius': '技能作用半径',
    'trig_cnt': '触发次数',
    'max_stack_cnt': '最大层数',
    'max_valid_stack_cnt': '最大有效层数',
    'init_stack_cnt': '初始层数',
    'cur_stack_cnt': '当前层数',
    'stun': '眩晕',
    'freeze': '冻结',
    'effect': '特效',
    'skill': '技能',
    'enemy': '目标敌人ID',
    'enemy_exclude': '排除敌人ID',
    'char': '目标干员/装置ID',
    'char_exclude': '排除干员/装置ID',
    'char_id': '干员ID',
    'tmpl_id': '模板ID',
    'tile': '地块',
    'move_speed': '移动速度',
    'tag': '标签',
    'rune_tag': '关卡符文标签',
    'filter_tag': '目标标签',
    'filter_tag_exclude': '排除标签',
    'profession': '职业',
    'unit_type': '单位类型',
    'sub_profession': '子职业',
    'buildable': '可部署类型',
    'direction': '方向',
    'ep_ratio': '损伤条比例',
    'ep_damage_ratio': '元素损伤比例',
    'ep_heal_ratio': '元素损伤恢复比例',
    'ep_break_duration': '元素爆发持续时间',
    'ep_damage_scale': '元素损伤倍率',
    'ep_damage_resistance': '元素损伤减免参数',
    'element_type': '元素类型',
    'damage_type': '伤害类型',
    'side': '阵营',
    'source': '来源',
    'target': '目标',
    'override_key': '覆盖键',
    'remaining_time': '剩余时间',
    'enable': '是否启用',
    'addition': '基础加算',
    'multiplier': '倍率加算',
    'final_scaler': '最终倍率',
    'final_addition': '最终加算',
    'physical': '作用于物理伤害',
    'magical': '作用于法术伤害',
}

BOOL_KEYS = {
    'enable', 'physical', 'magical', 'stun', 'freeze', 'respawn_disabled',
    'respawn_stopped',
}
SECONDS_KEYS = {
    'duration', 'chant_duration', 'delay', 'interval', 'first_trigger_interval',
    'reload_interval', 'hit_interval', 'respawn_time', 'remaining_time',
    'ep_break_duration',
}

LIFE_TYPE_NAMES = {0: '未指定', 1: '有限时长', 2: '无限时长', 3: '自定义时长'}


def _number(value):
    if isinstance(value, float):
        return f'{value:.6f}'.rstrip('0').rstrip('.') or '0'
    return str(value)


def _signed(value):
    text = _number(value)
    return text if text.startswith('-') else '+' + text


def blackboard_value(row):
    return row.get('value_str') or row.get('value', 0.0)


def blackboard_dict(rows):
    return {row.get('key', ''): blackboard_value(row) for row in rows if row.get('key')}


def format_blackboard_value(key, value):
    if key in BOOL_KEYS and isinstance(value, (int, float)):
        return '是' if value != 0 else '否'
    if key in SECONDS_KEYS and isinstance(value, (int, float)):
        return f'{_number(value)} 秒'
    if key == 'prob' and isinstance(value, (int, float)):
        return f'{_number(value)}（约 {_number(value * 100)}%）'
    if key in ('element_type', 'damage_type') and isinstance(value, (int, float)):
        enum_value = int(value)
        if key == 'element_type':
            return gs.ELEMENT_CN_NAMES.get(enum_value, f'枚举 {enum_value}')
        return {0: '无', 1: '物理', 2: '法术', 3: '真实', 4: '治疗', 5: '元素'}.get(
            enum_value, f'枚举 {enum_value}')
    return _number(value)


def describe_blackboard(rows):
    if not rows:
        return '-'
    parts = []
    for row in rows:
        key = row.get('key') or '?'
        label = BLACKBOARD_LABELS.get(key, f'参数 {key}')
        parts.append(f'{label}：{format_blackboard_value(key, blackboard_value(row))}')
    return '；'.join(parts)


def _modifier_description(modifier):
    terms = []
    if abs(modifier.get('addition', 0.0)) > 1e-9:
        terms.append(f"基础加算 {_signed(modifier['addition'])}")
    if abs(modifier.get('multiplier', 0.0)) > 1e-9:
        terms.append(f"倍率加算 {_signed(modifier['multiplier'])}")
    if abs(modifier.get('final_addition', 0.0)) > 1e-9:
        terms.append(f"最终加算 {_signed(modifier['final_addition'])}")
    if abs(modifier.get('final_scaler', 1.0) - 1.0) > 1e-9:
        terms.append(f"最终倍率 ×{_number(modifier['final_scaler'])}")
    return f"{modifier.get('name') or modifier.get('key') or '?'}：" + ('，'.join(terms) or '参与重算')


def buff_chinese_name(buff):
    key = buff.get('key', '')
    if key in BUFF_NAME_OVERRIDES:
        return BUFF_NAME_OVERRIDES[key]
    immunes = buff.get('abnormal_immunes') or []
    flags = buff.get('abnormal_flags') or []
    modifiers = buff.get('attribute_modifiers') or []
    if immunes:
        return '、'.join(immunes) + '免疫'
    if flags:
        return '、'.join(flags) + '状态'
    if modifiers:
        return '、'.join(m.get('name', '?') for m in modifiers[:2]) + '调整'
    if buff.get('has_shield'):
        return '伤害护盾'
    return '战斗效果'


def describe_active_buff(buff):
    parts = []
    override = BUFF_DESCRIPTION_OVERRIDES.get(buff.get('key', ''))
    if override:
        parts.append(override)
    modifiers = buff.get('attribute_modifiers') or []
    if modifiers:
        parts.append('；'.join(_modifier_description(m) for m in modifiers))
    for label, key in (('赋予状态', 'abnormal_flags'), ('赋予免疫', 'abnormal_immunes'),
                       ('反制状态', 'abnormal_antis'), ('赋予组合状态', 'abnormal_combos'),
                       ('组合状态免疫', 'abnormal_combo_immunes')):
        values = buff.get(key) or []
        if values:
            parts.append(f"{label}：" + '、'.join(values))
    if buff.get('has_shield'):
        types = [name for bit, name in gs.DAMAGE_TYPE_MASK_CN_NAMES.items()
                 if buff.get('shield_mask', 0) & bit]
        parts.append('提供' + ('/'.join(types) if types else '指定伤害类型') + '护盾')
    if not parts:
        parts.append('该效果由战斗事件或脚本执行，当前没有直接属性/状态修正项。')
    return '；'.join(parts)


def global_buff_chinese_name(buff):
    key = buff.get('key', '')
    if key in BUFF_NAME_OVERRIDES:
        return BUFF_NAME_OVERRIDES[key]
    defs = buff.get('buff_defs') or []
    if defs:
        first = {'key': defs[0].get('buff_key', '')}
        return buff_chinese_name(first)
    return '关卡全局效果'


def describe_global_buff(buff, enemy=None):
    key = buff.get('key', '')
    values = blackboard_dict(buff.get('blackboard') or [])
    target = values.get('enemy') or values.get('char') or '符合筛选条件的单位'
    if enemy is not None and target == getattr(enemy, 'eid', None):
        target = f'{enemy.name}（{enemy.eid}）'

    if key == 'damage_scale[type]':
        types = []
        if values.get('physical'):
            types.append('物理')
        if values.get('magical'):
            types.append('法术')
        type_text = '、'.join(types) if types else '指定类型'
        desc = (f'对 {target} 启用{type_text}伤害抗性规则；'
                f"伤害抗性参数={_number(values.get('damage_resistance', 0))}")
        if 'range_radius' in values:
            desc += f"，作用半径={_number(values['range_radius'])} 格"
        desc += '。该参数参与动态受击结算，不直接等同于固定减伤百分比。'
    elif key == 'disarmed_immune':
        desc = f'使 {target} 免疫缴械。'
    elif key == 'reduce_cost_by_interval':
        interval = values.get('interval', 0)
        cost = values.get('cost', 0)
        if isinstance(cost, (int, float)) and cost < 0:
            change = f'降低 {_number(abs(cost))} 点'
        else:
            change = f'变化 {_number(cost)} 点'
        desc = f'使 {target} 的部署费用每隔 {_number(interval)} 秒{change}。'
    else:
        desc = BUFF_DESCRIPTION_OVERRIDES.get(
            key, '向符合筛选条件的单位施加关卡级战斗效果。')

    if buff.get('applies_to_selected'):
        desc += ' 当前选中敌人已命中此效果。'
    else:
        desc += ' 当前选中敌人未命中此效果。'
    return desc


def describe_buff_def(data):
    key = data.get('buff_key') or data.get('template_key') or '?'
    name = BUFF_NAME_OVERRIDES.get(key, key)
    life_type = LIFE_TYPE_NAMES.get(data.get('life_time_type'), str(data.get('life_time_type')))
    duration = ''
    if data.get('life_time_type') == 1:
        duration = f"，时长 {_number(data.get('life_time', 0))} 秒"
    return f"{name}（{key}；{life_type}{duration}；优先级 {data.get('priority', 0)}）"
