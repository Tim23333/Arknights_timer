"""Implemented provider registry; game formulas live in a preset module."""
from ark_sim.presets import providers as ark

from . import projectile_profiles
from . import ray_projectile_profiles
from .selection import eligibility_profile
from .request_transforms import request_field_transform
from .qualified_areas import qualified_cell_offsets
from .deploy_connectivity import ground_routes

from .death_projectiles import qualified_radius
from .periodic_fields import uniform_trigger,cell_combat_members

BUILTIN_PROVIDERS = {
    'model.projectile.cardinal_map_ray': ray_projectile_profiles.trajectory,
    'model.projectile.qualified_swept_ray': ray_projectile_profiles.collision,
    'model.area.qualified_radius': qualified_radius,
    "model.field.uniform_trigger": uniform_trigger,
    "model.field.cell_combat_members": cell_combat_members,
    "model.deploy.ground_connectivity": ground_routes,
    "model.damage.request_field_transform": request_field_transform,
    "ark.selector.pure_eligibility": ark.pure_eligibility,
    "ark.behavior.decision": ark.behavior_decision,
    "model.targeting.eligibility": eligibility_profile,
    "ark.terrain.tile_options": ark.terrain_tile_options,
    "model.projectile.trajectory": projectile_profiles.trajectory,
    "model.projectile.collision": projectile_profiles.collision,
    "ark.movement.checkpoint_cartesian": ark.checkpoint_cartesian_position,
    "ark.movement.living_transition": ark.living_route_transition,
    "ark.spawn.uniform_rect": ark.spawn_uniform_rect,
    "ark.movement.steering_velocity": ark.steering_velocity,
    "ark.attributes.layers": ark.attribute_layers,
    "ark.attributes.time_layers": ark.time_attribute_layers,
    "ark.attributes.aggregate": ark.aggregate_layer,
    "ark.resource.bounds": ark.resource_bounds,
    "ark.resource.capacity_change": ark.capacity_change,
    "ark.deploy.ground": ark.ground_deploy,
    "ark.lifecycle.standard": ark.lifecycle,
    "ark.lifecycle.result": ark.battle_result,
    "ark.targeting.score": ark.targeting_score,
    "ark.targeting.selection": ark.targeting_selection,
    "ark.behavior.player_combat": ark.player_behavior,
    "ark.behavior.ground_melee": ark.ground_behavior,
    "ark.selector.grid": ark.selector_grid,
    "ark.area.cell_offsets": ark.area_cell_offsets,
    "ark.area.qualified_cell_offsets": qualified_cell_offsets,
    "ark.spatial.route": ark.spatial_route,
    "ark.spatial.blocking": ark.spatial_blocking,
    "ark.damage.pipeline": ark.damage_pipeline,
    "ark.damage.settlement_scale": ark.settlement_scale,
}

for _function in BUILTIN_PROVIDERS.values():
    _function.version = "ark-preset/1"

# Fingerprinted provider descriptors declare when effective attributes can
# change without an entity mutation. Custom providers remain conservative.
for _name in ("ark.attributes.layers", "ark.attributes.time_layers"):
    _callback = BUILTIN_PROVIDERS[_name]
    BUILTIN_PROVIDERS[_name] = {"callable": _callback, "version": _callback.version,
                              "attribute_time_dependency": "modifiers"}
_aggregate = BUILTIN_PROVIDERS["ark.attributes.aggregate"]
BUILTIN_PROVIDERS["ark.attributes.aggregate"] = {"callable": _aggregate, "version": _aggregate.version,
                                                "time_dependency": "static"}
