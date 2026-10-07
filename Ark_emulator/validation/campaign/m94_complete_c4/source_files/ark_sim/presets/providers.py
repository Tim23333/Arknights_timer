"""Pure Ark preset decisions. User providers can replace every entry."""
import math


def checkpoint_cartesian_position(inputs, params, context):
    signs = inputs["parameters"]["axis_signs"]
    return {"row": inputs["position"]["row"]+signs["row"]*inputs["offset"]["y"],
            "col": inputs["position"]["col"]+signs["col"]*inputs["offset"]["x"]}


def living_route_transition(inputs, params, context):
    return {"hidden": inputs["kind"] == 5, "relocate": inputs["kind"] == 6,
            "position": dict(inputs["checkpoint"]["position"]) if inputs["kind"] == 6 else dict(inputs["position"])}


def attribute_layers(inputs, params, context):
    value = inputs["base"]
    modifiers = inputs["modifier_layers"]
    operations = params.get("operations", {})
    aggregator = params.get("aggregator", {}).get("provider", "ark.attributes.aggregate")
    for record in inputs["order"]:
        layer = record["layer"]
        selected = [m for m in modifiers if m.get("layer", "flat") == layer]
        if not selected:
            continue
        parameters = context.invoke_provider(aggregator, {"layer": layer, "modifiers": selected},
                                             {"operation": operations.get(layer, "custom")})
        result = context.calculate("attributes.modifier_layer", {"value": value,
                                   "modifiers": selected, "layer_parameters": parameters})
        value = result.value
    return value


def time_attribute_layers(inputs, params, context):
    """Optional data-defined temporal modifiers, evaluated at the sample clock."""
    modifiers = []
    instances = {b["id"]: b for b in context["owner"]["components"].get("buffs", {}).get("instances", [])}
    sampled = context.get("attribute_sample_time", context["time"])
    for item in inputs["modifier_layers"]:
        modifier = dict(item)
        curve = item.get("parameters", {}).get("time_curve")
        if curve:
            instance = instances.get(item.get("buff_instance"))
            if instance is None:
                raise ValueError("temporal modifier requires its captured Buff instance")
            elapsed = max(0, (sampled-instance["started_at"])*context["quantum"])
            if curve.get("type") == "linear_remaining":
                duration = curve.get("duration_seconds")
                if duration is None and instance["expires_at"] is not None:
                    duration = (instance["expires_at"]-instance["started_at"])*context["quantum"]
                if duration is None or duration <= 0:
                    raise ValueError("remaining-ratio modifier requires positive duration")
                factor = max(0, 1-elapsed/duration)
            elif curve.get("type") == "staircase":
                step = curve["step_seconds"]
                if step <= 0:
                    raise ValueError("staircase modifier requires positive interval")
                factor = min(curve["max_steps"], math.floor(elapsed/step))
            else:
                raise ValueError("unknown temporal modifier curve")
            modifier["value"] *= factor
        modifiers.append(modifier)
    return attribute_layers({**dict(inputs), "modifier_layers": modifiers}, params, context)


def aggregate_layer(inputs, params, context):
    values = [m["value"] * m.get("stacks", 1) for m in inputs["modifiers"]]
    operation = params["operation"]
    result = {"additive": 0, "ratio": 0, "factor": 1}
    if operation == "add":
        result["additive"] = sum(values)
    elif operation == "ratio_sum":
        result["ratio"] = sum(values)
    elif operation == "ratio_product":
        result["factor"] = math.prod(1 + v for v in values)
    elif operation == "factor_product":
        result["factor"] = math.prod(values)
    elif operation == "max_add":
        result["additive"] = max(values, default=0)
    elif operation == "max_ratio":
        result["ratio"] = max(values, default=0)
    elif operation == "min_ratio":
        result["ratio"] = min(values, default=0)
    elif operation != "custom":
        raise ValueError(f"unknown preset aggregation operation {operation}")
    return result


