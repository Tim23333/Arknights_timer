"""Controlled offline Spine/Animator bindings; never changes installed readers."""
from __future__ import annotations

import argparse
import base64
import hashlib
import inspect
import json
import math
import struct
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "packages/campaign/animation_bindings.reference.json"
TARGETS = ("char_107_liskam", "char_179_cgbird", "char_003_kalts")
VERSION = "3.8.99"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def sha(path):
    return digest(path.read_bytes())


def source_record(path):
    return {"path": path.relative_to(ROOT.parent).as_posix(), "sha256": sha(path), "bytes": path.stat().st_size}


def cab(kind, cid):
    paths = [p for p in (ROOT.parent / "data" / kind / (cid + ".ab_unpacked")).glob("CAB-*") if not p.name.endswith(".resS")]
    if len(paths) != 1:
        raise ValueError(f"exactly one source CAB required: {kind}/{cid}")
    return paths[0]


def local(pointer):
    if not isinstance(pointer, dict) or pointer.get("m_FileID") != 0 or not pointer.get("m_PathID"):
        raise ValueError("required binding reference is absent or external")
    return pointer["m_PathID"]


def unity_payload(raw):
    """Read length-delimited Unity TextAsset, preserving binary Script bytes."""
    if len(raw) < 8:
        raise ValueError("truncated Unity TextAsset")
    name_length = struct.unpack_from("<i", raw)[0]
    if name_length < 0:
        raise ValueError("invalid Unity TextAsset name length")
    offset = (4 + name_length + 3) & ~3
    if offset + 4 > len(raw):
        raise ValueError("truncated Unity TextAsset name")
    length = struct.unpack_from("<i", raw, offset)[0]
    if length < 0 or offset + 4 + length > len(raw):
        raise ValueError("truncated Unity TextAsset Script")
    return raw[offset + 4:offset + 4 + length]


def source_frame(seconds, fps):
    """Snap only when exact float32 re-encoding proves an authored integer frame."""
    nearest = round(seconds * fps)
    snapped = struct.pack(">f", seconds) == struct.pack(">f", nearest / fps)
    return {"source_seconds_float32": seconds, "seconds": nearest / fps if snapped else seconds,
            "frame": nearest if snapped else seconds * fps, "exact_authored_frame": snapped}


def parse_spine(raw):
    from spine_asset.utils import SkeletonBinaryReader
    from spine_asset.v38.SkeletonBinary import SkeletonBinary

    header = SkeletonBinaryReader(raw)
    source_hash, version = header.read_string(), header.read_string()
    if version != VERSION:
        raise ValueError(f"unsupported Spine version {version!r}; reviewed version is {VERSION}")

    class BigEndianReader(SkeletonBinaryReader):
        def read_float32(self):
            value = self._stream.read(4)
            if len(value) != 4:
                raise ValueError("truncated Spine float32")
            result = struct.unpack(">f", value)[0]
            if not math.isfinite(result) or abs(result) > 1e8:
                raise ValueError("Spine float32 outside reviewed finite range")
            return result

    # Clone the trusted parser entry point with private globals, rather than
    # patching either class/module. All nested methods consume this reader.
    original = SkeletonBinary.read_skeleton_data
    private = types.FunctionType(original.__code__, {**original.__globals__, "SkeletonBinaryReader": BigEndianReader},
                                 original.__name__, original.__defaults__, original.__closure__)
    parser = SkeletonBinary()
    parsed = private(parser, raw)
    if parser._reader._stream.tell() != len(raw):
        raise ValueError("Spine reader did not consume the exact payload")
    fps = parsed.fps
    if fps != 30 or parsed.version != VERSION:
        raise ValueError("native Spine author FPS/version is not the reviewed 30FPS profile")
    animations = {}
    for animation in parsed.animations:
        duration = animation.duration
        if not math.isfinite(duration) or not 0 <= duration <= 120:
            raise ValueError(f"invalid animation duration: {animation.name}")
        events = []
        for timeline in animation.timelines:
            if type(timeline).__name__ != "EventTimeline":
                continue
            if len(timeline.frames) != len(timeline.events):
                raise ValueError("Spine event frame/value counts differ")
            for time, event in zip(timeline.frames, timeline.events):
                if not math.isfinite(time) or time < 0 or time > duration + 1e-5:
                    raise ValueError(f"event outside animation duration: {animation.name}")
                events.append({"name": event.data.name, **source_frame(time, fps)})
        animations[animation.name] = {"duration": source_frame(duration, fps),
            "events": sorted(events, key=lambda e: (e["seconds"], e["name"]))}
    return {"version": version, "spine_hash": source_hash, "author_fps": fps, "animations": animations}


