# -*- coding: utf-8 -*-
r"""游戏更新后刷新敌人扫描偏移与名称数据库。

推荐用法（在仓库根目录）：

    python -m tools.enemy_health.update_from_unpack --ark-data Ark_data

如果 AssetStudio-Arknights 的输出不在 ``data/anon``，追加：

    --assets D:\path\to\AssetStudio-output

如果手头是游戏原始 ``StreamingAssets/AB/.../anon``，且已安装 UnityPy：

    --ab-dir D:\path\to\StreamingAssets\AB\Android\anon

脚本会：
1. 从 dump.cs 严格按类名/字段名提取内存偏移并生成 generated_offsets.json；
2. 从 AssetStudio 输出或已解出的 bin 中复制 enemy_handbook_table/enemy_database；
3. 从 handbook 生成稳定、易打包的 enemy_names.json；
4. 对关键字段、未知枚举增量与名称数量做校验，失败时返回非零退出码。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

try:
    from . import game_structs as _game_structs
    from .enemy_db import parse_handbook
except ImportError:  # 兼容直接执行本文件
    import game_structs as _game_structs
    from enemy_db import parse_handbook


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OFFSETS = Path(__file__).with_name('generated_offsets.json')
TABLE_PREFIXES = ('enemy_handbook_table', 'enemy_database')
TABLE_PATTERN = re.compile(
    rb'(enemy_handbook_table|enemy_database)[a-fA-F0-9]{4,}')
CLASS_RE = re.compile(
    r'^(?:public|private|protected|internal)\s+(?:(?:abstract|sealed|static|readonly)\s+)*'
    r'(class|struct|enum)\s+([^\s:{]+)')
FIELD_RE = re.compile(r'^\s*.+?\s+([^\s;]+);\s*//\s*0x([0-9A-Fa-f]+)\s*$')
ENUM_RE = re.compile(r'^\s*public const\s+\S+\s+(\w+)\s*=\s*(-?\d+);')


# 输出类 -> (dump 命名空间, dump 类, 输出字段 -> dump 字段)
FIELD_MAP = {
    'EntityFields': ('Torappu.Battle', 'Entity', {
        'M_STATE_MACHINE': 'm_stateMachine', 'M_HP': 'm_hp', 'M_ES': 'm_es',
        'M_SP': 'm_sp', 'M_RESPAWN_CNT': 'm_respawnCnt', 'M_EP_ARRAY': 'm_epArray',
        'M_ATTRIBUTES': 'm_attributes', 'M_DIRECTION': 'm_direction',
        'M_EP_CONTROLLER': 'm_epController', 'M_SHIELD_CONTROLLER': 'm_shieldController',
        'ID': '<id>k__BackingField', 'TMPL_ID': '<tmplId>k__BackingField',
        'FINISH_REASON': '<finishReason>k__BackingField',
        'BUFF_CONTAINER': '<buffContainer>k__BackingField',
        'MAX_SP': '<maxSp>k__BackingField', 'MINUS_HP': '<minusHp>k__BackingField',
    }),
    'EnemyFields': ('Torappu.Battle', 'Enemy', {
        'M_CURRENT_TILE': 'm_currentTile', 'M_BLOCK_POSITION': 'm_blockPosition',
        'M_POS_IN_LAST_FRAME': 'm_posInLastFrame', 'M_ALL_SKILLS': 'm_allSkills',
        'ROUTE_SPAWN_POS': 'm_routeSpawnPosition', 'M_SKILLS': 'm_skills',
        'DATA': '<data>k__BackingField', 'OPTIONS': '<options>k__BackingField',
    }),
    'EnemyOptionsFields': ('', 'Enemy.Options', {
        'IS_SUMMON': 'isSummon', 'HIDDEN_GROUP_KEY': 'hiddenGroupKey',
        'ACTION_DATA': 'actionData',
    }),
    'AttributesFields': ('Torappu.Battle', 'Attributes', {
        'M_ABNORMAL_FLAGS_COUNTER': 'm_abnormalFlagsCounter',
        'M_ABNORMAL_IMMUNE_COUNTER': 'm_abnormalImmuneCounter',
        'M_ABNORMAL_ANTI_COUNTER': 'm_abnormalAntiCounter',
        'M_ABNORMAL_COMBO_MGR': 'm_abnormalComboMgr',
        'M_RAW_DATA': 'm_rawData', 'M_CACHED_DATA': 'm_cachedData',
    }),
    'AbnormalComboManagerFields': ('', 'Attributes.AbnormalComboManager', {
        'M_ABNORMAL_COMBO_COUNTER': 'm_abnormalComboCounter',
        'M_ABNORMAL_COMBO_IMMUNE_COUNTER': 'm_abnormalComboImmuneCounter',
    }),
    'StateMachineFields': ('Torappu', 'StateMachine', {
        'CURRENT_STATE_ID': '<currentStateId>k__BackingField',
    }),
    'EPControllerFields': ('', 'Entity.EPController', {
        'M_IS_IN_BREAK_RECOVERY': 'm_isInBreakRecovery',
    }),
    'ShieldUIControllerFields': ('', 'Entity.ShieldUIController', {
        'M_SHIELD_TO_SHOW': 'm_shieldToShow',
    }),
    'EnemySkillFields': ('Torappu.Battle', 'EnemySkill', {
        'MAX_TRIGGER_TIME': '_maxTriggerTime', 'OVERWRITE_INIT_CD': '_overwriteInitCooldown',
        'M_SP_COST': 'm_spCost', 'M_TRIGGER_CNT': 'm_triggerCnt',
        'M_COOLDOWN_TIMER': 'm_cooldownTimer', 'M_MAIN_ABILITY': 'm_mainAbility',
        'DATA': '<data>k__BackingField', 'OWNER': '<owner>k__BackingField',
    }),
    'PeriodicTimerFields': ('Torappu', 'PeriodicTimer', {
        'M_PERIOD_TIME': 'm_periodTime', 'M_REMAINING_TIME': 'm_remainingTime',
    }),
    'ESkillDataFields': ('', 'LevelData.EnemyData.ESkillData', {
        'PREFAB_KEY': 'prefabKey', 'PRIORITY': 'priority', 'COOLDOWN': 'cooldown',
        'INIT_COOLDOWN': 'initCooldown', 'SP_COST': 'spCost',
    }),
    'LevelEnemyDataFields': ('', 'LevelData.EnemyData', {
        'NAME': 'name', 'DESCRIPTION': 'description', 'KEY': 'key',
        'ATTRIBUTES': 'attributes',
    }),
    'BuffContainerFields': ('', 'Buff.BuffContainer', {'M_BUFFS': 'm_buffs'}),
    'BuffFields': ('Torappu.Battle', 'Buff', {
        'M_SOURCE': 'm_source', 'M_ABILITY': 'm_ability',
        'M_ATTRIBUTE_MULTIPLIERS': 'm_attributeMultipliers',
        'M_ATTRIBUTE_ADDITIONS': 'm_attributeAdditions',
        'M_ATTRIBUTE_FINAL_ADDITIONS': 'm_attributeFinalAdditions',
        'M_ATTRIBUTE_FINAL_SCALERS': 'm_attributeFinalScalers',
        'M_DATA': 'm_data', 'M_LIFE_TIME': 'm_lifeTime',
        'M_REMAINING_TIME': 'm_remainingTime', 'M_EXISTING_TIME': 'm_existingTime',
        'M_TRIGGER_CNT': 'm_triggerCnt', 'M_STACK_CNT': 'm_stackCnt',
        'M_MAX_VALID_STACK_CNT': 'm_maxValidStackCnt', 'M_BLACKBOARD': 'm_blackboard',
        'IS_FINISHED': 'm_isFinished', 'IS_ACTUALLY_ENABLED': 'm_isActuallyEnabled',
        'IS_VALID': 'm_isValid', 'IS_EP_BREAK_BUFF': 'm_isEpBreakBuff',
        'KEY': '<key>k__BackingField', 'OVERRIDE_KEY': '<overrideKey>k__BackingField',
        'INSTANCE_UID': '<instanceUid>k__BackingField',
        'PRIORITY': '<priority>k__BackingField',
        'ATTRIBUTE_MASK': '<attributeMask>k__BackingField',
        'ABNORMAL_FLAG_MASK': '<abnormalFlagMask>k__BackingField',
        'ABNORMAL_IMMUNE_MASK': '<abnormalImmuneMask>k__BackingField',
        'ABNORMAL_ANTI_MASK': '<abnormalAntiMask>k__BackingField',
        'ABNORMAL_COMBO_MASK': '<abnormalComboMask>k__BackingField',
        'ABNORMAL_COMBO_IMMUNE_MASK': '<abnormalComboImmuneMask>k__BackingField',
        'EFFECT_KEY': '<effectKey>k__BackingField', 'SHIELD_MASK': 'm_shieldMask',
        'HAS_SHIELD': '<hasShield>k__BackingField',
    }),
    'GlobalBuffFields': ('Torappu.Battle', 'GlobalBuff', {
        'KEY': '_key', 'BUFFS': '_buffs', 'SOURCE_TYPE': 'm_sourceType',
        'TARGET_MAP': 'm_targetMap', 'BLACKBOARD': 'blackboard',
        'INSTANCE_UID': '<instanceUid>k__BackingField',
    }),
    'BuffDataFields': ('Torappu', 'BuffData', {
        'BUFF_KEY': 'buffKey', 'TEMPLATE_KEY': 'templateKey',
        'LIFE_TIME_TYPE': 'lifeTimeType', 'DURATION_KEY': 'durationKey',
        'LIFE_TIME': 'lifeTime', 'PRIORITY': 'priority',
    }),
    'BattleControllerFields': ('Torappu.Battle', 'BattleController', {
        'MAP': '_map', 'SCHEDULER': '_scheduler',
        'FACTORY': '_factory', 'M_GLOBAL_BUFFS': 'm_globalBuffs',
        'M_LOGGER': 'm_logger', 'LEVEL_DATA': 'm_levelData',
        'GAME_MODE': 'm_gameMode', 'DIALOG_CONTROLLER': 'm_dialogController',
        'M_STATE': 'm_state', 'M_SPEED_LEVEL': 'm_speedLevel',
        'M_TIME_SCALE': 'm_originTimeScale', 'M_REAL_PLAY_TIME': 'm_realPlayTime',
        'UNIT_MANAGER': '<unitManager>k__BackingField',
    }),
    'SchedulerFields': ('Torappu.Battle', 'Scheduler', {
        'M_SPAWNED_ENEMIES_CNT': 'm_spawnedEnemiesCnt',
        'M_WAVE_START_TIME': 'm_waveStartTime',
        'M_FRAGMENT_START_TIME': 'm_fragmentStartTime', 'M_WAVES': 'm_waves',
        'M_ACTION_QUEUE': 'm_actionQueue',
        'M_MANAGED_WAVE_ENEMIES': 'm_managedWaveEnemies',
        'M_MANAGED_FINAL_ENEMIES': 'm_managedFinalEnemies',
        'M_CACHED_ENEMIES': 'm_cachedEnemies',
        'TOTAL_ENEMIES_CNT': '<totalEnemiesCnt>k__BackingField',
        'SCHEDULER_DRIVER': '<driver>k__BackingField',
    }),
    'UnitManagerFields': ('Torappu.Battle', 'UnitManager', {
        'ALL_UNITS': '<allUnits>k__BackingField',
        'CHARACTERS': '<characters>k__BackingField',
        'ENEMIES': '<enemies>k__BackingField',
        'NEUTRAL_UNITS': '<neutralUnits>k__BackingField',
    }),
    'SchedulerDriverFields': ('Torappu.Battle', 'SchedulerDriver', {
        'BATTLE_CONTROLLER': 'm_controller',
        'SCHEDULER_WRAPPER': 'm_mainScheduler',
    }),
    'LevelDataFields': ('Torappu', 'LevelData', {
        'LEVEL_ID': 'levelId', 'ENEMIES': 'enemies', 'ENEMY_DB_REFS': 'enemyDbRefs',
        'WAVES': 'waves', 'BRANCHES': 'branches',
    }),
    'WaveDataFields': ('', 'LevelData.WaveData', {
        'PRE_DELAY': 'preDelay', 'POST_DELAY': 'postDelay',
        'MAX_WAIT_NEXT': 'maxTimeWaitingForNextWave', 'FRAGMENTS': 'fragments',
    }),
    'FragmentDataFields': ('', 'LevelData.WaveData.FragmentData', {
        'PRE_DELAY': 'preDelay', 'ACTIONS': 'actions',
    }),
    'BranchDataFields': ('', 'LevelData.BranchData', {'PHASES': 'phases'}),
    'BranchPhaseDataFields': ('', 'LevelData.BranchData.PhaseData', {
        'PRE_DELAY': 'preDelay', 'ACTIONS': 'actions',
    }),
    'SpawnActionFields': ('', 'LevelData.WaveData.FragmentData.ActionData', {
        'ACTION_TYPE': 'actionType', 'MANAGED_BY_SCHEDULER': 'managedByScheduler',
        'KEY': 'key', 'COUNT': 'count', 'PRE_DELAY': 'preDelay',
        'INTERVAL': 'interval', 'ROUTE_INDEX': 'routeIndex',
        'HIDDEN_GROUP': 'hiddenGroup', 'RANDOM_SPAWN_GROUP': 'randomSpawnGroupKey',
        'RANDOM_SPAWN_PACK': 'randomSpawnGroupPackKey', 'RANDOM_TYPE': 'randomType',
        'REFRESH_TYPE': 'refreshType', 'WEIGHT': 'weight',
        'DONT_BLOCK_WAVE': 'dontBlockWave',
        'FORCE_BLOCK_WAVE_IN_BRANCH': 'forceBlockWaveInBranch',
        'IS_VALID': 'isValid', 'NOT_COUNT_IN_TOTAL': 'notCountInTotal',
        'EXTRA_META': 'extraMeta', 'ACTION_ID': 'actionId',
    }),
}

ENUM_MAP = {
    'AttributeType': ('Torappu', 'AttributeType'),
    'AbnormalFlag': ('Torappu', 'AbnormalFlag'),
    'AbnormalCombo': ('Torappu', 'AbnormalCombo'),
    'ElementType': ('Torappu.Battle', 'ElementType'),
}


def parse_dump(path: Path):
    classes = {}
    enums = {}
    namespace = ''
    current = None
    current_kind = ''
    fields = {}
    values = {}

    def finish():
        nonlocal current, fields, values
        if current is None:
            return
        key = (namespace_at_start, current)
        if current_kind == 'enum':
            enums[key] = values
        else:
            classes[key] = fields
        current = None
        fields = {}
        values = {}

    namespace_at_start = ''
    with path.open('r', encoding='utf-8-sig', errors='replace') as stream:
        for raw in stream:
            line = raw.rstrip('\r\n')
            if line.startswith('// Namespace:'):
                finish()
                namespace = line.partition(':')[2].strip()
                continue
            match = CLASS_RE.match(line)
            if match:
                finish()
                current_kind, current = match.groups()
                namespace_at_start = namespace
                continue
            if current is None:
                continue
            match = FIELD_RE.match(line)
            if match and current_kind != 'enum':
                field, value = match.groups()
                fields[field] = int(value, 16)
                continue
            match = ENUM_RE.match(line)
            if match and current_kind == 'enum':
                field, value = match.groups()
                values[field] = int(value)
    finish()
    return classes, enums


def build_offsets(dump_path: Path):
    classes, enums = parse_dump(dump_path)
    output = {}
    missing = []
    for output_class, (namespace, class_name, mapping) in FIELD_MAP.items():
        source = classes.get((namespace, class_name))
        if source is None:
            missing.append(f'{namespace}.{class_name}: class not found')
            continue
        converted = {}
        for output_name, field_name in mapping.items():
            if field_name not in source:
                missing.append(f'{namespace}.{class_name}.{field_name}')
            else:
                converted[output_name] = f'0x{source[field_name]:X}'
        if converted:
            output[output_class] = converted

    # 读取尺寸不是 dump 字段；用最后一个实际读取字段保守推导。
    if ('OPTIONS' in output.get('EnemyFields', {})
            and 'ACTION_DATA' in output.get('EnemyOptionsFields', {})):
        options = int(output['EnemyFields']['OPTIONS'], 0)
        action = int(output['EnemyOptionsFields']['ACTION_DATA'], 0)
        output['EnemyFields']['READ_SIZE'] = f'0x{(options + action + 0x10 + 7) & ~7:X}'
    if 'HAS_SHIELD' in output.get('BuffFields', {}):
        last = int(output['BuffFields']['HAS_SHIELD'], 0)
        output['BuffFields']['READ_SIZE'] = f'0x{(last + 4 + 7) & ~7:X}'
    if 'INSTANCE_UID' in output.get('GlobalBuffFields', {}):
        last = int(output['GlobalBuffFields']['INSTANCE_UID'], 0)
        output['GlobalBuffFields']['READ_SIZE'] = f'0x{(last + 8 + 7) & ~7:X}'
    if 'PRIORITY' in output.get('BuffDataFields', {}):
        last = int(output['BuffDataFields']['PRIORITY'], 0)
        output['BuffDataFields']['READ_SIZE'] = f'0x{(last + 0x10 + 7) & ~7:X}'
    if 'ACTION_ID' in output.get('SpawnActionFields', {}):
        last = int(output['SpawnActionFields']['ACTION_ID'], 0)
        output['SpawnActionFields']['READ_SIZE'] = f'0x{(last + 0x10 + 7) & ~7:X}'

    enum_output = {}
    for output_name, key in ENUM_MAP.items():
        source = enums.get(key)
        if source is None:
            missing.append(f'{key[0]}.{key[1]}: enum not found')
            continue
        enum_output[output_name] = dict(sorted(source.items(), key=lambda row: row[1]))
    required = {
        'EntityFields': ('M_HP', 'M_ATTRIBUTES', 'ID', 'BUFF_CONTAINER'),
        'EnemyFields': ('M_SKILLS', 'DATA', 'OPTIONS', 'READ_SIZE'),
        'AttributesFields': ('M_CACHED_DATA',),
        'BattleControllerFields': ('SCHEDULER', 'LEVEL_DATA', 'UNIT_MANAGER'),
    }
    fatal = [f'{cls}.{field}' for cls, names in required.items()
             for field in names if field not in output.get(cls, {})]
    return output, enum_output, missing, fatal


def sha256_file(path: Path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def display_source_path(path: Path):
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(resolved)


def identify_table(path: Path):
    lower = path.name.lower()
    for prefix in TABLE_PREFIXES:
        if lower.startswith(prefix) and path.suffix.lower() in ('.bin', '.dat', '.bytes'):
            return path.stem
    if not (path.name.startswith('CAB-') or '.bin_unpacked' in str(path.parent)):
        return None
    try:
        with path.open('rb') as stream:
            match = TABLE_PATTERN.search(stream.read(8192))
        return match.group(0).decode('ascii').lower() if match else None
    except OSError:
        return None


def extract_preunpacked(paths, tables_dir: Path):
    # 同一表的 hash 后缀会随版本变化。paths 按优先级排列，只保留每个前缀
    # 的第一个命中，避免显式传入的新表与默认 data/anon 旧表一起被复制。
    found = {}
    for root in paths:
        if not root or not root.exists():
            continue
        candidates = [root] if root.is_file() else root.rglob('*')
        for path in candidates:
            if not path.is_file():
                continue
            table_id = identify_table(path)
            if not table_id:
                continue
            prefix = next((item for item in TABLE_PREFIXES
                           if table_id.startswith(item)), None)
            if prefix and prefix not in found:
                found[prefix] = (table_id, path)
    tables_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for _prefix, (table_id, source) in sorted(found.items()):
        target = tables_dir / f'{table_id}.bin'
        try:
            same = source.resolve() == target.resolve()
        except OSError:
            same = False
        if not same:
            shutil.copy2(source, target)
        copied.append(target)
    return copied


def extract_unity_bundles(ab_dir: Path, tables_dir: Path):
    if not ab_dir:
        return []
    try:
        import UnityPy
    except ImportError:
        print('[警告] 指定了 --ab-dir，但未安装 UnityPy；先执行 pip install UnityPy。')
        return []
    found = []
    tables_dir.mkdir(parents=True, exist_ok=True)
    for path in ab_dir.rglob('*.bin'):
        try:
            env = UnityPy.load(str(path))
            for obj in env.objects:
                if obj.type.name != 'TextAsset':
                    continue
                asset = obj.read()
                name = str(getattr(asset, 'm_Name', ''))
                if not any(name.startswith(prefix) for prefix in TABLE_PREFIXES):
                    continue
                data = asset.m_Script
                if isinstance(data, str):
                    data = data.encode('utf-8', errors='surrogateescape')
                target = tables_dir / f'{name}.bin'
                target.write_bytes(data)
                found.append(target)
        except Exception as exc:
            print(f'[警告] 无法读取 AB {path.name}: {exc}')
    return found


def newest_table(tables_dir: Path, prefix: str):
    files = list(tables_dir.glob(f'{prefix}*.bin'))
    return max(files, key=lambda path: (path.stat().st_mtime, path.name)) if files else None


def write_names(tables_dir: Path, output: Path):
    handbook = newest_table(tables_dir, 'enemy_handbook_table')
    if not handbook:
        return None, 0
    db = parse_handbook(str(handbook))
    payload = {
        'source': handbook.name,
        'generated_at': _dt.datetime.now().astimezone().isoformat(timespec='seconds'),
        'enemy_count': len(db),
        'enemies': dict(sorted(db.items())),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n',
                      encoding='utf-8')
    return handbook, len(db)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ark-data', type=Path, default=REPO_ROOT / 'Ark_data',
                        help='Il2CppDumper 输出目录（内含 dump.cs）')
    parser.add_argument('--dump', type=Path, help='直接指定 dump.cs，优先于 --ark-data')
    parser.add_argument('--assets', type=Path, action='append', default=[],
                        help='AssetStudio 输出或已提取表目录；可重复指定')
    parser.add_argument('--ab-dir', type=Path,
                        help='原始 anon AB 目录（需要 UnityPy）')
    parser.add_argument('--tables-dir', type=Path, default=REPO_ROOT / 'data' / 'tables')
    parser.add_argument('--offsets-out', type=Path, default=DEFAULT_OFFSETS)
    parser.add_argument('--names-out', type=Path,
                        default=REPO_ROOT / 'data' / 'tables' / 'enemy_names.json')
    parser.add_argument('--check', action='store_true', help='仅校验，不写入文件')
    args = parser.parse_args(argv)

    dump_path = args.dump or args.ark_data / 'dump.cs'
    if not dump_path.is_file():
        parser.error(f'找不到 dump.cs: {dump_path}')
    classes, enums, missing, fatal = build_offsets(dump_path)
    if fatal:
        print('[失败] 新 dump 缺少扫描所需关键字段：')
        for item in fatal:
            print(f'  - {item}')
        return 2
    payload = {
        'schema_version': 1,
        'source': display_source_path(dump_path),
        'source_sha256': sha256_file(dump_path),
        'generated_at': _dt.datetime.now().astimezone().isoformat(timespec='seconds'),
        'classes': classes,
        'enums': enums,
    }
    if not args.check:
        args.offsets_out.parent.mkdir(parents=True, exist_ok=True)
        args.offsets_out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'[偏移] 已解析 {len(classes)} 个结构、{len(enums)} 个枚举'
          f'{"（仅检查）" if args.check else f" -> {args.offsets_out}"}')
    if missing:
        print(f'[警告] {len(missing)} 个非关键映射未找到；可能是字段改名：')
        for item in missing[:30]:
            print(f'  - {item}')
        if len(missing) > 30:
            print(f'  ... 其余 {len(missing) - 30} 项')

    search_paths = list(args.assets)
    default_asset = REPO_ROOT / 'data' / 'anon'
    if default_asset.exists():
        search_paths.append(default_asset)
    # Ark_data 偶尔也会同时放置 AssetStudio 输出；只检查相关命名文件/CAB。
    search_paths.append(args.ark_data)
    copied = [] if args.check else extract_preunpacked(search_paths, args.tables_dir)
    if not args.check and args.ab_dir:
        copied.extend(extract_unity_bundles(args.ab_dir, args.tables_dir))
    if copied:
        print('[数据表] ' + '，'.join(path.name for path in copied))

    handbook = newest_table(args.tables_dir, 'enemy_handbook_table')
    if args.check:
        count = len(parse_handbook(str(handbook))) if handbook else 0
    else:
        handbook, count = write_names(args.tables_dir, args.names_out)
    if handbook:
        print(f'[名称] {handbook.name}: {count} 个敌人'
              f'{"（仅检查）" if args.check else f" -> {args.names_out}"}')
        if handbook.stat().st_mtime + 1 < dump_path.stat().st_mtime:
            print('[警告] 当前 enemy_handbook_table 的修改时间早于新版 dump.cs，'
                  '它很可能仍是旧版本。请从本次游戏 AB 重新解包并通过 --assets 指定输出目录。')
        if count < 100:
            print('[失败] handbook 解析数量异常，未接受该名称库。')
            return 3
    else:
        print('[警告] 未找到新版 enemy_handbook_table；当前关卡仍会从 LevelData '
              '实时读取名称，但打包前请用 --assets 或 --ab-dir 补齐静态名称库。')

    known_flags = {name for _, name, _ in _game_structs.ABNORMAL_FLAG_DEFS}
    dump_flags = set(enums.get('AbnormalFlag', {})) - {'value__', 'E_NUM'}
    unknown = sorted(dump_flags - known_flags)
    if unknown:
        print('[警告] dump 新增了尚无中文映射的异常状态：' + '，'.join(unknown))
    return 0


if __name__ == '__main__':
    sys.exit(main())
