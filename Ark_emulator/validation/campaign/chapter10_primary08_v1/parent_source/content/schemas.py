"""Strict V2 schemas for implemented content, with explicit extension metadata."""
import math
from collections.abc import Mapping
from .repository import ContentError
from .spatial_validation import validate_map, validate_route, position as validate_position


COMMON = {"id", "kind", "version", "extends", "metadata", "rules", "dependencies", "dynamicReferences"}
FIELDS = {'ability': {'trigger_selector','tile_selector','initial_cooldown_seconds','timeline', 'activation', 'success_definition', 'duration_seconds', 'selector', 'events', 'wait_for_channels', 'interrupt_policy', 'target_capture', 'parameters', 'cooldown_seconds'}, 'attachment': {'hit_interval_seconds', 'recovery_on', 'step_interval_seconds', 'effect', 'source_cancel_flags', 'lifecycle', 'max_packets', 'completion_blocking', 'flight_lifetime_seconds', 'motion', 'refresh_interval_seconds', 'duration_seconds', 'ignored_owned_source_flags', 'force_reach_on_timeout', 'damage_integral', 'source_recovery_buff', 'target_buff'}, 'behavior': {'initial_state', 'transitions', 'states', 'provider', 'implementation', 'parameters', 'initial', 'decision'}, 'buff': {'capture','lifetime','removal', 'duration_seconds', 'modifiers', 'events', 'control_rule', 'stacking', 'interval_seconds', 'damage_hooks', 'control', 'contact_flags', 'effects', 'aura', 'duration_rule', 'active_rule', 'interval_rule', 'on_remove', 'movement_damage', 'parameters', 'selection_flags', 'toggle'}, 'calculation_rule': {'contractVersion', 'numeric', 'contract', 'implementation', 'parameters'}, 'control': {'on_cancel', 'ack_policy', 'clock_policy', 'on_complete', 'on_start', 'steps'}, 'entity': {'progression', 'talents', 'equipment', 'tags', 'components', 'growth'}, 'policy': {'contract', 'implementation', 'provider', 'parameters'}, 'preset': {'ruleset', 'provides', 'parameters', 'requires'}, 'projectile': {'chain', 'completion_blocking', 'on_invalid', 'motion', 'max_hits', 'stop_after_max', 'can_hit_same_target', 'collision', 'lifetime_seconds', 'stop_after_first', 'attach_at_launch', 'lifecycle'}, 'rule': {'contractVersion', 'numeric', 'contract', 'implementation', 'parameters'}, 'ruleset': {'reaction_budget', 'attribute_layers', 'numeric_profile', 'phase_order', 'bindings', 'parameters', 'quantum', 'system_order'}, 'scenario': {'cards','branches','timeline', 'seed', 'objectives', 'roster', 'commands', 'scheduledEffects', 'map', 'aliases', 'description', 'duration_seconds', 'waves', 'resources', 'initialEntities', 'ruleset', 'parameters', 'packages', 'routes'}, 'selector': {'limit', 'eligibility', 'ordering', 'provider', 'limit_attribute', 'eligible_rule', 'filters', 'exclude_abnormal_flags', 'parameters', 'region'}}
COMPONENT_FIELDS = {"depletion":None,"elemental": None,"tile_occupancy": {"blocks_deployment", "exclusive", "targetable", "withdrawable"},"ability_arbitration": None,"ability_timing": {"initial_cooldowns"},
    "selection_state": None,
    "rebirth": None,
    "attributes": {"base", "modifiers", "rules", "growth", "parameters", "layers", "attribute_rules"},
    "resources": None,
    "terrain_overlays": None,
    "abilities": None,
    "route_obstacle": {"rule", "contact_radius", "parameters"},
    "deployable": {"connectivity", "cooldown_start", "stock", "policy", "cost", "base_cost", "cooldown_seconds", "refund_ratio", "terrain", "capacity", "rules", "parameters", "deployed", "initial_state"},
    "behavior": {"machine", "state", "rules", "parameters"},
    "lifecycle": {"exit_rule", "exit_parameters", "policy", "initial_state", "rules", "parameters", "leak_loss", "revive", "death_projectiles", "death_spawns"},
    "spatial": {"route_motion_mode", "motion_mode", "coordinate_space", "position", "facing", "route", "route_id", "speed", "blocking", "occupancy", "radius", "projectile", "rules", "parameters", "wait_seconds", "movement", "steering", "timing_origins", "terrain", "block_capacity", "block_cost"},
    "buffs": {"initial", "policy", "rules", "parameters"},
    "buff_container": {"initial", "policy", "rules", "parameters"},
    "ownership": {"owner", "on_owner_retire"},
    "deck": {"on_create"},
}
RESOURCE_FIELDS = {"initial", "capacity", "capacity_attribute", "capacity_change_rule", "recovery_rule", "recovery_rate", "recovery", "rules", "parameters", "bounds_rule", "capacity_rule", "role", "events", "recovery_freeze_abilities", "recovery_freeze_rule"}
EFFECT_FIELDS = {'element','health_effect','element_effect','selection_projection','event', 'force', 'radius', 'additions', 'stream', 'facing', 'target', 'parameters', 'tags', 'center', 'type', 'definition', 'on_failure', 'state', 'machine', 'ignore_for_sp', 'rules', 'allowed', 'offset', 'position', 'distance', 'direction', 'remove_all', 'op', 'duration_seconds', 'projectile_definition', 'resource', 'fixed_amount', 'effects', 'on_success', 'damage_without_modify', 'delta', 'amount', 'attachment', 'kind', 'stacks', 'buff', 'read_mode', 'effect', 'delay_seconds', 'application_rule', 'ability', 'env_blackboard_injected', 'condition', 'probability', 'damage_flags', 'attack_type', 'node_is_env_damage', 'damage_type', 'owner', 'at_seconds', 'lifetime_seconds', 'metadata', 'selector', 'value', 'membership_rule', 'filters', 'scale', 'payload', 'center_position', 'bind_to_cast', 'origin', 'amount_rule', 'environmental'}
DEFAULT_CAPABILITIES = {'activations': {'manual', 'on_deploy', 'automatic_attack', 'passive'}, 'damage_types': {'arts', 'physical', 'true'}, 'effects': {'set_ability_cooldown','interrupt_ability','elemental_damage','elemental_attack','restart_behavior','finish_timeline_wave','regenerate', 'schedule', 'remove_buff', 'random', 'retire', 'apply_terrain_overlay', 'area', 'trigger_ability', 'advance_branch', 'heal', 'begin_attachment', 'no_source_damage', 'instant_kill', 'transition', 'activate_predefined', 'state', 'push', 'emit', 'apply_buff', 'set_motion_mode', 'move', 'damage', 'input_lock', 'modify_resource', 'spawn_on_tiles', 'spawn', 'buff_application', 'remove_terrain_overlay'}, 'read_modes': {'at_launch', 'at_hit', 'at_cast'}, 'stacking': {'extend', 'refresh', 'max', 'independent', 'add'}}


def fields(value, allowed, path):
    if not isinstance(value, Mapping):
        raise ContentError(f"{path}: expected an object")
    unknown = set(value) - allowed
    if unknown:
        raise ContentError(f"{path}: unknown fields {sorted(unknown)}")