def library_identity():
    import spine_asset
    from spine_asset.utils import SkeletonBinaryReader
    from spine_asset.v38.SkeletonBinary import SkeletonBinary
    directory = Path(spine_asset.__file__).parent
    files = {str(p.relative_to(directory)).replace("\\", "/"): sha(p) for p in sorted(directory.rglob("*.py"))}
    return {"package": "spine_asset", "installed_sources": files,
            "original_float_reader_source_sha256": digest(inspect.getsource(SkeletonBinaryReader.read_float32).encode()),
            "parser_entry_source_sha256": digest(inspect.getsource(SkeletonBinary.read_skeleton_data).encode()),
            "controlled_extractor_sha256": sha(Path(__file__)),
            "strategy": "private FunctionType globals with reader subclass; no module/class/site-packages mutation",
            "float32": "big-endian", "spine_versions": [VERSION], "author_fps": 30,
            "limits": {"absolute_float": 1e8, "animation_seconds": 120}}


def index_cab(path):
    import UnityPy
    objects = {o.path_id: o for o in UnityPy.load(str(path)).objects}
    monos = {key: o.read_typetree() for key, o in objects.items() if o.type.name == "MonoBehaviour"}
    return objects, monos


def fields(tree):
    return {k: v for k, v in tree.items() if not k.startswith("m_")}


def component(tree):
    return {"script_path_id": tree.get("m_Script", {}).get("m_PathID"), "fields": fields(tree)}


def resolve_animation(key, mapping, skeleton):
    rows = [r for r in mapping if r["animKey"] == key]
    if len(rows) != 1:
        raise ValueError(f"animation binding key is absent or ambiguous: {key}")
    row = rows[0]
    if not math.isfinite(row["speed"]) or row["speed"] <= 0:
        raise ValueError("animation mapping speed must be positive finite")
    if row["animName"] not in skeleton["animations"]:
        raise ValueError(f"mapped animation is missing: {key}->{row['animName']}")
    return {"key": key, "animation_name": row["animName"], "mapping": row,
            **skeleton["animations"][row["animName"]], "status": "native_binding_resolved"}


def character_bindings(cid, asset_store):
    pack_path, art_path = cab("charpack", cid), cab("chararts", cid)
    _, pack = index_cab(pack_path)
    objects, art = index_cab(art_path)
    roots = [(key, value) for key, value in pack.items() if "_modes" in value]
    animators = [(key, value) for key, value in art.items() if "_animations" in value]
    if len(roots) != 1 or len(animators) != 1:
        raise ValueError("character mode root or serialized Animator mapping is ambiguous")
    root_id, root = roots[0]
    animator_id, animator = animators[0]
    face_sources, evidence = {}, {str(animator_id): component(animator)}
    for face in ("front", "back"):
        renderer_id = local(animator["_" + face]["skeleton"])
        data_id = local(art[renderer_id]["skeletonDataAsset"])
        text_id = local(art[data_id]["skeletonJSON"])
        obj = objects[text_id]
        if obj.type.name != "TextAsset":
            raise ValueError("SkeletonDataAsset does not resolve to a TextAsset")
        wrapper = obj.get_raw_data()
        raw = unity_payload(wrapper)
        raw_hash = digest(raw)
        parsed = parse_spine(raw)
        asset_store[raw_hash] = {"payload_base64": base64.b64encode(raw).decode(), "bytes": len(raw),
            "payload_sha256": raw_hash, "textasset_raw_sha256": digest(wrapper), "parsed": parsed}
        face_sources[face] = {"renderer_path_id": renderer_id, "skeleton_data_path_id": data_id,
            "textasset_path_id": text_id, "native_asset_name": obj.read().m_Name, "payload_sha256": raw_hash}
        evidence[str(renderer_id)] = component(art[renderer_id])
        evidence[str(data_id)] = component(art[data_id])
    modes = []
    pack_evidence = {str(root_id): component(root)}
    for mode_index, pointer in enumerate(root["_modes"]):
        mode_id = local(pointer)
        mode = pack[mode_id]
        attack_id = local(mode["_attack"])
        attack = pack[attack_id]
        pack_evidence[str(mode_id)] = component(mode)
        pack_evidence[str(attack_id)] = component(attack)
        key = attack.get("_animKey", "")
        phase_source = None
        if not key:
            same_gameobject = [(pid, t) for pid, t in pack.items() if t.get("m_GameObject") == attack.get("m_GameObject") and t.get("_oneshotAnim")]
            if len(same_gameobject) == 1:
                phase_id, phase = same_gameobject[0]
                key = phase["_oneshotAnim"]
                phase_source = {"path_id": phase_id, "fields": fields(phase)}
                pack_evidence[str(phase_id)] = component(phase)
        entry = {"index": mode_index, "mode_path_id": mode_id, "attack_path_id": attack_id,
            "ability_animation_key": attack.get("_animKey", ""), "resolved_animation_key": key,
            "three_part_animation_source": phase_source, "bindings_by_face": {}, "pending": []}
        if not key:
            entry["pending"].append("no_native_animation_or_three_part_oneshot_key")
        else:
            for face, face_source in face_sources.items():
                parsed = asset_store[face_source["payload_sha256"]]["parsed"]
                entry["bindings_by_face"][face] = resolve_animation(key, animator["_animations"], parsed)
                if phase_source and phase_source["fields"]["_beginAnim"]:
                    entry["bindings_by_face"][face]["begin_animation"] = resolve_animation(phase_source["fields"]["_beginAnim"], animator["_animations"], parsed)
            if phase_source:
                entry["pending"].append("three_part_begin_and_loop_native_coroutine_playback_handoff_not_converted")
        entry["projectile_key"] = attack.get("_projectileKey")
        modes.append(entry)
    return {"character_id": cid, "status": "source_bindings_resolved_not_model_validated", "runnable": False,
            "charpack_source": source_record(pack_path), "chararts_source": source_record(art_path),
            "animator_path_id": animator_id, "serialized_animator_components": evidence,
            "serialized_charpack_components": pack_evidence, "face_sources": face_sources, "modes": modes,
            "pending": ["client_playback_scaling_and_state_handoff", "source_version_correspondence"]}


