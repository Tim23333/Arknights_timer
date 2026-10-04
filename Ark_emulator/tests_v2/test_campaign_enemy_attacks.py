"""First-stage enemy combat node extraction and real attack settlements."""
from copy import deepcopy
from functools import lru_cache
import json

import pytest

from ark_sim import Compiler, Engine
from tools.build_campaign_enemy_attacks import build, OUTPUT
from tools.build_mainline_draft import translate


@lru_cache(maxsize=1)
def contents():
    return build()


def probe(enemy):
    data = deepcopy(contents())
    unit = next(e for e in translate()["entities"] if e["metadata"]["native_id"] == enemy)
    data["entities"] = [unit, {"id": "unit/player_probe", "kind": "entity", "tags": ["player", "ground"],
        "components": {"attributes": {"base": {"max_hp": 2000, "def": 30, "mres": 0}}, "spatial": {},
        "resources": {"hp": {"initial": 2000, "capacity": 2000, "role": "health"}}}}]
    data["scenarioDraft"] = {"id": "scenario/enemy_probe", "ruleset": "ruleset/ark_standard", "map": {"rows": 5, "cols": 5},
        "initialEntities": [{"definition": unit["id"], "instanceAlias": "enemy", "position": {"row": 2, "col": 2}},
            {"definition": "unit/player_probe", "instanceAlias": "blocker", "position": {"row": 2, "col": 2}},
            {"definition": "unit/player_probe", "instanceAlias": "other", "position": {"row": 2, "col": 2}}]}
    if enemy == "enemy_1005_yokai":
        data["behaviors"] = [{"id": "behavior/campaign_passive", "kind": "behavior", "initial": "active", "states": {"active": {}}, "transitions": []}]
    return data


def test_artifact_preserves_null_attack_pointer_and_actual_combat_damage_type():
    data = contents()
    assert json.loads(OUTPUT.read_text(encoding="utf-8")) == data
    assert len(data["abilities"]) == 4
    rows = data["manifest"]["metadata"]["native_enemy_records"]
    assert len(rows) == 5
    assert all(r["source"]["raw_mode_attack_pointer"]["m_PathID"] == 0 for r in rows)
    assert all(r["source"]["combat_fields"]["_damageType"] == 1 for r in rows if not r["passive"])
    assert len([r for r in rows if r["passive"]]) == 1


@pytest.mark.parametrize("enemy,tick,expected", [
    ("enemy_1007_slime", 10, 1900), ("enemy_1027_mob", 12, 1780),
    ("enemy_1030_wteeth", 19, 1530), ("enemy_1000_gopro", 18, 1840),
])
def test_melee_damage_uses_real_attack_stats_and_only_current_blocker(enemy, tick, expected):
    sim = Engine.create(Compiler().compile(probe(enemy)))
    sim.ctx.set("enemy", ("runtime", "blocked_by"), sim.session.world.resolve("blocker"))
    sim.session.advance(tick)
    assert sim.ctx.resources.current("blocker", "hp") == 2000
    sim.session.advance(1)
    assert sim.ctx.resources.current("blocker", "hp") == expected
    assert sim.ctx.resources.current("other", "hp") == 2000


def test_unblocked_melee_enemy_cannot_attack_an_arbitrary_nearby_player():
    sim = Engine.create(Compiler().compile(probe("enemy_1007_slime")))
    sim.session.advance(31)
    assert sim.ctx.resources.current("blocker", "hp") == 2000
    assert not [e for e in sim.session.events if e["type"] == "damage.accepted"]


def test_passive_fly_enemy_does_not_get_an_attack_from_available_spine_events():
    sim = Engine.create(Compiler().compile(probe("enemy_1005_yokai")))
    sim.ctx.set("enemy", ("runtime", "blocked_by"), sim.session.world.resolve("blocker"))
    sim.session.advance(31)
    assert not sim.ctx.get("enemy", ("abilities",))
    assert sim.ctx.resources.current("blocker", "hp") == 2000
