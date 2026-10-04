"""Reject spatial semantics the current runtime cannot execute.

Only inline executable routes are checked. Scenario route inventories are
source metadata and may contain unresolved entries that are never selected.
"""
import math
from collections.abc import Mapping

from .repository import ContentError

BASIC_TILES = frozenset({"tile_floor", "tile_road", "tile_wall", "tile_forbidden",
                         "tile_start", "tile_flystart", "tile_end", "tile_empty"})
MOTION = {"WALK": 0, "FLY": 1}
CHECKPOINT = {"MOVE": 0, "WAIT_FOR_SECONDS": 1, "WAIT_FOR_PLAY_TIME": 2,
              "WAIT_CURRENT_FRAGMENT_TIME": 3, "WAIT_CURRENT_WAVE_TIME": 4,
              "DISAPPEAR": 5, "APPEAR_AT_POS": 6}


def route_policy(value, path, transition=False):
    if not isinstance(value, Mapping) or set(value) != {"rule", "parameters"}:
        fail(path, "explicit rule and parameters required")
    if not isinstance(value["rule"], str) or not value["rule"]:
        fail(path+".rule", "nonempty calculation rule ID required")
    params = value["parameters"]
    if transition:
        choices = {"hidden_effects": {"reject", "allow"}, "hidden_auras": {"suspend", "retain"},
                   "launched_source_effects": {"retain", "discard"}, "resource_timers": {"continue"}}
        if not isinstance(params, Mapping) or set(params) != set(choices):
            fail(path+".parameters", "all visibility/resource model choices must be explicit")
        for key, allowed in choices.items():
            if params[key] not in allowed: fail(path+".parameters."+key, "unsupported visibility model choice")
    else:
        if not isinstance(params, Mapping) or set(params) != {"axis_signs"}:
            fail(path+".parameters", "explicit Cartesian axis_signs required")
        axes = params["axis_signs"]
        if not isinstance(axes, Mapping) or set(axes) != {"row", "col"} or any(type(v) is not int or v not in (-1, 1) for v in axes.values()):
            fail(path+".parameters.axis_signs", "row/col must each be integer +1 or -1")


def fail(path, message):
    raise ContentError(f"{path}: {message}")


