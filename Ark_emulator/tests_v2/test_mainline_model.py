"""Native stage fields affecting mechanics survive the executable composition."""
import json
from ark_sim import Compiler, Engine
from tools.build_mainline_model import build, OUTPUT, ROOT


def test_native_weight_options_and_seed_survive_without_false_native_claims():
    data = build()
    assert json.loads(OUTPUT.read_text(encoding="utf8")) == data
    program = Compiler().compile(data)
    assert {key: program.definitions["unit/"+key]["components"]["attributes"]["base"]["mass_level"]
            for key in ("enemy_1030_wteeth", "enemy_1000_gopro", "enemy_1007_slime", "enemy_1027_mob", "enemy_1005_yokai")} == {
        "enemy_1030_wteeth": 2, "enemy_1000_gopro": 0, "enemy_1007_slime": 0, "enemy_1027_mob": 0, "enemy_1005_yokai": 0}
    native = json.loads((ROOT/"packages/campaign/native_reference/level_main_00-10.json").read_text(encoding="utf8"))
    meta = data["manifest"]["metadata"]
    assert meta["native_options"] == native["options"]
    assert meta["native_random_seed"] == native["randomSeed"] == 953816614
    assert len(program.scenario["waves"]) == 35
    assert len(program.scenario["roster"]) == 12
    assert meta["movement_and_rng_profile"]["spawn_jitter"] == "source_retained_not_executed"
    assert not meta["formal_mainline_approved"] and not meta["client_validated"]
    assert "native_spawn_random_range" in meta["pending"]


def test_support_pending_mechanics_remain_in_each_corresponding_squad_record():
    data = build()
    expected = json.loads((ROOT/"packages/campaign/talents.support.json").read_text(encoding="utf8"))[
        "manifest"]["metadata"]["pending_mechanics"]
    records = data["manifest"]["metadata"]["squad_model"]["integration"]
    assert len([r for r in records if "support" in r["talent_model_sources"]]) == 6
    for record in records:
        if "support" in record["talent_model_sources"]:
            assert set(expected) <= set(record["pending"])
    assert not data["scenarioDraft"]["metadata"]["model_validated"]


def test_mon3tr_card_requires_full_native_cost_instead_of_clamped_delta():
    data = build()
    data["scenarioDraft"].update(waves=[], scheduledEffects=[], objectives={},
        resources={"dp": {"initial": 5, "capacity": 99}}, initialEntities=[{
            "definition": "unit/char_003_kalts", "instanceAlias": "kalts", "position": {"row": 3, "col": 8}}])
    sim = Engine.create(Compiler().compile(data))
    sim.submit({"action": "skill", "source": "kalts", "ability": "ability/kalts_summon",
        "payload": {"position": {"row": 4, "col": 8}, "facing": "left"}})
    sim.session.advance(1)
    assert [e["payload"]["reason"] for e in sim.session.events if e["type"] == "command.rejected"] == ["insufficient resource dp"]
    assert not any(e["definition_id"] == "unit/kalts_mon3tr_model" for e in sim.session.world.entities())
    assert sim.ctx.resources.current("system/battle", "dp") == 5
    sim.ctx.resources.adjust("system/battle", "dp", value=10)
    sim.submit({"action": "skill", "source": "kalts", "ability": "ability/kalts_summon",
        "payload": {"position": {"row": 4, "col": 8}, "facing": "left"}})
    sim.session.advance(1)
    child = next(e for e in sim.session.world.entities() if e["definition_id"] == "unit/kalts_mon3tr_model")
    assert child["components"]["deployable"]["paid_cost"] == 10
    assert sim.ctx.resources.current("system/battle", "dp") == 0
