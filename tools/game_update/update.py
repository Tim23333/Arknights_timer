"""Build and validate the current replaceable game_data bundle.

python -m tools.game_update.update --game "E:\\...\\Arknights"
The Android target is explicitly restricted to a local emulator serial.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

from extract_tables import extract_tables
from tools.game_data import REPO_ROOT, sha256_file, validate_bundle
from tools.game_update.metadata import normalize_metadata
from tools.game_update.android_fields import decode_metadata, extract_fields
from tools.enemy_health.update_from_unpack import build_offsets, parse_dump


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def run(command, log: Path, *, env=None):
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('w', encoding='utf-8') as stream:
        result = subprocess.run([str(item) for item in command], cwd=REPO_ROOT,
                                stdout=stream, stderr=subprocess.STDOUT, env=env,
                                creationflags=0x08000000 if os.name == 'nt' else 0)
    if result.returncode:
        raise RuntimeError(f'Command failed ({result.returncode}); see {log}')


def copy_inputs(source: Path, destination: Path, *, prefix=None):
    """Copy only original files: the bundled extractor writes CABs beside input."""
    if not source.is_dir():
        return
    for file in source.rglob('*'):
        if not file.is_file() or any(part.endswith('_unpacked') for part in file.parts):
            continue
        if prefix and not file.name.startswith(prefix):
            continue
        target = destination / file.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, target)


def reset_cache(path: Path, work: Path):
    if not path.resolve().is_relative_to(work.resolve()) or path == work:
        raise ValueError('Cache cleanup path guard failed')
    if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
        raise ValueError('Cache reparse point rejected')
    if path.exists():
        shutil.rmtree(path)


def dump_pc(game: Path, work: Path) -> tuple[Path, dict]:
    tool_dir = work / 'toolchain'
    tool_dir.mkdir(parents=True, exist_ok=True)
    tool = tool_dir / 'Il2CppDumper.exe'
    shutil.copy2(REPO_ROOT / 'Ark_data' / 'Il2CppDumper.exe', tool)
    config = json.loads((REPO_ROOT / 'Ark_data' / 'config.json').read_text(encoding='utf-8'))
    config.update(RequireAnyKey=False, GenerateDummyDll=False, GenerateStruct=False,
                  ForceIl2CppVersion=False)
    write_json(tool_dir / 'config.json', config)
    source = game / 'Arknights_Data/il2cpp_data/Metadata/global-metadata.dat'
    metadata = normalize_metadata(source, work / 'metadata_standard.dat')
    output = work / 'pc_dump'
    output.mkdir(exist_ok=True)
    log = work / 'il2cpp.log'
    env = os.environ.copy()
    env['PATH'] = str(game) + os.pathsep + env.get('PATH', '')
    run([tool, game / 'GameAssembly.dll', metadata['path'], output], log, env=env)
    text = log.read_text(encoding='utf-8', errors='replace')
    if 'Done!' not in text or 'Some errors in dumping' in text or 'An error occurred' in text:
        raise RuntimeError(f'IL2CPP extraction incomplete; see {log}')
    return output / 'dump.cs', metadata


def snapshot_android(work: Path, serial: str) -> tuple[Path, dict]:
    # Never fall back to adb's default target (which may be a connected phone).
    if not (serial.startswith('127.0.0.1:') or serial.startswith('emulator-')):
        raise ValueError('Android extraction requires an explicit local emulator serial')
    from tools.enemy_health.memcore import MemCore, find_mumu_adb
    adb = find_mumu_adb()
    if not adb:
        raise FileNotFoundError('MuMu ADB not found')
    if ':' in serial:
        subprocess.run([adb, 'connect', serial], capture_output=True, check=True)
    def command(*args):
        result = subprocess.run([adb, '-s', serial, *args], capture_output=True, check=True)
        return result.stdout.decode('utf-8', errors='replace').strip()
    version_text = command('shell', 'dumpsys', 'package', 'com.hypergryph.arknights')
    import re
    version = re.search(r'versionName=(\S+)', version_text).group(1)
    version_code = int(re.search(r'versionCode=(\d+)', version_text).group(1))
    remote = command('shell', 'pm', 'path', 'com.hypergryph.arknights').splitlines()[0]
    if not remote.startswith('package:'):
        raise ValueError('Invalid emulator APK path')
    root = work / 'mumu_android'
    root.mkdir(parents=True, exist_ok=True)
    apk = root / 'base.apk'
    apk_state = {'serial': serial, 'version': version, 'version_code': version_code,
                 'package_path': remote.removeprefix('package:')}
    state_file = root / 'apk_source.json'
    saved = json.loads(state_file.read_text(encoding='utf-8')) if state_file.is_file() else None
    if not apk.is_file() or saved != apk_state:
        print(f'Pull emulator APK {version} from {serial}', flush=True)
        run([adb, '-s', serial, 'pull', apk_state['package_path'], apk], root / 'pull.log')
        write_json(state_file, apk_state)
    with zipfile.ZipFile(apk) as archive:
        for name in ('lib/arm64-v8a/libil2cpp.so',
                     'assets/bin/Data/Managed/Metadata/global-metadata.dat'):
            with archive.open(name) as source, (root / Path(name).name).open('wb') as target:
                shutil.copyfileobj(source, target, length=4 * 1024 * 1024)
    transform = decode_metadata(root / 'global-metadata.dat', root / 'metadata_decoded.dat')
    mc = MemCore(adb_path=adb, adb_serial=serial)
    try:
        mc.connect()
        maps = mc.shell(f'cat /proc/{mc.pid}/maps')
        biases = [int(row.split()[0].split('-')[0], 16)
                  for row in maps.splitlines()
                  if row.split()[-1].endswith('/libil2cpp.so')
                  and int(row.split()[2], 16) == 0]
        errors = []
        for bias in reversed(biases):
            try:
                proof = extract_fields(root / 'libil2cpp.so', Path(transform['path']),
                                       root / 'fields.cs', read_memory=mc.read, load_bias=bias)
                _, _, missing, fatal = build_offsets(root / 'fields.cs')
                if fatal:
                    raise ValueError(f'Missing critical fields: {fatal}')
                break
            except Exception as exc:
                errors.append(str(exc))
        else:
            raise RuntimeError(f'No validated live emulator field table: {errors}')
    finally:
        mc.close()
    info = {**apk_state, 'platform': 'android_arm64', 'metadata_transform': transform,
            'field_extraction': proof, 'missing_optional_fields': missing,
            'apk_sha256': sha256_file(apk),
            'binary_sha256': sha256_file(root / 'libil2cpp.so'),
            'metadata_sha256': sha256_file(root / 'global-metadata.dat')}
    return root / 'fields.cs', info


def profile(dump: Path, platform: str, source: dict, *, defaults=None):
    classes, enums, missing, fatal = build_offsets(dump)
    if fatal:
        raise ValueError(f'{platform}: missing critical fields: {fatal}')
    raw, _ = parse_dump(dump)
    inherited = defaults or {}
    complete = {name: dict(values) for name, values in inherited.items()}
    for name, fields in classes.items():
        complete.setdefault(name, {}).update(fields)
    bc = raw.get(('Torappu.Battle', 'BattleController'), {})
    logger = raw.get(('Torappu.Battle', 'BattleLogger'), {})
    runtime = {
        'rng': {'KLASS_NAME': '0x10', 'KLASS_NAMESPAZE': '0x18',
                'KLASS_STATIC_FIELDS': '0xB8', 'BC_STATIC_IMP': hex(bc['s_randomImp']),
                'BC_STATIC_TRIVIAL': hex(bc['s_randomTrivial'])},
        'deploy': {'LOGGER_CONTROLLER': hex(logger['m_controller']),
                   'LOGGER_LOGS': hex(logger['m_logs']), 'LOGGER_SQUAD': hex(logger['m_squad'])},
    }
    return {'schema_version': 1, 'platform': platform,
            'source': f'reference/{platform}/dump.cs', 'source_sha256': sha256_file(dump),
            'generated_at': datetime.now(timezone.utc).isoformat(), 'classes': complete,
            'enums': enums, 'runtime': runtime, 'source_info': source,
            'validation': {'critical_fields_present': True, 'generated_structure_count': len(classes),
                           'missing_optional_fields': missing,
                           'inherited_layouts': sorted(set(complete) - set(classes)),
                           'live_field_table': platform == 'android_arm64'}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', type=Path, default=Path(r'E:\Hypergryph Launcher\games\Arknights'))
    parser.add_argument('--output', type=Path, default=REPO_ROOT / 'game_data')
    parser.add_argument('--work', type=Path, default=REPO_ROOT / '.cache/game_update')
    parser.add_argument('--android-serial', default='127.0.0.1:16384')
    parser.add_argument('--reuse-extracted', action='store_true', help='Reuse this run\'s raw/effect cache for diagnostics')
    args = parser.parse_args(argv)
    game, work, output = args.game.resolve(), args.work.resolve(), args.output.resolve()
    if not work.is_relative_to(REPO_ROOT / '.cache'):
        raise ValueError('Update work directory must stay inside project .cache')
    work.mkdir(parents=True, exist_ok=True)
    if output in (REPO_ROOT, game, work) or output.is_relative_to(work):
        raise ValueError('Invalid bundle output directory')
    if output.exists() and not (output / 'manifest.json').is_file():
        raise ValueError('Refusing to replace a directory without a game_data manifest')
    base = game / 'Arknights_Data/StreamingAssets/AB/Windows'
    hot = game / 'Arknights_Data/PersistentData/Bundles'
    cli = REPO_ROOT / 'AssetStudio-ArknightsStudio/AssetStudioCLI/bin/Release/net8.0/ArknightsStudioCLI.exe'
    for required in (game / 'GameAssembly.dll', cli, base / 'anon'):
        if not required.exists():
            raise FileNotFoundError(required)
    print('[1/7] Extract base and hot tables from cache copies', flush=True)
    if not args.reuse_extracted:
        for name, source in (('base', base), ('hot', hot)):
            if not (source / 'anon').is_dir():
                continue
            target = work / 'inputs' / name / 'anon'
            reset_cache(target, work)
            reset_cache(work / f'raw_{name}', work)
            copy_inputs(source / 'anon', target)
            run([cli, target, '-t', 'textAsset', '-m', 'exportRaw', '-g', 'none',
                 '-o', work / f'raw_{name}', '--log-level', 'warning'], work / f'assets_{name}.log')
    print('[2/7] Extract PC and emulator-specific structure sources', flush=True)
    pc_dump, pc_transform = dump_pc(game, work)
    android_dump, android_source = snapshot_android(work, args.android_serial)
    print('[3/7] Build merged catalogs', flush=True)
    with tempfile.TemporaryDirectory(prefix='stage-', dir=work) as stage_name:
        stage = Path(stage_name)
        catalogs = stage / 'catalogs'
        tables = stage / 'tables'
        sources = extract_tables([work / 'raw_base', work / 'raw_hot'], tables)
        for side in ('character', 'enemy'):
            run([sys.executable, REPO_ROOT / f'ark_parser/{side}/extract_{side}_data.py',
                 '--tables-dir', tables, '--out-dir', catalogs], work / f'parse_{side}.log')
        from tools.deploy_tracker.char_names import build_char_names
        from tools.enemy_health.enemy_db import parse_handbook
        write_json(catalogs / 'char_names.json', build_char_names(str(tables / 'character_table.bin')))
        write_json(catalogs / 'enemy_names.json', parse_handbook(str(tables / 'enemy_handbook_table.bin')))
        print('[4/7] Extract current animation and ability data', flush=True)
        effect_inputs = work / 'effect_inputs'
        if not args.reuse_extracted:
            reset_cache(effect_inputs, work)
            reset_cache(work / 'effect_raw', work)
            for source in (base, hot):
                for name in ('battle', 'chararts', 'charpack', 'refs/arts'):
                    copy_inputs(source / name, effect_inputs / name,
                                prefix='enm_art' if name == 'refs/arts' else None)
            run([cli, effect_inputs, '-t', 'textAsset,monoBehaviour', '-m', 'exportRaw',
                 '-g', 'filename', '-o', work / 'effect_raw', '--log-level', 'warning'],
                work / 'effects_assets.log')
        run([sys.executable, REPO_ROOT / 'ark_parser/extract_effect_frames.py',
             '--assets-root', effect_inputs, '--catalogs-dir', catalogs,
             '--out', catalogs / 'effect_frames.json'], work / 'effect_frames.log')
        effects = json.loads((catalogs / 'effect_frames.json').read_text(encoding='utf-8'))
        for category in ('characters', 'enemies'):
            if not any(row.get('anims') for row in effects.get(category, {}).values()):
                raise ValueError(f'No {category} animation events extracted')
        print('[5/7] Write separate Android and PC profiles', flush=True)
        from tools.enemy_health import game_structs
        from tools.game_data import runtime_offsets
        defaults = {name: {key: hex(value) for key, value in vars(cls).items()
                           if key.isupper() and isinstance(value, int) and value >= 0}
                    for name, cls in vars(game_structs).items() if isinstance(cls, type)}
        for platform, dump, info, baseline in (
                ('pc_x64', pc_dump, {'metadata_transform': pc_transform,
                                    'binary_sha256': sha256_file(game / 'GameAssembly.dll'),
                                    'metadata_sha256': sha256_file(game / 'Arknights_Data/il2cpp_data/Metadata/global-metadata.dat')}, None),
                ('android_arm64', android_dump, android_source, defaults)):
            destination = stage / 'reference' / platform / 'dump.cs'
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dump, destination)
            write_json(stage / 'offsets' / f'{platform}.json', profile(destination, platform, info, defaults=baseline))
        overrides = stage / 'overrides'
        if (output / 'overrides').is_dir():
            shutil.copytree(output / 'overrides', overrides)
        else:
            overrides.mkdir()
            (overrides / 'README.md').write_text(
                '此目录保存手工 JSON 修正，更新时保留。用法见 ../README.md。\n', encoding='utf-8')
        guide = REPO_ROOT / 'docs/game_data.md'
        if guide.is_file():
            shutil.copy2(guide, stage / 'README.md')
        report = {'counts': {}, 'catalog_changes': {}, 'offset_changes': []}
        for name in ('characters', 'skills', 'enemy_database', 'stage_enemy_usage'):
            current = json.loads((catalogs / f'{name}.json').read_text(encoding='utf-8'))
            report['counts'][name] = len(current)
            previous_catalog = output / 'catalogs' / f'{name}.json'
            if previous_catalog.is_file():
                previous_rows = json.loads(previous_catalog.read_text(encoding='utf-8'))
                report['catalog_changes'][name] = {
                    'added': sorted(set(current) - set(previous_rows)),
                    'removed': sorted(set(previous_rows) - set(current))}
        previous_offsets = output / 'offsets' / 'android_arm64.json'
        if previous_offsets.is_file():
            old = json.loads(previous_offsets.read_text(encoding='utf-8'))['classes']
            new = json.loads((stage / 'offsets/android_arm64.json').read_text(encoding='utf-8'))['classes']
            for cls, fields in old.items():
                for field, value in fields.items():
                    replacement = new.get(cls, {}).get(field)
                    if replacement is not None and int(str(value), 0) != int(str(replacement), 0):
                        report['offset_changes'].append({'class': cls, 'field': field,
                                                         'before': value, 'after': replacement})
        report['source_validation'] = {'android_emulator': args.android_serial,
                                       'android_version': android_source['version'],
                                       'live_field_table': True}
        write_json(stage / 'update_report.json', report)
        print('[6/7] Hash and validate bundle', flush=True)
        files = {str(path.relative_to(stage)).replace('\\', '/'): {'sha256': sha256_file(path), 'size': path.stat().st_size}
                 for path in sorted(stage.rglob('*')) if path.is_file() and 'overrides' not in path.relative_to(stage).parts}
        identity = sha256_file(tables / 'hotupdate_meta_table.bin')[:12]
        metadata = {'schema_version': 1, 'data_version': datetime.now().strftime('%Y-%m-%d') + '-' + identity,
                    'generated_at': datetime.now(timezone.utc).isoformat(), 'runtime_platform': 'android_arm64',
                    'android_game_version': android_source['version'], 'emulator_serial': args.android_serial,
                    'pc_game_path': str(game), 'files': files, 'tables': sources,
                    'tools': {'il2cpp_dumper_sha256': sha256_file(REPO_ROOT / 'Ark_data/Il2CppDumper.exe'),
                              'asset_studio_sha256': sha256_file(cli)}}
        for row in metadata['tables'].values():
            row['source_layer'] = 'hot' if 'raw_hot' in row['source'] else 'base'
            row['source'] = f"{row['source_layer']}/{Path(row['source']).name}"
        write_json(stage / 'manifest.json', metadata)
        errors = validate_bundle(stage)
        if errors:
            raise ValueError(errors)
        print('[7/7] Publish validated game_data (preserving overrides)', flush=True)
        previous = work / 'previous_game_data'
        if previous.exists():
            if not previous.resolve().is_relative_to(work):
                raise ValueError('Previous bundle path guard failed')
            shutil.rmtree(previous)
        if output.exists():
            output.replace(previous)
        try:
            stage.replace(output)
        except Exception:
            if output.exists():
                shutil.rmtree(output)
            if previous.exists():
                previous.replace(output)
            raise
    print(f'Updated {output}; data version {metadata["data_version"]}; Android {android_source["version"]}', flush=True)


if __name__ == '__main__':
    main()
