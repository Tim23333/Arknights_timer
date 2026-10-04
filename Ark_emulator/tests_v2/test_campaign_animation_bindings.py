"""Independent byte-order, explicit mapping, provenance and failure checks."""
import base64
from copy import deepcopy
import json
import struct

import pytest

from spine_asset.utils import SkeletonBinaryReader
from spine_asset.v38.SkeletonBinary import SkeletonBinary
from tools.extract_campaign_animation_bindings import (OUTPUT, ROOT, build, digest, library_identity,
    parse_spine, resolve_animation, source_frame, unity_payload)


@pytest.fixture(scope="module")
def reference():
    return json.loads(OUTPUT.read_bytes())


def test_frozen_result_matches_current_bytes_and_reader_identity(reference):
    assert build() == reference
    assert reference["runnable"] is reference["conversion_approved"] is False
    assert reference["reader_identity"]["spine_versions"] == ["3.8.99"]


def test_raw_asset_bytes_reparse_and_match_full_payload_hash(reference):
    for key, asset in reference["skeleton_assets"].items():
        raw = base64.b64decode(asset["payload_base64"], validate=True)
        assert len(raw) == asset["bytes"]
        assert digest(raw) == key == asset["payload_sha256"]
        assert parse_spine(raw) == asset["parsed"]


def test_controlled_parse_never_patches_original_reader_or_installed_files(reference):
    original = SkeletonBinaryReader.read_float32
    before = library_identity()
    for asset in reference["skeleton_assets"].values():
        parse_spine(base64.b64decode(asset["payload_base64"]))
    assert SkeletonBinaryReader.read_float32 is original
    assert library_identity() == before
    assert SkeletonBinaryReader(struct.pack(">f", .2)).read_float32() == pytest.approx(-428443584)


@pytest.mark.parametrize("face", ["front", "back"])
def test_liskarm_explicit_oneshot_alias_and_begin_chain(face, reference):
    row = reference["operators"]["char_107_liskam"]
    mode = row["modes"][0]
    assert mode["ability_animation_key"] == ""
    assert mode["three_part_animation_source"]["fields"]["_oneshotAnim"] == "Attack"
    assert mode["three_part_animation_source"]["fields"]["_onlyPlayBeginAnimWhenFirstAttack"] == 1
    binding = mode["bindings_by_face"][face]
    assert binding["mapping"]["animKey"] == "Attack" and binding["mapping"]["animName"] == "Attack_Loop"
    assert [(e["name"], e["frame"], e["seconds"]) for e in binding["events"]] == [("OnAttack", 1, 1/30)]
    assert binding["begin_animation"]["duration"]["frame"] == 10
    assert row["face_sources"][face]["native_asset_name"] == "char_107_liskarm.skel"


@pytest.mark.parametrize("index,key", [(0, "Attack_A"), (1, "Attack_C")])
def test_nightingale_mode_alias_is_explicit_and_has_frame_twenty_seven(reference, index, key):
    row = reference["operators"]["char_179_cgbird"]
    mode = row["modes"][index]
    assert mode["ability_animation_key"] == key
    for face in ("front", "back"):
        binding = mode["bindings_by_face"][face]
        assert binding["mapping"]["animKey"] == key
        assert binding["mapping"]["animName"] == "Attack"
        assert [(e["name"], e["frame"], e["seconds"]) for e in binding["events"]] == [("OnAttack", 27, .9)]


def test_animator_renderer_data_textasset_chain_has_exact_local_references(reference):
    for row in reference["operators"].values():
        animator = row["serialized_animator_components"][str(row["animator_path_id"])]["fields"]
        for face, source in row["face_sources"].items():
            assert animator["_"+face]["skeleton"] == {"m_FileID": 0, "m_PathID": source["renderer_path_id"]}
            renderer = row["serialized_animator_components"][str(source["renderer_path_id"])]["fields"]
            data = row["serialized_animator_components"][str(source["skeleton_data_path_id"])]["fields"]
            assert renderer["skeletonDataAsset"]["m_PathID"] == source["skeleton_data_path_id"]
            assert data["skeletonJSON"]["m_PathID"] == source["textasset_path_id"]
            assert source["payload_sha256"] in reference["skeleton_assets"]


def test_mapping_does_not_fallback_to_similarly_named_attack(reference):
    asset = next(iter(reference["skeleton_assets"].values()))["parsed"]
    with pytest.raises(ValueError, match="absent or ambiguous"):
        resolve_animation("Attack_C", [{"animKey": "Attack_A", "animName": "Attack", "speed": 1}], asset)
    with pytest.raises(ValueError, match="mapped animation is missing"):
        resolve_animation("Attack_C", [{"animKey": "Attack_C", "animName": "missing", "speed": 1}], asset)


def test_frame_snap_uses_float32_equality_not_nearest_frame_guess():
    native = struct.unpack(">f", struct.pack(">f", 1/30))[0]
    assert source_frame(native, 30)["exact_authored_frame"] is True
    assert source_frame(native, 30)["seconds"] == 1/30
    assert source_frame(.05, 30)["exact_authored_frame"] is False
    assert source_frame(.05, 30)["seconds"] == .05


def test_unreviewed_version_and_trailing_payload_are_rejected(reference):
    raw = base64.b64decode(next(iter(reference["skeleton_assets"].values()))["payload_base64"])
    with pytest.raises(ValueError, match="unsupported Spine version"):
        parse_spine(raw.replace(b"3.8.99", b"4.1.00", 1))
    with pytest.raises(ValueError, match="exact payload"):
        parse_spine(raw+b"\x00")


@pytest.mark.parametrize("raw", [b"", struct.pack("<i", -1)+b"0000", struct.pack("<i", 1)+b"x\x00\x00\x00"+struct.pack("<i", 100)])
def test_corrupt_unity_textasset_cannot_silently_yield_a_skeleton(raw):
    with pytest.raises(ValueError):
        unity_payload(raw)


def test_kaltsit_has_exact_key_speed_five_and_is_not_claimed_instant(reference):
    projectile = reference["projectiles"]["projectile_chr_kalts"]
    assert projectile["key"] == "projectile_chr_kalts" and projectile["speed"] == 5
    mover = projectile["components"][projectile["movement_path_id"]]["fields"]
    assert mover["_onlyReachedInTime"] == 0
    assert mover["_delayTime"] == 0
    assert mover["_raiseHeight"] == pytest.approx(.3)
    assert projectile["instant_or_visual_only_proven"] is False
    assert projectile["pending"]
    assert reference["operators"]["char_003_kalts"]["modes"][0]["projectile_key"] == projectile["key"]


def test_legacy_frame_table_identity_is_not_written_by_extractor(reference):
    path = ROOT.parent / "data/tables/effect_frames.json"
    before = digest(path.read_bytes())
    build()
    assert digest(path.read_bytes()) == before
