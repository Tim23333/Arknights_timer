"""Offline recovery of named LevelData .dat assets; no simulator imports.

Calibrated core: map, routes/checkpoints, waves, predefines. Other root fields
retain the existing research parser's output and are explicitly unverified.
Never uses a reference JSON to populate decoded data.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
PARSER_DIR = ROOT.parent / "ark_parser/enemy"
CORE_FIELDS = ("mapData", "routes", "extraRoutes", "waves", "predefines", "hardPredefines")
REFERENCE_COMMIT = "56aee3d6c5a29c3a0d192456d70d14252cbb0804"


class RecoveryError(ValueError):
    pass


def parser_module():
    if not (PARSER_DIR / "extract_level_data.py").is_file():
        raise FileNotFoundError(f"Offline FB helper missing: {PARSER_DIR}")
    path = str(PARSER_DIR)
    if path not in sys.path:
        sys.path.insert(0, path)
    return importlib.import_module("extract_level_data")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def local_path(path):
    return Path(os.path.relpath(Path(path).resolve(), ROOT)).as_posix()


def payload(data: bytes, expected_name: str):
    if len(data) < 160:
        raise RecoveryError("Truncated named LevelData asset")
    size = struct.unpack_from("<I", data)[0]
    if not 1 <= size <= 512 or size + 4 > len(data):
        raise RecoveryError("Invalid TextAsset name length")
    try:
        name = data[4:4+size].decode("ascii")
    except UnicodeDecodeError as exc:
        raise RecoveryError("Non-ASCII LevelData asset name") from exc
    if name != expected_name:
        raise RecoveryError(f"Asset name mismatch: {name!r} != {expected_name!r}")
    # The named export adds a 132-byte sign/version envelope after alignment.
    offset = ((4 + size + 3) & ~3) + 132
    if offset + 16 >= len(data):
        raise RecoveryError("Truncated FlatBuffers payload")
    return name, offset, data[offset:]


class Decoder:
    def __init__(self, fb, helper):
        self.fb, self.e = fb, helper
        self.issues = []

    def fields(self, pos, allowed=None, scope="table"):
        result = self.fb.table_fields(pos)
        if allowed is not None:
            extra = [i for i, p in enumerate(result) if p is not None and i > allowed]
            if extra:
                self.issues.append(f"{scope}: unsupported present field indices {extra}")
        return result

    @staticmethod
    def field(fields, i):
        return fields[i] if i < len(fields) else None

    def integer(self, fields, i, default=0):
        p = self.field(fields, i)
        return self.fb.i32(p) if p is not None else default

    def floating(self, fields, i):
        p = self.field(fields, i)
        value = self.fb.f32(p) if p is not None else 0.0
        if not math.isfinite(value):
            raise RecoveryError("Non-finite float in LevelData")
        return round(value, 6)

    def boolean(self, fields, i):
        p = self.field(fields, i)
        if p is None:
            return False
        b = self.fb.d[p]
        if b not in (0, 1):
            raise RecoveryError(f"Invalid byte bool {b} at {p}")
        return bool(b)

    def string(self, fields, i):
        p = self.field(fields, i)
        if p is None:
            return None
        t = self.fb.target_of(p)
        # Empty strings are legal (helper is_string excludes length zero).
        n = self.fb.u32(t)
        if n > 65536 or t + 4 + n >= self.fb.size or self.fb.d[t+4+n] != 0:
            raise RecoveryError("Invalid string offset/length")
        return self.fb.d[t+4:t+4+n].decode("utf8")

    def target(self, fields, i):
        p = self.field(fields, i)
        return self.fb.target_of(p) if p is not None else None

    def enum(self, fields, i, names):
        value = self.integer(fields, i)
        if value not in names:
            raise RecoveryError(f"Unsupported enum value {value}")
        return names[value]

    def point(self, pos, float_point=False):
        if pos is None:
            raise RecoveryError("Missing encoded coordinate table; refusing to fabricate position")
        f = self.fields(pos, 1, "coordinate")
        read = self.floating if float_point else self.integer
        return dict(zip(("x", "y") if float_point else ("row", "col"), (read(f, 0), read(f, 1))))

    def vector_tables(self, pos, parse):
        if pos is None:
            return None
        n = self.fb.u32(pos)
        if n > 100000 or pos + 4 + n * 4 > self.fb.size:
            raise RecoveryError("Vector exceeds payload bounds")
        result = []
        for i in range(n):
            slot = pos + 4 + i * 4
            # Null entries must retain indices instead of shifting routes.
            result.append(None if self.fb.i32(slot) == 0 else parse(self.fb.target_of(slot)))
        return result

    def checkpoint(self, pos):
        f = self.fields(pos, 5, "checkpoint")
        return {"type": self.enum(f, 0, self.e.CHECKPOINT_TYPE), "time": self.floating(f, 1),
                "position": self.point(self.target(f, 2)),
                "reachOffset": self.point(self.target(f, 3), True),
                "randomizeReachOffset": self.boolean(f, 4), "reachDistance": self.floating(f, 5)}

    def blackboard(self,pos):
        def pair(p):
            f=self.fields(p,2,'blackboard DataPair')
            key=self.string(f,0)
            if not key:
                raise RecoveryError('Blackboard key missing')
            return {'key':key,'value':self.floating(f,1),'valueStr':self.string(f,2)}
        return self.vector_tables(pos,pair)

    def tile(self,pos):
        # These native LevelData exports use the legacy TileData serializer:
        # field5=blackboard, field6=effects. Current dump.cs adds an advanced
        # mask before them; applying that newer schema corrupts old assets.
        f=self.fields(pos,6,'legacy TileData')
        mappings = {1:('heightType',{0:'LOWLAND',1:'HIGHLAND'}),
                    2:('buildableType',{0:'NONE',1:'MELEE',2:'RANGED',3:'ALL'}),
                    3:('passableMask',{0:'NONE',1:'WALK_ONLY',2:'FLY_ONLY',3:'ALL'}),
                    4:('playerSideMask',{0:'ALL',2:'SIDE_A',4:'SIDE_B',255:'NONE'})}
        out={'tileKey':self.string(f,0),'blackboard':self.blackboard(self.target(f,5)),'effects':None}
        for i,(nm,names) in mappings.items():
            out[nm]=self.enum(f,i,names)
        if self.target(f,6) is not None:
            self.issues.append('legacy TileData: present uncalibrated effects')
            out['effects']={'_unparsed_offset':self.target(f,6)}
        return out

    def route(self, pos):
        f = self.fields(pos, 9, "route")
        out = {"motionMode": self.enum(f, 0, self.e.MOTION_MODE),
               "startPosition": self.point(self.target(f, 1)), "endPosition": self.point(self.target(f, 2)),
               "spawnRandomRange": self.point(self.target(f, 3), True),
               "spawnOffset": self.point(self.target(f, 4), True),
               "checkpoints": self.vector_tables(self.target(f, 5), self.checkpoint)}
        out.update({nm: self.boolean(f, i) for i, nm in enumerate(
            ("allowDiagonalMove", "visitEveryTileCenter", "visitEveryNodeCenter", "visitEveryCheckPoint"), 6)})
        return out

    def action(self, pos):
        f = self.fields(pos, 21, "action")
        out = self.e.parse_action(self.fb, pos)
        for name in ("actionType", "randomType", "refreshType"):
            item = out[name]
            if item["name"] == "?":
                raise RecoveryError(f"Unsupported {name} {item}")
            out[name] = item["name"]
        for i, nm in ((3, "count"), (6, "routeIndex"), (16, "weight")):
            out[nm] = self.integer(f, i)
        for i, nm in ((4, "preDelay"), (5, "interval")):
            out[nm] = self.floating(f, i)
        for i, nm in ((1, "managedByScheduler"), (7, "blockFragment"), (8, "autoPreviewRoute"),
                      (9, "autoDisplayEnemyInfo"), (10, "isUnharmfulAndAlwaysCountAsKilled"),
                      (17, "dontBlockWave"), (18, "forceBlockWaveInBranch"), (20, "notCountInTotal")):
            out[nm] = self.boolean(f, i)
        if self.field(f, 19) is not None:
            self.issues.append("action: present uncalibrated field19")
        if self.field(f, 21) is not None:
            self.issues.append("action: present uncalibrated extraMeta")
        return out

    def fragment(self, pos):
        f = self.fields(pos, 1, "fragment")
        return {"preDelay": self.floating(f, 0), "actions": self.vector_tables(self.target(f, 1), self.action)}

    def wave(self, pos):
        f = self.fields(pos, 4, "wave")
        return {"preDelay": self.floating(f, 0), "postDelay": self.floating(f, 1),
                "maxTimeWaitingForNextWave": self.floating(f, 2),
                "fragments": self.vector_tables(self.target(f, 3), self.fragment),
                "advancedWaveTag": self.string(f, 4)}

    def predefined(self, pos, placed=False, token_card=False):
        f = self.fields(pos, 13 if placed else 12 if token_card else 11, "predefined")
        # Custom serializer writes derived fields before inherited fields:
        # placed: position/direction; token card: initialCnt; plain card: none.
        off = 2 if placed else 1 if token_card else 0
        out = {"hidden": self.boolean(f, off), "alias": self.string(f, off+1),
               "showSpIllust": self.boolean(f, off+3)}
        for i, nm in ((2, "uniEquipIds"), (4, "masterInfos"), (10, "overrideSkillBlackboard"), (11, "overrideTalents")):
            p = self.target(f, off+i)
            out[nm] = None
            if p is not None:
                if nm=='overrideSkillBlackboard':
                    out[nm]=self.blackboard(p)
                else:
                    self.issues.append(f"predefined: present uncalibrated {nm}")
                    out[nm] = {"_unparsed_offset": p}
        inst_pos = self.target(f, off+5)
        if inst_pos is None:
            raise RecoveryError("Predefined metadata missing")
        meta = self.fields(inst_pos, 4, "predefined metadata")
        out["inst"] = {"characterKey": self.string(meta, 0), "level": self.integer(meta, 1),
                       "phase": self.enum(meta, 2, {0:"PHASE_0", 1:"PHASE_1", 2:"PHASE_2"}),
                       "favorPoint": self.integer(meta, 3), "potentialRank": self.integer(meta, 4)}
        if not out['inst']['characterKey']:
            raise RecoveryError('Predefined characterKey missing')
        out.update({"skillIndex": self.integer(f, off+6), "mainSkillLvl": self.integer(f, off+7),
                    "skinId": self.string(f, off+8), "tmplId": self.string(f, off+9)})
        if placed:
            out.update({"position": self.point(self.target(f, 0)),
                        "direction": self.enum(f, 1, {0:"UP", 1:"RIGHT", 2:"DOWN", 3:"LEFT"})})
        if token_card:
            out["initialCnt"] = self.integer(f, 0)
        return out

    def predefines(self, pos):
        if pos is None:
            return None
        f = self.fields(pos, 3, "predefines")
        return {nm: self.vector_tables(self.target(f, i),
                    lambda p, i=i: self.predefined(p, placed=i<2, token_card=i==3)) or []
                for i, nm in enumerate(("characterInsts", "tokenInsts", "characterCards", "tokenCards"))}

    def map_data(self, pos):
        if pos is None:
            raise RecoveryError("LevelData map missing")
        f = self.fields(pos, 5, "mapData")
        result = self.e.parse_map_data(self.fb, pos)
        mp = self.target(f, 0)
        if mp is None:
            raise RecoveryError("Map grid table missing")
        mf = self.fields(mp, 2, "map grid")
        rows, cols = self.integer(mf,0), self.integer(mf,1)
        vp = self.target(mf,2)
        if rows<=0 or cols<=0 or vp is None:
            raise RecoveryError("Map dimensions or cell vector missing")
        n = self.fb.u32(vp)
        # Grid cells are u16, unlike table vectors whose slots are u32.
        if vp+4+n*2>self.fb.size:
            raise RecoveryError("Map u16 cells exceed payload bounds")
        cells = [self.fb.u16(vp+4+i*2) for i in range(n)]
        grid = {"rows":rows,"cols":cols}
        if len(cells) != grid["rows"] * grid["cols"]:
            raise RecoveryError("Map dimensions do not match cell count")
        result["map"] = [cells[i:i+grid["cols"]] for i in range(0, len(cells), grid["cols"])]
        result['tiles']=self.vector_tables(self.target(f,1),self.tile)
        if result['tiles'] is None or any(t is None for t in result['tiles']):
            raise RecoveryError('Map tile definitions missing')
        result['tileCount']=len(result['tiles'])
        tags=self.target(f,3)
        if tags is not None:
            n=self.fb.u32(tags)
            if n>100000 or tags+4+n*4>self.fb.size:
                raise RecoveryError('Map tags exceed payload bounds')
            result['tags']=[self.string([tags+4+i*4],0) for i in range(n)]
        for i, nm in ((2, "blockEdges"), (3, "tags"), (4, "effects"), (5, "layerRects")):
            result.setdefault(nm, None)
            if self.target(f, i) is not None and i in (2, 4, 5):
                self.issues.append(f"mapData: present partially calibrated {nm}")
        return result


def compare_core(decoded, reference):
    """Compare all reference core fields; ignore known extractor metadata only."""
    differences = []
    extras = {"tileCount", "advancedBuildableMask", "notCountInTotal"}
    def walk(a, b, path):
        if not a and not b and isinstance(a, (list,dict,type(None))) and isinstance(b, (list,dict,type(None))):
            return
        if isinstance(b, dict) and isinstance(a, dict):
            for k in b:
                if k not in a:
                    differences.append({"path": path+"."+k, "issue":"missing_decoded_field"})
                else:
                    walk(a[k], b[k], path+"."+k)
            for k in a.keys()-b.keys()-extras:
                if a[k] is not None:
                    differences.append({"path": path+"."+k, "issue":"extra_decoded_field"})
        elif isinstance(b, list) and isinstance(a,list):
            if len(a)!=len(b):
                differences.append({"path":path,"issue":"length_mismatch","decoded":len(a),"reference":len(b)})
            for i,(x,y) in enumerate(zip(a,b)):
                walk(x,y,f"{path}[{i}]")
        elif isinstance(a,(int,float)) and isinstance(b,(int,float)) and not isinstance(a,bool) and not isinstance(b,bool):
            if not math.isclose(a,b,abs_tol=1e-5):
                differences.append({"path":path,"decoded":a,"reference":b})
        elif a != b:
            differences.append({"path":path,"decoded":a,"reference":b})
    for key in CORE_FIELDS:
        walk(decoded.get(key), reference.get(key), key)
    return differences


def canonical_core(decoded):
    """Semantic serialization for exact comparisons after documented defaults.

    Empty arrays/dicts/null collections are equivalent exports. Research-only
    tile counts and absent newer-schema fields are not native core content.
    No coordinates, enums, non-default values or list entries are removed.
    """
    def canonical(value):
        if isinstance(value,dict):
            out={}
            for k,v in value.items():
                if k=='tileCount' or v is None or (k=='notCountInTotal' and v is False):
                    continue
                out[k]=canonical(v)
            return out or None
        if isinstance(value,list):
            return [canonical(v) for v in value] or None
        return value
    return {k:canonical(decoded.get(k)) for k in CORE_FIELDS}


def extract(path: Path, reference_path: Path | None = None):
    e = parser_module()
    name, offset, data = payload(path.read_bytes(), path.stem)
    fb = e.LevelFB(data, str(path))
    try:
        decoder = Decoder(fb,e)
        f = decoder.fields(fb.root, 21, "LevelData")
        result = e.parse_level(fb,fb.root)
        result["levelId"] = name  # Actual exported TextAsset name, not invented internal levelId.
        result["mapData"] = decoder.map_data(decoder.target(f,5))
        for i,nm in ((10,"routes"),(11,"extraRoutes")):
            result[nm] = decoder.vector_tables(decoder.target(f,i),decoder.route)
        result["waves"] = decoder.vector_tables(decoder.target(f,14),decoder.wave)
        for i,nm in ((16,"predefines"),(17,"hardPredefines")):
            result[nm] = decoder.predefines(decoder.target(f,i))
        used = {a["routeIndex"] for w in result["waves"] for fr in w["fragments"] for a in fr["actions"] if a["actionType"]=="SPAWN"}
        for idx in used:
            if idx<0 or idx>=len(result["routes"] or []) or not result["routes"][idx]:
                raise RecoveryError(f"SPAWN references absent route {idx}")
            if result["routes"][idx]["motionMode"]=="E_NUM":
                decoder.issues.append(f"SPAWN references placeholder route {idx}")
        report = {"status":"partial", "core_status":"decoded_unverified", "level_id":name,
                  "source_path":local_path(path),"source_sha256":sha(path),"payload_offset":offset,
                  "helper_sha256":sha(PARSER_DIR/'extract_level_data.py'),
                  "fb_helper_sha256":sha(PARSER_DIR/'extract_enemy_data.py'),
                  "extractor_sha256":sha(Path(__file__)),
                  "core_fields":list(CORE_FIELDS),"issues":decoder.issues,
                  "unverified_root_fields":[n for i,n in enumerate(e.LEVEL_NAMES) if n not in CORE_FIELDS and decoder.field(f,i) is not None],
                  "spawn_route_indices":sorted(used),"v2_status":"not_validated"}
        if decoder.issues:
            report['core_status']='decoded_partial'
        if reference_path is not None:
            ref = json.loads(reference_path.read_text(encoding='utf8'))
            differences = compare_core(result,ref)
            exact_equal = canonical_core(result)==canonical_core(ref)
            report.update({"reference_path":local_path(reference_path),"reference_sha256":sha(reference_path),
                           "differences":differences,"core_exact_equal":exact_equal})
            report["core_status"] = "reference_verified" if exact_equal and not differences and not decoder.issues else "reference_mismatch_or_partial"
        result["_recovery"] = report
        return result
    except (IndexError,struct.error,KeyError,TypeError,ValueError) as exc:
        raise RecoveryError(f"{name}: {exc}") from exc


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-dir',type=Path,default=ROOT.parent/'unpack_work/release_20260831/base_raw')
    p.add_argument('--catalog',type=Path,default=ROOT/'packages/campaign/mainline_catalog.json')
    p.add_argument('--reference-dir',type=Path,default=ROOT/'packages/campaign/native_reference')
    p.add_argument('--output-dir',type=Path,default=ROOT/'packages/campaign/recovered_levels')
    p.add_argument('--report',type=Path,default=ROOT/'validation/campaign/data_recovery.json')
    p.add_argument('--reference-commit',default=REFERENCE_COMMIT,
                   help='Provenance label supplied by reference fetcher; file hashes are independently recorded')
    p.add_argument('--level',action='append',help='Limit to explicit native level IDs')
    args=p.parse_args()
    if not args.source_dir.is_dir():
        raise FileNotFoundError(f"Missing binary source directory: {args.source_dir}")
    ids=args.level or [r['level_id'] for r in json.loads(args.catalog.read_text(encoding='utf8'))['stages'] if r['selected']]
    args.output_dir.mkdir(parents=True,exist_ok=True)
    reports=[]
    for lid in ids:
        path=args.source_dir/(lid+'.dat');ref=args.reference_dir/(lid+'.json')
        try:
            decoded=extract(path,ref if ref.exists() else None)
            output=args.output_dir/(lid+'.json')
            output.write_text(json.dumps(decoded,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
            reports.append({**decoded['_recovery'],'output_path':local_path(output),'output_sha256':sha(output)})
        except (RecoveryError,FileNotFoundError) as exc:
            reports.append({'level_id':lid,'status':'failed','error':str(exc),
                            'source_path':local_path(path),
                            'source_sha256':sha(path) if path.is_file() else None,
                            'v2_status':'not_validated'})
    counts={'attempted':len(ids),'decoded':sum(r['status']!='failed' for r in reports),
            'failed':sum(r['status']=='failed' for r in reports),
            'core_reference_verified':sum(r.get('core_status')=='reference_verified' for r in reports)}
    report={'schema':'ark_sim.campaign_data_recovery.v1','offline_only':True,
            'reference_repository':'ArknightsAssets/ArknightsGamedata',
            'reference_commit':args.reference_commit,'reference_commit_is_fetcher_provenance_label':True,
            'core_fields':list(CORE_FIELDS),'counts':counts,'levels':reports}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(counts,ensure_ascii=False))


if __name__=='__main__':
    main()
