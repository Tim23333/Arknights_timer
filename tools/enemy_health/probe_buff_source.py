# -*- coding: utf-8 -*-
"""Buff 来源实体 + blackboard 键诊断探针（只读，使用 memsrv v4）

用法: python tools/enemy_health/probe_buff_source.py [秒数] [adb serial]
在关卡内运行, 周期性读取所有敌人 buff:
1. 追踪 source 实体地址/类名/ID 的变化 (定位"来源列在编号和干员名之间切换")
2. 对含未解析键 (?) 的 blackboard, 逐个条目打印 key_ptr 原始值/区域权限/
   绕过 is_ptr 的直接试读结果 (定位键名解析失败原因)
"""

import os
import struct
import sys
import time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(errors='replace')

if __package__ in (None, ''):
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    __package__ = 'tools.enemy_health'

from .enemy_reader import EnemyReader
from . import game_structs as gs


def _u64(b, off):
    return int.from_bytes(b[off:off + 8], 'little') if b and len(b) >= off + 8 else 0


def _i32(b, off):
    return int.from_bytes(b[off:off + 4], 'little', signed=True) \
        if b and len(b) >= off + 4 else 0


def region_perms(mc, addr):
    for s, e, perms, name in mc.regions:
        if s <= addr < e:
            return f'{perms} {name or "(anon)"}'
    return '(不在任何映射)'


def describe_source(mc, source):
    """读取 source 实体的类名和 Entity.id 字符串。"""
    if not source:
        return ('-', '-')
    klass = ''
    try:
        klass = mc.read_klass_name(source) or '?'
    except Exception:
        klass = '?'
    ent_id = ''
    blk = mc.read(source, gs.EntityFields.ID + 8)
    if blk:
        id_ptr = _u64(blk, gs.EntityFields.ID)
        if mc.is_ptr(id_ptr):
            ent_id = mc.read_ustring(id_ptr) or ''
    return (klass, ent_id or '-')


def dump_blackboard_diag(reader, buff, log):
    """对 blackboard 含未解析键的 buff, 逐条目打印原始诊断。"""
    mc = reader.mc
    blk = mc.read(buff['addr'], gs.BuffFields.READ_SIZE)
    if not blk:
        return
    bb = _u64(blk, gs.BuffFields.M_BLACKBOARD)
    log(f'    [bb诊断] buff={buff["key"]} blackboard={hex(bb)} '
        f'{region_perms(mc, bb)}')
    head = mc.read(bb, 0x20)
    if not head:
        log('    [bb诊断] 头读不到')
        return
    items, count = _u64(head, gs.ListInternal.ITEMS), _i32(head, gs.ListInternal.SIZE)
    log(f'    [bb诊断] items={hex(items)} count={count}')
    if not (0 < count <= 64):
        return
    data = mc.read(items + gs.Il2CppArray.ITEMS, count * 0x18)
    if not data:
        log('    [bb诊断] 条目数组读不到')
        return
    for idx in range(count):
        off = idx * 0x18
        key_ptr = _u64(data, off)
        value = struct.unpack_from('<f', data, off + 8)[0]
        line = (f'    [{idx}] key_ptr={hex(key_ptr)} rw={mc.is_ptr(key_ptr)} '
                f'{region_perms(mc, key_ptr) if key_ptr else ""} value={value:g}')
        if key_ptr:
            raw = mc.read(key_ptr, gs.Il2CppString.CHARS + 128)
            if raw and len(raw) >= gs.Il2CppString.CHARS:
                cnt = _i32(raw, gs.Il2CppString.LENGTH)
                if 0 <= cnt <= 64:
                    text = raw[gs.Il2CppString.CHARS:
                               gs.Il2CppString.CHARS + cnt * 2].decode(
                                   'utf-16-le', errors='replace')
                    line += f' str={text!r}'
                else:
                    line += f' (count={cnt} 非法)'
            else:
                line += ' (该区域读不到)'
        log(line)


def main():
    seconds = 8.0
    serial = '127.0.0.1:16384'
    args = sys.argv[1:]
    if args:
        seconds = float(args[0])
    if len(args) > 1:
        serial = args[1]
    reader = EnemyReader(adb_serial=serial)
    reader.log('[探针] 连接游戏进程 ...')
    reader.mc.connect()
    reader.log('[探针] bootstrap ...')
    if not reader.bootstrap():
        reader.log('[探针] 定位失败, 请确认已进入关卡')
        return
    snap = reader.poll_fast()
    if not snap.get('ok'):
        reader.log(f"[探针] 首帧失败: {snap.get('msg')}")
        return
    reader.log(f"[探针] 敌人 {len(snap['enemies'])} 个, 开始追踪 buff 来源 {seconds}s")

    last_sig = {}
    bb_dumped = set()
    t0 = time.time()
    first = True
    while time.time() - t0 < seconds:
        snap = reader.poll_fast()
        if not snap.get('ok'):
            time.sleep(0.4)
            continue
        for enemy in snap['enemies']:
            if getattr(enemy, 'lifecycle', 'active') != 'active':
                continue
            ptr = getattr(enemy, 'buff_container_ptr', 0)
            if not ptr:
                continue
            try:
                buffs = reader._read_active_buffs(ptr)
            except Exception as e:
                reader.log(f'[探针] 读 buff 失败: {e}')
                continue
            for buff in buffs:
                key = buff['key']
                source = buff['source_addr']
                klass, ent_id = describe_source(reader.mc, source) \
                    if source else ('-', '关卡/无实体')
                in_names = source in reader._names
                sig = (key, source, klass, ent_id, in_names)
                if first or last_sig.get((enemy.addr, key)) != sig:
                    last_sig[(enemy.addr, key)] = sig
                    reader.log(
                        f"[{time.time() - t0:5.1f}s] {enemy.name} buff={key}\n"
                        f"    source={hex(source) if source else 0} "
                        f"klass={klass} id={ent_id} "
                        f"in_names={in_names} 显示={buff['source']}")
                if (buff['addr'] not in bb_dumped
                        and any(not row.get('key')
                                for row in buff.get('blackboard', []))):
                    bb_dumped.add(buff['addr'])
                    dump_blackboard_diag(reader, buff, reader.log)
        first = False
        time.sleep(0.4)


if __name__ == '__main__':
    main()