def finite(value, path, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        fail(path, "expected a finite number")
    if minimum is not None and value < minimum:
        fail(path, f"must be >= {minimum}")


def position(value, path, map_definition=None):
    if not isinstance(value, Mapping) or set(value) != {"row", "col"}:
        fail(path, "position requires exactly row and col")
    for key in ("row", "col"):
        finite(value[key], f"{path}.{key}")
    if map_definition:
        from ..domains.spatial import project_cell
        projected = project_cell(value)
        for key, size, cell in (("row", "rows", projected[0]), ("col", "cols", projected[1])):
            if not 0 <= cell < map_definition[size]:
                fail(f"{path}.{key}", "position outside declared map")


def enum(value, mapping, path):
    if value is None:
        return 0  # Existing normalized V2 ground fixtures omit the default.
    if isinstance(value, Mapping):
        if set(value) - {"name", "value"}:
            fail(path, "unknown enum fields")
        name, number = value.get("name"), value.get("value")
        if name is not None and name not in mapping:
            fail(path, f"unsupported enum name {name!r}")
        if number is None and name in mapping:
            return mapping[name]
        if type(number) is not int or number not in mapping.values():
            fail(path, f"unsupported enum value {number!r}")
        if name is not None and mapping[name] != number:
            fail(path, f"enum name/value mismatch: {name!r}/{number!r}")
        return number
    if isinstance(value, str):
        if value not in mapping:
            fail(path, f"unsupported enum name {value!r}")
        return mapping[value]
    if type(value) is not int or value not in mapping.values():
        fail(path, f"unsupported enum value {value!r}")
    return value


def validate_route(route, path, map_definition=None):
    if not isinstance(route, Mapping):
        fail(path, "expected an inline route object")
    enum(route.get("motionMode"), MOTION, f"{path}.motionMode")
    if "allowDiagonalMove" in route and type(route["allowDiagonalMove"]) is not bool:
        fail(f"{path}.allowDiagonalMove", "expected boolean")
    if "startPosition" in route:
        position(route["startPosition"], f"{path}.startPosition", map_definition)
    if "endPosition" not in route:
        fail(f"{path}.endPosition", "required by executable route")
    position(route["endPosition"], f"{path}.endPosition", map_definition)
    checkpoints = route.get("checkpoints")
    if checkpoints is None:
        checkpoints = []
    if not isinstance(checkpoints, (list, tuple)):
        fail(f"{path}.checkpoints", "expected a list")
    if "transition_policy" in route: route_policy(route["transition_policy"], path+".transition_policy", True)
    if "reach_offset_policy" in route: route_policy(route["reach_offset_policy"], path+".reach_offset_policy")
    hidden = False
    for index, checkpoint in enumerate(checkpoints):
        location = f"{path}.checkpoints[{index}]"
        if not isinstance(checkpoint, Mapping):
            fail(location, "expected an object")
        kind = enum(checkpoint.get("type"), CHECKPOINT, f"{location}.type")
        # Compiler resolves mutable copies before freezing. Canonicalize strings
        # so the existing integer checkpoint driver really executes a WAIT.
        if isinstance(checkpoint.get("type"), str) or (
                isinstance(checkpoint.get("type"), Mapping) and "value" not in checkpoint["type"]):
            checkpoint["type"] = kind
        if kind in (0, 6) and "position" not in checkpoint:
            fail(f"{location}.position", "required by MOVE checkpoint")
        if "position" in checkpoint and checkpoint["position"] is not None:
            position(checkpoint["position"], f"{location}.position", map_definition)
        elif kind in (0, 6):
            fail(f"{location}.position", "required by MOVE checkpoint")
        if kind in (1, 2, 3, 4):
            time = checkpoint.get("time")
            finite(0 if time is None else time, f"{location}.time", 0)
        if kind in (5, 6):
            if "transition_policy" not in route: fail(location, "disappear/appear requires explicit transition_policy")
            if kind == 5 and hidden: fail(location, "nested disappear has no matching appearance")
            if kind == 6 and not hidden: fail(location, "appearance requires preceding disappearance")
            hidden = kind == 5
        elif hidden and kind == 0:
            fail(location, "hidden route permits WAIT then APPEAR, not MOVE")
        offset = checkpoint.get("reachOffset", {"x": 0, "y": 0})
        if not isinstance(offset, Mapping) or set(offset) != {"x", "y"}: fail(location+".reachOffset", "exact x/y offset required")
        for axis in ("x", "y"): finite(offset[axis], location+".reachOffset."+axis)
        randomize = checkpoint.get("randomizeReachOffset")
        # Native nullable/undefined flags are not requests for a random sampler.
        # Explicit False is supported; integer zero is not a boolean flag.
        if randomize is not None and (type(randomize) is not bool or randomize):
            fail(location+".randomizeReachOffset", "random checkpoint offset has no declared supported sampler")
        reach = checkpoint.get("reachDistance", 0)
        finite(0 if reach is None else reach, location+".reachDistance", 0)
        if reach: fail(location+".reachDistance", "nonzero native capture radius requires another explicit model")
        if any(offset.values()):
            if kind not in (0, 6): fail(location, "nonzero offset only supported for MOVE/APPEAR")
            if "reach_offset_policy" not in route: fail(location, "nonzero reachOffset requires explicit reach_offset_policy")
            signs = route["reach_offset_policy"]["parameters"]["axis_signs"]
            actual = {"row": checkpoint["position"]["row"]+signs["row"]*offset["y"],
                      "col": checkpoint["position"]["col"]+signs["col"]*offset["x"]}
            position(actual, location+".effective_position", map_definition)
        else: actual = checkpoint.get("position")
        if (kind == 6 or (kind == 0 and any(offset.values()))) and map_definition:
            from ark_sim.domains.spatial import GridTopology
            topology = GridTopology(map_definition)
            row, col = topology._cell(actual)
            if enum(route.get("motionMode"), MOTION, path+".motionMode") == 0 and not (topology.appearance_passable(row,col) if kind==6 else topology.passable(row,col)):
                fail(location+".effective_position", "ground appearance/offset cannot target an impassable cell")
    if hidden: fail(path, "route ends disappeared without paired appearance")
    if map_definition and map_definition.get("tile_mechanics"):
        from ..domains.tile_mechanics import descriptor,validate_pair,paired_rule
        from ..domains.spatial import GridTopology
        grid=GridTopology(map_definition);current=route.get('startPosition');entry=None
        for index,checkpoint in enumerate(checkpoints):
            kind=enum(checkpoint.get('type'),CHECKPOINT,path)
            if kind in (0,6):
                offset=checkpoint.get('reachOffset',{'x':0,'y':0})
                signs=route.get('reach_offset_policy',{}).get('parameters',{}).get('axis_signs',{'row':1,'col':1})
                destination={'row':checkpoint['position']['row']+signs['row']*offset['y'],
                    'col':checkpoint['position']['col']+signs['col']*offset['x']}
            if kind==5:
                if current is None:fail(path,'portal entry requires declared route origin')
                entry=descriptor(grid,current)
            elif kind==6:
                target=descriptor(grid,destination)
                try:
                    active=validate_pair(entry['profile'],target['profile'])
                    if active:paired_rule(entry['profile'],target['profile'],route['transition_policy']['rule'])
                except ValueError as error:fail(path+f'.checkpoints[{index}]',str(error))
                entry=None
            if kind in (0,6):current=destination


def validate_map(value, path):
    if not isinstance(value, Mapping):
        fail(path, "expected an object")
    for key in ("rows", "cols"):
        if type(value.get(key)) is not int or value[key] <= 0:
            fail(f"{path}.{key}", "expected a positive integer")
    from ..domains.tile_mechanics import validate_profiles
    profiles=value.get('tile_mechanics',{})
    try:validate_profiles(profiles)
    except ValueError as error:fail(path,str(error))
    tiles = value.get("tiles")
    if tiles is None:
        if any(p.get('type')=='occupancy_buff_field' for p in profiles.values()):
            fail(path+'.tiles','tile field profiles require explicit row-major tiles')
        return
    if not isinstance(tiles, (list, tuple)) or len(tiles) != value["rows"] * value["cols"]:
        fail(f"{path}.tiles", "expected exactly rows * cols row-major entries")
    for index, tile in enumerate(tiles):
        location = f"{path}.tiles[{index}]"
        if not isinstance(tile, Mapping):
            fail(location, "expected an object")
        key = tile.get("tileKey", "tile_floor")
        if not isinstance(key, str) or (key not in BASIC_TILES and key not in profiles):
            fail(f"{location}.tileKey", f"unsupported tile mechanic {key!r}")
        if key in profiles:
            for field in ('blackboard','effects'):
                data=tile.get(field)
                if data is not None and not isinstance(data,(Mapping,list,tuple)):
                    fail(location+'.'+field,'portal data must be null or an empty data collection')
        static=profiles.get(key,{})
        if static.get('type')=='declared_static_tile':
            for field,expected in static['expected_options'].items():
                actual=tile.get(field)
                if type(actual) is not type(expected) or actual!=expected:fail(location+'.'+field,'static tile source option differs')
            for field,expected in [('blackboard',static['expected_blackboard']),('effects',static['expected_effects'])]:
                actual=tile.get(field)
                if type(actual) is not type(expected) or actual!=expected:fail(location+'.'+field,'static tile source data differs')
        for field in ("passableMask", "buildableType"):
            number = tile.get(field)
            if number is not None and (type(number) is not int or not 0 <= number <= 3):
                fail(f"{location}.{field}", "expected a normalized integer mask in [0, 3] or null")
        field_profile=profiles.get(key,{}) if key in profiles else {}
        if field_profile.get('type')=='periodic_effect_field':
            from ..domains.tile_fields import board,same_data
            if not same_data(board(tile),field_profile['expected_blackboard']):fail(location,'periodic field blackboard not exactly bound')
        elif field_profile.get('type')=='occupancy_buff_field':
            from ..domains.tile_fields import validate_data as validate_field_data
            try:validate_field_data(tile,field_profile)
            except ValueError as error:fail(location,str(error))
        elif tile.get("blackboard"):
            fail(f"{location}.blackboard", "tile blackboard behavior is unsupported")
        if tile.get('effects'):fail(location+'.effects','tile effects behavior is unsupported')