def kalts_projectile():
    paths = [p for p in (ROOT.parent / "data/battle/prefabs").glob("*projectiles.ab_unpacked/CAB-*") if not p.name.endswith(".resS")]
    if len(paths) != 1:
        raise ValueError("native projectile CAB is ambiguous")
    objects, monos = index_cab(paths[0])
    names = {key: o.read().m_Name for key, o in objects.items() if o.type.name == "GameObject"}
    rows = {str(key): {"gameobject_path_id": t["m_GameObject"]["m_PathID"],
        "script_path_id": t["m_Script"]["m_PathID"], "fields": fields(t)} for key, t in monos.items()
        if names.get(t["m_GameObject"]["m_PathID"]) == "projectile_chr_kalts"}
    movers = [(key, r["fields"]) for key, r in rows.items() if "_speed" in r["fields"]]
    if len(movers) != 1 or movers[0][1]["_speed"] <= 0:
        raise ValueError("exact native Kaltsit projectile movement is ambiguous or missing")
    return {"key": "projectile_chr_kalts", "status": "native_movement_parameters_resolved", "source": source_record(paths[0]),
            "components": rows, "movement_path_id": movers[0][0], "speed": movers[0][1]["_speed"],
            "instant_or_visual_only_proven": False,
            "pending": ["RangedHeal_GetProjectileActions_hit_or_reached_native_callback_order",
                        "native_paracurve_homing_and_exact_travel_formula_not_converted"]}


def native_declarations():
    """Keep declaration evidence distinct from unavailable native method bodies."""
    path = ROOT.parent / "Ark_data/Il2CppDumper_current/dump.cs"
    headers = {"public class RangedHeal : Heal", "public class ParacurveMovement : BasicMovement",
               "public class ThreePartOneshotAnimation : AbilityStandard.Behaviour"}
    blocks, active, depth, opened = {}, None, 0, False
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            stripped = line.strip()
            if active is None:
                header = next((key for key in headers if stripped.startswith(key + " //")), None)
                if header:
                    active, depth, opened = header, 0, False
                    blocks[header] = {"line": number, "declaration": ""}
            if active is not None:
                blocks[active]["declaration"] += line
                depth += line.count("{") - line.count("}")
                opened = opened or "{" in line
                if opened and depth == 0:
                    active = None
                    if len(blocks) == len(headers):
                        break
    if len(blocks) != len(headers):
        raise ValueError("native type declaration evidence incomplete")
    return {"source": source_record(path), "classes": blocks,
            "certainty": "serialized field layout corroboration; dump methods are stubs, not executable logic proof"}


def build():
    before = library_identity()
    assets = {}
    operators = {cid: character_bindings(cid, assets) for cid in TARGETS}
    after = library_identity()
    if before != after:
        raise ValueError("installed Spine reader source changed during offline extraction")
    return {"schema": "ark-sim/campaign-animation-bindings/v1", "status": "offline_source_bindings_only",
            "runnable": False, "conversion_approved": False, "reader_identity": before, "skeleton_assets": assets,
            "operators": operators, "projectiles": {"projectile_chr_kalts": kalts_projectile()}, "native_declaration_evidence": native_declarations(),
            "rounding_policy": "retain raw float32; snap integer authored frames only after exact float32 re-encoding equality"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    value = build()
    if args.check:
        if json.loads(args.output.read_bytes()) != value:
            raise ValueError("animation source, reader implementation or binding identity changed")
    else:
        args.output.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"operators": len(value["operators"]), "skeletons": len(value["skeleton_assets"]), "runnable": False}))


if __name__ == "__main__":
    main()