def resource_bounds(inputs, params, context):
    value, capacity = inputs["candidate"], inputs["capacity"]
    options = dict(params, **dict(inputs["bounds_parameters"]))
    low = options.get("minimum", 0)
    high = options.get("maximum", capacity)
    if options.get("mode", "clamp") == "reject" and not low <= value <= high:
        return {"value": value, "overflow": 0, "accepted": False}
    bounded = min(high, max(low, value))
    return {"value": bounded, "overflow": value - bounded, "accepted": True}


def capacity_change(inputs, params, context):
    options = dict(params, **dict(inputs["parameters"]))
    mode = options.get("capacity_change_mode", "preserve_absolute")
    current, old, new = inputs["current"], inputs["old_capacity"], inputs["new_capacity"]
    if mode == "preserve_absolute":
        value = current
    elif mode == "preserve_ratio":
        value = current*new/old if old else 0
    elif mode == "preserve_missing":
        value = max(0, new-(old-current))
    elif mode == "fill" or (mode == "birth_full" and inputs["reason"].get("initializing")):
        value = new
    elif mode == "birth_full":
        value = current
    else:
        raise ValueError("unknown resource capacity-change profile")
    return max(0, value)


def terrain_tile_options(inputs, params, context):
    """Stable ownership layers; explicit model costs, no native-ID branches."""
    result = dict(inputs["base"])
    key = result.get("tileKey", "tile_floor")
    ground = key not in {"tile_wall", "tile_forbidden", "tile_flystart"} and (
        key in {"tile_start", "tile_end"} or bool((result.get("passableMask", 1) or 0) & 1))
    for layer in sorted(inputs["layers"], key=lambda x: (x["priority"], x["sequence"], x["owner"])):
        values = layer["values"]
        result.update(values)
        if "passableMask" in values:
            ground = bool(values["passableMask"] & 1)
    result["groundPassable"] = ground
    result["movementCost"] = params.get("obstacle_like_cost", 3) if result.get("obstacleLikeMoveCost", False) else params.get("normal_cost", 1)
    return result


def ground_deploy(inputs, params, context):
    terrain, states = inputs["terrain"], inputs["states"]
    restrictions = inputs["entity"].get("components", {}).get("deployable", {})
    allowed = restrictions.get("terrain", "ground")
    mask = 2 if allowed == "high" else 1 if allowed == "ground" else 3
    checks = [(states.get("finished", False), "battle_finished"),
              (not terrain.get("inside", False), "out_of_map"),
              (not int(terrain.get("buildable", 0) or 0) & mask, "not_buildable"),
              (terrain.get("occupied", False), "occupied"),
              ("advanced_build_mask" in restrictions.get("parameters", {}) and not int(terrain.get("advancedBuildMask", 1)) & restrictions["parameters"]["advanced_build_mask"], "advanced_not_buildable"),
              (states.get("instances", 0) >= restrictions.get("parameters", {}).get("max_instances", 1), "already_deployed"),
              (states.get("cooldown", False), "on_cooldown"),
              (states.get("at_capacity", False), "capacity"),
              (not inputs["resources"].get("affordable", True), "insufficient_resource")]
    reason = next((message for failed, message in checks if failed), "ok")
    return {"accepted": reason == "ok", "reason": reason}


def lifecycle(inputs, params, context):
    params = dict(context.get("lifecycle_parameters", {}), **dict(params))
    resource = params.get("resource", "hp")
    amount = inputs["resources"].get(resource, {}).get("current")
    died = amount is not None and amount <= params.get("threshold", 0)
    revive = params.get("revive", False) and died
    return {"action": "revive" if revive else "death" if died else "none",
            "state": "alive" if revive or not died else "dead",
            "resource": resource, "reason": "resource_threshold",
            "value": params.get("revive_value", 1) if revive else 0}


