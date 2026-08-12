"""Regression coverage for official map/route coordinate normalization."""

from ark_emulator import Simulator


def _stage_510():
    return Simulator(stage_id="main_05-10", level_id=None)


def test_510_map_and_routes_share_top_based_coordinates():
    battle = _stage_510().battle

    # The exported top row contains Faust's teleporter; red gates occupy the
    # right edge further down.  This catches the old vertically mirrored map.
    assert battle.map.tile(0, 7).tile_key == "tile_telout"
    assert battle.map.tile(0, 9).tile_key == "tile_telin"
    assert battle.map.tile(5, 11).tile_key == "tile_start"

    route = battle.routes[1]
    assert route["startPosition"] == {"row": 5, "col": 11}
    assert route["endPosition"] == {"row": 4, "col": 0}
    assert route["checkpoints"][0]["position"] == {"row": 5, "col": 9}
    assert route["checkpoints"][1]["position"] == {"row": 4, "col": 8}


def test_510_enemy_visits_move_checkpoints_before_waiting():
    battle = _stage_510().battle
    battle.waves.timeline = [{"t": 9999.0, "actionType": "STORY"}]
    battle.waves._idx = 0
    # Keep the controller alive while the manually spawned enemy walks; the
    # normal end-condition removes the last enemy once a finished empty wave
    # is observed.
    battle.waves.finished = False
    battle.life_point = 999
    enemy = battle.spawn_enemy("enemy_1507_mephi", 1, source_ev={
        "waveStart": 0.0, "fragmentStart": 0.0})

    visited = []
    last = enemy._checkpoint_idx
    for _ in range(30 * 25):
        battle.tick_once()
        if enemy._checkpoint_idx != last:
            visited.append((enemy._checkpoint_idx,
                            round(enemy.pos_y, 2), round(enemy.pos_x, 2)))
            last = enemy._checkpoint_idx
        if enemy._checkpoint_idx >= 2:
            break

    assert visited[:2] == [(1, 5.0, 9.0), (2, 4.0, 8.0)]
    assert enemy.dead is False


def test_web_deploy_coordinates_are_not_flipped_again():
    battle = _stage_510().battle
    battle.cost = 999
    # Row 4 / col 3 is the visibly displayed ground road tile.
    assert battle.map.tile(4, 3).buildable_type == 1
    ok, inst_id = battle.deploy("char_149_scave", 4, 3)
    assert ok, inst_id
    operator = next(op for op in battle.operators if op.inst_id == inst_id)
    assert (operator.row, operator.col) == (4, 3)
