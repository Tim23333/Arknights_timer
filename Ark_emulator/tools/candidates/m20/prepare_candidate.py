"""Create a separate dormant-instance candidate from immutable M16 bytes."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT.parent/"unpack_work/campaign_m16_terrain_candidate"
OUT = ROOT.parent/"unpack_work/campaign_m20_dormant_candidate"


def replace(relative, old, new, expected=1):
    path = OUT/relative; value = path.read_text(encoding="utf8")
    if value.count(old) != expected: raise ValueError("unexpected frozen source shape: "+relative+" / "+old[:50])
    path.write_text(value.replace(old, new), encoding="utf8", newline="\n")


def main():
    if OUT.exists(): raise ValueError("candidate already exists; never overwrite a working/frozen implementation")
    if not BASE.is_dir() or OUT.parent.resolve() != (ROOT.parent/"unpack_work").resolve(): raise ValueError("invalid named workspace target")
    shutil.copytree(BASE/"ark_sim", OUT/"ark_sim", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    replace("ark_sim/domains/context.py", "    def selectable(self, ref):\n        return self.alive(ref) and not self.route_hidden(ref)",
        "    def active(self, ref):\n        return self.alive(ref) and bool(self.get(ref, ('runtime', 'active'), True))\n\n    def selectable(self, ref):\n        return self.active(ref) and not self.route_hidden(ref)")
    replace("ark_sim/domains/context.py", "        return not self.route_hidden(ref) or self.visibility_policy(ref).get(\"hidden_effects\", \"reject\") == \"allow\"",
        "        return bool(self.get(ref, ('runtime', 'active'), True)) and (not self.route_hidden(ref) or self.visibility_policy(ref).get(\"hidden_effects\", \"reject\") == \"allow\")")
    replace("ark_sim/domains/context.py", "        return not self.route_hidden(ref) or self.visibility_policy(ref).get(\"hidden_auras\", \"suspend\") == \"retain\"",
        "        return bool(self.get(ref, ('runtime', 'active'), True)) and (not self.route_hidden(ref) or self.visibility_policy(ref).get(\"hidden_auras\", \"suspend\") == \"retain\")")
    # Domain participation uses active; biological lifecycle continues using alive.
    for relative in ("abilities.py", "resources.py", "behavior.py", "buffs.py"):
        path = OUT/"ark_sim/domains"/relative
        value = path.read_text(encoding="utf8")
        path.write_text(value.replace("self.ctx.alive(", "getattr(self.ctx, 'active', self.ctx.alive)("), encoding="utf8", newline="\n")
    replace("ark_sim/domains/deployment.py", "if context.alive(e[\"id\"]) and e[\"components\"].get(\"deployable\")", "if context.active(e[\"id\"]) and e[\"components\"].get(\"deployable\")")
    path = OUT/"ark_sim/domains/movement.py"; value = path.read_text(encoding="utf8")
    value = value.replace("self.ctx.alive(", "getattr(self.ctx, 'active', self.ctx.alive)(")
    value = value.replace("and not self.ctx.route_hidden(e[\"id\"])]", "and self.ctx.get(e[\"id\"], ('runtime', 'active'), True) and not self.ctx.route_hidden(e[\"id\"])]")
    path.write_text(value, encoding="utf8", newline="\n")
    replace("ark_sim/domains/lifecycle.py", "owner=None, lifetime_seconds=None, on_owner_retire=\"retain\"):", "owner=None, lifetime_seconds=None, on_owner_retire=\"retain\", active=True, registration_key=None):")
    replace("ark_sim/domains/lifecycle.py", "        if alias is not None and (not isinstance(alias, str) or not alias):", "        if type(active) is not bool:\n            raise ValueError('initial active state must be boolean')\n        if registration_key is not None:\n            if not isinstance(registration_key, str) or not registration_key:\n                raise ValueError('registration key must be a nonempty string')\n            if registration_key in self.ctx.state().get('predefined_registry', {}):\n                raise ValueError('duplicate registration key')\n        if alias is not None and (not isinstance(alias, str) or not alias):")
    replace("ark_sim/domains/lifecycle.py", "        for overlay in components.get(\"terrain_overlays\", ()):",
        "        if registration_key is not None:\n            registry = self.ctx.state().get('predefined_registry', {})\n            registry[registration_key] = ref\n            self.ctx.state_update(predefined_registry=registry)\n        if not active:\n            self.ctx.set(ref, ('runtime', 'active'), False)\n            self.ctx.set(ref, ('runtime', 'state'), 'dormant')\n            self.ctx.set(ref, ('runtime', 'deployed'), False)\n            self.ctx.set(ref, ('runtime', 'initializing'), False)\n            self.ctx.set(ref, ('runtime', 'activation_plan'), {'deployed': deployed, 'lifetime_seconds': lifetime_seconds})\n            self.ctx.emit('entity.registered', {'source': ref, 'target': ref, 'definition': definition_id, 'registration_key': registration_key, 'active': False})\n            return ref\n        return self._initialize_created(ref, components, resources, buff_config, lifetime_seconds, deployed)\n\n    def _initialize_created(self, ref, components, resources, buff_config, lifetime_seconds, deployed):\n        definition_id = self.ctx.entity(ref)['definition_id']\n        for overlay in components.get(\"terrain_overlays\", ()):")
    # Activation reuses the registered resources and actor identity. It is atomic
    # even when its deferred rules, deck effects or Buff initialization fail.
    replace("ark_sim/domains/lifecycle.py", "    def prune_expired(self, session):", '''    def activate_predefined(self, key):
        with self.ctx.session.atomic():
            if not isinstance(key, str) or not key:
                raise ValueError('activation requires nonempty registration key')
            registry = self.ctx.state().get('predefined_registry', {})
            if key not in registry:
                raise ValueError('unknown predefined registration key')
            ref = registry[key]
            if not self.ctx.alive(ref) or self.ctx.get(ref, ('runtime', 'active'), True):
                raise ValueError('predefined actor is not a living dormant instance')
            if self.ctx.get(ref, ('runtime', 'state')) != 'dormant':
                raise ValueError('predefined actor has incompatible activation state')
            plan = self.ctx.get(ref, ('runtime', 'activation_plan'))
            self.ctx.set(ref, ('runtime', 'active'), True)
            self.ctx.set(ref, ('runtime', 'state'), 'alive')
            self.ctx.set(ref, ('runtime', 'initializing'), True)
            self.ctx.set(ref, ('runtime', 'deployed'), plan['deployed'])
            self.ctx.set(ref, ('runtime', 'activation_plan'), None)
            components = self.ctx.get(ref, ())
            resources = {name: data['spec'] for name, data in components.get('resources', {}).items()}
            buff_config = components.get('buffs', {})
            self._initialize_created(ref, components, resources, buff_config, plan['lifetime_seconds'], plan['deployed'])
            self.ctx.emit('entity.activated', {'source': ref, 'target': ref, 'registration_key': key})
            self.ctx.spatial.blocking()
            return ref

    def prune_expired(self, session):''')
    replace("ark_sim/adapters/api.py", "component_overrides=item.get(\"components\"), rule_overrides=item.get(\"rules\"), tags=item.get(\"tags\"))",
        "component_overrides=item.get(\"components\"), rule_overrides=item.get(\"rules\"), tags=item.get(\"tags\"),\n                                      active=item.get('active', True), registration_key=item.get('registration_key'))")
    replace("ark_sim/adapters/api.py", "            if not self.ctx.alive(ref):", "            if not self.ctx.active(ref):")
    replace("ark_sim/domains/effects.py", "            if operation == \"random\":", "            if operation == 'activate_predefined':\n                if target != self.ctx.session.world.resolve('system/battle'):\n                    raise ValueError('predefined activation effect targets battle registry')\n                self.ctx.lifecycle.activate_predefined(effect['parameters']['key'])\n            elif operation == \"random\":")
    replace("ark_sim/content/schemas.py", '"input_lock", "retire", "apply_terrain_overlay", "remove_terrain_overlay"}', '"input_lock", "retire", "apply_terrain_overlay", "remove_terrain_overlay", "activate_predefined"}')
    replace("ark_sim/content/schemas.py", '    if effect["op"] == "input_lock":', '''    if effect['op'] == 'activate_predefined':
        options = effect.get('parameters')
        if not isinstance(options, Mapping) or set(options) != {'key'} or not isinstance(options['key'], str) or not options['key']:
            raise ContentError(f"{path}.parameters: activation requires one nonempty registration key")
        if effect.get('target') != 'battle' or effect.get('selector'):
            raise ContentError(f"{path}: activation must explicitly target the battle registry without selector")
    if effect["op"] == "input_lock":''')
    replace("ark_sim/content/schemas.py", '"tags", "deployed", "route", "parameters"}, path)', '"tags", "deployed", "route", "parameters", "active", "registration_key"}, path)')
    replace("ark_sim/content/schemas.py", '        for index, entity in enumerate(definition.get("initialEntities", [])):', '        registration_keys = set()\n        for index, entity in enumerate(definition.get("initialEntities", [])):')
    replace("ark_sim/content/schemas.py", '            if "route" in entity:\n                validate_route', '''            if 'active' in entity and type(entity['active']) is not bool:
                raise ContentError(f"{path}.active: boolean required")
            if 'registration_key' in entity:
                key = entity['registration_key']
                if not isinstance(key, str) or not key or key in registration_keys:
                    raise ContentError(f"{path}.registration_key: unique nonempty key required")
                registration_keys.add(key)
            if entity.get('active', True) is False and not entity.get('registration_key'):
                raise ContentError(f"{path}: dormant initial entity requires registration key")
            if "route" in entity:
                validate_route''')
    from refine_candidate import refine
    refine(OUT)
    print(str(OUT))


if __name__ == "__main__": main()