def battle_result(inputs, params, context):
    objective = context.get("objectives", {})
    resource = objective.get("life_resource", "life")
    value = inputs["resources"].get(resource, {}).get("current")
    if objective.get("type") == "waves":
        if value is not None and value <= objective.get("defeat_threshold", 0):
            return {"finished": True, "result": "defeat", "reason": "life_exhausted"}
        alive = [e for e in context["entity_states"] if "enemy" in e["tags"] and e["components"].get("runtime", {}).get("alive", False)]
        if inputs["waves"].get("pending", 0) == 0 and inputs["waves"].get("timeline_complete", True) and not alive:
            return {"finished": True, "result": "victory", "reason": "waves_cleared"}
    return {"finished": False, "result": "running", "reason": "objectives_pending"}


def targeting_score(inputs, params, context):
    candidate = inputs["candidate"]
    runtime = candidate.get("components", {}).get("runtime", {})
    if context.get("healing", False):
        return context.get("health_ratio", 1)
    return (inputs["distance"] - (params.get("blocked_priority", 100000) if runtime.get("blocked_by") == inputs["source"].get("id") else 0))


def targeting_selection(inputs, params, context):
    if context.get("ordering") == "random":
        remaining, selected = list(inputs["candidates"]), []
        for sample in inputs["samples"]:
            if not remaining:
                break
            selected.append(remaining.pop(min(len(remaining)-1, math.floor(sample["value"]*len(remaining))))["id"])
        return selected
    values = [(candidate, inputs["scores"].get(str(candidate["id"]), 0)) for candidate in inputs["candidates"]]
    if context.get("ordering") != "provider":
        values.sort(key=lambda pair: (pair[1], pair[0]["id"]))
    limit = inputs["limits"].get("count")
    return [x["id"] for x, _ in values[:limit] if limit is not None] if limit is not None else [x["id"] for x, _ in values]


def player_behavior(inputs, params, context):
    return {"move": False, "attack": True, "state": "alive"}


def ground_behavior(inputs, params, context):
    return {"move": not inputs.get("blocked_by"), "attack": bool(inputs.get("blocked_by")),
            "state": "alive"}


def pure_eligibility(inputs,params,context):
    return context.invoke_provider(inputs['selector_provider'],{'source':inputs['source'],'candidates':inputs['candidates'],'region':inputs['region']},inputs['selector_parameters'])


def behavior_decision(inputs,params,context):
    p={**dict(params),**dict(inputs['parameters'])};v=inputs['visibility'];c=inputs['controls']
    if set(p)-{'stop_cast_groups','target_key','blocked_target','stop_on_target'}:raise ValueError('unsupported declared behavior decision parameter')
    for name in ('blocked_target','stop_on_target'):
        if name in p and type(p[name]) is not bool:raise ValueError('behavior decision boolean parameter required')
    if not isinstance(p.get('stop_cast_groups',[]),(list,tuple)) or any(key not in inputs['cast_groups'] for key in p.get('stop_cast_groups',[])):raise ValueError('behavior stop_cast_groups must name declared groups')
    if p.get('target_key','normal') not in inputs['eligible_ids']:raise ValueError('behavior target_key must name declared selector')
    if not v['alive'] or not v['active'] or v['hidden']:return {'move':False,'attack':False}
    busy=any(inputs['cast_groups'].get(key) for key in p.get('stop_cast_groups',[]))
    target=bool(inputs['eligible_ids'].get(p.get('target_key','normal'),[]))
    blocked=inputs['blocked_by'] is not None
    if p.get('blocked_target',False):target=blocked and inputs['blocked_by'] in inputs['eligible_ids'].get(p.get('target_key','normal'),[])
    return {'move':bool(c['move'] and not blocked and not busy and not (p.get('stop_on_target',True) and target)),
            'attack':bool(c['attack'] and c['abilities'] and not busy and target)}


