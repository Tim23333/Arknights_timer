"""Regression tests for the client's four-way SPFA + nextNode smoothing."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator.map import GameMap, TileData


def _map(rows, cols, blocked=(), holes=()):
    blocked = set(blocked)
    holes = set(holes)
    tiles = []
    for row in range(rows):
        for col in range(cols):
            if (row, col) in blocked:
                raw = {"tileKey": "tile_forbidden", "passableMask": 0}
            elif (row, col) in holes:
                raw = {"tileKey": "tile_hole", "passableMask": 1}
            else:
                raw = {"tileKey": "tile_road", "passableMask": 1}
            tiles.append(TileData(row * cols + col, raw))
    return GameMap(rows, cols, tiles)


def _route(start, end, diagonal=True, checkpoints=None):
    return {
        "startPosition": {"row": start[0], "col": start[1]},
        "endPosition": {"row": end[0], "col": end[1]},
        "allowDiagonalMove": diagonal,
        "motionMode": {"value": 0},
        "checkpoints": checkpoints or [],
    }


def test_diagonal_smoothing_keeps_manhattan_distance():
    game_map = _map(3, 3)
    start = game_map.idx(2, 2)
    target = game_map.idx(0, 0)
    nxt, dist = game_map.build_flow_field(target, 0, True)

    assert dist[start] == 4.0
    assert nxt[start] == target


def test_non_diagonal_smoothing_stops_at_next_turn():
    game_map = _map(3, 3)
    start = game_map.idx(2, 2)
    target = game_map.idx(0, 0)
    nxt, dist = game_map.build_flow_field(target, 0, False)

    assert dist[start] == 4.0
    assert game_map.rc(nxt[start]) == (0, 2)


def test_minor_axis_one_checks_entire_two_by_n_rectangle():
    game_map = _map(2, 4, blocked={(1, 1)})
    start = game_map.idx(1, 3)
    target = game_map.idx(0, 0)

    checked = {game_map.rc(i)
               for i in game_map._supercover_cells(start, target)}
    assert checked == {(row, col) for row in range(2) for col in range(4)}
    assert not game_map._line_clear(start, target, 0)


def test_corner_crossing_checks_two_extra_cells():
    game_map = _map(2, 2, blocked={(0, 1)})
    start = game_map.idx(1, 1)
    target = game_map.idx(0, 0)

    checked = {game_map.rc(i)
               for i in game_map._supercover_cells(start, target)}
    assert checked == {(0, 0), (0, 1), (1, 0), (1, 1)}
    assert not game_map._line_clear(start, target, 0)


def test_short_axis_step_checks_two_extra_cells():
    for blocked in ({(0, 2)}, {(1, 1)}):
        game_map = _map(3, 6, blocked=blocked)
        start = game_map.idx(0, 0)
        target = game_map.idx(2, 5)
        assert not game_map._line_clear(start, target, 0), blocked


def test_hole_is_high_cost_and_blocks_ground_smoothing():
    game_map = _map(3, 3, holes={(1, 1)})
    start = game_map.idx(2, 2)
    target = game_map.idx(0, 0)
    nxt, dist = game_map.build_flow_field(target, 0, True)

    assert dist[start] == 4.0
    assert nxt[start] != target


def test_route_path_is_segmented_and_appear_jump_is_not_drawn():
    game_map = _map(5, 6)
    checkpoints = [
        {"type": {"value": 0}, "position": {"row": 4, "col": 2}},
        {"type": {"value": 5}},
        {"type": {"value": 6}, "position": {"row": 1, "col": 4}},
        {"type": {"value": 0}, "position": {"row": 1, "col": 5}},
    ]
    route = _route((4, 0), (0, 5), checkpoints=checkpoints)

    segments = game_map.route_path(route)

    assert len(segments) == 3
    assert segments[0]["points"][0] == {"row": 4, "col": 0}
    assert segments[0]["points"][-1] == {"row": 4, "col": 2}
    assert segments[1]["points"][0] == {"row": 1, "col": 4}
    assert segments[1]["points"][-1] == {"row": 1, "col": 5}
    assert segments[2]["points"][0] == {"row": 1, "col": 5}
    assert segments[2]["points"][-1] == {"row": 0, "col": 5}


def test_checkpoint_reach_offset_does_not_move_path_field_target_tile():
    game_map = _map(4, 5)
    checkpoints = [{
        "type": {"value": 0},
        "position": {"row": 2, "col": 1},
        "reachOffset": {"x": 0.75, "y": 0.0},
    }]
    route = _route((2, 0), (2, 4), checkpoints=checkpoints)

    first = game_map.route_path(route)[0]

    assert first["points"][-1] == {"row": 2, "col": 1}


def test_route_distance_accumulates_segments_and_skips_tunnel_gap():
    game_map = _map(5, 8)
    checkpoints = [
        {"type": {"value": 0}, "position": {"row": 2, "col": 2}},
        {"type": {"value": 5}},
        {"type": {"value": 6}, "position": {"row": 2, "col": 5}},
    ]
    route = _route((2, 0), (2, 7), checkpoints=checkpoints)
    assert game_map.route_distance_to_final(route, 0, 2, 0) == 4.0
    assert game_map.route_distance_to_final(route, 1, 2, 2) == 2.0


if __name__ == "__main__":
    import traceback
    tests = [value for name, value in sorted(globals().items())
             if name.startswith("test_")]
    failed = 0
    for test in tests:
        try:
            test()
            print("OK", test.__name__)
        except Exception:
            failed += 1
            print("FAIL", test.__name__)
            traceback.print_exc()
    print("all path smoothing tests passed" if not failed
          else "%d failed" % failed)
    raise SystemExit(1 if failed else 0)
