"""Required calculations follow active content and its explicit rule scopes."""
from collections.abc import Mapping
from .repository import ContentError


def capability_preflight(scenario, definitions, ruleset, rules, catalog=None):
    global_scopes = [ruleset.get("bindings", {}), scenario.get("rules", {})]
    requirements = []
    for ident,definition in definitions.items():
        spec=definition.get("components",{}).get("route_obstacle")
        if spec is not None:
            rule=rules.get(spec["rule"])
            if rule is None or rule.get("contract")!="blocking.obstacle":raise ContentError(ident+": obstacle rule must implement blocking.obstacle")
            requirements.append({"calculation":"blocking.obstacle","rule":spec["rule"],"required_by":ident+".route_obstacle"})
    for ident,definition in definitions.items():
        if definition.get("kind")=="buff":
            for key in ("active_rule","control_rule"):
                if key in definition:
                    rule=rules.get(definition[key])
                    if rule is None or rule.get("contract")!="buff.applicability":raise ContentError(ident+": applicability rule must implement buff.applicability")
                    requirements.append({"calculation":"buff.applicability","rule":definition[key],"required_by":ident+"."+key})
    entity_binding_ids = {id(definition["rules"]) for definition in definitions.values()
                          if definition.get("kind") == "entity" and "rules" in definition}

    def require(calculation, path, scopes=(), explicit=None):
        chosen = explicit
        if chosen is None:
            candidates = global_scopes if calculation == "time.quantize" else [*global_scopes, *scopes]
            owner = (catalog or {}).get("contracts", {}).get(calculation, {}).get("owner", "owner")
            for scope in candidates:
                if id(scope) in entity_binding_ids and owner in {"scenario", "ability", "effect"}:
                    continue
                if calculation in scope:
                    chosen = scope[calculation]
        if chosen is None:
            raise ContentError(f"{path}: required calculation {calculation} has no rule binding")
        if chosen not in rules or rules[chosen].get("contract") != calculation:
            raise ContentError(f"{path}: required calculation {calculation} is bound to incompatible rule {chosen}")
        requirements.append({"calculation": calculation, "rule": chosen, "required_by": path})

    def resources(values, path, scopes):
        for name, spec in values.items():
            local = [*scopes, spec.get("rules", {})]
            if spec.get("recovery_freeze_rule") or "resource.recovery_freeze" in spec.get("rules", {}):
                require("resource.recovery_freeze", f"{path}.{name}", local, spec.get("recovery_freeze_rule"))
            for calculation, field in (("resource.capacity", "capacity_rule"), ("resource.bounds", "bounds_rule")):
                require(calculation, f"{path}.{name}", local, spec.get(field))
            if spec.get("capacity_change_rule") or "capacity_change_mode" in spec.get("parameters", {}):
                require("resource.capacity_change", f"{path}.{name}", local, spec.get("capacity_change_rule"))
            if "recovery_rule" in spec or "recovery_rate" in spec or "recovery" in spec or "resource.recovery" in spec.get("rules", {}):
                require("resource.recovery", f"{path}.{name}", local, spec.get("recovery_rule"))
            if spec.get("recovery", {}).get("mode") == "periodic":
                require("time.quantize", f"{path}.{name}.recovery")

    for _id, _definition in definitions.items():
        if _definition.get("kind") == "buff" and _definition.get("toggle"):
            spec=_definition["toggle"];require("passive.toggle",_id+".toggle",explicit=spec["rule"])
            child=definitions[spec["buff"]]
            if child.get("kind") != "buff" or child.get("duration_seconds") is not None or child.get("duration_rule") or child.get("toggle") or child.get("stacking",{}).get("mode") != "independent":raise ContentError(_id+": toggle child requires permanent independent non-toggle Buff")
        if _definition.get("kind") == "entity" and _definition.get("rules",{}).get("targeting.availability"):
            require("targeting.availability",_id+".rules",explicit=_definition["rules"]["targeting.availability"])
        if _definition.get("kind") == "selector" and _definition.get("eligibility"):
            require("targeting.eligibility", _id+".eligibility", explicit=_definition["eligibility"]["rule"])
        if _definition.get("kind") == "entity" and "selection_state" in _definition.get("components", {}):
            from ..domains.selection import validate_state
            validate_state(_definition["components"]["selection_state"], _id+".selection_state")

    selectors_seen = set()
    def selector(identifier, path, scopes):
        if not identifier:
            return
        selectors_seen.add(identifier)
        require("targeting.score", path, scopes)
        require("targeting.selection", path, scopes)

    def effect(item, path, scopes):
        local = [*scopes, item.get("rules", {})]
        if item.get("op") == "area" and item.get("membership_rule"):
            require("area.members", path+".membership_rule", explicit=item["membership_rule"])
            member_rule = definitions[item["membership_rule"]]
            if member_rule["implementation"].get("provider") == "ark.area.qualified_cell_offsets":
                from ..domains.qualified_areas import validate_parameters
                options = {**member_rule.get("parameters", {}), **item.get("parameters", {})}
                try:validate_parameters(options)
                except ValueError as error:raise ContentError(path+": "+str(error)) from error
                require("targeting.eligibility", path+".eligibility", explicit=options["eligibility"]["rule"])
        if item.get("projectile_definition"):
            projectile=definitions[item["projectile_definition"]]
            if projectile.get("kind") != "projectile": raise ContentError(path+": projectile reference kind required")
            require("time.quantize", path)

        op = item.get("op")
        if op == "apply_terrain_overlay":
            require("terrain.tile_options", path, (), item.get("parameters", {}).get("rule"))
            if "position" in item.get("parameters", {}):
                overlay_position(item["parameters"]["position"], path)
        if op == "damage":
            require("damage.pipeline", path, local)
        elif op in ("heal", "regenerate"):
            require("healing.base", path, local)
        elif op == "schedule":
            require("time.quantize", path, local)
        elif op == "push":
            require("movement.displacement", path, local)
            require("movement.distance", path, local)
            require("time.quantize", path, local)
        elif op == "random":
            require("random.check", path, local)
        if item.get("amount_rule"):
            require("resource.recovery", path, local, item["amount_rule"])
        if item.get("selector"):
            selector(item["selector"], path, local)
        for key in ("on_success", "on_failure", "effects"):
            for index, child in enumerate(item.get(key, [])):
                effect(child, f"{path}.{key}[{index}]", local)

    def control_effect(item, path):
        """Controls use the nonspatial battle source, without fabricated stats."""
        if item.get("projectile_definition"): raise ContentError(path+": projectile launch requires actor spatial source")
        if item.get("selector"):
            selected = definitions[item["selector"]]
            if selected.get("region", {}).get("type") != "all":
                raise ContentError(f"{path}.selector: control effect requires explicit spatial origin; only nonspatial all is supported")
        op = item.get("op")
        if op in {"apply_terrain_overlay", "remove_terrain_overlay"} and item.get("target", "selected") in {"source", "self", "battle", "owner"}:
            raise ContentError(f"{path}: control terrain layers require selected actors or an explicit actor ID")
        if op in {"retire", "apply_terrain_overlay", "remove_terrain_overlay"} and not item.get("selector") and item.get("target", "selected") in {"selected", "self", "source", "battle", "owner"}:
            raise ContentError(f"{path}: control retirement requires an explicit actor target or nonspatial selector")
        if op in {"heal", "regenerate", "push"}:
            raise ContentError(f"{path}: control {op} requires actor source attributes/origin")
        if op in {"move", "area"} and (item.get("target") in {"source", "battle"} or not item.get("selector") or item.get("center") == "source"):
            raise ContentError(f"{path}: control {op} requires explicit actor spatial origin/target")
        if op == "damage":
            chosen = None
            for scope in [*global_scopes, item.get("rules", {})]:
                chosen = scope.get("damage.pipeline", chosen)
            if chosen is not None:
                bindings = rules[chosen].get("metadata", {}).get("input_bindings", {})
                if any(binding.get("entity") == "source" for binding in bindings.values()):
                    raise ContentError(f"{path}: control damage pipeline requires actor source attributes; bind an explicit source-independent pipeline")
        for key in ("on_success", "on_failure", "effects"):
            for index, child in enumerate(item.get(key, [])): control_effect(child, f"{path}.{key}[{index}]")
        if "effect" in item:
            effect(item["effect"], f"{path}.effect", local)

    def events(subscriptions, path, scopes):
        for index, subscription in enumerate(subscriptions):
            for child_index, child in enumerate(subscription.get("effects", [])):
                effect(child, f"{path}[{index}].effects[{child_index}]", scopes)

    abilities_seen = set()
    def ability(identifier, path, scopes):
        abilities_seen.add(identifier)
        definition = definitions[identifier]
        local = [*scopes, definition.get("rules", {})]
        for calculation in ("time.quantize", "ability.windup", "ability.repeat", "ability.duration", "ability.recovery"):
            require(calculation, path, local)
        activation = definition.get("activation", {})
        for index, child in enumerate(activation.get("on_start", ())):
            effect(child, f"{path}.activation.on_start[{index}]", local)
        parameters = {**definition.get("parameters", {}), **activation.get("parameters", {})}
        if activation.get("mode") == "automatic_attack" or parameters.get("replace_attack"):
            require("time.interval", path, local, activation.get("interval_rule"))
        for cost in activation.get("costs", []):
            require("resource.cost", path, local, cost.get("rule"))
        selector(definition.get("selector"), path, local)
        for index, entry in enumerate(definition.get("timeline", [])):
            for child in ([entry["effect"]] if "effect" in entry else entry.get("effects", [])):
                effect(child, f"{path}.timeline[{index}]", local)
        events(definition.get("events", []), f"{path}.events", local)

    def route(path, scopes, definition=None):
        definition = definition or {}
        if definition.get("transition_policy"):
            require("movement.transition", path+".transition_policy", scopes, definition["transition_policy"]["rule"])
        if definition.get("reach_offset_policy"):
            require("movement.checkpoint_position", path+".reach_offset_policy", scopes, definition["reach_offset_policy"]["rule"])
        for calculation in ("time.quantize", "movement.path", "movement.speed", "movement.distance",
                            "blocking.eligibility", "blocking.capacity", "blocking.occupancy", "lifecycle.leak_loss"):
            require(calculation, path, scopes)
        for index, checkpoint in enumerate((definition or {}).get("checkpoints") or []):
            kind = checkpoint.get("type", 0)
            if isinstance(kind, Mapping):
                kind = kind.get("value", kind.get("name"))
            if kind in (1, 2, 3, 4, "WAIT_FOR_SECONDS", "WAIT_FOR_PLAY_TIME", "WAIT_CURRENT_FRAGMENT_TIME", "WAIT_CURRENT_WAVE_TIME"):
                require("movement.wait_deadline", f"{path}.checkpoints[{index}]", scopes, checkpoint.get("deadline_rule"))

    def deploy(path, scopes):
        for calculation in ("time.quantize", "deploy.cost", "deploy.refund", "deploy.cooldown", "deploy.capacity", "deploy.eligibility"):
            require(calculation, path, scopes)

    def captured_origins(item, path):
        entity = definitions[item["definition"]]
        spatial = entity.get("components", {}).get("spatial", {})
        overrides = item.get("components", {}).get("spatial", {})
        actual_route = item.get("route", overrides.get("route", spatial.get("route")))
        origins = {**spatial.get("timing_origins", {}), **overrides.get("timing_origins", {}),
                   **item.get("parameters", {}).get("timing_origins", {})}
        for index, checkpoint in enumerate((actual_route or {}).get("checkpoints") or []):
            kind = checkpoint.get("type", 0)
            if isinstance(kind, Mapping):
                kind = kind.get("value", kind.get("name"))
            key = "fragment_start" if kind in (3, "WAIT_CURRENT_FRAGMENT_TIME") else "wave_start" if kind in (4, "WAIT_CURRENT_WAVE_TIME") else None
            if key and (type(origins.get(key)) is not int or origins[key] < 0):
                raise ContentError(f"{path}.checkpoints[{index}]: deadline requires captured {key} origin")

    def instance_route(item, path):
        entity = definitions[item["definition"]]
        spatial = entity.get("components", {}).get("spatial", {})
        overrides = item.get("components", {}).get("spatial", {})
        actual = item.get("route", overrides.get("route", spatial.get("route")))
        if actual:
            scopes = [*entity_scopes.get(item["definition"], []), item.get("rules", {}),
                      spatial.get("rules", {}), overrides.get("rules", {})]
            route(path, scopes, actual)

    def overlay_position(position, path):
        geometry = scenario.get("map", {"rows": 1, "cols": 1})
        if (not isinstance(position, Mapping) or set(position) != {"row", "col"} or
                any(type(position[a]) is not int or not 0 <= position[a] < geometry[n]
                    for a, n in (("row", "rows"), ("col", "cols")))):
            raise ContentError(f"{path}: terrain overlays require an integer cell inside scenario map")

    def overlay_instance(item, path):
        definition = definitions[item["definition"]]
        merged = {**definition.get("components", {}), **item.get("components", {})}
        if merged.get("terrain_overlays"):
            from ark_sim.domains.terrain import validate_spec
            for overlay in merged["terrain_overlays"]:
                try: validate_spec(overlay)
                except (TypeError, ValueError) as error: raise ContentError(f"{path}: {error}") from error
                require("terrain.tile_options", path, (), overlay.get("rule"))
            overlay_position(item.get("position", merged.get("spatial", {}).get("position", {"row": 0, "col": 0})), path)
            placement = item.get("placement", {})
            if any(placement.get("random_range", {}).values()) or any(placement.get("offset", {}).values()):
                raise ContentError(f"{path}: terrain owner placement must resolve to an explicitly integer cell")

    entity_scopes = {}
    for identifier, definition in definitions.items():
        if definition.get("kind") != "entity":
            continue
        components = definition.get("components", {})
        scopes = [definition.get("rules", {})]
        machine=definitions.get(components.get('behavior',{}).get('machine'),{})
        if machine.get('decision'):
            config=machine['decision'];require('behavior.decision',identifier+'.behavior',scopes,config['rule'])
            if config.get('mode_resource') and config['mode_resource'] not in components.get('resources',{}):
                raise ContentError(identifier+': absent behavior mode resource')
            if config.get('mode_resource'):
                initial=components['resources'][config['mode_resource']].get('initial',0)
                if type(initial) not in (int,float) or int(initial)!=initial or int(initial) not in {p['mode'] for p in config['profiles']}:
                    raise ContentError(identifier+': initial behavior mode must be integral and declared')
            owned=set(components.get('abilities',[]))
            for profile in config['profiles']:
                for group in profile.get('cast_groups',[]):
                    if any(a not in owned for a in group['abilities']):raise ContentError(identifier+': behavior cast group includes unowned ability')
                for entry in profile.get('selectors',[]):
                    selected=definitions[entry['selector']]
                    if selected.get('kind')!='selector':raise ContentError(identifier+': behavior selector reference is not selector')
                    if selected.get('limit_attribute') and not selected.get('eligible_rule'):
                        raise ContentError(identifier+': dynamic selector limit requires explicit pure eligibility rule')
                    require('selector.eligibility',identifier+'.behavior',scopes,selected.get('eligible_rule'))
        if components.get("spatial", {}).get("steering"):
            steering = components["spatial"]["steering"]
            require("movement.steering", f"{identifier}.spatial.steering", scopes, steering.get("rule"))
        entity_scopes[identifier] = scopes
        for overlay in components.get("terrain_overlays", ()):
            require("terrain.tile_options", f"{identifier}.terrain_overlays", (), overlay.get("rule"))
        attributes = components.get("attributes", {})
        for stat in attributes.get("base", {}):
            require("attributes.effective", f"{identifier}.attributes.{stat}",
                    [*scopes, attributes.get("rules", {}), attributes.get("attribute_rules", {}).get(stat, {})])
        growth = definition.get("growth", attributes.get("growth", {}))
        for stat, spec in growth.items():
            require("attributes.growth", f"{identifier}.growth.{stat}",
                    [*scopes, attributes.get("rules", {}), attributes.get("attribute_rules", {}).get(stat, {})], spec.get("rule"))
        resources(components.get("resources", {}), f"{identifier}.resources", scopes)
        for child in components.get("deck", {}).get("on_create", []):
            effect(child, f"{identifier}.deck.on_create", scopes)
        for ability_id in components.get("abilities", []):
            ability(ability_id, f"{identifier} -> {ability_id}", scopes)
        lifecycle = components.get("lifecycle", {})
        if lifecycle.get("policy"):
            require("lifecycle.death", f"{identifier}.lifecycle", [*scopes, lifecycle.get("rules", {})])
        spatial = components.get("spatial", {})
        if spatial.get("route"):
            route(f"{identifier}.spatial.route", [*scopes, spatial.get("rules", {})], spatial["route"])
        connectivity=components.get('deployable',{}).get('connectivity')
        if connectivity is not None:require('deploy.connectivity',identifier+'.deployable.connectivity',scopes,connectivity['rule'])
        if "deployable" in components:
            deploy(f"{identifier}.deployable", [*scopes, components["deployable"].get("rules", {})])

    for identifier, definition in definitions.items():
        kind, scopes = definition.get("kind"), [definition.get("rules", {})]
        if kind == "ability" and identifier not in abilities_seen:
            ability(identifier, identifier, [])
        elif kind == "selector" and identifier not in selectors_seen:
            selector(identifier, identifier, [])
            if definition.get('eligible_rule'):require('selector.eligibility',identifier,scopes,definition['eligible_rule'])
        elif kind == "projectile":
            require("projectile.trajectory", identifier+".motion", scopes, definition["motion"]["rule"])
            require("projectile.collision", identifier+".collision", scopes, definition["collision"]["rule"])
            require("time.quantize", identifier)
            for index,item in enumerate(definition.get("on_invalid", [])): effect(item, f"{identifier}.on_invalid[{index}]", scopes)
        elif kind == "buff":
            for hook in definition.get("damage_hooks", []):
                require("damage.request" if hook["phase"] == "before" else "damage.pipeline",
                    f"{identifier}.damage_hooks", scopes, hook["rule"])
            for calculation, explicit in (("buff.duration", definition.get("duration_rule")),
                                           ("buff.interval", definition.get("interval_rule")),
                                           ("buff.stack_amount", definition.get("stacking", {}).get("rule")), ("time.quantize", None)):
                require(calculation, identifier, scopes, explicit)
            if definition.get("modifiers"):
                for modifier in definition["modifiers"]:
                    candidates = [entity for entity in definitions.values() if entity.get("kind") == "entity"
                                  and modifier["attribute"] in entity.get("components", {}).get("attributes", {}).get("base", {})]
                    if not candidates:
                        require("attributes.effective", identifier, scopes)
                    for entity in candidates:
                        attributes = entity["components"]["attributes"]
                        require("attributes.effective", identifier, [entity.get("rules", {}), attributes.get("rules", {}),
                            attributes.get("attribute_rules", {}).get(modifier["attribute"], {})])
            for index, item in enumerate(definition.get("effects", [])):
                effect(item, f"{identifier}.effects[{index}]", scopes)
            for index, item in enumerate(definition.get("on_remove", [])):
                effect(item, f"{identifier}.on_remove[{index}]", scopes)
            if definition.get("movement_damage"):
                effect(definition["movement_damage"]["effect"], f"{identifier}.movement_damage.effect", scopes)
            events(definition.get("events", []), f"{identifier}.events", scopes)
        elif kind == "control":
            require("time.quantize", identifier)
            for name in ("on_start", "on_complete", "on_cancel"):
                for index, item in enumerate(definition.get(name, [])):
                    effect(item, f"{identifier}.{name}[{index}]", scopes); control_effect(item, f"{identifier}.{name}[{index}]")
            for index, step in enumerate(definition["steps"]):
                for item in step.get("effects", []):
                    effect(item, f"{identifier}.steps[{index}]", scopes); control_effect(item, f"{identifier}.steps[{index}]")
        elif kind == "behavior" and definition.get("states"):
            for name, state in definition["states"].items():
                for key in ("on_enter", "on_exit"):
                    for index, item in enumerate(state.get(key, [])):
                        effect(item, f"{identifier}.states.{name}.{key}[{index}]", scopes)
            for index, transition in enumerate(definition.get("transitions", [])):
                for child in transition.get("effects", []):
                    effect(child, f"{identifier}.transitions[{index}]", scopes)

    resources(scenario.get("resources", {}), f"{scenario['id']}.resources", [])
    for key,profile in scenario.get('map',{}).get('tile_mechanics',{}).items():
        if profile.get('type')=='contact_lifecycle':require('tile.contact',f"{scenario['id']}.map.tile_mechanics.{key}",explicit=profile['rule'])
        elif profile.get('rule'):require('movement.transition',f"{scenario['id']}.map.tile_mechanics.{key}",explicit=profile['rule'])
    if scenario.get("timeline") is not None:
        require("time.quantize", f"{scenario['id']}.timeline")
        for wi, wave in enumerate(scenario["timeline"]["waves"]):
            for fi, fragment in enumerate(wave["fragments"]):
                for ai, action in enumerate(fragment["actions"]):
                    path = f"{scenario['id']}.timeline.waves[{wi}].fragments[{fi}].actions[{ai}]"
                    if action["kind"] == "spawn":
                        spawn = action["spawn"]
                        overlay_instance(spawn, path)
                        if spawn.get("placement"):
                            require("spawn.position", path, explicit=spawn["placement"]["rule"])
                        instance_route(spawn, path+".route")
                    elif action["kind"] == "effects":
                        for child in action["effects"]:
                            effect(child, path, [])
    for index, entry in enumerate(scenario.get("scheduledEffects", [])):
        path = f"{scenario['id']}.scheduledEffects[{index}]"
        require("time.quantize", path)
        if entry["effect"].get("op") in {"apply_terrain_overlay", "remove_terrain_overlay"}:
            control_effect(entry["effect"], path)
        effect(entry["effect"], path, [])
    for index, wave in enumerate(scenario.get("waves", [])):
        overlay_instance(wave, f"{scenario['id']}.waves[{index}]")
        captured_origins(wave, f"{scenario['id']}.waves[{index}].route")
        require("time.quantize", f"{scenario['id']}.waves[{index}]")
        if wave.get("placement"):
            require("spawn.position", f"{scenario['id']}.waves[{index}].placement", explicit=wave["placement"]["rule"])
        instance_route(wave, f"{scenario['id']}.waves[{index}].route")
    for index, item in enumerate(scenario.get("initialEntities", [])):
        overlay_instance(item, f"{scenario['id']}.initialEntities[{index}]")
        captured_origins(item, f"{scenario['id']}.initialEntities[{index}].route")
        instance_route(item, f"{scenario['id']}.initialEntities[{index}].route")
    if scenario.get("objectives"):
        require("lifecycle.result", f"{scenario['id']}.objectives")
    for command in scenario.get("commands", []):
        require("time.quantize", f"{scenario['id']}.commands")
        if command.get("action", command.get("type")) == "deploy":
            deploy(f"{scenario['id']}.commands.deploy", entity_scopes.get(command.get("entity", command.get("definition")), []))
    return requirements