def number(value, path, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ContentError(f"{path}: expected a finite number")
    if minimum is not None and value < minimum:
        raise ContentError(f"{path}: must be >= {minimum}")


def validate_timing(value, path):
    if "at" in value and "at_seconds" in value:
        raise ContentError(f"{path}: at and at_seconds are mutually exclusive")
    if "at" in value and (type(value["at"]) is not int or value["at"] < 0):
        raise ContentError(f"{path}.at: expected a nonnegative integer logical time")
    if "at_seconds" in value:
        number(value["at_seconds"], f"{path}.at_seconds", 0)


def validate_effect(effect, path, capabilities):
    fields(effect, EFFECT_FIELDS, path)
    if effect.get('op') in {'set_ability_cooldown', 'interrupt_ability'}:
        if set(effect)-{'op','target','ability','duration_seconds','parameters','metadata','rules','condition'} or not isinstance(effect.get('ability'),str) or not effect['ability']:
            raise ContentError(path+': owned ability effect requires exact reference and supported fields')
        if effect['op']=='set_ability_cooldown':number(effect.get('duration_seconds'),path+'.duration_seconds',0)
        elif 'duration_seconds' in effect:raise ContentError(path+': interrupt cannot specify a cooldown duration')
    if effect.get('op') in {'elemental_damage','elemental_attack'}:
        from ..domains.elemental import validate_effect as elemental_effect
        try:elemental_effect(effect)
        except ValueError as error:raise ContentError(path+': '+str(error)) from error
        if effect['op']=='elemental_attack':
            validate_effect(effect['health_effect'],path+'.health_effect',capabilities)
            validate_effect(effect['element_effect'],path+'.element_effect',capabilities)
    if effect.get('op') == 'restart_behavior':
        from ..domains.behavior_restart import validate
        try:validate(effect)
        except ValueError as error:raise ContentError(path+': '+str(error)) from error
    no_source_fields = {"fixed_amount", "origin", "ignore_for_sp", "attack_type", "damage_without_modify", "node_is_env_damage", "env_blackboard_injected", "environmental"}
    if effect.get("op") != "no_source_damage" and set(effect) & no_source_fields:
        raise ContentError(path+": no-source fields require the explicit no_source_damage operation")
    if effect.get("op") == "no_source_damage":
        from ..domains.no_source_damage import validate_request
        try: validate_request(effect)
        except ValueError as error: raise ContentError(path+": "+str(error)) from error
    if "bind_to_cast" in effect and (effect.get("op") != "apply_buff" or type(effect["bind_to_cast"]) is not bool):
        raise ContentError(path+": bind_to_cast requires apply_buff and strict bool")
    if effect.get("op") == "begin_attachment" and not isinstance(effect.get("attachment"), str):
        raise ContentError(path+": begin_attachment requires an explicit reference")
    if "damage_flags" in effect:
        flags = effect["damage_flags"]
        if effect.get("op") != "damage" or not isinstance(flags, Mapping) or set(flags) != {"source_attack_type", "ignore_for_sp"} or flags["source_attack_type"] not in {"NORMAL", "SPLASH", "BUFF", "ADDITION", "NONE"} or type(flags["ignore_for_sp"]) is not bool:
            raise ContentError(path+": explicit typed actor damage_flags required")
    if 'selection_projection' in effect:
        projection=effect['selection_projection']
        if (effect.get('op')!='area' or not effect.get('membership_rule')
            or not isinstance(projection,Mapping) or set(projection)!={'defaults'}):
            raise ContentError(path+': selection_projection requires an area membership rule and explicit defaults')
        from ..domains.selection import validate_state
        try:validate_state(projection['defaults'],path+'.selection_projection.defaults',complete=True)
        except ValueError as error:raise ContentError(str(error)) from error
    if "membership_rule" in effect and (effect.get("op") != "area" or not isinstance(effect["membership_rule"], str) or not effect["membership_rule"]):
        raise ContentError(f"{path}.membership_rule: area-only nonempty explicit rule required")
    if effect.get("op") == "finish_timeline_wave":
        from ..domains.timeline import validate_finish_request
        try:validate_finish_request(effect)
        except ValueError as error:raise ContentError(path+": "+str(error)) from error
    if effect.get("op") == "advance_branch":
        if set(effect)!={"op","parameters"} or not isinstance(effect["parameters"],Mapping) or set(effect["parameters"])!={"branch"} or not isinstance(effect["parameters"]["branch"],str) or not effect["parameters"]["branch"]:
            raise ContentError(path+": advance_branch requires one explicit named program")
    if effect.get('op') == 'trigger_ability' and effect.get('parameters',{}).get('on_rejection','raise') not in ('raise','skip'):
        raise ContentError(path+': ability rejection policy requires raise or skip')
    if effect.get("op") == "buff_application":
        from ..domains.buff_application import validate_effect as validate_application_effect
        try: validate_application_effect(effect)
        except ValueError as error: raise ContentError(path+": "+str(error))
    if effect.get("op") == "spawn_on_tiles":
        from ..domains.tile_targets import validate_effect as validate_tile_effect
        try:validate_tile_effect(effect)
        except ValueError as error:raise ContentError(path+": "+str(error))
    if effect.get("op") not in capabilities["effects"]:
        raise ContentError(f"{path}: unsupported effect op {effect.get('op')!r}")
    if effect.get("op") == "damage" and effect.get("damage_type", "physical") not in capabilities.get("damage_types", DEFAULT_CAPABILITIES["damage_types"]):
        raise ContentError(f"{path}.damage_type: unsupported damage type {effect.get('damage_type')!r}")
    required = {"modify_resource": ("resource",), "apply_buff": ("buff",), "remove_buff": ("buff",),
                "spawn": ("definition",), "schedule": ("effect",), "trigger_ability": ("ability",), "push": ("force",)}
    for field in required.get(effect["op"], ()):
        if field not in effect:
            raise ContentError(f"{path}.{field}: required by {effect['op']} effect")
    if "projectile_definition" in effect:
        if effect["op"] not in {"damage", "heal", "area"} or not isinstance(effect["projectile_definition"], str) or not effect["projectile_definition"]:
            raise ContentError(path+".projectile_definition: damage/heal/area exact projectile reference required")
    if "center_position" in effect:
        if effect["op"] != "area": raise ContentError(path+".center_position: area only")
        validate_position(effect["center_position"], path+".center_position")
    if effect["op"] == "modify_resource":
        if len(set(effect) & {"delta", "amount", "value", "amount_rule"}) != 1:
            raise ContentError(f"{path}: modify_resource requires exactly one of delta, amount, value, or amount_rule")
    if effect["op"] == "random":
        if not isinstance(effect.get("stream"), str) or not effect["stream"]:
            raise ContentError(f"{path}.stream: explicit random stream required")
        number(effect.get("probability", 1), f"{path}.probability", 0)
        if effect.get("probability", 1) > 1:
            raise ContentError(f"{path}.probability: must be <=1")
    if effect['op'] == 'activate_predefined':
        options = effect.get('parameters')
        if not isinstance(options, Mapping) or set(options) != {'key'} or not isinstance(options['key'], str) or not options['key']:
            raise ContentError(f"{path}.parameters: activation requires one nonempty registration key")
        if effect.get('target') != 'battle' or effect.get('selector'):
            raise ContentError(f"{path}: activation must explicitly target the battle registry without selector")
    if effect["op"] == "input_lock":
        options = effect.get("parameters", {})
        if not isinstance(options.get("key"), str) or not options["key"] or type(options.get("enabled")) is not bool:
            raise ContentError(f"{path}.parameters: input_lock requires key and boolean enabled")
    if effect["op"] in {"apply_terrain_overlay", "remove_terrain_overlay"}:
        from ark_sim.domains.terrain import validate_spec
        try:
            if effect["op"] == "apply_terrain_overlay":
                validate_spec(effect.get("parameters"), position=True)
            else:
                options = effect.get("parameters", {})
                if set(options) != {"key"} or not isinstance(options["key"], str) or not options["key"]:
                    raise ValueError("remove overlay requires explicit nonempty owner key")
            if effect.get("target") in {"battle", "system/battle"}:
                raise ValueError("terrain overlay requires actor ownership")
        except (ValueError, TypeError) as error:
            raise ContentError(f"{path}: {error}") from error
    if effect["op"] == "set_motion_mode" and "route_motion_mode" in effect.get("parameters", {}) and (type(effect["parameters"]["route_motion_mode"]) is not int or effect["parameters"]["route_motion_mode"] not in (0,1)):
        raise ContentError(path+": route motion mode must be WALK0/FLY1")
    if effect["op"] == "set_motion_mode" and (type(effect.get("value")) is not int or effect["value"] not in (0,1)):
        raise ContentError(path+": explicit WALK0/FLY1 motion mode required")
    if effect["op"] == "instant_kill":
        from ..domains.rebirth import validate_kill
        try:validate_kill(effect.get('parameters'))
        except ValueError as error:raise ContentError(path+': '+str(error)) from error
        if effect.get("target","selected") in {"battle","scenario"}:raise ContentError(path+": instant_kill cannot target battle")
    if effect["op"] == "retire":
        parameters = effect.get("parameters", {})
        if not isinstance(parameters, Mapping):
            raise ContentError(f"{path}.parameters: retire requires an object")
        reason = parameters.get("reason")
        if not isinstance(reason, str) or not reason or not reason.replace('_', '').isalnum():
            raise ContentError(f"{path}.parameters.reason: retire requires an explicit nonempty event-safe reason")
        if effect.get("target") in {"battle", "system/battle"}:
            raise ContentError(f"{path}.target: retire cannot remove the reserved battle entity")
    mode = effect.get("read_mode", {})
    if not isinstance(mode, Mapping):
        raise ContentError(f"{path}.read_mode must be an object")
    for key, value in mode.items():
        if key not in {"source_attributes", "target_attributes", "targets"} or value not in capabilities["read_modes"]:
            raise ContentError(f"{path}.read_mode.{key}: unsupported mode {value!r}")
    for key in ("on_success", "on_failure", "effects"):
        for index, child in enumerate(effect.get(key, [])):
            validate_effect(child, f"{path}.{key}[{index}]", capabilities)
    if "effect" in effect:
        validate_effect(effect["effect"], f"{path}.effect", capabilities)
    for key in ("amount", "delta", "value", "scale", "additions", "distance", "delay_seconds"):
        if key in effect:
            number(effect[key], f"{path}.{key}")
    if effect["op"] == "area":
        if effect.get("center", "target") not in {"source", "target"}:
            raise ContentError(f"{path}.center: expected source or target")
        if effect.get("membership_rule") is None:
            number(effect.get("radius"), f"{path}.radius", 0)
        else:
            if not isinstance(effect["membership_rule"], str) or not effect["membership_rule"]:
                raise ContentError(f"{path}.membership_rule: nonempty rule required")
            if "radius" in effect:
                raise ContentError(f"{path}: radius and membership_rule are mutually exclusive")
            offsets = effect.get("parameters", {}).get("offsets")
            if offsets is not None and (not isinstance(offsets, (list, tuple)) or not offsets or any(not isinstance(x, (list, tuple)) or len(x)!=2 or any(type(v) is not int for v in x) for x in offsets)):
                raise ContentError(f"{path}.parameters.offsets: nonempty integer cell-offset pairs required")
        if not effect.get("effects"):
            raise ContentError(f"{path}.effects: area requires effects")
        for restriction in effect.get("filters", []):
            fields(restriction, {"tag", "state"}, f"{path}.filters")
            if "state" in restriction and restriction["state"] != "alive":
                raise ContentError(f"{path}.filters.state: only alive is supported")
    if effect["op"] == "spawn":
        if effect.get("owner") not in {None, "source", "target"}:
            raise ContentError(f"{path}.owner: expected source or target")
        if "lifetime_seconds" in effect:
            number(effect["lifetime_seconds"], f"{path}.lifetime_seconds", 0)
        options = effect.get("parameters", {})
        if "deployment_payment_amount" in options:
            number(options["deployment_payment_amount"], f"{path}.parameters.deployment_payment_amount", 0)
        if "max_owned" in options and (type(options["max_owned"]) is not int or options["max_owned"] < 1):
            raise ContentError(f"{path}.parameters.max_owned: positive integer required")
        if options.get("on_owner_retire", "retain") not in {"retain", "remove"}:
            raise ContentError(f"{path}.parameters.on_owner_retire: expected retain or remove")
    if effect["op"] == "push":
        number(effect["force"], f"{path}.force")


def validate_events(events, path, capabilities):
    if not isinstance(events, (list, tuple)):
        raise ContentError(f"{path}: expected a list of event subscriptions")
    for index, subscription in enumerate(events):
        location = f"{path}[{index}]"
        fields(subscription, {"event", "condition", "effects", "parameters", "target"}, location)
        if subscription.get("target", "owner") not in {"owner", "event_source", "event_target"}:
            raise ContentError(f"{location}.target: expected owner, event_source, event_target")
        if not isinstance(subscription.get("event"), str):
            raise ContentError(f"{location}.event must be an explicit event name")
        if "condition" in subscription and not isinstance(subscription["condition"], str):
            raise ContentError(f"{location}.condition must be an expression string")
        if not isinstance(subscription.get("effects"), (list, tuple)) or not subscription["effects"]:
            raise ContentError(f"{location}.effects requires an implemented nonempty effect list")
        for effect in subscription["effects"]:
            validate_effect(effect, f"{location}.effects", capabilities)


def validate_modifier(modifier, path):
    fields(modifier, {"attribute", "layer", "value", "stacks", "rule", "operation", "parameters"}, path)
    for field in ("rule", "operation"):
        if field in modifier:
            raise ContentError(f"{path}.{field}: per-modifier execution is unsupported; bind attributes.modifier_layer or attributes.effective")
    if not isinstance(modifier.get("attribute"), str):
        raise ContentError(f"{path}.attribute: expected an attribute name")
    number(modifier.get("value"), f"{path}.value")
    if "stacks" in modifier:
        number(modifier["stacks"], f"{path}.stacks", 0)


def validate_definition(definition, capabilities=None):
    capabilities = capabilities or DEFAULT_CAPABILITIES
    identifier = definition["id"]
    kind = definition.get("kind")
    if kind not in FIELDS:
        raise ContentError(f"{identifier}: unsupported definition kind {kind!r}")
    fields(definition, COMMON | FIELDS[kind], identifier)
    if kind == "projectile":
        if 'completion_blocking' in definition and type(definition['completion_blocking']) is not bool:
            raise ContentError(identifier+': completion_blocking must be bool')
        for name in ("motion", "collision"):
            if name not in definition: raise ContentError(f"{identifier}.{name}: required")
            fields(definition[name], {"rule", "parameters"} | ({"allow_other_targets"} if name=="collision" else set()), f"{identifier}.{name}")
            if not isinstance(definition[name].get("rule"), str) or not definition[name]["rule"]: raise ContentError(f"{identifier}.{name}.rule: exact rule required")
        if "allow_other_targets" in definition["collision"] and type(definition["collision"]["allow_other_targets"]) is not bool: raise ContentError(identifier+".collision.allow_other_targets: boolean required")
        number(definition.get("lifetime_seconds"), identifier+".lifetime_seconds", 0)
        if "max_hits" not in definition or (definition["max_hits"] is not None and (type(definition["max_hits"]) is not int or definition["max_hits"] < 0)): raise ContentError(identifier+".max_hits: explicit nonnegative integer or null (unlimited) required")
        for name in ("can_hit_same_target", "stop_after_max", "stop_after_first", "attach_at_launch"):
            if type(definition.get(name)) is not bool: raise ContentError(identifier+"."+name+": explicit boolean required")
        policy=definition.get("lifecycle", {})
        fields(policy, {"source_invalid", "source_hidden", "target_invalid", "target_hidden", "finish_on_reach", "hit_on_reach", "force_reach_on_expire", "hit_on_expire"}, identifier+".lifecycle")
        for name in ("source_invalid", "source_hidden"):
            if policy.get(name) not in {"retain", "cancel"}: raise ContentError(identifier+".lifecycle."+name+": explicit retain/cancel policy required")
        for name in ("target_invalid", "target_hidden"):
            if policy.get(name) not in {"retain_position", "cancel"}: raise ContentError(identifier+".lifecycle."+name+": explicit retain_position/cancel policy required")
        for name in ("finish_on_reach", "hit_on_reach", "force_reach_on_expire", "hit_on_expire"):
            if type(policy.get(name)) is not bool: raise ContentError(identifier+".lifecycle."+name+": explicit boolean required")
        for index,item in enumerate(definition.get("on_invalid", [])): validate_effect(item, f"{identifier}.on_invalid[{index}]", capabilities)
        if 'chain' in definition:
            from ..domains.projectile_chains import validate as validate_chain
            validate_chain(definition['chain'], definition)
    elif kind == "control":
        if definition.get("rules"): raise ContentError(f"{identifier}.rules: bind individual effect rules; control owner rule scope is unsupported")
        if definition.get("clock_policy") != "logical": raise ContentError(f"{identifier}.clock_policy: explicit logical required")
        if definition.get("ack_policy") not in {"external", "immediate"}: raise ContentError(f"{identifier}.ack_policy: explicit external or immediate required")
        steps = definition.get("steps")
        if not isinstance(steps, (list, tuple)) or len(steps) > 10000: raise ContentError(f"{identifier}.steps: bounded list required")
        def control_effects(effects, path):
            if not isinstance(effects, (list, tuple)): raise ContentError(f"{path}: effect list required")
            def has_schedule(value):
                if isinstance(value, Mapping): return value.get("op") == "schedule" or any(has_schedule(v) for k,v in value.items() if k not in {"metadata", "payload", "parameters"})
                if isinstance(value, (list, tuple)): return any(has_schedule(v) for v in value)
                return False
            for index, effect in enumerate(effects):
                validate_effect(effect, f"{path}[{index}]", capabilities)
                if has_schedule(effect): raise ContentError(f"{path}: control effects use delay steps instead of unowned schedule jobs")
        keys = set()
        for index, step in enumerate(steps):
            path = f"{identifier}.steps[{index}]"; kind_step = step.get("kind") if isinstance(step, Mapping) else None
            if kind_step == "effects":
                fields(step, {"kind", "effects", "metadata"}, path); control_effects(step.get("effects"), path+".effects")
            elif kind_step == "delay":
                fields(step, {"kind", "seconds", "metadata"}, path); number(step.get("seconds"), path+".seconds", 0)
            elif kind_step == "ack":
                fields(step, {"kind", "key", "metadata"}, path)
                key = step.get("key")
                if not isinstance(key, str) or not key or key in keys: raise ContentError(f"{path}.key: unique nonempty ack key required")
                keys.add(key)
            else: raise ContentError(f"{path}.kind: effects/delay/ack required")
        for name in ("on_start", "on_complete", "on_cancel"): control_effects(definition.get(name, []), identifier+"."+name)
    elif kind == "entity":
        for field in ("equipment", "progression", "talents"):
            if definition.get(field):
                raise ContentError(f"{identifier}.{field}: execution is unsupported in this runtime")
        components = definition.get("components")
        if not isinstance(components, Mapping):
            raise ContentError(f"{identifier}.components: expected an object")
        for key, value in components.items():
            if key not in COMPONENT_FIELDS:
                raise ContentError(f"{identifier}.components: unsupported component {key!r}")
            allowed = COMPONENT_FIELDS[key]
            if allowed is not None:
                fields(value, allowed, f"{identifier}.components.{key}")
        if 'elemental' in components:
            from ..domains.elemental import validate as elemental_component
            try:elemental_component(components['elemental'])
            except ValueError as error:raise ContentError(identifier+': '+str(error)) from error
            for key,profile in components['elemental']['elements'].items():
                for phase in ('on_break','on_end'):
                    for index,child in enumerate(profile.get(phase,())):
                        validate_effect(child,identifier+'.elemental.'+key+'.'+phase+'['+str(index)+']',capabilities)
        lifecycle=components.get('lifecycle',{})
        if 'exit_rule' in lifecycle:
            if not isinstance(lifecycle['exit_rule'],str) or not lifecycle['exit_rule']: raise ContentError(identifier+': nonempty exit rule ID required')
            if not isinstance(lifecycle.get('exit_parameters',{}),Mapping): raise ContentError(identifier+': exit parameters must be record')
        elif 'exit_parameters' in lifecycle: raise ContentError(identifier+': exit parameters require explicit rule')
        if components.get('lifecycle',{}).get('death_spawns') is not None:
            from ..domains.death_spawns import validate as validate_death_spawns
            validate_death_spawns(components['lifecycle']['death_spawns'])
        emissions=components.get('lifecycle',{}).get('death_projectiles')
        if emissions is not None:
            from ark_sim.domains.death_projectiles import validate
            if not isinstance(emissions,(list,tuple)):raise ContentError(identifier+': death_projectiles must be array')
            for index,spec in enumerate(emissions):
                try:validate(spec)
                except (ValueError,TypeError) as error:raise ContentError(identifier+': '+str(error)) from error
                validate_effect(spec['effect'],identifier+'.death_projectiles['+str(index)+'].effect',capabilities)
        if 'depletion' in components:
            from ..domains.depletion import validate as validate_depletion
            try:validate_depletion(components['depletion'],components)
            except ValueError as error:raise ContentError(identifier+': '+str(error))
        if "rebirth" in components:
            from ..domains.rebirth import validate
            validate(components["rebirth"],components)
            for key in ("on_begin","on_finish"):
                for i,effect in enumerate(components["rebirth"].get(key,[])):validate_effect(effect,identifier+".rebirth."+key+"["+str(i)+"]",capabilities)
        if "tile_occupancy" in components:
            from ..domains.tile_targets import validate_occupancy
            validate_occupancy(components["tile_occupancy"])
        if "selection_state" in components:
            from ..domains.selection import validate_state
            validate_state(components["selection_state"], identifier+".selection_state")
        if "terrain_overlays" in components:
            from ark_sim.domains.terrain import validate_spec
            layers = components["terrain_overlays"]
            if not isinstance(layers, (list, tuple)):
                raise ContentError(identifier+".terrain_overlays must be a list")
            keys = set()
            for layer in layers:
                try: validate_spec(layer)
                except (ValueError, TypeError) as error: raise ContentError(identifier+": "+str(error)) from error
                if layer["key"] in keys: raise ContentError(identifier+": duplicate terrain owner key")
                keys.add(layer["key"])
        connectivity=components.get('deployable',{}).get('connectivity')
        if 'connectivity' in components.get('deployable',{}):
            from ..domains.deploy_connectivity import validate_profile
            try:validate_profile(connectivity)
            except ValueError as error:raise ContentError(identifier+': '+str(error)) from error
        if "cooldown_start" in components.get("deployable",{}):
            start=components['deployable']['cooldown_start']
            if type(start) is not str or start not in ('deploy','retire'):
                raise ContentError(identifier+': cooldown_start must be deploy or retire')
        stock=components.get("deployable",{}).get("stock")
        if stock is not None:
            fields(stock,{"resource","amount","rule"},identifier+".deployable.stock")
            if not isinstance(stock.get("resource"),str) or not stock["resource"] or type(stock.get("amount")) is not int or stock["amount"]<=0:
                raise ContentError(identifier+": stock requires nonempty battle resource and positive integer amount")
            if "rule" in stock and (not isinstance(stock["rule"],str) or not stock["rule"]):raise ContentError(identifier+": stock rule must be nonempty ID")
        obstacle=components.get("route_obstacle")
        if obstacle is not None:
            if set(obstacle)!={"rule","contact_radius","parameters"} or not isinstance(obstacle["rule"],str) or not obstacle["rule"] or not isinstance(obstacle["parameters"],Mapping):raise ContentError(identifier+": route obstacle requires rule, radius and explicit parameters")
            number(obstacle["contact_radius"],identifier+".route_obstacle.contact_radius",0)
        advanced = components.get("deployable", {}).get("parameters", {}).get("advanced_build_mask")
        if advanced is not None and (type(advanced) is not int or advanced <= 0):
            raise ContentError(identifier+": advanced_build_mask requires a positive integer mask")
        if "buffs" in components and "buff_container" in components:
            raise ContentError(f"{identifier}.components: buffs and buff_container are mutually exclusive aliases")
        for effect in components.get("deck", {}).get("on_create", []):
            validate_effect(effect, f"{identifier}.components.deck.on_create", capabilities)
        for key in ("buffs", "buff_container"):
            if key in components:
                initial = components[key].get("initial", [])
                if not isinstance(initial, (list, tuple)) or not all(isinstance(ref, str) and ref.strip() for ref in initial):
                    raise ContentError(f"{identifier}.components.{key}.initial: expected a list of Buff ID strings")
        if "route_id" in components.get("spatial", {}):
            raise ContentError(f"{identifier}.spatial.route_id: route ID resolution is unsupported; use an inline route")
        spatial = components.get("spatial", {})
        if "route_motion_mode" in spatial and ("motion_mode" not in spatial or type(spatial["route_motion_mode"]) is not int or spatial["route_motion_mode"] not in (0,1)):
            raise ContentError("route_motion_mode requires explicit valid motion_mode and WALK0/FLY1 route mode")
        if "motion_mode" in spatial and (type(spatial["motion_mode"]) is not int or spatial["motion_mode"] not in (0,1)):
            raise ContentError(identifier+": explicit spatial motion mode WALK0/FLY1 required")
        if "capacity" in components.get("deployable", {}):
            number(components["deployable"]["capacity"], f"{identifier}.deployable.capacity", 0)
        if "route" in spatial:
            validate_route(spatial["route"], f"{identifier}.components.spatial.route")
        if "position" in spatial:
            validate_position(spatial["position"], f"{identifier}.components.spatial.position")
        for attr, value in components.get("attributes", {}).get("base", {}).items():
            number(value, f"{identifier}.attributes.base.{attr}")
        for index, modifier in enumerate(components.get("attributes", {}).get("modifiers", [])):
            validate_modifier(modifier, f"{identifier}.attributes.modifiers[{index}]")
        growth_sources = [definition.get("growth", {}), components.get("attributes", {}).get("growth", {})]
        for growth in growth_sources:
            if not isinstance(growth, Mapping):
                raise ContentError(f"{identifier}.growth: expected an attribute-to-growth map")
            for attr, spec in growth.items():
                path = f"{identifier}.growth.{attr}"
                fields(spec, {"rule", "level", "parameters"}, path)
                if "rule" in spec and (not isinstance(spec["rule"], str) or not spec["rule"].strip()):
                    raise ContentError(f"{path}.rule must be a nonempty attributes.growth rule reference when specified")
                number(spec.get("level", 1), f"{path}.level", 0)
                if attr not in components.get("attributes", {}).get("base", {}):
                    raise ContentError(f"{path}: growth refers to an undefined base attribute")
        attribute_rules = components.get("attributes", {}).get("attribute_rules", {})
        if not isinstance(attribute_rules, Mapping):
            raise ContentError(f"{identifier}.attribute_rules: expected an attribute-to-bindings map")
        for attribute, bindings in attribute_rules.items():
            if attribute not in components.get("attributes", {}).get("base", {}):
                raise ContentError(f"{identifier}.attribute_rules.{attribute}: unknown base attribute")
            if not isinstance(bindings, Mapping) or not all(isinstance(ref, str) for ref in bindings.values()):
                raise ContentError(f"{identifier}.attribute_rules.{attribute}: expected calculation-to-rule bindings")
        resources = components.get("resources", {})
        if not isinstance(resources, Mapping):
            raise ContentError(f"{identifier}.resources must be an object")
        for resource, values in resources.items():
            path = f"{identifier}.resources.{resource}"
            fields(values, RESOURCE_FIELDS, path)
            for name in ("initial", "capacity", "recovery_rate"):
                if name in values:
                    number(values[name], f"{path}.{name}", 0 if name == "capacity" else None)
            if "capacity_attribute" in values and values["capacity_attribute"] not in components.get("attributes", {}).get("base", {}):
                raise ContentError(f"{path}.capacity_attribute: unknown attribute {values['capacity_attribute']}")
            validate_recovery(values, path)
        abilities = components.get("abilities", [])
        if "ability_arbitration" in components:
            from ..domains.ability_arbitration import validate as validate_arbitration
            validate_arbitration(components["ability_arbitration"], abilities)
        if "ability_timing" in components:
            from ark_sim.domains.ability_timing import validate_overrides
            try:validate_overrides(components["ability_timing"], abilities)
            except ValueError as error:raise ContentError(identifier+": "+str(error)) from error
        if not isinstance(abilities, (list, tuple)) or not all(isinstance(v, str) for v in abilities):
            raise ContentError(f"{identifier}.abilities must be an ID list")
    elif kind == "ability":
        if 'trigger_selector' in definition and (not isinstance(definition['trigger_selector'],str) or not definition['trigger_selector']):raise ContentError(identifier+': trigger_selector requires an explicit selector ID')
        if "initial_cooldown_seconds" in definition:
            number(definition["initial_cooldown_seconds"], identifier+".initial_cooldown_seconds", 0)
        if "tile_selector" in definition:
            from ..domains.tile_targets import validate_selector
            validate_selector(definition["tile_selector"])
            if definition.get("selector") or definition.get("target_capture") == "each_hit":
                raise ContentError(identifier+": tile selection requires independent start capture")
        if "wait_for_channels" in definition and type(definition["wait_for_channels"]) is not bool:
            raise ContentError(identifier+": wait_for_channels requires strict bool")
        activation = definition.get("activation", {})
        if "settle_blocking" in activation and type(activation["settle_blocking"]) is not bool:
            raise ContentError(identifier+": settle_blocking requires strict boolean")
        flags = activation.get("forbidden_source_flags", [])
        if not isinstance(flags, (list, tuple)) or any(type(flag) is not int or not 0 <= flag < 46 for flag in flags):
            raise ContentError(identifier+": forbidden_source_flags requires typed enum values")
        fields(activation, {"settle_blocking", "forbidden_source_flags","mode", "costs", "interval_rule", "interval_seconds", "event", "events", "condition", "rules", "parameters", "cooldown_seconds", "duration_seconds", "on_start"}, f"{identifier}.activation")
        if not isinstance(activation.get("on_start", []), (list, tuple)):
            raise ContentError(f"{identifier}.activation.on_start: expected effect list")
        for index, effect in enumerate(activation.get("on_start", [])):
            validate_effect(effect, f"{identifier}.activation.on_start[{index}]", capabilities)
        if "wait_for_projectiles" in definition.get("parameters", {}) and type(definition["parameters"]["wait_for_projectiles"]) is not bool:
            raise ContentError(f"{identifier}.parameters.wait_for_projectiles: expected boolean")
        if activation.get("mode") not in capabilities["activations"]:
            raise ContentError(f"{identifier}: unsupported activation {activation.get('mode')!r}")
        if "auto_only" in activation.get("parameters", {}) and type(activation["parameters"]["auto_only"]) is not bool:
            raise ContentError(f"{identifier}.activation.parameters.auto_only: expected boolean")
        for option in ("reset_attack_clock", "cancel_pending_attacks"):
            if option in activation.get("parameters", {}) and type(activation["parameters"][option]) is not bool:
                raise ContentError(f"{identifier}.activation.parameters.{option}: expected boolean")
        if activation.get("mode") == "passive" and not (activation.get("event") or activation.get("events")):
            raise ContentError(f"{identifier}: passive activation requires an explicit event")
        interruption = definition.get("interrupt_policy", {})
        fields(interruption, {"on_source_death", "refund"}, f"{identifier}.interrupt_policy")
        if interruption.get("on_source_death", "cancel_remaining") != "cancel_remaining" or interruption.get("refund", "none") != "none":
            raise ContentError(f"{identifier}.interrupt_policy: continue and refund policies are unsupported")
        validate_events(definition.get("events", []), f"{identifier}.events", capabilities)
        for index, cost in enumerate(activation.get("costs", [])):
            fields(cost, {"resource", "amount", "rule", "parameters", "rules", "owner"}, f"{identifier}.activation.costs[{index}]")
            if cost.get("owner", "source") not in {"source", "battle", "owner"}:
                raise ContentError(f"{identifier}.activation.costs[{index}].owner: expected source, battle, or owner")
            if not isinstance(cost.get("resource"), str) or ("amount" not in cost and "rule" not in cost):
                raise ContentError(f"{identifier}.activation.costs[{index}]: cost needs resource and amount or rule")
            if "amount" in cost:
                number(cost["amount"], f"{identifier}.cost.amount", 0)
        for index, entry in enumerate(definition.get("timeline", [])):
            path = f"{identifier}.timeline[{index}]"
            fields(entry, {"at_seconds", "at", "effect", "effects", "repeat", "condition", "rules"}, path)
            validate_timing(entry, path)
            if "repeat" in entry:
                repeat = entry["repeat"]
                fields(repeat, {"count", "interval_seconds", "rule", "parameters"}, f"{path}.repeat")
                count = repeat.get("count", 1)
                if not isinstance(count, int) or isinstance(count, bool) or not 0 < count <= 10000:
                    raise ContentError(f"{path}.repeat.count must be an integer in 1..10000")
                number(repeat.get("interval_seconds", 0), f"{path}.repeat.interval_seconds", 0)
            if "effect" not in entry and not entry.get("effects"):
                raise ContentError(f"{path}: timeline entry requires an implemented effect")
            if "effect" in entry:
                validate_effect(entry["effect"], f"{path}.effect", capabilities)
            for effect in entry.get("effects", []):
                validate_effect(effect, f"{path}.effects", capabilities)
    elif kind == "buff":
        if definition.get('capture') is not None:
            from ..domains.buff_capture import validate as validate_capture
            try:validate_capture(definition['capture'])
            except ValueError as error:raise ContentError(identifier+': '+str(error)) from error
        if definition.get('lifetime') is not None:
            from ..domains.buff_lifetime import validate
            try:validate(definition['lifetime'])
            except ValueError as error:raise ContentError(identifier+': '+str(error)) from error
        if "toggle" in definition:
            from ..domains.toggles import validate
            validate(definition["toggle"],identifier+".toggle")
        if "selection_flags" in definition:
            from ..domains.selection import validate_state
            validate_state(definition["selection_flags"], identifier+".selection_flags", contribution=True)
        for index, hook in enumerate(definition.get("damage_hooks", [])):
            location = f"{identifier}.damage_hooks[{index}]"
            fields(hook, {"phase", "rule", "condition", "samples", "group", "priority", "after_effects"}, location)
            if "group" in hook and (not isinstance(hook["group"], str) or not hook["group"]):
                raise ContentError(f"{location}.group: expected nonempty group name")
            if "priority" in hook:
                number(hook["priority"], f"{location}.priority")
            if hook.get("phase") not in {"before", "after", "receiver_request"} or not isinstance(hook.get("rule"), str):
                raise ContentError(f"{location}: phase and rule required")
            if 'after_effects' in hook:
                if hook['phase'] != 'receiver_request' or not isinstance(hook['after_effects'], (list, tuple)) or len(hook['after_effects']) > 32:
                    raise ContentError(location+': finite after_effects belong only to receiver_request')
                for child_index, child in enumerate(hook['after_effects']):
                    validate_effect(child, location+'.after_effects['+str(child_index)+']', capabilities)
                    if child.get('op') not in {'apply_buff', 'remove_buff', 'emit'} or child.get('target', 'selected') not in {'selected', 'target', 'source', 'self'}:
                        raise ContentError(location+': postmodifier effects are finite holder Buff/emit writes')
            if "condition" in hook and not isinstance(hook["condition"], str):
                raise ContentError(f"{location}.condition: expected expression")
            if "samples" in hook:
                fields(hook["samples"], {"stream", "count"}, f"{location}.samples")
                if not isinstance(hook["samples"].get("stream"), str) or not hook["samples"]["stream"]:
                    raise ContentError(f"{location}.samples.stream: explicit stream required")
                if type(hook["samples"].get("count", 1)) is not int or not 0 <= hook["samples"].get("count", 1) <= 100:
                    raise ContentError(f"{location}.samples.count: bounded integer required")
        if "contact_flags" in definition:
            flags=definition["contact_flags"]
            if not isinstance(flags,Mapping) or set(flags)!={"defer_fall"} or type(flags["defer_fall"]) is not bool:
                raise ContentError(identifier+": contact_flags requires explicit defer_fall boolean")
        if "movement_damage" in definition:
            fields(definition["movement_damage"], {"effect"}, f"{identifier}.movement_damage")
            effect = definition["movement_damage"].get("effect")
            if not isinstance(effect, Mapping) or effect.get("op") != "damage":
                raise ContentError(f"{identifier}.movement_damage: explicit damage effect required")
            validate_effect(effect, f"{identifier}.movement_damage.effect", capabilities)
            if not definition.get("interval_rule"):
                number(definition.get("interval_seconds"), f"{identifier}.interval_seconds", 0)
                if not definition["interval_seconds"]:
                    raise ContentError(f"{identifier}.movement_damage: positive sampling interval required")
        if "aura" in definition:
            aura = definition["aura"]
            fields(aura, {"selector", "buff", "lease_policy"}, f"{identifier}.aura")
            if not all(isinstance(aura.get(key), str) and aura[key].strip() for key in ("selector", "buff")):
                raise ContentError(f"{identifier}.aura: selector and buff references are required")
            if 'lease_policy' in aura:
                p=aura['lease_policy']
                if not isinstance(p,Mapping) or set(p)-{'mode','identity','source_binding','external_child_collision','owner_activity','modifier_stacks'} or not {'mode','identity','source_binding','external_child_collision'}<=set(p) or p['mode']!='shared' or p['identity']!=['definition','target'] or p['source_binding']!='oldest_live_lease' or p['external_child_collision']!='reject' or p.get('owner_activity','active_only') not in ('active_only','active_or_rebirth_waiting'):
                    raise ContentError(f"{identifier}.aura: explicit shared lease policy required")
                if 'modifier_stacks' in p:
                    m=p['modifier_stacks']
                    if not isinstance(m,Mapping) or set(m)!={'rule','maximum'} or not isinstance(m['rule'],str) or not m['rule'] or type(m['maximum']) is not int or not 1<=m['maximum']<=128:raise ContentError(identifier+': shared lease modifier stacks requires explicit rule and finite positive cap')
        control = definition.get("control", {})
        fields(control, {"move", "attack", "abilities", "block", "interrupt"}, f"{identifier}.control")
        if any(type(value) is not bool for value in control.values()):
            raise ContentError(f"{identifier}.control: flags must be booleans")
        for key in ("duration_seconds", "interval_seconds"):
            if key in definition:
                number(definition[key], f"{identifier}.{key}", 0)
        stacking = definition.get("stacking", {"mode": "refresh"})
        fields(stacking, {"mode", "identity", "max_stacks", "policy", "parameters", "rule"}, f"{identifier}.stacking")
        if "policy" in stacking:
            raise ContentError(f"{identifier}.stacking.policy: custom policy execution is unsupported")
        if stacking.get("mode") not in capabilities["stacking"] and "policy" not in stacking:
            raise ContentError(f"{identifier}: unsupported stacking mode {stacking.get('mode')!r}")
        for index, modifier in enumerate(definition.get("modifiers", [])):
            validate_modifier(modifier, f"{identifier}.modifiers[{index}]")
        for effect in definition.get("effects", []):
            validate_effect(effect, f"{identifier}.effects", capabilities)
        if not isinstance(definition.get("on_remove", []), (list, tuple)):
            raise ContentError(f"{identifier}.on_remove: expected effect list")
        for effect in definition.get("on_remove", []):
            validate_effect(effect, f"{identifier}.on_remove", capabilities)
        validate_events(definition.get("events", []), f"{identifier}.events", capabilities)
    elif kind == "attachment":
        from ..domains.attachments import validate_profile
        try: validate_profile(definition)
        except ValueError as error: raise ContentError(identifier+": "+str(error)) from error
        validate_effect(definition["effect"], identifier+".effect", capabilities)
    elif kind == "selector":
        flags = definition.get("exclude_abnormal_flags", [])
        if not isinstance(flags, (list, tuple)) or any(type(flag) is not int or not 0 <= flag < 46 for flag in flags):
            raise ContentError(identifier+": exclude_abnormal_flags requires typed enum values")
        if "eligibility" in definition:
            from ..domains.selection import validate_eligibility
            validate_eligibility(definition["eligibility"], identifier+".eligibility")
        if "limit" in definition and "limit_attribute" in definition:
            raise ContentError(f"{identifier}: limit and limit_attribute are mutually exclusive")
        if definition.get("limit") is not None and (type(definition["limit"]) is not int or definition["limit"] < 0):
            raise ContentError(f"{identifier}.limit: expected nonnegative integer")
        if "limit_attribute" in definition and (not isinstance(definition["limit_attribute"], str) or not definition["limit_attribute"].strip()):
            raise ContentError(f"{identifier}.limit_attribute: expected attribute name")
        region = definition.get("region", {})
        fields(region, {"type", "offsets", "rotate_with_facing", "radius", "range", "provider", "parameters", "blocked_only"}, f"{identifier}.region")
        if definition.get("provider", "ark.selector.grid") == "ark.selector.grid":
            if region.get("type", "grid_offsets") not in {"grid_offsets", "all", "radius", "circle", "manhattan"}:
                raise ContentError(f"{identifier}.region.type: unsupported built-in region {region.get('type')!r}")
            if region.get("type") in {"radius", "circle", "manhattan"}:
                number(region.get("radius"), f"{identifier}.region.radius", 0)
        for index, restriction in enumerate(definition.get("filters", [])):
            fields(restriction, {"tag", "state", "owner", "field"}, f"{identifier}.filters[{index}]")
            if "field" in restriction:
                spec = restriction["field"]
                fields(spec, {"scope", "path", "equals", "bits_any", "default"}, f"{identifier}.filters[{index}].field")
                if spec.get("scope", "runtime") not in {"runtime", "definition"}:
                    raise ContentError(f"{identifier}.filters[{index}].field.scope: runtime or definition required")
                path = spec.get("path")
                if not isinstance(path, (list, tuple)) or not path or any(not ((isinstance(k,str) and k) or (type(k) is int and k >= 0)) for k in path):
                    raise ContentError(f"{identifier}.filters[{index}].field.path: nonempty mapping/list path required")
                if ("equals" in spec) == ("bits_any" in spec):
                    raise ContentError(f"{identifier}.filters[{index}].field: exactly one equals or bits_any operation required")
                if "bits_any" in spec and (type(spec["bits_any"]) is not int or spec["bits_any"] < 0):
                    raise ContentError(f"{identifier}.filters[{index}].field.bits_any: nonnegative integer mask required")
                for key in ("equals", "default"):
                    if key in spec and spec[key] is not None and type(spec[key]) not in (str, bool, int, float):
                        raise ContentError(f"{identifier}.filters[{index}].field.{key}: scalar value required")
                    if key in spec and type(spec[key]) in (int, float):
                        number(spec[key], f"{identifier}.filters[{index}].field.{key}")
            if "owner" in restriction and restriction["owner"] != "source":
                raise ContentError(f"{identifier}.filters[{index}].owner: expected source")
            if "state" in restriction and restriction["state"] != "alive":
                raise ContentError(f"{identifier}.filters[{index}].state: only alive filtering is implemented")
        for offset in region.get("offsets", []):
            if not isinstance(offset, (list, tuple)) or len(offset) != 2 or not all(isinstance(x, (int, float)) for x in offset):
                raise ContentError(f"{identifier}.region.offsets must contain coordinate pairs")
    elif kind == "ruleset":
        if "quantum" not in definition:
            raise ContentError(f"{identifier}.quantum must be explicitly declared or inherited from a preset")
        number(definition["quantum"], f"{identifier}.quantum", 0)
        if definition["quantum"] == 0:
            raise ContentError(f"{identifier}.quantum must be positive")
        if not isinstance(definition.get("bindings", {}), Mapping):
            raise ContentError(f"{identifier}.bindings must be an object")
    elif kind in {"calculation_rule", "rule"}:
        bindings = definition.get("metadata", {}).get("input_bindings", {})
        if not isinstance(bindings, Mapping):
            raise ContentError(f"{identifier}.metadata.input_bindings must be a map")
        for name, binding in bindings.items():
            path = f"{identifier}.metadata.input_bindings.{name}"
            fields(binding, {"entity", "attribute_role", "attribute"}, path)
            if binding.get("entity") not in {"source", "target"}:
                raise ContentError(f"{path}.entity must be source or target")
            if not isinstance(binding.get("attribute", binding.get("attribute_role")), str):
                raise ContentError(f"{path}: declare an attribute or attribute_role")
    elif kind == "behavior":
        if definition.get('decision'):
            from ark_sim.domains.behavior_decision import validate_config
            try:validate_config(definition['decision'])
            except ValueError as error:raise ContentError(identifier+': '+str(error)) from error
        if not definition.get("provider") and not definition.get("implementation"):
            states = definition.get("states")
            if not isinstance(states, Mapping) or not states:
                raise ContentError(f"{identifier}: behavior requires an implemented provider or nonempty state graph")
            initial = definition.get("initial_state", definition.get("initial"))
            if initial not in states:
                raise ContentError(f"{identifier}: initial state is absent from graph")
            for name, state in states.items():
                fields(state, {"on_enter", "on_exit"}, f"{identifier}.states.{name}")
                for key in ("on_enter", "on_exit"):
                    if not isinstance(state.get(key, []), (list, tuple)):
                        raise ContentError(f"{identifier}.states.{name}.{key} must be an effect list")
                    for effect in state.get(key, []):
                        validate_effect(effect, f"{identifier}.states.{name}.{key}", capabilities)
            transitions = definition.get("transitions", [])
            if not isinstance(transitions, (list, tuple)):
                raise ContentError(f"{identifier}.transitions must be a list")
            for index, transition in enumerate(transitions):
                path = f"{identifier}.transitions[{index}]"
                fields(transition, {"from", "to", "condition", "condition_rule", "priority", "effects", "parameters"}, path)
                if transition.get("from") not in states and transition.get("from") != "*":
                    raise ContentError(f"{path}.from references an unknown state")
                if transition.get("to") not in states:
                    raise ContentError(f"{path}.to references an unknown state")
                if "condition" in transition and not isinstance(transition["condition"], str):
                    raise ContentError(f"{path}.condition must be an expression string")
                number(transition.get("priority", 0), f"{path}.priority")
                for effect in transition.get("effects", []):
                    validate_effect(effect, f"{path}.effects", capabilities)
    elif kind == "scenario":
        if 'cards' in definition:
            cards=definition['cards']
            if (not isinstance(cards,(list,tuple)) or len(cards)>128
                or any(type(x) is not str or not x for x in cards) or len(cards)!=len(set(cards))):
                raise ContentError(identifier+': cards requires finite unique entity IDs')
            if set(cards)&set(definition.get('roster',[])):
                raise ContentError(identifier+': cards and selected roster must be disjoint')
        if definition.get("branches") is not None:
            from ..domains.branches import validate as validate_branches
            validate_branches(definition["branches"],lambda e:validate_effect(e,identifier+".branches",capabilities))
        aliases = {"system/battle"}

        def reserve_alias(alias, path):
            if alias is None:
                return
            if isinstance(alias, str) and alias.startswith("control/") and any(a.get("kind") == "control" for w in definition.get("timeline", {}).get("waves", []) for f in w["fragments"] for a in f["actions"]):
                raise ContentError(f"{path}: control/ is reserved for runtime control IDs")
            if not isinstance(alias, str) or not alias:
                raise ContentError(f"{path}: expected a nonempty instance alias")
            if alias in aliases:
                raise ContentError(f"{identifier}: duplicate instance alias {alias} at {path}")
            aliases.add(alias)
        map_definition = definition.get("map")
        if map_definition is not None:
            validate_map(map_definition, f"{identifier}.map")
        if "timeline" in definition:
            if definition.get("waves"):
                raise ContentError(f"{identifier}: timeline and flat waves are mutually exclusive")
            from .timeline_validation import validate_timeline
            validate_timeline(definition["timeline"], f"{identifier}.timeline", map_definition, capabilities)
        for index, entry in enumerate(definition.get("scheduledEffects", [])):
            path = f"{identifier}.scheduledEffects[{index}]"
            fields(entry, {"at", "at_seconds", "effect", "metadata"}, path)
            validate_timing(entry, path)
            validate_effect(entry.get("effect"), f"{path}.effect", capabilities)
        registration_keys = set()
        for index, entity in enumerate(definition.get("initialEntities", [])):
            path = f"{identifier}.initialEntities[{index}]"
            fields(entity, {"definition", "instanceAlias", "position", "facing", "components", "rules", "tags", "deployed", "route", "parameters", "active", "registration_key", "reactivation"}, path)
            if not isinstance(entity.get("definition"), (str, Mapping)):
                raise ContentError(f"{path}.definition is required")
            if entity.get('reactivation') is not None:
                from ..domains.predefined_reactivation import validate
                try:validate(entity['reactivation'])
                except ValueError as error:raise ContentError(path+': '+str(error)) from error
                if entity.get('active',True) is not False or not entity.get('registration_key') or entity.get('instanceAlias') is not None:
                    raise ContentError(path+': reusablepredefine requires dormant registered actor without instancealias')
            if 'active' in entity and type(entity['active']) is not bool:
                raise ContentError(f"{path}.active: boolean required")
            if entity.get('active', True) is False and type(entity.get('deployed', False)) is not bool:
                raise ContentError(f"{path}.deployed: dormant deployment state must be boolean")
            if 'registration_key' in entity:
                key = entity['registration_key']
                if not isinstance(key, str) or not key or key in registration_keys:
                    raise ContentError(f"{path}.registration_key: unique nonempty key required")
                registration_keys.add(key)
            if entity.get('active', True) is False and not entity.get('registration_key'):
                raise ContentError(f"{path}: dormant initial entity requires registration key")
            if "route" in entity:
                validate_route(entity["route"], f"{path}.route", map_definition)
            if "position" in entity:
                validate_position(entity["position"], f"{path}.position", map_definition)
            spatial = entity.get("components", {}).get("spatial", {})
            if "route_motion_mode" in spatial and ("motion_mode" not in spatial or type(spatial["route_motion_mode"]) is not int or spatial["route_motion_mode"] not in (0,1)):
                raise ContentError("route_motion_mode requires explicit valid motion_mode and WALK0/FLY1 route mode")
            if "motion_mode" in spatial and (type(spatial["motion_mode"]) is not int or spatial["motion_mode"] not in (0,1)):
                raise ContentError(path+": explicit spatial motion mode WALK0/FLY1 required")
            if "route" in spatial:
                validate_route(spatial["route"], f"{path}.components.spatial.route", map_definition)
            alias = entity.get("instanceAlias")
            reserve_alias(alias, f"{path}.instanceAlias")
        for command in definition.get("commands", []):
            fields(command, {"at_seconds", "at", "action", "type", "source", "entity", "ability", "definition", "position", "row", "col", "facing", "instanceAlias", "alias", "payload", "resource", "delta", "target", "parameters", "components", "tags", "control", "step"}, f"{identifier}.commands")
            if command.get("action", command.get("type")) == "control_ack":
                fields(command, {"at_seconds", "at", "action", "type", "control", "step"}, f"{identifier}.commands.control_ack")
                if (not isinstance(command.get("control"), str) or not command["control"] or type(command.get("step")) is not int
                        or command["step"] < 0 or command.get("type", "control_ack") != "control_ack"):
                    raise ContentError(f"{identifier}.commands.control_ack: exact control reference and nonnegative integer step required")
            validate_timing(command, f"{identifier}.commands")
        for name, spec in definition.get("resources", {}).items():
            fields(spec, RESOURCE_FIELDS, f"{identifier}.resources.{name}")
            validate_recovery(spec, f"{identifier}.resources.{name}")
        for index, wave in enumerate(definition.get("waves", [])):
            path = f"{identifier}.waves[{index}]"
            fields(wave, {"at_seconds", "at", "definition", "position", "placement", "route", "route_id", "instanceAlias", "facing", "components", "tags", "rules", "parameters", "count", "interval_seconds"}, path)
            validate_timing(wave, path)
            if "placement" in wave:
                placement = wave["placement"]
                fields(placement, {"rule", "stream", "sample_axes", "sample_zero_range", "random_range", "offset"}, f"{path}.placement")
                if not isinstance(placement.get("rule"), str) or not placement["rule"]:
                    raise ContentError(f"{path}.placement.rule: explicit calculation rule required")
                if not isinstance(placement.get("stream"), str) or not placement["stream"]:
                    raise ContentError(f"{path}.placement.stream: explicit random stream required")
                axes = placement.get("sample_axes")
                if not isinstance(axes, (list, tuple)) or len(set(axes)) != len(axes) or set(axes) != {"row", "col"}:
                    raise ContentError(f"{path}.placement.sample_axes: declare row and col exactly once in sampling order")
                if type(placement.get("sample_zero_range", False)) is not bool:
                    raise ContentError(f"{path}.placement.sample_zero_range: boolean required")
                for field in ("random_range", "offset"):
                    validate_position(placement.get(field), f"{path}.placement.{field}")
                for axis, value in placement["random_range"].items():
                    number(value, f"{path}.placement.random_range.{axis}", 0)
                if "position" not in wave:
                    raise ContentError(f"{path}.position: placement requires an explicit anchor")
            if "route_id" in wave:
                raise ContentError(f"{path}.route_id: route ID resolution is unsupported; use an inline route")
            if "count" in wave and (type(wave["count"]) is not int or wave["count"] != 1):
                raise ContentError(f"{path}.count: one absolute wave entry supports exactly one instance; expand entries explicitly")
            if "interval_seconds" in wave:
                number(wave["interval_seconds"], f"{path}.interval_seconds", 0)
                if wave["interval_seconds"] != 0:
                    raise ContentError(f"{path}.interval_seconds: repeated wave scheduling is unsupported; expand entries explicitly")
            if "definition" not in wave:
                raise ContentError(f"{path}.definition is required for an absolute spawn wave")
            if "route" in wave:
                validate_route(wave["route"], f"{path}.route", map_definition)
            if "position" in wave:
                validate_position(wave["position"], f"{path}.position", map_definition)
            spatial = wave.get("components", {}).get("spatial", {})
            if "route_motion_mode" in spatial and ("motion_mode" not in spatial or type(spatial["route_motion_mode"]) is not int or spatial["route_motion_mode"] not in (0,1)):
                raise ContentError("route_motion_mode requires explicit valid motion_mode and WALK0/FLY1 route mode")
            if "motion_mode" in spatial and (type(spatial["motion_mode"]) is not int or spatial["motion_mode"] not in (0,1)):
                raise ContentError(path+": explicit spatial motion mode WALK0/FLY1 required")
            if "route" in spatial:
                validate_route(spatial["route"], f"{path}.components.spatial.route", map_definition)
            reserve_alias(wave.get("instanceAlias"), f"{path}.instanceAlias")
        for wi, wave in enumerate(definition.get("timeline", {}).get("waves", [])):
            for fi, fragment in enumerate(wave["fragments"]):
                for ai, action in enumerate(fragment["actions"]):
                    if action["kind"] not in {"spawn", "control"}:
                        continue
                    path = f"{identifier}.timeline.waves[{wi}].fragments[{fi}].actions[{ai}].instanceAlias"
                    alias = (action["spawn"] if action["kind"] == "spawn" else action).get("instanceAlias")
                    if alias is None:
                        continue
                    if not isinstance(alias, str) or not alias:
                        reserve_alias(alias, path)
                    count = action.get("count", 1)
                    for repeat in range(count):
                        reserve_alias(f"{alias}/{repeat}" if count > 1 else alias, path)
    return definition


def validate_recovery(spec, path):
    exact_abilities(spec.get("recovery_freeze_abilities"), path+".recovery_freeze_abilities", "recovery_freeze_abilities" in spec)
    if "recovery_freeze_rule" in spec and (not isinstance(spec["recovery_freeze_rule"], str) or not spec["recovery_freeze_rule"]):
        raise ContentError(f"{path}.recovery_freeze_rule: exact calculation rule ID required")
    if "recovery" in spec:
        driver = spec["recovery"]
        fields(driver, {"mode", "interval_seconds", "event", "owner_role", "amount", "condition", "selector", "empty_value", "selector_interval_seconds", "interrupt_when_empty", "interrupt_abilities", "interrupt_cast_modes"}, f"{path}.recovery")
        exact_abilities(driver.get("interrupt_abilities"), path+".recovery.interrupt_abilities", "interrupt_abilities" in driver)
        if "interrupt_cast_modes" in driver:
            modes = driver["interrupt_cast_modes"]
            if not isinstance(modes, (list, tuple)) or any(m not in {"manual", "passive", "automatic_attack", "on_deploy"} for m in modes):
                raise ContentError(f"{path}.recovery.interrupt_cast_modes: explicit supported activation mode list required")
        if ("interrupt_abilities" in driver or "interrupt_cast_modes" in driver) and (not driver.get("selector") or driver.get("interrupt_when_empty") is not True):
            raise ContentError(f"{path}.recovery: interrupt filters require selector and interrupt_when_empty=true")
        if "selector" in driver:
            if not isinstance(driver["selector"], str) or not driver["selector"]:
                raise ContentError(f"{path}.recovery.selector: expected selector ID")
            if "empty_value" in driver:
                number(driver["empty_value"], f"{path}.recovery.empty_value")
            number(driver.get("selector_interval_seconds", 0), f"{path}.recovery.selector_interval_seconds", 0)
            if "interrupt_when_empty" in driver and type(driver["interrupt_when_empty"]) is not bool:
                raise ContentError(f"{path}.recovery.interrupt_when_empty: boolean required")
        elif any(k in driver for k in ("empty_value", "selector_interval_seconds", "interrupt_when_empty")):
            raise ContentError(f"{path}.recovery: selector gate options require a selector")
        mode = driver.get("mode", "continuous")
        if mode not in {"continuous", "periodic", "event"}:
            raise ContentError(f"{path}.recovery.mode: unsupported recovery driver {mode!r}")
        if mode == "event":
            if "interval_seconds" in driver or not isinstance(driver.get("event"), str) or not driver["event"]:
                raise ContentError(f"{path}.recovery: event driver requires an event and no interval")
            if driver.get("owner_role", "source") not in ("source", "target", "any"):
                raise ContentError(f"{path}.recovery.owner_role: expected source, target or any")
            number(driver.get("amount", 1), f"{path}.recovery.amount")
            if "condition" in driver and not isinstance(driver["condition"], str):
                raise ContentError(f"{path}.recovery.condition: expected expression string")
            if not isinstance(spec.get("recovery_rule"), str):
                raise ContentError(f"{path}.recovery: event driver requires explicit resource.recovery rule")
        elif any(key in driver for key in ("event", "owner_role", "amount", "condition")):
            raise ContentError(f"{path}.recovery: event fields require event mode")
        elif mode == "periodic":
            number(driver.get("interval_seconds"), f"{path}.recovery.interval_seconds", 0)
            if driver["interval_seconds"] <= 0:
                raise ContentError(f"{path}.recovery.interval_seconds must be positive")
        elif "interval_seconds" in driver:
            raise ContentError(f"{path}.recovery: continuous driver does not accept interval_seconds")
    parameters = spec.get("parameters", {})
    if not isinstance(parameters, Mapping):
        raise ContentError(f"{path}.parameters: expected an object")
    for field in ("pause_at_full", "freeze_while_cast"):
        if field in parameters and not isinstance(parameters[field], bool):
            raise ContentError(f"{path}.parameters.{field}: expected a boolean")


def exact_abilities(value, path, present):
    if present and (not isinstance(value, (list, tuple)) or any(not isinstance(v, str) or not v for v in value) or len(set(value)) != len(value)):
        raise ContentError(f"{path}: unique exact ability ID list required (may be empty)")
