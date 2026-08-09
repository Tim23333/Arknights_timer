#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract projectile speeds from [uc]projectiles AB into a JSON table.

Source: data/battle/prefabs/[uc]projectiles.ab_unpacked/CAB-* (or the game's
StreamingAssets copy). Each projectile GameObject has a movement component
with `_speed` (grids/second); the table is keyed by GameObject name.

Output: ark_emulator/ark_emulator/data_projectile_speeds.json
"""
import glob
import io as _io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import UnityPy

DEFAULT_CABS = [
    r"G:\Arknights\data\battle\prefabs\[uc]projectiles.ab_unpacked",
    r"G:\Arknights\unpack_work\proj_scan\[uc]projectiles.ab_unpacked",
    r"G:\Arknights\unpack_work\prefabs_scan\[uc]projectiles.ab_unpacked",
]


def main():
    cabs = []
    for d in DEFAULT_CABS:
        if os.path.isdir(d):
            cabs += [os.path.join(d, f) for f in os.listdir(d)
                     if f.startswith("CAB-")]
    if not cabs:
        print("no projectile CAB found")
        return 1
    out = {}
    for cab in cabs:
        if cab.endswith(".resS"):
            continue
        env = UnityPy.load(cab)
        names = {}
        monos = []
        for obj in env.objects:
            if obj.type.name == "GameObject":
                try:
                    names[obj.path_id] = obj.read().m_Name
                except Exception:
                    names[obj.path_id] = "?"
            elif obj.type.name == "MonoBehaviour":
                try:
                    tt = obj.read_typetree()
                except Exception:
                    continue
                go = tt.get("m_GameObject", {}).get("m_PathID")
                if "_speed" in tt:
                    monos.append((go, tt.get("_speed")))
        for go, speed in monos:
            nm = names.get(go)
            if not nm or nm == "?":
                continue
            try:
                sp = float(speed)
            except (TypeError, ValueError):
                continue
            if sp > 0:
                out[nm] = sp
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "data_projectile_speeds.json")
    with _io.open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"projectile speeds: {len(out)} keys -> {path}")
    for probe in ("projectile_sword_rain", "projectile_faust_s1",
                  "projectile_shot_1024", "projectile_magic_blast_1"):
        print(" ", probe, "->", out.get(probe))
    return 0


if __name__ == "__main__":
    sys.exit(main())