def area_cell_offsets(inputs, params, context):
    from ark_sim.domains.spatial import project_cell
    options = dict(params, **dict(inputs["parameters"]))
    offsets = options.get("offsets")
    if not isinstance(offsets, (list, tuple)) or not offsets or any(not isinstance(x,(list,tuple)) or len(x)!=2 or any(type(v) is not int for v in x) for x in offsets):
        raise ValueError("area cell offsets require nonempty integer pairs")
    row, col = project_cell(inputs["center_position"])
    cells = {(row+dr,col+dc) for dr,dc in offsets}
    return [entity["id"] for entity in inputs["candidates"] if project_cell(entity["components"]["spatial"]["position"]) in cells]


def selector_grid(inputs, params, context):
    from ark_sim.domains.spatial import project_cell
    source = inputs["source"]
    region = inputs["region"]
    if region.get("type") == "all": return [entity["id"] for entity in inputs["candidates"]]
    position = source.get("components", {}).get("spatial", {}).get("position")
    if position is None: raise ValueError("spatial selector requires an explicit source position")
    facing = source["components"]["spatial"].get("facing", "right")
    cells = set()
    for row, col in region.get("offsets", ()):
        if region.get("rotate_with_facing", True):
            row, col = {"right": (row, col), "up": (-col, row),
                        "left": (-row, -col), "down": (col, -row)}[facing]
        cells.add(project_cell({"row": position["row"] + row, "col": position["col"] + col}))
    accepted = []
    for entity in inputs["candidates"]:
        pos = entity["components"].get("spatial", {}).get("position")
        if pos is None:
            continue
        if region.get("type") == "all":
            inside = True
        elif region.get("type") in ("radius", "circle"):
            inside = math.hypot(pos["row"]-position["row"], pos["col"]-position["col"]) <= region["radius"]
        elif region.get("type") == "manhattan":
            inside = abs(pos["row"]-position["row"])+abs(pos["col"]-position["col"]) <= region["radius"]
        else:
            inside = project_cell(pos) in cells
        if params.get("include_blocked") and entity["components"].get("runtime", {}).get("blocked_by") == source["id"]:
            inside = True
        if inside:
            accepted.append(entity["id"])
    return accepted


def spatial_route(inputs, params, context):
    from ark_sim.domains.spatial import GridTopology, route_motion_mode
    route = context.get("source", {}).get("components", {}).get("spatial", {}).get("route", {})
    return GridTopology(inputs["map"]).path(inputs["origin"], inputs["destination"], route_motion_mode(route),
        allow_diagonal=bool(params.get("use_route_diagonal") and route.get("allowDiagonalMove", False)),
        corner_cut=params.get("corner_cut", False))


def spawn_uniform_rect(inputs, params, context):
    """Explicit Cartesian model; independent of native RNG or map seed claims."""
    samples = {}
    for sample in inputs["samples"]:
        axis, value = sample.get("axis"), sample.get("value")
        if axis not in {"row", "col"} or axis in samples or type(value) not in (int, float) or not 0 <= value < 1:
            raise ValueError("spawn samples require unique axes and values in [0,1)")
        samples[axis] = value
    position = {}
    for axis in ("row", "col"):
        extent = inputs["random_range"][axis]
        sign = params.get("axis_signs", {}).get(axis, 1)
        if extent < 0 or sign not in (-1, 1):
            raise ValueError("spawn rectangle requires nonnegative extents and signed axes")
        if extent and axis not in samples:
            raise ValueError("spawn rectangle lacks a nonzero-axis sample")
        position[axis] = inputs["anchor"][axis]+inputs["offset"][axis]+(
            (2*samples[axis]-1)*extent*sign if axis in samples else 0)
    return position


