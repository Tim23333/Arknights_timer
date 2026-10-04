"""One-time bounded candidate edits; never targets production runtime."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[4]/'unpack_work/campaign_m16_terrain_candidate'
assert ROOT.resolve()==Path('D:/Arknights/Arknights_timer/unpack_work/campaign_m16_terrain_candidate')
def edit(name,old,new):
 p=ROOT/name;s=p.read_text(encoding='utf8');assert old in s,(name,old);p.write_text(s.replace(old,new,1),encoding='utf8',newline='')
edit('ark_sim/domains/context.py','self.timeline = None','self.timeline = self.terrain = None')
edit('ark_sim/domains/providers.py','BUILTIN_PROVIDERS = {','BUILTIN_PROVIDERS = {\n    "ark.terrain.tile_options": ark.terrain_tile_options,')
edit('ark_sim/presets/providers.py','def ground_deploy(inputs, params, context):','''def terrain_tile_options(inputs, params, context):
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


def ground_deploy(inputs, params, context):''')
edit('ark_sim/presets/providers.py','(terrain.get("occupied", False), "occupied"),','''(terrain.get("occupied", False), "occupied"),
              (not int(terrain.get("advancedBuildMask", 1)) & restrictions.get("parameters", {}).get("advanced_build_mask", 1), "advanced_not_buildable"),''')
edit('ark_sim/domains/deployment.py','"terrain": {"inside": inside,','"terrain": {**tile, "inside": inside,')
edit('ark_sim/domains/movement.py','self.map_definition = thaw(context.program.scenario.get("map", {"rows": 1, "cols": 1}))\n        self.grid = GridTopology(self.map_definition)','self._base_map_definition = thaw(context.program.scenario.get("map", {"rows": 1, "cols": 1}))\n        self.grid = GridTopology(self._base_map_definition)')
p=ROOT/'ark_sim/domains/movement.py';s=p.read_text();at=s.index('\n    def ',s.index('self.grid ='))
s=s[:at]+'''\n    @property
    def map_definition(self):
        terrain = getattr(self.ctx, "terrain", None)
        return terrain.map() if terrain is not None else self._base_map_definition
'''+s[at:];p.write_text(s,newline='')
edit('ark_sim/domains/spatial.py','self.rows, self.cols =','self.tile_reader = None\n        self.rows, self.cols =')
edit('ark_sim/domains/spatial.py','return thaw(self._tiles[row * self.cols + col])','return self.tile_reader(row, col) if self.tile_reader else thaw(self._tiles[row * self.cols + col])')
edit('ark_sim/domains/spatial.py','tile = self._tiles[row * self.cols + col]\n        key =','tile = self.tile(row, col)\n        if "groundPassable" in tile:\n            return tile["groundPassable"]\n        key =')
edit('ark_sim/domains/spatial.py','if allow_diagonal:\n            return self._diagonal_path(start, end, target, corner_cut)','if allow_diagonal or any(self.tile(r, c).get("movementCost", 1) != 1 for r in range(self.rows) for c in range(self.cols)):\n            return self._diagonal_path(start, end, target, corner_cut, allow_diagonal)')
edit('ark_sim/domains/spatial.py','def _diagonal_path(self, start, end, target, corner_cut):','def _diagonal_path(self, start, end, target, corner_cut, allow_diagonal=True):')
edit('ark_sim/domains/spatial.py','neighbours = (*self._NEIGHBOURS, (-1, -1), (-1, 1), (1, -1), (1, 1))','neighbours = (*self._NEIGHBOURS, (-1, -1), (-1, 1), (1, -1), (1, 1)) if allow_diagonal else self._NEIGHBOURS')
edit('ark_sim/domains/spatial.py','candidate = cost+(math.sqrt(2) if dr and dc else 1)','candidate = cost+(math.sqrt(2) if dr and dc else 1)*self.tile(*neighbour).get("movementCost", 1)')
edit('ark_sim/domains/terrain.py',"base=thaw(self.ctx.program.scenario['map'])","base=thaw(self.ctx.spatial._base_map_definition)")
edit('ark_sim/adapters/api.py','from ark_sim.domains.controls import ControlSystem','from ark_sim.domains.controls import ControlSystem\nfrom ark_sim.domains.terrain import TerrainSystem')
edit('ark_sim/adapters/api.py','self.ctx.spatial = SpatialSystem(self.ctx)','''self.ctx.spatial = SpatialSystem(self.ctx)
        def uses_terrain(value):
            if isinstance(value, dict) or hasattr(value, "items"):
                return "terrain_overlays" in value or value.get("op") in {"apply_terrain_overlay", "remove_terrain_overlay"} or any(uses_terrain(v) for v in value.values())
            return isinstance(value, (list, tuple)) and any(uses_terrain(v) for v in value)
        if uses_terrain(program.definitions):
            self.ctx.terrain = TerrainSystem(self.ctx)
            self.ctx.spatial.grid.tile_reader = self.ctx.terrain.tile''')
edit('ark_sim/adapters/api.py','self.session.add_system(self.ctx.lifecycle.prune_expired, phase=0)','''if self.ctx.terrain is not None:
            self.session.add_system(self.ctx.terrain.tick, phase=0)
        self.session.add_system(self.ctx.lifecycle.prune_expired, phase=0)''')
edit('ark_sim/domains/lifecycle.py','    def create(self, definition_id,','''    def create(self, *args, **kwargs):
        if self.ctx.terrain is None:
            return self._create(*args, **kwargs)
        with self.ctx.session.atomic():
            return self._create(*args, **kwargs)

    def _create(self, definition_id,''')
edit('ark_sim/domains/lifecycle.py','        if lifetime_seconds is not None:\n            if type(lifetime_seconds)','''        for overlay in components.get("terrain_overlays", ()):
            self.ctx.terrain.apply(ref, overlay)
        if lifetime_seconds is not None:
            if type(lifetime_seconds)''')
edit('ark_sim/domains/lifecycle.py','    def retire(self, ref, reason):','''    def retire(self, ref, reason):
        if self.ctx.terrain is None:
            return self._retire(ref, reason)
        with self.ctx.session.atomic():
            return self._retire(ref, reason)

    def _retire(self, ref, reason):''')
edit('ark_sim/domains/lifecycle.py','self.ctx.set(ref, ("runtime", "state"), reason)\n        self.ctx.abilities','self.ctx.set(ref, ("runtime", "state"), reason)\n        if self.ctx.terrain is not None:\n            self.ctx.terrain.remove(ref)\n        self.ctx.abilities')
edit('ark_sim/domains/effects.py','            elif operation == "retire":','''            elif operation == "apply_terrain_overlay":
                self.ctx.terrain.apply(target, effect["parameters"])
            elif operation == "remove_terrain_overlay":
                self.ctx.terrain.remove(target, effect["parameters"]["key"])
            elif operation == "retire":''')
edit('ark_sim/content/schemas.py','    "resources": None,','    "resources": None,\n    "terrain_overlays": None,')
edit('ark_sim/content/schemas.py','"input_lock", "retire"}','"input_lock", "retire", "apply_terrain_overlay", "remove_terrain_overlay"}')
edit('ark_sim/content/schemas.py','    if effect["op"] == "retire":','''    if effect["op"] in {"apply_terrain_overlay", "remove_terrain_overlay"}:
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
    if effect["op"] == "retire":''')
edit('ark_sim/content/schemas.py','        if "buffs" in components and','''        if "terrain_overlays" in components:
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
        if "buffs" in components and''')
edit('ark_sim/content/capabilities.py','        if op == "damage":','''        if op == "apply_terrain_overlay":
            require("terrain.tile_options", path, (), item.get("parameters", {}).get("rule"))
        if op == "damage":''')
edit('ark_sim/content/capabilities.py','if op == "retire" and not item.get("selector")','if op in {"retire", "apply_terrain_overlay", "remove_terrain_overlay"} and not item.get("selector")')
edit('ark_sim/content/capabilities.py','        attributes = components.get("attributes", {})','''        for overlay in components.get("terrain_overlays", ()):
            require("terrain.tile_options", f"{identifier}.terrain_overlays", (), overlay.get("rule"))
        attributes = components.get("attributes", {})''')
p=ROOT/'ark_sim/rules/contracts.json';j=json.loads(p.read_bytes());j['contracts'].append({'id':'terrain.tile_options','kind':'calculation','owner':'scenario','inputs':[{'name':'base','type':'record','required':True},{'name':'layers','type':'record_list','required':True},{'name':'position','type':'position','required':True}],'outputType':'record','implementations':['expression','graph','provider'],'description':'Pure stable owned tile-layer merge; movement and deployment consume normalized effective options.'});p.write_text(json.dumps(j,indent=2)+'\n',newline='')
p=ROOT/'ark_sim/content/presets/ark_standard.json';j=json.loads(p.read_bytes());j['rules'].append({'id':'rule/ark_terrain_tile_options','kind':'calculation_rule','contract':'terrain.tile_options','implementation':{'type':'provider','provider':'ark.terrain.tile_options'},'parameters':{'normal_cost':1,'obstacle_like_cost':3}});j['rulesets'][0]['bindings']['terrain.tile_options']='rule/ark_terrain_tile_options';p.write_text(json.dumps(j,indent=2)+'\n',newline='')
