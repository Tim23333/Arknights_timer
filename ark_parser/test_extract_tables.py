"""Tests for exact exportRaw table-name extraction."""

import struct

from extract_tables import scan_cab_file


def _write_export_raw(path, table_id, signature_prefix=b"8"):
    name = table_id.encode("ascii")
    path.write_bytes(struct.pack("<I", len(name)) + name + signature_prefix + b"\0" * 256)


def test_signature_hex_byte_is_not_appended_to_table_id(tmp_path):
    path = tmp_path / "activity_table.dat"
    _write_export_raw(path, "activity_table721b1b", b"8")
    assert scan_cab_file(path) == "activity_table721b1b"


def test_exact_name_supports_non_hex_signature_prefix(tmp_path):
    path = tmp_path / "enemy_database.dat"
    _write_export_raw(path, "enemy_databasea5b667", b"\xcb")
    assert scan_cab_file(path) == "enemy_databasea5b667"
