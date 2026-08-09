# -*- coding: utf-8 -*-
"""动作生效帧展示：敌我双方详情窗口「生效帧」tab 的行构建。

数据源 data/tables/effect_frames.json（ark_parser/extract_effect_frames.py 产物），
经 tools/enemy_health/enemy_db.load_effect_frames 加载。数据为静态配置：
每个动作（普攻/技能）的动画名、动画事件时间（生效帧）、弹道速度。

命中帧 = 弹道发射帧 + 距离 × 每格帧数；每格帧数 = 30 / 弹道速度(格/秒)。
"""

from tools.enemy_health.enemy_db import load_effect_frames

TICK = 30.0

COLUMNS = ['动作', '动画', '起手', '生效事件/帧', '弹道', '弹道速度', '命中帧']


def _sec_frames(t):
    """秒 → '1.3333s = 40帧'（帧数接近整数取整，否则保留 1 位小数）。"""
    if t is None:
        return '-'
    f = t * TICK
    fs = f'{round(f):g}' if abs(f - round(f)) < 0.05 else f'{f:.1f}'
    return f'{t:g}s = {fs}帧'


def _events_text(anim):
    """动画的事件列表 → 'OnAttack 0.9s = 27帧'（多事件换行）。"""
    if not anim:
        return '-'
    evs = anim.get('ev') or []
    if not evs:
        return '-'
    return '\n'.join(f"{e.get('n', '?')} {_sec_frames(e.get('t'))}" for e in evs)


def _match_anims(anims, key):
    """动画名匹配：精确优先，否则前缀变体（Attack → Attack_A/Attack_B...）。"""
    if not key:
        return []
    if key in anims:
        return [(key, anims[key])]
    return [(n, a) for n, a in sorted(anims.items())
            if n.startswith(key + '_')]


def _events_text(matched):
    """匹配到的动画事件 → 每行动画名: 事件 时间 = 帧。"""
    lines = []
    for name, anim in matched:
        evs = anim.get('ev') or []
        if not evs:
            continue
        prefix = f'{name}: ' if len(matched) > 1 else ''
        lines += [f"{prefix}{e.get('n', '?')} {_sec_frames(e.get('t'))}"
                  for e in evs]
    return '\n'.join(lines) or '-'


def _attack_event_frame(anim):
    """动画的生效帧（优先 OnAttack 事件，否则第一个事件），返回秒。"""
    if not anim:
        return None
    evs = anim.get('ev') or []
    for e in evs:
        if e.get('n') == 'OnAttack':
            return e.get('t')
    return evs[0].get('t') if evs else None


def _move_text(info):
    speed = info.get('projectileSpeed')
    if speed:
        return f'{speed:g} 格/秒 = {TICK / speed:g} 帧/格'
    fly = info.get('projectileFlyTime')
    if fly:
        return f'固定飞行 {_sec_frames(fly)}'
    return '-'


def _hit_text(launch_t, info):
    speed = info.get('projectileSpeed')
    if launch_t is not None and speed:
        per_tile = TICK / speed
        launch_f = launch_t * TICK
        examples = '，'.join(f'{d}格→{round(launch_f + d * per_tile):g}帧'
                            for d in (5, 10))
        return f'发射帧+距离×{per_tile:g}帧（{examples}）'
    fly = info.get('projectileFlyTime')
    if launch_t is not None and fly:
        f = fly * TICK
        fs = f'{round(f):g}' if abs(f - round(f)) < 0.05 else f'{f:.1f}'
        return f'发射帧+固定{fs}帧'
    return '-'


def _action_row(label, info, anims):
    """单个动作 → 表格行。info 含 animKey/preDelay/projectileKey/projectileSpeed 等。"""
    anim_key = info.get('animKey') or info.get('oneshotAnim') or ''
    matched = _match_anims(anims, anim_key)
    anim_text = anim_key or '-'
    if len(matched) == 1 and matched[0][1].get('d'):
        anim_text += f"（{matched[0][1]['d']:g}s = {matched[0][1].get('df'):g}帧）"
    elif len(matched) > 1:
        anim_text += f"（{len(matched)} 个变体）"
    pre = info.get('preDelay')
    pre_text = _sec_frames(pre) if pre else '-'
    proj = info.get('projectileKey') or '-'
    # 发射帧: 等待动画事件的取 OnAttack; 否则取 preDelay(起手结束即生效)
    first = matched[0][1] if matched else None
    if info.get('waitForAttackEvent'):
        launch_t = _attack_event_frame(first)
        if launch_t is None:
            launch_t = pre
    else:
        launch_t = pre if pre else _attack_event_frame(first)
    return (label, anim_text, pre_text, _events_text(matched), proj,
            _move_text(info), _hit_text(launch_t, info))


def _extra_anim_rows(anims, used_keys):
    """未被任何动作引用的攻击/技能动画 → 补充行（如 Skill_3_Combat）。"""
    rows = []
    for name, anim in sorted(anims.items()):
        if name in used_keys:
            continue
        if not (name.startswith('Attack') or name.startswith('Skill')):
            continue
        if not (anim.get('ev') or []):
            continue
        rows.append((f'动画 {name}',
                     f"{anim.get('d'):g}s = {anim.get('df'):g}帧",
                     '-', _events_text([(name, anim)]), '-', '-', '-'))
    return rows


def enemy_frame_rows(eid):
    """敌方生效帧行：普攻 + 各技能 + 未引用动画。无数据返回 []。"""
    entry = load_effect_frames().get('enemies', {}).get(eid)
    if not entry:
        return []
    anims = entry.get('anims') or {}
    rows = []
    used = set()
    attack = entry.get('attack')
    if attack:
        key = attack.get('animKey') or attack.get('oneshotAnim') or ''
        used.update(n for n, _ in _match_anims(anims, key))
        rows.append(_action_row('普攻', attack, anims))
    for sk in entry.get('skills') or []:
        key = sk.get('animKey') or sk.get('oneshotAnim') or ''
        used.update(n for n, _ in _match_anims(anims, key))
        rows.append(_action_row(sk.get('prefabKey') or '技能', sk, anims))
    rows += _extra_anim_rows(anims, used)
    return rows


def character_frame_rows(cid):
    """我方生效帧行：按 prefab mode（Default=普攻, S2/S3=技能2/3）+ 技能名映射。"""
    entry = load_effect_frames().get('characters', {}).get(cid)
    if not entry:
        return []
    anims = entry.get('anims') or {}
    skills = entry.get('skills') or []
    rows = []
    used = set()
    for m in entry.get('modes') or []:
        mode = m.get('mode') or '?'
        attack = m.get('attack') or {}
        label = mode
        anim_hint = None
        if mode == 'Default':
            label = '普攻'
            anim_hint = 'Attack'
        elif mode.startswith('S') and mode[1:].isdigit():
            idx = int(mode[1:]) - 1
            if 0 <= idx < len(skills) and skills[idx].get('name'):
                label = f"{skills[idx]['name']}（{mode}）"
            else:
                label = f'技能{mode[1:]}（{mode}）'
            anim_hint = 'Skill' if idx == 0 else f'Skill_{mode[1:]}'
        if not attack.get('animKey') and not attack.get('oneshotAnim') and anim_hint:
            attack = dict(attack)
            attack['animKey'] = anim_hint
        key = attack.get('animKey') or attack.get('oneshotAnim') or ''
        used.update(n for n, _ in _match_anims(anims, key))
        rows.append(_action_row(label, attack, anims))
    rows += _extra_anim_rows(anims, used)
    return rows