def steering_velocity(inputs, params, context):
    """Bounded proportional velocity response, an explicit model profile."""
    options = dict(params, **dict(inputs["parameters"]))
    factor, maximum = options["response_factor"], options["max_acceleration"]
    speed, dt = inputs["speed"], inputs["delta_seconds"]
    if min(factor, maximum, speed) < 0 or dt <= 0:
        raise ValueError("steering requires nonnegative coefficients and positive time")
    origin, destination = inputs["origin"], inputs["destination"]
    dr, dc = destination["row"]-origin["row"], destination["col"]-origin["col"]
    distance = math.hypot(dr, dc)
    desired = {"row": dr/distance*speed if distance else 0, "col": dc/distance*speed if distance else 0}
    force = {axis: (desired[axis]-inputs["velocity"][axis])*factor for axis in ("row", "col")}
    magnitude = math.hypot(force["row"], force["col"])
    if magnitude > maximum:
        force = {axis: value*maximum/magnitude for axis, value in force.items()}
    velocity = {axis: inputs["velocity"][axis]+force[axis]*dt for axis in ("row", "col")}
    magnitude = math.hypot(velocity["row"], velocity["col"])
    if magnitude > speed:
        velocity = {axis: value*speed/magnitude for axis, value in velocity.items()}
    position = {axis: origin[axis]+velocity[axis]*dt for axis in ("row", "col")}
    step_r, step_c = velocity["row"]*dt, velocity["col"]*dt
    step_squared = step_r*step_r+step_c*step_c
    along = dr*step_r+dc*step_c
    radius = options.get("arrival_radius", 0)
    if type(radius) not in (int, float) or radius < 0:
        raise ValueError("steering arrival radius must be nonnegative")
    projection = min(1, max(0, along/step_squared)) if step_squared else 0
    closest = math.hypot(dr-projection*step_r, dc-projection*step_c)
    reached = distance == 0 or (along > 0 and (
        (radius > 0 and closest <= radius) or
        (along >= distance*distance and abs(dr*step_c-dc*step_r) <= 1e-12)))
    if reached:
        position = dict(destination)
    return {"position": position, "velocity": velocity, "arrival_captured": reached}


def spatial_blocking(inputs, params, context):
    from ark_sim.domains.spatial import route_motion_mode
    route = inputs["target"]["components"].get("spatial", {}).get("route", {})
    if route_motion_mode(route) == 1:
        return {"accepted": False, "reason": "flying"}
    blocker = inputs["blocker"]["components"]["spatial"]["position"]
    target = inputs["target"]["components"]["spatial"]["position"]
    distance = math.hypot(blocker["row"]-target["row"], blocker["col"]-target["col"])
    return {"accepted": distance <= params.get("radius", 1), "reason": "nearby" if distance <= params.get("radius", 1) else "distant"}


def damage_pipeline(inputs, params, context):
    if inputs["effect"]["damage_type"] not in {"physical", "arts", "true"}:
        raise ValueError(f"Unsupported Ark damage type: {inputs['effect']['damage_type']}")
    power = context.calculate("damage.base", {"attack": inputs["effect"]["attack"],
                              "scale": inputs["effect"]["scale"], "additions": inputs["effect"]["additions"]}).value
    amount = context.calculate("damage.mitigation", {"power": power, "defense": inputs["effect"]["defense"],
                               "resistance": inputs["effect"]["resistance"], "damage_type": inputs["effect"]["damage_type"]}).value
    return {"accepted": True, "amount": amount,
            "allocations": [], "events": []}


def settlement_scale(inputs, params, context):
    """Scale only this receiver's health allocations; shield charges survive."""
    effect, target = inputs["effect"], inputs["target"]
    settlement = dict(effect["settlement"])
    factor = effect[params.get("multiplier_field", "multiplier")]
    if factor < 0 or not math.isfinite(factor):
        raise ValueError("settlement multiplier must be finite and nonnegative")
    resource = effect.get("resource") or next((k for k,v in target["components"].get("resources", {}).items()
        if v.get("spec", {}).get("role") == "health"), params.get("health_resource", "hp"))
    allocations = []
    for item in settlement.get("allocations", []):
        row = dict(item)
        if row.get("target", "target") in ("target", target["id"]) and row.get("resource", resource) == resource:
            if "delta" in row:
                row["delta"] *= factor
            elif "amount" in row:
                row["amount"] *= factor
        allocations.append(row)
    settlement["amount"] *= factor
    settlement["allocations"] = allocations
    return settlement
