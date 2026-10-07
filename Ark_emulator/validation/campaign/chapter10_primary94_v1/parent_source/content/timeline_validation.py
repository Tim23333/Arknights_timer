"""Strict action timeline schema, independent of source-game field names."""
from collections.abc import Mapping
from .repository import ContentError


def validate_timeline(value, path, map_definition, capabilities):
    from .schemas import fields, number, validate_effect, validate_definition
    fields(value, {"policy", "negative_timeout_policy", "waves", "metadata"}, path)
    if value.get("policy") not in {"managed_clear", "time_only"}:
        raise ContentError(f"{path}.policy: explicit managed_clear or time_only required")
    if value.get("negative_timeout_policy") not in {"wait_for_clear", "skip_wait"}:
        raise ContentError(f"{path}.negative_timeout_policy: explicit policy required")
    if not isinstance(value.get("waves"), (list, tuple)):
        raise ContentError(f"{path}.waves: expected a list")
    for wi, wave in enumerate(value["waves"]):
        wp = f"{path}.waves[{wi}]"
        fields(wave, {"pre_delay_seconds", "post_delay_seconds", "max_wait_seconds", "fragments", "metadata"}, wp)
        for field in ("pre_delay_seconds", "post_delay_seconds"):
            number(wave.get(field, 0), f"{wp}.{field}", 0)
        timeout = wave.get("max_wait_seconds", -1)
        number(timeout, f"{wp}.max_wait_seconds")
        if timeout < 0 and timeout != -1:
            raise ContentError(f"{wp}.max_wait_seconds: only -1 is an allowed negative sentinel")
        if not isinstance(wave.get("fragments"), (list, tuple)):
            raise ContentError(f"{wp}.fragments: expected a list")
        for fi, fragment in enumerate(wave["fragments"]):
            fp = f"{wp}.fragments[{fi}]"
            fields(fragment, {"pre_delay_seconds", "actions", "metadata"}, fp)
            number(fragment.get("pre_delay_seconds", 0), f"{fp}.pre_delay_seconds", 0)
            if not isinstance(fragment.get("actions"), (list, tuple)):
                raise ContentError(f"{fp}.actions: expected a list")
            for ai, action in enumerate(fragment["actions"]):
                ap = f"{fp}.actions[{ai}]"
                fields(action, {"kind", "delay_seconds", "interval_seconds", "count", "managed", "blocks_wave", "blocks_fragment", "spawn", "effects", "metadata", "definition", "instanceAlias"}, ap)
                if action.get("kind") not in {"spawn", "effects", "control"}:
                    raise ContentError(f"{ap}.kind: expected spawn/effects/control")
                count = action.get("count", 1)
                if type(count) is not int or not 0 <= count <= 10000:
                    raise ContentError(f"{ap}.count: expected nonnegative bounded integer")
                for field in ("delay_seconds", "interval_seconds"):
                    number(action.get(field, 0), f"{ap}.{field}", 0)
                for flag in ("managed", "blocks_wave", "blocks_fragment"):
                    if flag in action and type(action[flag]) is not bool:
                        raise ContentError(f"{ap}.{flag}: boolean required")
                if action["kind"] != "control" and ("definition" in action or "instanceAlias" in action):
                    raise ContentError(f"{ap}: control fields require control action kind")
                if action["kind"] == "control":
                    if "spawn" in action or "effects" in action or not isinstance(action.get("definition"), str) or not action["definition"]:
                        raise ContentError(f"{ap}: control requires exact definition and no spawn/effects")
                    if not action.get("managed", True) and (action.get("blocks_wave", True) or action.get("blocks_fragment", False)):
                        raise ContentError(f"{ap}: unmanaged control cannot block wave or fragment")
                elif action["kind"] == "spawn":
                    if "effects" in action:
                        raise ContentError(f"{ap}: spawn and effects are mutually exclusive")
                    spawn = action.get("spawn")
                    if not isinstance(spawn, Mapping) or "at" in spawn or "at_seconds" in spawn:
                        raise ContentError(f"{ap}.spawn: relative action must contain one untimed spawn object")
                    if not action.get("managed", True) and (action.get("blocks_wave", True) or action.get("blocks_fragment", False)):
                        raise ContentError(f"{ap}: unmanaged spawn cannot block wave or fragment")
                    validate_definition({"id": "scenario/timeline_spawn_validation", "kind": "scenario",
                        "map": map_definition, "waves": [spawn]}, capabilities)
                else:
                    if "spawn" in action or any(action.get(flag, False) for flag in ("managed", "blocks_wave", "blocks_fragment")):
                        raise ContentError(f"{ap}: synchronous effects cannot hold managed membership")
                    if not isinstance(action.get("effects"), (list, tuple)):
                        raise ContentError(f"{ap}.effects: expected list")
                    for ei, effect in enumerate(action["effects"]):
                        validate_effect(effect, f"{ap}.effects[{ei}]", capabilities)
