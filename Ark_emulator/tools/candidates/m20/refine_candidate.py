"""Apply the recorded strict registration preflight refinements."""
from pathlib import Path


def refine(root):
    def patch(relative, old, new):
        path = root/relative; value = path.read_text(encoding="utf8")
        if new in value: return
        if value.count(old) != 1: raise ValueError("unexpected M20 source shape: "+relative)
        path.write_text(value.replace(old, new), encoding="utf8", newline="\n")
    patch('ark_sim/domains/lifecycle.py', 'on_owner_retire="retain", active=True, registration_key=None):', 'on_owner_retire="retain", *, active=True, registration_key=None):')
    patch('ark_sim/domains/terrain.py', "or not self.ctx.alive(owner):raise ValueError('terrain overlay requires a living actor owner')", "or not getattr(self.ctx, 'active', self.ctx.alive)(owner):raise ValueError('terrain overlay requires an active living actor owner')")
    patch('ark_sim/domains/effects.py', '            operation = effect["op"]', '''            operation = effect["op"]
            if operation not in {'activate_predefined', 'retire', 'emit', 'remove_buff', 'remove_terrain_overlay'} and not self.ctx.get(target, ('runtime', 'active'), True):
                self.ctx.emit('effect.inactive_rejected', {'source': source, 'target': target, 'operation': operation}, cause)
                continue''')
    patch('ark_sim/domains/behavior.py', '    def transition(self, ref, state, cause=None):', '''    def transition(self, ref, state, cause=None):
        if not self.ctx.get(ref, ('runtime', 'active'), True):
            raise ValueError('dormant instance cannot enter behavior states before activation')''')
    patch('ark_sim/domains/behavior.py', '    def plan(self, ref):', '''    def plan(self, ref):
        if not self.ctx.get(ref, ('runtime', 'active'), True):
            return {'move': False, 'attack': False}''')
    patch('ark_sim/domains/buffs.py', '            for e in self.ctx.session.world.entities() for key, data in e["components"].get("resources", {}).items()]', '''            for e in self.ctx.session.world.entities() if e['components'].get('runtime', {}).get('active', True)
            for key, data in e["components"].get("resources", {}).items()]''')
    patch('ark_sim/domains/lifecycle.py', '        self.ctx.set(ref, ("runtime", "alive"), False)', '''        self.ctx.set(ref, ("runtime", "alive"), False)
        if 'active' in self.ctx.get(ref, ('runtime',)):
            self.ctx.set(ref, ('runtime', 'active'), False)''')
    patch('ark_sim/domains/lifecycle.py', 'from collections.abc import Mapping', 'from collections.abc import Mapping\nimport math')
    patch('ark_sim/domains/lifecycle.py', '        if self.ctx.terrain is None:\n            return self._create', "        if self.ctx.terrain is None and kwargs.get('active', True) and kwargs.get('registration_key') is None:\n            return self._create")
    patch('ark_sim/domains/lifecycle.py', "        if type(active) is not bool:\n            raise ValueError('initial active state must be boolean')", "        if type(active) is not bool:\n            raise ValueError('initial active state must be boolean')\n        if not active and type(deployed) is not bool:\n            raise ValueError('dormant deployed state must be boolean')")
    patch('ark_sim/domains/lifecycle.py', '        lifetime_seconds = lifetime_seconds if lifetime_seconds is not None else parameters.get("lifetime_seconds")', '        lifetime_seconds = lifetime_seconds if lifetime_seconds is not None else parameters.get("lifetime_seconds")\n        if not active and lifetime_seconds is not None and (type(lifetime_seconds) not in (int, float) or not math.isfinite(lifetime_seconds) or lifetime_seconds < 0):\n            raise ValueError(\'dormant lifetime must be nonnegative finite seconds\')')
    patch('ark_sim/content/schemas.py', "            if 'active' in entity and type(entity['active']) is not bool:\n                raise ContentError(f\"{path}.active: boolean required\")", "            if 'active' in entity and type(entity['active']) is not bool:\n                raise ContentError(f\"{path}.active: boolean required\")\n            if entity.get('active', True) is False and type(entity.get('deployed', False)) is not bool:\n                raise ContentError(f\"{path}.deployed: dormant deployment state must be boolean\")")
    patch('ark_sim/content/compiler.py', '        self._validate_entity_abilities(definitions, selected_scene)', '''        self._validate_entity_abilities(definitions, selected_scene)
        registered = {item['registration_key'] for item in selected_scene.get('initialEntities', ()) if item.get('registration_key')}
        def validate_activation(value):
            if isinstance(value, dict):
                if value.get('op') == 'activate_predefined' and value.get('parameters', {}).get('key') not in registered:
                    raise CompileError('activate_predefined references an unknown initial registration key')
                for key, child in value.items():
                    if key not in {'metadata', 'payload', 'parameters', 'manifest'}: validate_activation(child)
            elif isinstance(value, (list, tuple)):
                for child in value: validate_activation(child)
        validate_activation(definitions)''')


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[4]/'unpack_work/campaign_m20_dormant_candidate'
    refine(root)
    print(str(root))
