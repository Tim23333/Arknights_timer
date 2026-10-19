"""Opt-in native C protocol checks on an explicitly selected local emulator."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys

import pytest


def test_production_native_protocol_on_local_emulator():
    adb, serial = os.environ.get('AK_NATIVE_ADB'), os.environ.get('AK_NATIVE_SERIAL')
    if not adb or not serial:
        pytest.skip('set AK_NATIVE_ADB and AK_NATIVE_SERIAL for native emulator checks')
    if not serial.startswith(('127.0.0.1:', 'localhost:')):
        pytest.fail('native tests require an explicit local emulator serial')
    folder = Path(__file__).resolve().parent
    cache = folder.parents[1] / '.cache' / 'native_protocol'
    cache.mkdir(parents=True, exist_ok=True)
    tag = hashlib.sha256((folder / 'memsrv.c').read_bytes()
                         + (folder / 'test_native_protocol.c').read_bytes()).hexdigest()[:16]
    binary = cache / ('protocol-' + tag)
    flags = {'creationflags': getattr(subprocess, 'CREATE_NO_WINDOW', 0)}
    if not binary.exists():
        subprocess.run([sys.executable, '-m', 'ziglang', 'cc', '-target', 'aarch64-linux-musl',
            '-static', '-O2', '-I', str(folder), str(folder / 'test_native_protocol.c'),
            '-o', str(binary)], check=True, timeout=120, **flags)
    remote = '/data/local/tmp/ark_timer_native_' + tag
    command = [adb, '-s', serial]
    try:
        subprocess.run(command + ['push', str(binary), remote], check=True,
                       capture_output=True, timeout=20, **flags)
        result = subprocess.run(command + ['shell', 'chmod 700 ' + remote + ' && ' + remote],
                                capture_output=True, text=True, timeout=30, **flags)
        (cache / ('result-' + tag + '.txt')).write_text(result.stdout + result.stderr, encoding='utf-8')
        assert result.returncode == 0, result.stdout + result.stderr
        assert not any(line.startswith('FAIL ') for line in result.stdout.splitlines())
        assert len([line for line in result.stdout.splitlines() if line.startswith('PASS ')]) == 21
    finally:
        subprocess.run(command + ['shell', 'rm -f ' + remote], capture_output=True, timeout=10, **flags)
